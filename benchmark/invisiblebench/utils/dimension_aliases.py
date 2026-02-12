"""Shared dimension/categorization helpers for v2 reporting and scoring."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional


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


def _normalize_dimension_key(raw_key: Any) -> Optional[str]:
    if not isinstance(raw_key, str):
        return None
    normalized = raw_key.strip().lower()
    if not normalized:
        return None
    return DIMENSION_ALIASES.get(normalized, normalized)


def normalize_dimension_scores(raw_scores: Mapping[str, Any] | None) -> Dict[str, Any]:
    """Normalize legacy dimension keys to v2 canonical names."""
    normalized: Dict[str, Any] = {}
    if not isinstance(raw_scores, Mapping):
        return normalized

    for key, value in raw_scores.items():
        canonical = _normalize_dimension_key(key)
        if canonical is None:
            continue
        if canonical not in normalized:
            normalized[canonical] = value

    return normalized


def extract_numeric_dimension_value(value: Any) -> Optional[float]:
    """Extract numeric score from either scalar or score-dict payload."""
    if isinstance(value, dict):
        value = value.get("score")
    if isinstance(value, (int, float)):
        return float(value)
    return None


def normalize_category(value: Any) -> str:
    """Normalize category values with legacy tier fallback."""
    if isinstance(value, str) and value.strip():
        normalized = value.strip().lower()
        return {
            "context": "context",
            "continuity": "continuity",
        }.get(normalized, normalized)

    if isinstance(value, int):
        return {
            0: "safety",
            1: "safety",
            2: "empathy",
            3: "continuity",
        }.get(value, "unknown")

    return "unknown"

