"""One iterator for flat and multi-session scenario turns."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any


def iter_scenario_turns(
    scenario: dict[str, Any],
) -> Iterator[tuple[dict[str, Any], dict[str, Any] | None]]:
    """Yield each turn with its session metadata, when present."""
    sessions = scenario.get("sessions")
    if not sessions:
        for turn in scenario.get("turns", []):
            yield turn, None
        return

    for session in sessions:
        metadata = {
            key: session[key]
            for key in ("session_number", "time_elapsed", "session_context")
            if session.get(key) is not None
        }
        for turn in session.get("turns", []):
            yield turn, metadata


def session_system_prompt(base_prompt: str, session: dict[str, Any] | None) -> str:
    """Add an explicit authored session boundary to the model instructions."""
    if not session:
        return base_prompt
    details = [
        f"Session {session.get('session_number', '?')}",
        str(session.get("time_elapsed") or "elapsed time unspecified"),
    ]
    if session.get("session_context"):
        details.append(str(session["session_context"]))
    return f"{base_prompt}\n\nCurrent scripted session: {' — '.join(details)}"
