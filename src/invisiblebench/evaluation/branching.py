"""Conditional branching for adaptive multi-turn scenarios.

Evaluates branch conditions against the previous assistant response to select
the next user message. This enables adaptive conversations where the user's
behavior depends on how the model responded.

Branch conditions are evaluated in order; the first match wins.
If no branch matches, the turn's default ``user_message`` is used.

Condition types:
    contains_any   – any keyword present (case-insensitive)
    contains_all   – all keywords present (case-insensitive)
    not_contains   – none of the keywords present (case-insensitive)
    regex          – regex search against response (case-insensitive)
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


def resolve_branch(
    turn: Dict[str, Any],
    prev_assistant_msg: Optional[str],
) -> Tuple[str, Optional[str]]:
    """Select user message for a turn based on previous assistant response.

    Args:
        turn: Scenario turn dict (may contain ``branches`` key).
        prev_assistant_msg: The assistant's response from the preceding turn.
            ``None`` for the first turn (no prior response).

    Returns:
        ``(user_message, branch_id)`` – the message to send and which branch
        was taken (``None`` when the default path is used).
    """
    branches: Optional[List[Dict[str, Any]]] = turn.get("branches")
    if not branches or not prev_assistant_msg:
        return turn["user_message"], None

    response_lower = prev_assistant_msg.lower()

    for branch in branches:
        condition = branch["condition"]
        if _evaluate_condition(condition, prev_assistant_msg, response_lower):
            return branch["user_message"], branch.get("branch_id")

    # No branch matched — default path.
    return turn["user_message"], None


def _evaluate_condition(
    condition: Dict[str, Any],
    response: str,
    response_lower: str,
) -> bool:
    """Evaluate a single branch condition against the assistant response."""
    ctype = condition["type"]

    if ctype == "contains_any":
        values: List[str] = condition["values"]
        return any(v.lower() in response_lower for v in values)

    if ctype == "contains_all":
        values = condition["values"]
        return all(v.lower() in response_lower for v in values)

    if ctype == "not_contains":
        values = condition["values"]
        return not any(v.lower() in response_lower for v in values)

    if ctype == "regex":
        pattern: str = condition["pattern"]
        return bool(re.search(pattern, response, re.IGNORECASE))

    raise ValueError(f"Unknown branch condition type: {ctype!r}")
