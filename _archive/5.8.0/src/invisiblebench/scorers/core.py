"""Derive one conversation's check verdicts from saved judge answers."""

from __future__ import annotations

from collections.abc import Iterable

from inspect_ai.scorer import Score
from typesafe_sdk import Answer as TypedAnswer

from invisiblebench.evaluation import rules
from invisiblebench.models.scan import DIMENSIONS, Check, Judgment, Role, Thresholds, Verdict

CHECK_LAYERS = {
    dimension: layer for layer, dimensions in DIMENSIONS.items() for dimension in dimensions
}


def derive_conversation(
    checks: Iterable[Check],
    transcript: list[dict],
    answers: dict[tuple[Role, int], dict[str, TypedAnswer]],
    thresholds: Thresholds,
    *,
    model_id: str,
    scenario_id: str,
    plan_sha256: str,
    memory_declared: bool = False,
) -> list[tuple[Judgment, set[Verdict]]]:
    """Keep possible verdicts beside each exact verdict for Inspect metrics."""
    return [
        rules.analyze(
            check,
            transcript,
            answers,
            thresholds,
            model_id=model_id,
            scenario_id=scenario_id,
            plan_sha256=plan_sha256,
            memory_declared=memory_declared,
        )
        for check in checks
    ]


def inspect_score(analyses: list[tuple[Judgment, set[Verdict]]]) -> Score:
    """Record every check verdict and its exact uncertainty in one Inspect sample."""
    checks = [
        {
            "check_id": judgment.check_id,
            "layer": CHECK_LAYERS[judgment.check_id.split(".", 1)[0]],
            "dimension": judgment.check_id.split(".", 1)[0],
            "verdict": judgment.verdict.value,
            "possible_verdicts": sorted(verdict.value for verdict in possible),
            "rationale": judgment.rationale,
            "evidence": [span.model_dump(mode="json") for span in judgment.evidence],
            "plan_sha256": judgment.plan_sha256,
        }
        for judgment, possible in analyses
    ]
    return Score(
        value={item["check_id"]: item["verdict"] for item in checks},
        metadata={"checks": checks},
    )
