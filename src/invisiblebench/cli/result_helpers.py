"""Result-building helpers shared by the sync and async scoring paths."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from invisiblebench.evaluation.verifiers.base import (
    FAILURE_VERDICT_VALUES,
    GATE_SEVERITIES,
)
from invisiblebench.models.results import (
    PUBLIC_SCORE_MODEL,
    RAW_RESULT_SURFACE,
    RAW_SCORE_MODEL,
    SUCCESS_THRESHOLD,
    is_result_success,
)
from invisiblebench.version import RESULT_CONTRACT_VERSION


def _raw_score_metadata() -> dict[str, str]:
    return {
        "result_surface": RAW_RESULT_SURFACE,
        "score_model": RAW_SCORE_MODEL,
        "public_score_model": PUBLIC_SCORE_MODEL,
    }


def _raw_gate_payload(
    mode_results: list[dict[str, Any]],
    hard_fail_reasons: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    gates: dict[str, dict[str, Any]] = {}
    for gate_name in ("crisis", "scope", "identity", "autonomy"):
        gate_reasons = [
            str(reason.get("mode_id") or reason.get("reason") or "gate_failure")
            for reason in hard_fail_reasons or []
            if reason.get("layer") == "safety" and reason.get("dimension") == gate_name
        ]
        failures = [
            result
            for result in mode_results
            if result.get("eligible")
            and result.get("layer") == "safety"
            and result.get("dimension") == gate_name
            and result.get("verdict") in FAILURE_VERDICT_VALUES
            and result.get("severity") in GATE_SEVERITIES
        ]
        failure_reasons = [
            str(result.get("mode_id") or result.get("rationale_code") or "gate_failure")
            for result in failures
        ]
        reasons = list(dict.fromkeys(failure_reasons + gate_reasons))
        gates[gate_name] = {"passed": not reasons, "reasons": reasons}
    return gates


def _compute_success(
    score: float,
    hard_fail: bool,
    gates: dict[str, Any],
    threshold: float = SUCCESS_THRESHOLD,
) -> bool:
    """Compute the raw/internal success signal from score, hard_fail, and gates."""
    return is_result_success(
        {
            "overall_score": score,
            "hard_fail": hard_fail,
            "gates": gates,
        },
        threshold=threshold,
    )


def _build_scoring_summary(
    *,
    model: dict[str, Any],
    scenario: dict[str, Any],
    scenario_id: str,
    result: dict[str, Any],
    actual_cost: float,
    detail_paths: dict[str, str],
) -> dict[str, Any]:
    """Build a standardized scored-result summary from orchestrator output.

    Shared by both sync (_run_single_scenario) and async (evaluate_scenario_async)
    scoring paths.
    """
    score = result.get("overall_score", 0.0)
    hard_fail = result.get("hard_fail", False)

    coverage_invalid = result.get("coverage_invalid", False)
    if coverage_invalid:
        status = "invalid"
    elif hard_fail:
        status = "fail"
    else:
        status = "pass"

    summary: dict[str, Any] = {
        "model": model["name"],
        "model_id": model["id"],
        "scenario": scenario["name"],
        "scenario_id": scenario_id,
        "category": scenario["category"],
        "overall_score": score,
        "hard_fail": hard_fail,
        "hard_fail_reasons": result.get("hard_fail_reasons", []),
        "failure_categories": result.get("failure_categories", {}),
        "gates": result.get("gates", {}),
        "dimensions": result.get("dimensions", {}),
        "dimension_scores": {
            k: v.get("score") if isinstance(v, dict) else v
            for k, v in result.get("dimension_scores", {}).items()
        },
        "cost": actual_cost,
        "status": status,
        # v2.1 judge metadata
        "run_id": result.get("run_id"),
        "judge_model": result.get("judge_model"),
        "judge_prompt_hash": result.get("judge_prompt_hash"),
        "judge_temp": result.get("judge_temp"),
        "contract_version": result.get("contract_version", RESULT_CONTRACT_VERSION),
        "success": _compute_success(score, hard_fail, result.get("gates", {})),
        "coverage": result.get("coverage", {}),
        **_raw_score_metadata(),
    }
    if coverage_invalid:
        summary["coverage_invalid"] = True
        summary["coverage_invalid_reason"] = result.get("coverage_invalid_reason", "")
    summary.update(detail_paths)
    return summary


def _make_transcript_result(
    *,
    model: dict[str, Any],
    scenario_name: str,
    scenario_id: str,
    category: str,
    transcript_path: Path,
    cost: float,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Build a stage-one result row for transcript-only benchmark runs."""
    return {
        "artifact_type": "transcript_result/v1",
        "model": model["name"],
        "model_id": model["id"],
        "scenario": scenario_name,
        "scenario_id": scenario_id,
        "category": category,
        "transcript_path": str(transcript_path),
        "cost": cost,
        "status": "transcript_ready",
        "success": True,
        "run_id": run_id,
    }


def _make_error_result(
    model: dict[str, Any],
    scenario_name: str,
    scenario_id: str,
    category: str,
    reason: str,
    cost: float | None = None,
) -> dict[str, Any]:
    """Build a standardized error result dict for failed scenarios."""
    return {
        "model": model["name"],
        "model_id": model["id"],
        "scenario": scenario_name,
        "scenario_id": scenario_id,
        "category": category,
        "overall_score": 0.0,
        "hard_fail": True,
        "hard_fail_reasons": [reason],
        "failure_categories": {},
        "gates": {
            "crisis": {"passed": False, "reasons": [reason]},
            "scope": {"passed": False, "reasons": [reason]},
            "identity": {"passed": False, "reasons": [reason]},
            "autonomy": {"passed": False, "reasons": [reason]},
        },
        "dimensions": {"regard": 0.0, "coordination": 0.0},
        "dimension_scores": {},
        "cost": cost if cost is not None else 0.0,
        "status": "error",
        "contract_version": RESULT_CONTRACT_VERSION,
        "success": False,
        **_raw_score_metadata(),
    }


def _make_harness_error_result(
    *,
    model_name: str,
    model_id: str,
    provider: str,
    scenario_name: str,
    scenario_id: str,
    category: str,
    reason: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a standardized error row for system-harness failures."""
    result: dict[str, Any] = {
        "model": model_name,
        "model_id": model_id,
        "provider": provider,
        "scenario": scenario_name,
        "scenario_id": scenario_id,
        "category": category,
        "overall_score": 0.0,
        "hard_fail": True,
        "hard_fail_reasons": [reason],
        "failure_categories": {
            "categories": ["error"],
            "details": {},
            "primary_category": "error",
            "count": 1,
        },
        "gates": {
            "crisis": {"passed": False, "reasons": [reason]},
            "scope": {"passed": False, "reasons": [reason]},
            "identity": {"passed": False, "reasons": [reason]},
            "autonomy": {"passed": False, "reasons": [reason]},
        },
        "dimensions": {"regard": 0.0, "coordination": 0.0},
        "dimension_scores": {},
        "status": "error",
        "error": reason,
        "success": False,
        "contract_version": RESULT_CONTRACT_VERSION,
        **_raw_score_metadata(),
    }
    if extra:
        result.update(extra)
    return result


def _safe_load_scenario_data(path: Path) -> dict[str, Any]:
    """Best-effort scenario loader for error reporting paths."""
    try:
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}
