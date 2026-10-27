"""Lint turn index fields."""

from __future__ import annotations

from typing import Any


def lint_turn_indices(scenario: dict[str, Any]) -> list[str]:
    """Return warnings for mixed or inconsistent turn index usage."""
    warnings: list[str] = []
    warnings.extend(_lint_list(scenario.get("turns", []), "turns"))
    warnings.extend(_lint_list(scenario.get("probes", []), "probes"))
    for idx, turn in enumerate(scenario.get("turns", [])):
        warnings.extend(_lint_list(turn.get("probes", []), f"turns[{idx}].probes"))

    for idx, session in enumerate(scenario.get("sessions", [])):
        warnings.extend(_lint_list(session.get("turns", []), f"sessions[{idx}].turns"))
        for turn_idx, turn in enumerate(session.get("turns", [])):
            warnings.extend(
                _lint_list(turn.get("probes", []), f"sessions[{idx}].turns[{turn_idx}].probes")
            )

    return warnings


def _lint_list(items: list[Any], label: str) -> list[str]:
    warnings: list[str] = []
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
