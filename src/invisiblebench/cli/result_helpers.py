"""Result-building helpers for benchmark run artifacts."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
