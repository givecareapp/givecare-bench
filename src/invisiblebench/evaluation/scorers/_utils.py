"""Shared utilities for evaluation scorers.

Internal module — import from here, not from individual scorer files.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Bool coercion (shared by rubric_scorer and orchestrator)
# ---------------------------------------------------------------------------

_TRUE_VALUES = {"true", "yes", "1"}
_FALSE_VALUES = {"false", "no", "0"}


def coerce_bool(value: Any) -> Optional[bool]:
    """Coerce a loosely-typed value to bool, or return None if unrecognised."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if value == 1:
            return True
        if value == 0:
            return False
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _TRUE_VALUES:
            return True
        if normalized in _FALSE_VALUES:
            return False
    return None


# ---------------------------------------------------------------------------
# Stopwords (shared by rubric_scorer and regard)
# ---------------------------------------------------------------------------

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "did", "does",
    "for", "from", "had", "has", "have", "i", "if", "in", "is", "it", "its",
    "me", "model", "my", "no", "not", "of", "on", "or", "our", "so", "that",
    "the", "their", "they", "this", "to", "was", "we", "with", "you", "your",
}


# ---------------------------------------------------------------------------
# Scenario traversal helpers (shared by rubric_scorer and false_refusal)
# ---------------------------------------------------------------------------


def all_turns(scenario: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return all turn dicts from a scenario (flat or multi-session)."""
    turns: List[Dict[str, Any]] = []
    turns.extend(scenario.get("turns", []))
    for session in scenario.get("sessions", []):
        turns.extend(session.get("turns", []))
    return turns


# ---------------------------------------------------------------------------
# Transcript helpers (shared by coordination, false_refusal, memory, etc.)
# ---------------------------------------------------------------------------


def assistant_text_by_turn(transcript: List[Dict[str, Any]]) -> Dict[int, str]:
    """Return concatenated assistant content keyed by turn number."""
    by_turn: Dict[int, List[str]] = {}
    for msg in transcript:
        if msg.get("role") != "assistant":
            continue
        turn = msg.get("turn")
        if not isinstance(turn, int):
            continue
        by_turn.setdefault(turn, []).append(str(msg.get("content", "")).strip())
    return {t: "\n".join(p for p in parts if p) for t, parts in by_turn.items()}


def user_text_by_turn(transcript: List[Dict[str, Any]]) -> Dict[int, str]:
    """Return concatenated user content keyed by turn number."""
    by_turn: Dict[int, List[str]] = {}
    for msg in transcript:
        if msg.get("role") != "user":
            continue
        turn = msg.get("turn")
        if not isinstance(turn, int):
            continue
        by_turn.setdefault(turn, []).append(str(msg.get("content", "")).strip())
    return {t: "\n".join(p for p in parts if p) for t, parts in by_turn.items()}


def get_assistant_response_at_turn(transcript: List[Dict[str, Any]], turn: int) -> str:
    """Return first assistant response at an exact turn, or empty string."""
    for msg in transcript:
        if msg.get("role") == "assistant" and msg.get("turn") == turn:
            return str(msg.get("content", ""))
    return ""


def format_conversation(transcript: List[Dict[str, Any]]) -> str:
    """Format transcript into a labelled conversation string for LLM prompts."""
    return "\n\n".join([
        f"Turn {m['turn']} ({'User' if m['role'] == 'user' else 'AI'}):\n{m['content']}"
        for m in sorted(transcript, key=lambda x: (x["turn"], 0 if x["role"] == "user" else 1))
    ])


# ---------------------------------------------------------------------------
# Text helpers (shared by rubric_scorer and regard)
# ---------------------------------------------------------------------------


def question_keywords(question: str) -> List[str]:
    """Extract meaningful keywords from a rubric question."""
    tokens = re.findall(r"[a-zA-Z]{3,}", question.lower())
    words = [t for t in tokens if t not in STOPWORDS]
    return list(dict.fromkeys(words))


def quote_snippet(text: str, max_len: int = 160) -> str:
    """Return a truncated single-line snippet of text."""
    snippet = " ".join(text.split())
    if len(snippet) <= max_len:
        return snippet
    return snippet[: max_len - 3] + "..."


# ---------------------------------------------------------------------------
# LLM free-text response parsers (shared by regard and coordination)
# ---------------------------------------------------------------------------


def parse_score_value(line: str, default: float = 0.0) -> float:
    """Parse score from 'DIMENSION: 8' (1-10 scale) or 'DIMENSION: 0.8' (0-1 scale).

    Normalizes 1-10 integer scores to 0.0-1.0 range.
    """
    try:
        raw = float(line.split(":")[1].strip())
        if raw > 1.0:
            return max(0.0, min(1.0, (raw - 1.0) / 9.0))
        return raw
    except (ValueError, IndexError):
        return default


def parse_penalty_value(line: str) -> float:
    """Parse penalty from '-0.3 x 2' or '-0.6'."""
    try:
        val_str = line.split(":")[1].strip()
        if "x" in val_str:
            parts = val_str.split("x")
            return float(parts[0].strip()) * float(parts[1].strip())
        return float(val_str)
    except (ValueError, IndexError):
        return 0.0

