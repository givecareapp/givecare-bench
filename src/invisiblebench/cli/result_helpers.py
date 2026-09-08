"""Helpers for transcript-run result rows."""
from __future__ import annotations

from pathlib import Path
from typing import Any


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
    """Build a transcript-stage error row.

    This row records a harness failure. It is not a model judgment and must
    not use score or hard-fail fields.
    """
    return {
        "artifact_type": "transcript_result/v1",
        "model": model["name"],
        "model_id": model["id"],
        "scenario": scenario_name,
        "scenario_id": scenario_id,
        "category": category,
        "cost": cost if cost is not None else 0.0,
        "status": "error",
        "error": reason,
        "success": False,
    }
