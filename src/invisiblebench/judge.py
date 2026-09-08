"""Plan, save, resume, validate, and replay a portable judgment ledger."""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import shutil
from pathlib import Path
from typing import Any

from invisiblebench.api.client import (
    _MODEL_PRICING,
    DEFAULT_JUDGE_MODEL,
    ModelAPIClient,
    cost_tracker,
    maximum_reasonable_cost_ceiling,
)
from invisiblebench.evaluation.check_registry import load_checks
from invisiblebench.evaluation.judgment import (
    JUDGE_INSTRUCTIONS,
    input_hash,
    judge_check,
    parse_decision,
    request_messages,
)
from invisiblebench.models.scan import (
    Decision,
    FileRef,
    JudgeSettings,
    Judgment,
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
LEDGER_FILE = "judgments.jsonl"


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


def _transcript(content: bytes) -> list[dict[str, Any]]:
    turns = [json.loads(line) for line in content.splitlines() if line.strip()]
    if not turns or any(not isinstance(turn, dict) for turn in turns):
        raise ValueError("transcript must contain turn objects")
    if not any(turn.get("role") == "assistant" for turn in turns):
        raise ValueError("transcript must contain an assistant response")
    for turn in turns:
        if turn.get("role") in {"user", "assistant"} and (
            type(turn.get("turn")) is not int
            or turn["turn"] < 1
            or not isinstance(turn.get("content"), str)
        ):
            raise ValueError("conversation turns require content and a positive integer turn")
    return turns


def _snapshot(path: Path, destination: Path, bundle: Path) -> FileRef:
    content = path.read_bytes()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    return FileRef(path=destination.relative_to(bundle).as_posix(), sha256=sha256(content))


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
    bundle.mkdir(parents=True, exist_ok=False)
    try:
        sources = []
        for run in sorted({path.resolve() for path in run_dirs}):
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
            destination = bundle / "inputs" / sha256(manifest_path.read_bytes())
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
        settings = JudgeSettings(model=judge_model)
        token_envelope = sum(
            len(
                json.dumps(
                    request_messages(check, _transcript(_read_ref(bundle, transcript))),
                    ensure_ascii=False,
                ).encode()
            )
            for source in sources
            for transcript in source.transcripts
            for check in checks
        )
        pricing = _MODEL_PRICING.get(judge_model)
        calls = sum(len(source.transcripts) for source in sources) * len(checks)
        estimate = (
            (token_envelope * pricing[0] + calls * settings.max_tokens * pricing[1]) / 1_000_000
            if pricing is not None
            else None
        )
        root = get_project_root()
        plan = ScanPlan(
            benchmark_version=get_benchmark_version(root),
            engine_version=ENGINE_VERSION,
            scenario_corpus_sha256=scenario_corpus_hash(root),
            judge=settings,
            instructions=JUDGE_INSTRUCTIONS,
            checks=checks,
            sources=sources,
            input_token_envelope=token_envelope,
            estimated_cost_usd=estimate,
        )
        with (bundle / PLAN_FILE).open("xb") as stream:
            stream.write(json_bytes(plan.model_dump(mode="json")))
            stream.flush()
            os.fsync(stream.fileno())
        return plan
    except BaseException:
        shutil.rmtree(bundle)
        raise


def _current_plan(plan: ScanPlan) -> None:
    if (
        plan.benchmark_version != get_benchmark_version()
        or plan.engine_version != ENGINE_VERSION
        or plan.scenario_corpus_sha256 != scenario_corpus_hash(get_project_root())
        or plan.checks != list(load_checks().values())
        or plan.instructions != JUDGE_INSTRUCTIONS.strip()
        or plan.judge != JudgeSettings(model=plan.judge.model)
    ):
        raise ValueError("plan differs from the current benchmark, criteria, or judge settings")


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


def load_scan(
    bundle: Path,
    *,
    complete: bool = False,
    current: bool = False,
) -> tuple[ScanPlan, list[Judgment]]:
    """Validate the same ledger for resume, inspection, scoring, and publication."""
    bundle = Path(bundle)
    plan_bytes = (bundle / PLAN_FILE).read_bytes()
    plan = ScanPlan.model_validate_json(plan_bytes)
    plan_sha = sha256(plan_bytes)
    checks = {check.id: check for check in plan.checks}
    transcripts = {}
    for source in plan.sources:
        _read_ref(bundle, source.manifest)
        _read_ref(bundle, source.summary)
        for ref in source.transcripts:
            transcripts[ref.model_id, ref.scenario_id] = _transcript(_read_ref(bundle, ref))
    ledger = bundle / LEDGER_FILE
    content = ledger.read_bytes() if ledger.exists() else b""
    if content and not content.endswith(b"\n"):
        raise ValueError("ledger has an unfinished last line; resume the scan to recover it")
    records, seen = [], set()
    for line in content.splitlines():
        record = Judgment.model_validate_json(line)
        pair = record.model_id, record.scenario_id
        if record.key in seen or pair not in transcripts or record.check_id not in checks:
            raise ValueError("duplicate or unplanned judgment")
        if record.plan_sha256 != plan_sha:
            raise ValueError("judgment is bound to a different scan plan")
        transcript = transcripts[pair]
        messages = request_messages(checks[record.check_id], transcript, plan.instructions)
        if input_hash(messages) != record.input_sha256:
            raise ValueError("judgment request differs from the frozen inputs")
        if record.error is None:
            decision = parse_decision(
                record.raw_response or "", record.judge.finish_reason, transcript
            )
            if decision.model_dump() != record.model_dump(include=set(Decision.model_fields)):
                raise ValueError("stored judgment differs from the raw judge decision")
        elif record.error == "judge_api_error" and record.raw_response is not None:
            raise ValueError("an API error cannot contain a judge response")
        records.append(record)
        if record.error is None:
            seen.add(record.key)
    if (complete or current) and len(seen) != plan.planned_calls:
        raise ValueError(f"scan is incomplete: {len(seen)}/{plan.planned_calls} judgments")
    if current:
        _current_plan(plan)
        _publication_sources(bundle, plan)
    return plan, records


def run_scan(
    bundle: Path,
    *,
    max_cost_usd: float,
    client: Any | None = None,
) -> list[Judgment]:
    """Resume from completed judgments. Save each result before the next call."""
    bundle = Path(bundle)
    if not (bundle / PLAN_FILE).is_file():
        raise ValueError("a saved dry-run scan plan is required")
    with (bundle / LEDGER_FILE).open("a+b") as journal:
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
        plan, records = load_scan(bundle)
        _current_plan(plan)
        done = {record.key for record in records if record.error is None}
        if len(done) == plan.planned_calls:
            return records
        estimate = plan.estimated_cost_usd
        if not math.isfinite(max_cost_usd) or max_cost_usd <= 0:
            raise ValueError("max_cost_usd must be finite and positive")
        if estimate is None or max_cost_usd < estimate:
            raise ValueError("unknown pricing or the dry-run estimate exceeds max_cost_usd")
        if max_cost_usd > maximum_reasonable_cost_ceiling(estimate):
            raise ValueError("max_cost_usd exceeds the dry-run plan's accepted ceiling")
        spent = sum(record.cost_usd for record in records)
        if spent >= max_cost_usd:
            raise ValueError("saved judgment costs have reached max_cost_usd")
        cost_tracker.reset(max_cost_usd=max_cost_usd - spent)
        client = client if client is not None else ModelAPIClient()
        plan_sha = sha256((bundle / PLAN_FILE).read_bytes())
        for source in plan.sources:
            for ref in source.transcripts:
                transcript = _transcript(_read_ref(bundle, ref))
                for check in plan.checks:
                    if (ref.model_id, ref.scenario_id, check.id) in done:
                        continue
                    record = judge_check(
                        client,
                        transcript,
                        check,
                        plan.judge,
                        instructions=plan.instructions,
                        model_id=ref.model_id,
                        scenario_id=ref.scenario_id,
                        plan_sha256=plan_sha,
                    )
                    journal.write(record.model_dump_json().encode() + b"\n")
                    journal.flush()
                    os.fsync(journal.fileno())
                    records.append(record)
                    if record.error is not None:
                        raise RuntimeError(
                            f"{record.check_id}: {record.error}; attempt saved. Resume to retry this unfinished request."
                        )
                    done.add(record.key)
        return records


def replay_scan(bundle: Path) -> list[str]:
    """Reparse saved responses through the current judge code without API calls."""
    plan, records = load_scan(bundle, complete=True)
    _current_plan(plan)
    checks = {check.id: check for check in plan.checks}
    transcripts = {
        (ref.model_id, ref.scenario_id): _transcript(_read_ref(bundle, ref))
        for ref in plan.transcripts
    }
    differences = []

    class ReplayClient:
        def __init__(self, saved: Judgment):
            self.saved = saved

        def call_model(self, **kwargs):
            if self.saved.error == "judge_api_error":
                raise RuntimeError("saved API failure")
            if self.saved.raw_response is None:
                return None
            return {
                "response": self.saved.raw_response,
                "finish_reason": self.saved.judge.finish_reason,
                "raw": {"model": self.saved.judge.model, "provider": self.saved.judge.provider},
            }

    for saved in records:
        replayed = judge_check(
            ReplayClient(saved),
            transcripts[saved.model_id, saved.scenario_id],
            checks[saved.check_id],
            plan.judge,
            instructions=plan.instructions,
            model_id=saved.model_id,
            scenario_id=saved.scenario_id,
            plan_sha256=saved.plan_sha256,
        )
        if replayed.model_dump(exclude={"cost_usd", "error_detail"}) != saved.model_dump(
            exclude={"cost_usd", "error_detail"}
        ):
            differences.append("/".join(saved.key))
    return differences
