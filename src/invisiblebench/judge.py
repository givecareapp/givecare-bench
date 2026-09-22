"""Plan, save, resume, validate, and replay a portable scan.

A scan keeps two files. `answers.jsonl` is the append-only record of what the
judge model returned: one row per conversation turn that carries questions.
`judgments.jsonl` is derived: one verdict per conversation and check, a pure
function of the plan and the saved answers. The derived file is rewritten from
the answers, never edited, and every load checks that it still matches.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import shutil
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any

from typesafe_sdk import SystemOneResponse

from invisiblebench.api.client import (
    CostBudgetExceededError,
    cost_tracker,
    maximum_reasonable_cost_ceiling,
)
from invisiblebench.api.typesafe import (
    DEFAULT_JUDGE_MODEL,
    InvalidJudgeOutput,
    SystemOneClient,
    estimated_cost,
    validate_answers,
)
from invisiblebench.evaluation import rules
from invisiblebench.evaluation.check_registry import load_checks
from invisiblebench.models.scan import (
    Answer,
    Check,
    FileRef,
    JudgeObservation,
    JudgeSettings,
    Judgment,
    MemoryContext,
    QuestionPlan,
    RequestTask,
    Role,
    ScanPlan,
    SourceRun,
    TranscriptSource,
)
from invisiblebench.utils.benchmark_inventory import (
    collect_public_scenario_ids,
    get_benchmark_version,
    get_project_root,
)
from invisiblebench.utils.manifest import scenario_corpus_hash
from invisiblebench.version import ENGINE_VERSION

PLAN_FILE = "scan_plan.json"
ANSWERS_FILE = "answers.jsonl"
LEDGER_FILE = "judgments.jsonl"

Turn = dict[str, Any]
Conversation = tuple[list[Turn], MemoryContext]
Request = dict[str, Any]


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def _read_ref(bundle: Path, ref: FileRef) -> bytes:
    path = bundle
    for part in ref.path.split("/"):
        path /= part
        if path.is_symlink():
            raise ValueError(f"bundle input must not be a symlink: {ref.path}")
    content = path.read_bytes()
    if sha256(content) != ref.sha256:
        raise ValueError(f"bundle input changed: {ref.path}")
    return content


def _transcript(content: bytes) -> list[Turn]:
    turns = [json.loads(line) for line in content.splitlines() if line.strip()]
    if not turns or any(not isinstance(turn, dict) for turn in turns):
        raise ValueError("transcript must contain turn objects")
    if not any(turn.get("role") == "assistant" for turn in turns):
        raise ValueError("transcript must contain an assistant response")
    seen: set[tuple[str, int]] = set()
    for turn in turns:
        if turn.get("role") not in {"user", "assistant"}:
            continue
        if (
            type(turn.get("turn")) is not int
            or turn["turn"] < 1
            or not isinstance(turn.get("content"), str)
        ):
            raise ValueError("conversation turns require content and a positive integer turn")
        if (turn["role"], turn["turn"]) in seen:
            raise ValueError("a transcript cannot repeat a role and turn number")
        seen.add((turn["role"], turn["turn"]))
    return turns


def _source_conversations(bundle: Path, source: SourceRun):
    manifest = json.loads(_read_ref(bundle, source.manifest))
    summary = json.loads(_read_ref(bundle, source.summary))
    if not manifest.get("run_id") or manifest["run_id"] != summary.get("run_id"):
        raise ValueError("source manifest and summary run IDs must match")
    policy = manifest.get("transcript_policy", {})
    if not isinstance(policy, dict):
        raise ValueError("transcript_policy must be an object")
    entries, identities = {}, set()
    for item in summary["transcripts"]:
        path, identity = item["transcript_path"], (item["model_id"], item["scenario_id"])
        if path in entries or identity in identities:
            raise ValueError("duplicate source transcript path or model/scenario identity")
        entries[path] = item
        identities.add(identity)
    source_root = Path(source.summary.path).parent
    for ref in source.transcripts:
        item = entries.get(Path(ref.path).relative_to(source_root).as_posix())
        if item is None or any(
            item.get(key) != getattr(ref, key)
            for key in ("model", "model_id", "scenario_id", "category")
        ):
            raise ValueError("planned transcript does not match its source summary")
        memory = MemoryContext.model_validate({
            "persistent_memory": policy.get("persistent_memory", False),
            "evidence": item.get("memory_evidence", []),
        })
        if memory.persistent_memory and (manifest.get("harness"), manifest.get("mode")) != (
            "product",
            "committed",
        ):
            raise ValueError(
                "raw model runs cannot declare persistent memory; use product/committed"
            )
        transcript = _transcript(_read_ref(bundle, ref))
        response_turns = {turn["turn"] for turn in transcript if turn.get("role") == "assistant"}
        if any(event.turn not in response_turns for event in memory.evidence):
            raise ValueError("memory evidence must name an observed assistant response turn")
        yield ref, transcript, memory


def _conversations(bundle: Path, plan: ScanPlan) -> dict[tuple[str, str], Conversation]:
    return {
        (ref.model_id, ref.scenario_id): (transcript, memory)
        for source in plan.sources
        for ref, transcript, memory in _source_conversations(bundle, source)
    }


def _requests(
    checks: list[Check], transcript: list[Turn], memory: MemoryContext
) -> dict[tuple[Role, int], Request]:
    """Every judge request for one conversation: a turn with at least one question."""
    requests = {}
    for role, turn in rules.request_turns(transcript):
        request = rules.build_request(checks, transcript, role, turn, memory)
        if request["questions"]:
            requests[role, turn] = request
    return requests


def _planned_requests(
    plan: ScanPlan, conversations: dict[tuple[str, str], Conversation]
) -> dict[tuple[str, str], dict[tuple[Role, int], Request]]:
    return {
        pair: _requests(plan.checks, transcript, memory)
        for pair, (transcript, memory) in conversations.items()
    }


def _snapshot(path: Path, destination: Path, bundle: Path) -> FileRef:
    content = path.read_bytes()
    ref = FileRef(path=destination.relative_to(bundle).as_posix(), sha256=sha256(content))
    if path == destination:
        _read_ref(bundle, ref)
        return ref
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    return ref


def plan_scan(
    run_dirs: list[Path],
    bundle: Path,
    *,
    judge_model: str = DEFAULT_JUDGE_MODEL,
    limit: int | None = None,
    filename_filter: str | None = None,
) -> ScanPlan:
    """Freeze source bytes and judge inputs without creating a model client."""
    if limit is not None and limit < 1:
        raise ValueError("limit must be positive")
    if not run_dirs:
        raise ValueError("at least one transcript run is required")
    bundle = bundle.resolve()
    runs = sorted({path.resolve() for path in run_dirs})
    in_place = runs == [bundle]
    if in_place:
        if (bundle / PLAN_FILE).exists() or (bundle / ANSWERS_FILE).exists():
            raise ValueError(
                "this run already has a scan; use a new output directory to judge again"
            )
    else:
        if any(run.is_relative_to(bundle) for run in runs):
            raise ValueError("a new scan directory cannot contain its source runs")
        bundle.mkdir(parents=True, exist_ok=False)
    try:
        sources = []
        for run in runs:
            manifest_path, summary_path = run / "run_manifest.json", run / "transcript_run.json"
            manifest, summary = (
                json.loads(manifest_path.read_bytes()),
                json.loads(summary_path.read_bytes()),
            )
            if manifest.get("schema") != "invisiblebench-run-manifest/v3":
                raise ValueError("source run must use invisiblebench-run-manifest/v3")
            if summary.get("artifact_type") != "transcript_run/v1":
                raise ValueError("source run must contain transcript_run/v1")
            selected = summary["transcripts"]
            if filename_filter:
                selected = [
                    item
                    for item in selected
                    if filename_filter.lower() in item["transcript_path"].lower()
                ]
            if limit is not None:
                selected = selected[:limit]
            if not selected:
                raise ValueError(f"no transcripts selected from {run.name}")
            destination = run if in_place else bundle / "inputs" / sha256(manifest_path.read_bytes())
            inputs = []
            for item in selected:
                relative = FileRef(path=item["transcript_path"], sha256="0" * 64).path
                original = run / relative
                if not original.resolve().is_relative_to(run):
                    raise ValueError("source transcript escapes its run directory")
                ref = _snapshot(original, destination / relative, bundle)
                _transcript(_read_ref(bundle, ref))
                inputs.append(
                    TranscriptSource(
                        **ref.model_dump(),
                        **{
                            key: item[key]
                            for key in ("model", "model_id", "scenario_id", "category")
                        },
                    )
                )
            sources.append(
                SourceRun(
                    manifest=_snapshot(manifest_path, destination / "run_manifest.json", bundle),
                    summary=_snapshot(summary_path, destination / "transcript_run.json", bundle),
                    transcripts=inputs,
                )
            )
        checks = list(load_checks().values())
        envelope, planned = 0, 0
        for source in sources:
            for _ref, transcript, memory in _source_conversations(bundle, source):
                for request in _requests(checks, transcript, memory).values():
                    envelope += len(json.dumps(request, ensure_ascii=False).encode())
                    planned += 1
        root = get_project_root()
        plan = ScanPlan(
            benchmark_version=get_benchmark_version(root),
            engine_version=ENGINE_VERSION,
            scenario_corpus_sha256=scenario_corpus_hash(root),
            judge=JudgeSettings(model=judge_model),
            checks=checks,
            sources=sources,
            planned_requests=planned,
            input_token_envelope=envelope,
            estimated_cost_usd=estimated_cost(judge_model, envelope),
        )
        with (bundle / PLAN_FILE).open("xb") as stream:
            stream.write(json_bytes(plan.model_dump(mode="json")))
            stream.flush()
            os.fsync(stream.fileno())
        return plan
    except BaseException:
        if not in_place:
            shutil.rmtree(bundle)
        raise


def plan_rejudge(frozen: Path, bundle: Path, *, model: str = DEFAULT_JUDGE_MODEL) -> ScanPlan:
    """Plan a new judge over the exact frozen sources and checks, never inside the old run."""
    frozen, bundle = frozen.resolve(), bundle.resolve()
    if bundle.is_relative_to(frozen) or frozen.is_relative_to(bundle):
        raise ValueError("the new run must be separate from its frozen source")
    plan, _, _ = load_scan(frozen, complete=True)
    candidate = plan.model_copy(update={
        "judge": JudgeSettings(model=model, thresholds=plan.judge.thresholds),
        "estimated_cost_usd": estimated_cost(model, plan.input_token_envelope),
    })
    bundle.mkdir(parents=True, exist_ok=False)
    try:
        refs = {ref.path: ref for source in plan.sources
                for ref in [source.manifest, source.summary, *source.transcripts]}
        for ref in refs.values():
            _read_ref(frozen, ref)
            if _snapshot(frozen / ref.path, bundle / ref.path, bundle).sha256 != ref.sha256:
                raise ValueError("frozen source changed while planning")
        with (bundle / PLAN_FILE).open("xb") as stream:
            stream.write(json_bytes(candidate.model_dump(mode="json")))
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        shutil.rmtree(bundle)
        raise
    return candidate


def _current_plan(plan: ScanPlan) -> None:
    if (
        plan.benchmark_version != get_benchmark_version()
        or plan.engine_version != ENGINE_VERSION
        or plan.scenario_corpus_sha256 != scenario_corpus_hash(get_project_root())
        or plan.checks != list(load_checks().values())
        or plan.judge != JudgeSettings(model=plan.judge.model)
    ):
        raise ValueError("plan differs from the current benchmark, checks, or judge settings")


def _publication_sources(bundle: Path, plan: ScanPlan) -> None:
    expected = set(collect_public_scenario_ids())
    by_model: dict[str, set[str]] = {}
    contracts = set()
    for source in plan.sources:
        manifest = json.loads(_read_ref(bundle, source.manifest))
        summary = json.loads(_read_ref(bundle, source.summary))
        entries = summary.get("transcripts") or []
        if (
            manifest.get("schema") != "invisiblebench-run-manifest/v3"
            or manifest.get("benchmark_version") != plan.benchmark_version
            or manifest.get("scenario_hash") != plan.scenario_corpus_sha256
            or manifest.get("git_dirty") is not False
            or not manifest.get("git_sha")
            or not manifest.get("transcript_policy")
            or manifest.get("harness") != "llm"
            or manifest.get("mode") != "raw"
            or summary.get("artifact_type") != "transcript_run/v1"
            or summary.get("run_id") != manifest.get("run_id")
            or summary.get("status") != "complete"
            or summary.get("error_count") != 0
            or summary.get("missing_count") != 0
            or summary.get("transcript_count") != len(entries)
            or summary.get("expected_transcripts") != len(entries)
            or set(summary.get("model_ids") or []) != set(manifest.get("model_ids") or [])
            or {item.get("scenario_id") for item in entries}
            != set(manifest.get("scenario_ids") or [])
        ):
            raise ValueError("publication requires complete, comparable source runs")
        contracts.add(
            json.dumps(
                {
                    key: manifest.get(key)
                    for key in ("git_sha", "harness", "mode", "transcript_policy")
                },
                sort_keys=True,
            )
        )
        by_pair = {(item["model_id"], item["scenario_id"]): item for item in entries}
        if len(by_pair) != len(entries):
            raise ValueError("source summary has duplicate model/scenario pairs")
        parent = Path(source.summary.path).parent
        for transcript in source.transcripts:
            item = by_pair.get((transcript.model_id, transcript.scenario_id))
            if (
                item is None
                or any(
                    item.get(key) != getattr(transcript, key)
                    for key in ("model", "model_id", "scenario_id", "category")
                )
                or (parent / item["transcript_path"]).as_posix() != transcript.path
            ):
                raise ValueError("transcript identity differs from the retained source summary")
            by_model.setdefault(transcript.model_id, set()).add(transcript.scenario_id)
    if len(contracts) != 1 or any(scenarios != expected for scenarios in by_model.values()):
        raise ValueError(
            "publication requires the complete current scenario roster for every model"
        )


def _read_answers(
    bundle: Path,
    plan_sha256: str,
    requests: dict[tuple[str, str], dict[tuple[Role, int], Request]],
) -> list[Answer]:
    path = bundle / ANSWERS_FILE
    content = path.read_bytes() if path.exists() else b""
    if content and not content.endswith(b"\n"):
        raise ValueError("ledger has an unfinished last line; resume the scan to recover it")
    answers: list[Answer] = []
    settled: set[tuple[str, str, str, int]] = set()
    for line in content.splitlines():
        answer = Answer.model_validate_json(line)
        request = requests.get((answer.model_id, answer.scenario_id), {}).get(
            (answer.role, answer.turn)
        )
        if request is None or answer.key in settled:
            raise ValueError("duplicate or unplanned answer")
        if answer.plan_sha256 != plan_sha256:
            raise ValueError("answer is bound to a different scan plan")
        if answer.input_sha256 != rules.input_hash(request):
            raise ValueError("answer request differs from the frozen inputs")
        if answer.answers is not None:
            validate_answers(answer.answers, request["questions"]) 
        answers.append(answer)
        if answer.error is None:
            settled.add(answer.key)
    return answers


def derive_all(
    plan: ScanPlan,
    conversations: dict[tuple[str, str], Conversation],
    answers: list[Answer],
    plan_sha256: str,
) -> list[Judgment]:
    """Apply every check's rule to the saved answers. One judgment per pair and check."""
    saved: dict[tuple[str, str], dict[tuple[Role, int], dict[str, float]]] = {}
    for answer in answers:
        if answer.answers is not None:
            saved.setdefault((answer.model_id, answer.scenario_id), {})[
                answer.role, answer.turn
            ] = answer.answers
    judgments = []
    for ref in plan.transcripts:
        pair = (ref.model_id, ref.scenario_id)
        transcript, memory = conversations[pair]
        for check in plan.checks:
            judgments.append(
                rules.derive(
                    check,
                    transcript,
                    saved.get(pair, {}),
                    plan.judge.thresholds,
                    model_id=ref.model_id,
                    scenario_id=ref.scenario_id,
                    plan_sha256=plan_sha256,
                    memory_declared=memory.persistent_memory,
                )
            )
    return judgments


def _write_judgments(bundle: Path, judgments: list[Judgment]) -> None:
    content = b"".join(judgment.model_dump_json().encode() + b"\n" for judgment in judgments)
    temporary = bundle / (LEDGER_FILE + ".tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, bundle / LEDGER_FILE)
    finally:
        temporary.unlink(missing_ok=True)


def load_scan(
    bundle: Path,
    *,
    complete: bool = False,
    current: bool = False,
    verify_judgments: bool = True,
) -> tuple[ScanPlan, list[Answer], list[Judgment]]:
    """Validate the same scan for resume, inspection, scoring, and publication."""
    bundle = Path(bundle)
    plan_bytes = (bundle / PLAN_FILE).read_bytes()
    plan = ScanPlan.model_validate_json(plan_bytes)
    plan_sha = sha256(plan_bytes)
    conversations = _conversations(bundle, plan)
    requests = _planned_requests(plan, conversations)
    planned = sum(len(turns) for turns in requests.values())
    answers = _read_answers(bundle, plan_sha, requests)
    finished = {answer.key for answer in answers if answer.error is None}
    ledger = bundle / LEDGER_FILE
    judgments: list[Judgment] = []
    if ledger.exists():
        judgments = [
            Judgment.model_validate_json(line) for line in ledger.read_bytes().splitlines() if line
        ]
        if verify_judgments and (
            len(finished) != planned
            or judgments != derive_all(plan, conversations, answers, plan_sha)
        ):
            raise ValueError("stored judgments differ from the saved answers")
    if complete or current:
        if len(finished) != planned:
            raise ValueError(f"scan is incomplete: {len(finished)}/{planned} answers")
        if not ledger.exists():
            raise ValueError("scan is incomplete: no judgments were derived from its answers")
    if current:
        _current_plan(plan)
        _publication_sources(bundle, plan)
    return plan, answers, judgments


def _ask(
    client: Any, model: str, request: Request, *, model_id: str, scenario_id: str,
    role: Role, turn: int, plan_sha256: str,
) -> Answer:
    identity = {
        "model_id": model_id, "scenario_id": scenario_id, "role": role, "turn": turn,
        "plan_sha256": plan_sha256, "input_sha256": rules.input_hash(request),
    }
    before = cost_tracker.total
    result = None
    error = detail = None
    try:
        result = client.ask(model=model, **request)
        if not isinstance(result, SystemOneResponse):
            raise ValueError("judge must return a typed SDK response")
        validate_answers(result.answers, request["questions"])
        if result.model != model:
            raise ValueError("returned judge differs from the requested model")
    except CostBudgetExceededError:
        raise
    except InvalidJudgeOutput as exc:
        result, error, detail = exc.response, "invalid_judge_output", str(exc)
    except ValueError as exc:
        error, detail = "invalid_judge_output", str(exc)
    except Exception as exc:
        error, detail = "judge_api_error", type(exc).__name__
    valid_response = isinstance(result, SystemOneResponse)
    return Answer(
        **identity,
        judge=JudgeObservation(model=result.model if valid_response else None),
        answers=result.answers if valid_response and error is None else None,
        input_tokens=(result.usage.input_tokens or 0) if valid_response else 0,
        cost_usd=cost_tracker.total - before,
        error=error, error_detail=detail,
    )


@contextmanager
def execute_requests(
    bundle: Path, *, model: str, plan_sha256: str, requests: dict,
    estimate: float | None, max_cost_usd: float, client: Any | None = None,
):
    """The sole offline request loop. Hold the lock through the caller's projection."""
    if not math.isfinite(max_cost_usd) or max_cost_usd <= 0:
        raise ValueError("max_cost_usd must be finite and positive")
    with (bundle / ANSWERS_FILE).open("a+b") as journal, ExitStack() as clients:
        try:
            fcntl.flock(journal.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("this scan is already running") from exc
        journal.seek(0)
        content = journal.read()
        if content and not content.endswith(b"\n"):
            journal.truncate(content.rfind(b"\n") + 1)
            journal.flush()
            os.fsync(journal.fileno())
        answers = _read_answers(bundle, plan_sha256, requests)
        if any(a.error is None and a.judge.model != model for a in answers):
            raise ValueError("saved answer came from a different judge")
        done = {a.key for a in answers if a.error is None}
        pending = [(mid, sid, role, turn, request)
                   for (mid, sid), turns in requests.items()
                   for (role, turn), request in turns.items()
                   if (mid, sid, role, turn) not in done]
        if pending:
            if estimate is None or max_cost_usd < estimate:
                raise ValueError("unknown pricing or the dry-run estimate exceeds max_cost_usd")
            if max_cost_usd > maximum_reasonable_cost_ceiling(estimate):
                raise ValueError("max_cost_usd exceeds the dry-run plan's accepted ceiling")
            spent = sum(a.cost_usd for a in answers)
            if spent >= max_cost_usd:
                raise ValueError("saved judgment costs have reached max_cost_usd")
            cost_tracker.reset(max_cost_usd=max_cost_usd - spent)
            if client is None:
                client = clients.enter_context(SystemOneClient())
            for mid, sid, role, turn, request in pending:
                answer = _ask(client, model, request, model_id=mid, scenario_id=sid,
                              role=role, turn=turn, plan_sha256=plan_sha256)
                journal.write(answer.model_dump_json().encode() + b"\n")
                journal.flush()
                os.fsync(journal.fileno())
                answers.append(answer)
                if answer.error is not None:
                    raise RuntimeError(f"{sid} {role} turn {turn}: {answer.error}; attempt saved. "
                                       "Resume to retry this unfinished request.")
        yield answers


def plan_questions(
    bundle: Path, tasks: list[RequestTask], *, model: str = DEFAULT_JUDGE_MODEL,
    sources: dict[str, Path] | None = None,
) -> QuestionPlan:
    envelope = sum(len(json.dumps(t.request, ensure_ascii=False).encode()) for t in tasks)
    plan = QuestionPlan(judge=JudgeSettings(model=model), tasks=tasks,
                        estimated_cost_usd=estimated_cost(model, envelope))
    bundle.mkdir(parents=True, exist_ok=False)
    try:
        for name, path in (sources or {}).items():
            relative = FileRef(path=name, sha256="0" * 64).path
            plan.inputs.append(_snapshot(path, bundle / relative, bundle))
        with (bundle / PLAN_FILE).open("xb") as stream:
            stream.write(json_bytes(plan.model_dump(mode="json")))
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        shutil.rmtree(bundle)
        raise
    return plan


def question_requests(plan: QuestionPlan) -> dict:
    requests: dict = {}
    for task in plan.tasks:
        requests.setdefault((task.model_id, task.scenario_id), {})[task.role, task.turn] = task.request
    return requests


def run_questions(bundle: Path, *, max_cost_usd: float, client: Any | None = None) -> list[Answer]:
    content = (bundle / PLAN_FILE).read_bytes()
    plan = QuestionPlan.model_validate_json(content)
    for ref in plan.inputs:
        _read_ref(bundle, ref)
    with execute_requests(bundle, model=plan.judge.model, plan_sha256=sha256(content),
                          requests=question_requests(plan), estimate=plan.estimated_cost_usd,
                          max_cost_usd=max_cost_usd, client=client) as answers:
        return answers


def run_scan(bundle: Path, *, max_cost_usd: float, client: Any | None = None) -> list[Judgment]:
    """Execute a frozen scan, then derive the judgments while holding its journal lock."""
    bundle = Path(bundle)
    if not (bundle / PLAN_FILE).is_file():
        raise ValueError("a saved dry-run scan plan is required")
    content = (bundle / PLAN_FILE).read_bytes()
    plan = ScanPlan.model_validate_json(content)
    _current_plan(plan)
    conversations = _conversations(bundle, plan)
    digest = sha256(content)
    with execute_requests(bundle, model=plan.judge.model, plan_sha256=digest,
                          requests=_planned_requests(plan, conversations),
                          estimate=plan.estimated_cost_usd, max_cost_usd=max_cost_usd,
                          client=client) as answers:
        if (bundle / LEDGER_FILE).exists():
            return load_scan(bundle, complete=True)[2]
        judgments = derive_all(plan, conversations, answers, digest)
        _write_judgments(bundle, judgments)
        return judgments


def replay_scan(bundle: Path) -> list[str]:
    """Derive the verdicts again from the saved answers, without API calls."""
    bundle = Path(bundle)
    plan, answers, saved = load_scan(bundle, complete=True, verify_judgments=False)
    derived = derive_all(
        plan, _conversations(bundle, plan), answers, sha256((bundle / PLAN_FILE).read_bytes())
    )
    differences = {
        "/".join(judgment.key)
        for judgment, stored in zip(derived, saved, strict=False)
        if judgment != stored
    }
    for extra in derived[len(saved):] + saved[len(derived):]:
        differences.add("/".join(extra.key))
    return sorted(differences)
