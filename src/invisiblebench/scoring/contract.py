"""Small, shared predicates for the current LLM judgment contract.

The benchmark has one verdict vocabulary.  This module deliberately contains
no calibration, gate, claim, or composite-score policy.
"""

from __future__ import annotations

from typing import Any

CANONICAL_VERDICTS = frozenset({"PASS", "FAIL", "UNCLEAR", "NOT_APPLICABLE"})
PASS_VERDICT = "PASS"
FAIL_VERDICT = "FAIL"
UNCLEAR_VERDICT = "UNCLEAR"
NOT_APPLICABLE_VERDICT = "NOT_APPLICABLE"


def verdict_value(value: Any) -> str:
    """Return a serialized verdict value without accepting retired aliases."""

    raw = getattr(value, "value", value)
    return str(raw or "")


def dimensions_from_checks(checks: dict[str, dict[str, Any]]) -> dict[str, dict[str, str]]:
    """Build the dimension index used by the pure scoring functions."""

    return {
        str(check_id): {
            "layer": mode["layer"],
            "dimension": mode["dimension"],
        }
        for check_id, mode in checks.items()
    }


__all__ = [
    "CANONICAL_VERDICTS",
    "FAIL_VERDICT",
    "NOT_APPLICABLE_VERDICT",
    "PASS_VERDICT",
    "UNCLEAR_VERDICT",
    "dimensions_from_checks",
    "verdict_value",
]
