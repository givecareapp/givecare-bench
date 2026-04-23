"""Retry, atomic writes, and error recovery."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)



def load_state(state_path: "Path | str") -> dict[str, Any]:
    """Load and validate state from JSON file."""
    state_path = Path(state_path)

    if not state_path.exists():
        raise FileNotFoundError(
            f"Resume state file not found: {state_path}. " "Cannot resume from non-existent state."
        )

    try:
        with open(state_path) as f:
            state = json.load(f)

        if not isinstance(state, dict):
            raise ValueError("State must be a dictionary")

        required_fields = ["status", "dimension_scores"]
        missing = [f for f in required_fields if f not in state]
        if missing:
            raise ValueError(f"State missing required fields: {missing}")

        logger.info(f"Loaded state from {state_path}")
        return state

    except json.JSONDecodeError as e:
        raise ValueError(
            f"Corrupted state file (invalid JSON): {state_path}. "
            f"Error: {e}. Cannot resume from corrupted state."
        ) from e
    except OSError as e:
        raise ValueError(f"Failed to load state from {state_path}: {e}") from e



def create_error_result(error: Exception, dimension: str) -> dict[str, Any]:
    """Standardized error result for a failed scorer."""
    return {
        "status": "error",
        "error": f"{type(error).__name__}: {str(error)}",
        "score": 0.0,
        "breakdown": {},
        "evidence": [],
    }


def determine_overall_status(dimension_scores: dict[str, Any]) -> str:
    """Overall status from dimension statuses."""
    statuses = [dim.get("status") for dim in dimension_scores.values()]

    error_count = statuses.count("error")
    total_count = len(statuses)

    if error_count == total_count:
        return "error"
    elif error_count > 0:
        return "completed_with_errors"
    else:
        return "completed"


def format_error_summary(dimension_scores: dict[str, Any]) -> str:
    """Format error summary for logging."""
    errors = []
    for dim, dim_data in dimension_scores.items():
        if dim_data.get("status") == "error":
            error_msg = dim_data.get("error", "Unknown error")
            errors.append(f"  - {dim}: {error_msg}")

    if not errors:
        return "No errors"

    return "Errors encountered:\n" + "\n".join(errors)
