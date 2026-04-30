"""Dimension alias normalization and category helpers."""

from __future__ import annotations

import warnings
from typing import Any, Mapping

V2_DIMENSIONS = [
    "safety",
    "compliance",
    "regard",
    "coordination",
    "false_refusal",
    "memory",
]

DIMENSION_ALIASES = {
    "attunement": "regard",
    "belonging": "regard",
    "consistency": "memory",
}


def _normalize_dimension_key(raw_key: Any, *, warn: bool = True) -> str | None:
    if not isinstance(raw_key, str):
        return None
    normalized = raw_key.strip().lower()
    if not normalized:
        return None
    canonical = DIMENSION_ALIASES.get(normalized)
    if canonical is not None and warn:
        warnings.warn(
            f"Dimension name '{normalized}' is deprecated, use '{canonical}' instead.",
            DeprecationWarning,
            stacklevel=3,
        )
        return canonical
    return canonical if canonical is not None else normalized


def normalize_dimension_scores(raw_scores: Mapping[str, Any] | None) -> dict[str, Any]:
    """Normalize aliased dimension keys to canonical names."""
    normalized: dict[str, Any] = {}
    if not isinstance(raw_scores, Mapping):
        return normalized

    for key, value in raw_scores.items():
        canonical = _normalize_dimension_key(key)
        if canonical is None:
            continue
        if canonical not in normalized:
            normalized[canonical] = value

    return normalized


def extract_numeric_dimension_value(value: Any) -> float | None:
    """Extract numeric score from either scalar or score-dict payload."""
    if isinstance(value, dict):
        value = value.get("score")
    if isinstance(value, (int, float)):
        return float(value)
    return None


def normalize_category(value: Any) -> str:
    """Normalize category string values."""
    if isinstance(value, str) and value.strip():
        return value.strip().lower()

    return "unknown"

