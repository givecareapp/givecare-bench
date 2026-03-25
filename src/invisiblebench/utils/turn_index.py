"""Utilities for normalizing and linting turn index fields."""

from __future__ import annotations

from typing import Any, Dict, List


def get_turn_index(item: Dict[str, Any]) -> int | None:
    """Return the turn index from common field names."""
    for key in ("t", "turn_number", "turn"):
        value = item.get(key)
        if value is not None:
            return value
    return None


def normalize_turn_indices(scenario: Dict[str, Any]) -> List[str]:
    """Normalize turn indices in-place to ensure `t` exists."""
    warnings: List[str] = []
    _normalize_list(scenario.get("turns", []), warnings, "turns")
    _normalize_list(scenario.get("probes", []), warnings, "probes")
    _normalize_list(scenario.get("risk_triggers", []), warnings, "risk_triggers")
    for idx, turn in enumerate(scenario.get("turns", [])):
        _normalize_list(turn.get("probes", []), warnings, f"turns[{idx}].probes")

    for idx, session in enumerate(scenario.get("sessions", [])):
        _normalize_list(session.get("turns", []), warnings, f"sessions[{idx}].turns")
        for turn_idx, turn in enumerate(session.get("turns", [])):
            _normalize_list(
                turn.get("probes", []), warnings, f"sessions[{idx}].turns[{turn_idx}].probes"
            )

    return warnings


def lint_turn_indices(scenario: Dict[str, Any]) -> List[str]:
    """Return warnings for mixed or inconsistent turn index usage."""
    warnings: List[str] = []
    warnings.extend(_lint_list(scenario.get("turns", []), "turns"))
    warnings.extend(_lint_list(scenario.get("probes", []), "probes"))
    warnings.extend(_lint_list(scenario.get("risk_triggers", []), "risk_triggers"))
    for idx, turn in enumerate(scenario.get("turns", [])):
        warnings.extend(_lint_list(turn.get("probes", []), f"turns[{idx}].probes"))

    for idx, session in enumerate(scenario.get("sessions", [])):
        warnings.extend(_lint_list(session.get("turns", []), f"sessions[{idx}].turns"))
        for turn_idx, turn in enumerate(session.get("turns", [])):
            warnings.extend(
                _lint_list(turn.get("probes", []), f"sessions[{idx}].turns[{turn_idx}].probes")
            )

    return warnings


def _normalize_list(items: List[Any], warnings: List[str], label: str) -> None:
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        t_value = item.get("t")
        turn_number = item.get("turn_number")
        turn_value = item.get("turn")

        if t_value is None:
            if turn_number is not None:
                item["t"] = turn_number
            elif turn_value is not None:
                item["t"] = turn_value
        elif turn_number is not None and t_value != turn_number:
            warnings.append(f"{label}[{idx}] t={t_value} != turn_number={turn_number}")


def _lint_list(items: List[Any], label: str) -> List[str]:
    warnings: List[str] = []
    has_t_only = False
    has_turn_only = False

    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        has_t = "t" in item
        has_turn = "turn_number" in item
        if has_t and not has_turn:
            has_t_only = True
        if has_turn and not has_t:
            has_turn_only = True
        if has_t and has_turn and item.get("t") != item.get("turn_number"):
            warnings.append(
                f"{label}[{idx}] t={item.get('t')} != turn_number={item.get('turn_number')}"
            )

    if has_t_only and has_turn_only:
        warnings.append(f"{label} uses mixed t and turn_number fields")

    return warnings
