"""Inspect scorer with frozen, journaled Jev requests per sample."""

from __future__ import annotations

import asyncio
import fcntl
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from inspect_ai.scorer import Score, Target, scorer
from inspect_ai.solver import TaskState

from invisiblebench.api.typesafe import (
    DEFAULT_JUDGE_MODEL,
    CostTracker,
    estimated_cost,
    maximum_reasonable_cost_ceiling,
)
from invisiblebench.evaluation.check_registry import load_checks
from invisiblebench.evaluation.requests import conversation_requests, merge_answers
from invisiblebench.judge import (
    ANSWERS_FILE,
    ATTEMPTS_FILE,
    LEDGER_FILE,
    _require_settled,
    execute_requests,
    json_bytes,
    sha256,
)
from invisiblebench.models.scan import Answer, MemoryContext, Thresholds
from invisiblebench.scorers.core import derive_conversation, inspect_score

PLAN_FILE = "inspect_score_plan.json"


def state_transcript(state: TaskState) -> list[dict[str, Any]]:
    """Read the solver's authored turn identities directly from Inspect messages."""
    transcript = []
    for message in state.messages:
        if message.role not in {"user", "assistant"}:
            continue
        metadata = dict(message.metadata or {})
        turn = metadata.pop("turn", None)
        if type(turn) is not int or turn < 1:
            raise ValueError("Inspect messages require a positive authored turn number")
        transcript.append({"role": message.role, "turn": turn, "content": message.text, **metadata})
    if not transcript or not any(turn["role"] == "assistant" for turn in transcript):
        raise ValueError("Inspect sample has no assistant reply to score")
    return transcript


def _sample_dir(root: Path, state: TaskState) -> Path:
    identity = json_bytes([str(state.model), str(state.sample_id), state.epoch])
    return root / hashlib.sha256(identity).hexdigest()


def _write_plan(path: Path, content: bytes, *, create: bool) -> None:
    if path.exists():
        if path.read_bytes() != content:
            old, new = json.loads(path.read_bytes()), json.loads(content)
            changed = sorted(key for key in old.keys() | new.keys() if old.get(key) != new.get(key))
            raise ValueError(f"saved Inspect score plan differs from this sample: {changed}")
        return
    if not create:
        raise ValueError("a saved dry-run Inspect score plan is required before judge dispatch")
    if any(path.parent.iterdir()):
        raise ValueError("sample journal exists without a frozen Inspect score plan")
    with path.open("xb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def _saved_answers(path: Path) -> list[Answer]:
    if not path.exists():
        return []
    return [Answer.model_validate_json(line) for line in path.read_bytes().splitlines() if line]


def _saved_cost(root: Path) -> float:
    total = 0.0
    for bundle in root.iterdir():
        if bundle.is_symlink():
            raise ValueError("Inspect journal root must not contain symlinks")
        if not bundle.is_dir():
            continue
        answers = _saved_answers(bundle / ANSWERS_FILE)
        attempts = bundle / ATTEMPTS_FILE
        if attempts.exists():
            with attempts.open("r+b") as stream:
                _require_settled(stream, answers)
        total += sum(answer.cost_usd for answer in answers)
    return total


def _score_sync(
    state: TaskState,
    *,
    ledger_dir: Path,
    judge_model: str,
    max_cost_usd: float,
    plan_only: bool = True,
) -> Score:
    root = ledger_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        bundle = _sample_dir(root, state)
        if bundle.is_symlink():
            raise ValueError("Inspect sample journal must not be a symlink")
        bundle.mkdir(exist_ok=True)
        transcript = state_transcript(state)
        checks = list(load_checks().values())
        thresholds = Thresholds()
        model_id, scenario_id = str(state.model), str(state.sample_id)
        memory = MemoryContext()
        requests = conversation_requests(checks, transcript, memory)
        plan = {
            "schema": "invisiblebench-inspect-score-plan/v1",
            "model_id": model_id,
            "scenario_id": scenario_id,
            "epoch": state.epoch,
            "judge_model": judge_model,
            "thresholds": thresholds.model_dump(mode="json"),
            "checks": [check.model_dump(mode="json") for check in checks],
            "transcript_sha256": sha256(json_bytes(transcript)),
            "request_keys": sorted([role, turn, digest] for role, turn, digest in requests),
        }
        content = json_bytes(plan)
        _write_plan(bundle / PLAN_FILE, content, create=plan_only)
        estimate = estimated_cost(
            judge_model,
            sum(len(json.dumps(request, ensure_ascii=False).encode()) for request in requests.values()),
        )
        if plan_only:
            return Score.unscored(
                reason="judge_plan_only",
                metadata={
                    "plan_sha256": sha256(content),
                    "planned_requests": len(requests),
                    "estimated_cost_usd": estimate,
                    "judge_model": judge_model,
                },
            )
        digest = sha256(content)
        spent_elsewhere = _saved_cost(root) - sum(
            answer.cost_usd for answer in _saved_answers(bundle / ANSWERS_FILE)
        )
        available = max_cost_usd - spent_elsewhere
        ceiling = min(available, maximum_reasonable_cost_ceiling(estimate or 0.0))
        with execute_requests(
            bundle,
            model=judge_model,
            plan_sha256=digest,
            requests={(model_id, scenario_id): requests},
            estimate=estimate,
            max_cost_usd=ceiling,
            tracker=CostTracker(),
        ) as answers:
            saved: dict = {}
            for answer in answers:
                if answer.error is None and answer.answers is not None:
                    merge_answers(saved, answer.role, answer.turn, answer.answers)
            analyses = derive_conversation(
                checks,
                transcript,
                saved,
                thresholds,
                model_id=model_id,
                scenario_id=scenario_id,
                plan_sha256=digest,
                memory_declared=memory.persistent_memory,
            )
            ledger = b"".join(
                judgment.model_dump_json().encode() + b"\n" for judgment, _ in analyses
            )
            ledger_path = bundle / LEDGER_FILE
            if ledger_path.exists():
                if ledger_path.read_bytes() != ledger:
                    raise ValueError("saved Inspect judgments differ from saved answers")
            else:
                with ledger_path.open("xb") as stream:
                    stream.write(ledger)
                    stream.flush()
                    os.fsync(stream.fileno())
            score = inspect_score(analyses)
            score.metadata.update(
                {"model_id": model_id, "scenario_id": scenario_id, "epoch": state.epoch}
            )
            return score


@scorer(metrics=[])
def safety_care_scorer(
    ledger_dir: str,
    max_cost_usd: float,
    judge_model: str = DEFAULT_JUDGE_MODEL,
    plan_only: bool = True,
):
    """Score one completed Inspect sample; a single run-wide ceiling covers all samples."""

    async def score(state: TaskState, _target: Target) -> Score:
        return await asyncio.to_thread(
            _score_sync,
            state,
            ledger_dir=Path(ledger_dir),
            judge_model=judge_model,
            max_cost_usd=max_cost_usd,
            plan_only=plan_only,
        )

    return score
