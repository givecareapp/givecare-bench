"""Pure Care observations for the LLM-first benchmark contract.

Care is reported per quality.  The qualities stay separate, and every
PASS/FAIL/UNCLEAR/NOT_APPLICABLE result remains visible in the output.
"""

from __future__ import annotations

from typing import Any

from invisiblebench.scoring.contract import (
    FAIL_VERDICT,
    NOT_APPLICABLE_VERDICT,
    PASS_VERDICT,
    UNCLEAR_VERDICT,
    dimensions_from_checks,
    verdict_value,
)

CARE_DIMENSIONS: tuple[str, ...] = (
    "belonging",
    "attunement",
    "relational",
    "advocacy",
)
VERDICT_KEYS: tuple[str, ...] = (
    PASS_VERDICT,
    FAIL_VERDICT,
    UNCLEAR_VERDICT,
    NOT_APPLICABLE_VERDICT,
)


def _normalise_dim_map(dim_map: dict[str, dict[str, str]] | None) -> dict[str, dict[str, str]]:
    if dim_map is not None:
        return dim_map
    from invisiblebench.evaluation.check_registry import load_checks

    return dimensions_from_checks(load_checks())


def _blank() -> dict[str, Any]:
    return {
        "counts": dict.fromkeys(VERDICT_KEYS, 0),
        "pass": 0,
        "fail": 0,
        "unclear": 0,
        "not_applicable": 0,
        "eligible": 0,
        "resolved": 0,
        "denominator": 0,
    }


def _record(target: dict[str, Any], verdict: str) -> None:
    if verdict not in VERDICT_KEYS:
        raise ValueError(f"non-canonical verdict in scoring row: {verdict!r}")
    target["counts"][verdict] += 1
    if verdict == PASS_VERDICT:
        target["pass"] += 1
        target["resolved"] += 1
    elif verdict == FAIL_VERDICT:
        target["fail"] += 1
        target["resolved"] += 1
    elif verdict == UNCLEAR_VERDICT:
        target["unclear"] += 1
    else:
        target["not_applicable"] += 1
        return
    target["eligible"] += 1
    target["denominator"] += 1


def scenario_care(
    mode_results: list[dict[str, Any]],
    dim_map: dict[str, dict[str, str]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Count one row's Care verdicts by quality."""

    dimensions = _normalise_dim_map(dim_map)
    output = {dimension: _blank() for dimension in CARE_DIMENSIONS}
    for result in mode_results or []:
        mode_id = str(result.get("mode_id") or "")
        info = dimensions.get(mode_id)
        if not info or info.get("layer") != "care":
            continue
        dimension = str(info.get("dimension") or "")
        if dimension in output:
            _record(output[dimension], verdict_value(result.get("verdict")))
    return output


def model_care_distribution(
    scenario_cares: list[dict[str, dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    """Aggregate Care quality observations without cross-quality averaging."""

    result: dict[str, dict[str, Any]] = {}
    for dimension in CARE_DIMENSIONS:
        merged = _blank()
        observed_scenarios = 0
        for scenario in scenario_cares:
            source = scenario.get(dimension) or {}
            counts = source.get("counts") or {}
            for verdict in VERDICT_KEYS:
                merged["counts"][verdict] += int(counts.get(verdict, 0) or 0)
            for field in (
                "pass",
                "fail",
                "unclear",
                "not_applicable",
                "eligible",
                "resolved",
                "denominator",
            ):
                merged[field] += int(source.get(field, 0) or 0)
            if int(source.get("denominator", 0) or 0) > 0:
                observed_scenarios += 1
        denominator = merged["denominator"]
        result[dimension] = {
            "pass_rate": round(merged["pass"] / denominator, 4) if denominator else None,
            "n": denominator,
            "denominator": denominator,
            "scenario_denominator": len(scenario_cares),
            "eligible_scenarios": observed_scenarios,
            "eligible": merged["eligible"],
            "resolved": merged["resolved"],
            "unclear": merged["unclear"],
            "not_applicable": merged["not_applicable"],
            "counts": merged["counts"],
            "directional": True,
            "observation_type": "MODEL-JUDGED",
            "uncertainty": "UNCLEAR is included in the denominator",
        }
    return result


__all__ = ["CARE_DIMENSIONS", "VERDICT_KEYS", "model_care_distribution", "scenario_care"]
