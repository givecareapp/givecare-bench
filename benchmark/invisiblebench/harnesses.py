"""Eval harness resolution and dispatch helpers.

A harness adapts a target system to the benchmark core.
A mode selects how that harness runs.
"""
from __future__ import annotations

from typing import Optional, Tuple

_PROVIDER_TO_HARNESS = {
    "openrouter": "llm",
    "givecare": "givecare",
}

_DEFAULT_MODE = {
    "llm": "raw",
    "givecare": "live",
}

_MODE_ALIASES = {
    ("llm", "benchmark"): "raw",
    ("llm", "openrouter"): "raw",
}

_ALLOWED_MODES = {
    "llm": {"raw"},
    "givecare": {"live", "integration", "orchestrator"},
}

_IMPLEMENTED_MODES = {
    "llm": {"raw"},
    "givecare": {"live", "orchestrator"},
}


def resolve_harness_mode(
    *,
    harness: Optional[str] = None,
    provider: Optional[str] = None,
    mode: Optional[str] = None,
) -> Tuple[str, str]:
    """Resolve CLI selections into a normalized harness/mode tuple."""
    resolved_harness = harness
    if resolved_harness is None:
        resolved_harness = _PROVIDER_TO_HARNESS.get(provider or "openrouter", "llm")

    if resolved_harness not in _ALLOWED_MODES:
        raise ValueError(f"Unknown harness '{resolved_harness}'")

    resolved_mode = (mode or _DEFAULT_MODE[resolved_harness]).lower()
    resolved_mode = _MODE_ALIASES.get((resolved_harness, resolved_mode), resolved_mode)

    if resolved_mode not in _ALLOWED_MODES[resolved_harness]:
        allowed = ", ".join(sorted(_ALLOWED_MODES[resolved_harness]))
        raise ValueError(
            f"Unsupported mode '{resolved_mode}' for harness '{resolved_harness}'. "
            f"Allowed: {allowed}"
        )

    return resolved_harness, resolved_mode


def is_mode_implemented(harness: str, mode: str) -> bool:
    """Return True if the harness/mode pair is implemented."""
    return mode in _IMPLEMENTED_MODES.get(harness, set())


def adapter_name(harness: str, mode: str) -> str:
    """Return the normalized adapter artifact label."""
    return f"{harness}-{mode}"
