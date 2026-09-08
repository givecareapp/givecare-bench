"""Deterministic Safety/Care projection for the public leaderboard.

The projection is a view of the retained judge ledger.  It contains separate
Safety and Care observations, keeps uncertainty counts, and has no composite,
rank, calibration, or clinical-validity claim.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from invisiblebench.evaluation.check_registry import check_dimensions
from invisiblebench.scoring.care import CARE_DIMENSIONS, model_care_distribution, scenario_care
from invisiblebench.scoring.safety import SAFETY_DIMENSIONS, model_safety_rates, scenario_safety
from invisiblebench.utils.io import load_jsonl

SCHEMA_VERSION = "safety-care/v2"
OBSERVATION_TYPE = "MODEL-JUDGED"
_SAFETY_LINES = SAFETY_DIMENSIONS
_CARE_QUALITIES_V2 = CARE_DIMENSIONS


def _group_rows(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        model = str(row.get("model") or "")
        model_id = str(row.get("model_id") or model)
        if not model:
            raise ValueError("scan row is missing model")
        grouped[(model_id, model)].append(row)
    return dict(grouped)


def _dimension_map() -> dict[str, dict[str, str]]:
    return check_dimensions()


def _model_entry(
    model_id: str,
    model: str,
    rows: list[dict[str, Any]],
    dimensions: dict[str, dict[str, str]],
) -> dict[str, Any]:
    safety = model_safety_rates(
        [scenario_safety(row.get("mode_results") or [], dimensions) for row in rows]
    )
    care = model_care_distribution(
        [scenario_care(row.get("mode_results") or [], dimensions) for row in rows]
    )

    # The fixed roster makes a missing check visible as an empty observation.
    safety_lines = {dimension: dict(safety[dimension]) for dimension in _SAFETY_LINES}
    qualities = {dimension: dict(care[dimension]) for dimension in _CARE_QUALITIES_V2}
    return {
        "model": model,
        "model_id": model_id,
        "observation_type": OBSERVATION_TYPE,
        "scenario_count": len(rows),
        "safety": {
            "observation_type": OBSERVATION_TYPE,
            "lines": safety_lines,
        },
        "care": {
            "observation_type": OBSERVATION_TYPE,
            "qualities": qualities,
        },
    }


def build_scorecard(scan_path: str | Path) -> dict[str, Any]:
    """Build the current ``safety-care/v2`` projection from scan JSONL."""

    path = Path(scan_path)
    if not path.is_file():
        raise FileNotFoundError(f"scan file not found: {path}")
    rows = load_jsonl(path)
    if not rows:
        raise ValueError(f"scan file is empty: {path}")
    dimensions = _dimension_map()
    models = [
        _model_entry(model_id, model, model_rows, dimensions)
        for (model_id, model), model_rows in sorted(_group_rows(rows).items())
    ]
    return {
        "schema": SCHEMA_VERSION,
        "models": models,
        "notes": {
            "observation_type": OBSERVATION_TYPE,
            "uncertainty": "UNCLEAR is retained and included in every eligible denominator.",
            "care": "Care qualities are directional observations and are not combined.",
            "safety": "Safety dimensions are reported separately and are not combined.",
        },
    }


__all__ = [
    "OBSERVATION_TYPE",
    "SCHEMA_VERSION",
    "_CARE_QUALITIES_V2",
    "_SAFETY_LINES",
    "build_scorecard",
]
