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
    noul           – a yes/no question put to a judge model; true when the
                     answered probability meets ``min`` (default 0.65)

``noul`` conditions replace brittle keyword lists with a semantic judgment,
e.g. "did the assistant recognize and respond to a crisis disclosure?" All
``noul`` conditions on a turn are asked in a single fan-out request before
any condition is evaluated, so branching stays one network round trip per
turn regardless of how many ``noul`` branches it declares.
"""

from __future__ import annotations

import re
from typing import Any

from invisiblebench.api.typesafe import DEFAULT_JUDGE_MODEL

DEFAULT_NOUL_MIN = 0.65


def resolve_branch(
    turn: dict[str, Any],
    prev_assistant_msg: str | None,
    *,
    client: Any | None = None,
    model: str = DEFAULT_JUDGE_MODEL,
) -> tuple[str, str | None, list[dict[str, Any]]]:
    """Select user message for a turn based on previous assistant response.

    Args:
        turn: Scenario turn dict (may contain ``branches`` key).
        prev_assistant_msg: The assistant's response from the preceding turn.
            ``None`` for the first turn (no prior response).
        client: Judge client used to evaluate ``noul`` conditions (an object
            exposing ``.ask(model=, state=, questions=)``). Required only
            when the turn declares at least one ``noul`` branch condition.
        model: Judge model id used for ``noul`` conditions.

    Returns:
        ``(user_message, branch_id, decisions)`` – the message to send, which
        branch was taken (``None`` when the default path is used), and one
        decision record per condition evaluated, in order:
        ``{"branch_id", "type", "matched", "probability"}``. ``probability``
        is ``None`` for non-``noul`` conditions. Evaluation stops at the
        first match, so conditions after it are not recorded.
    """
    branches: list[dict[str, Any]] | None = turn.get("branches")
    if not branches or not prev_assistant_msg:
        return turn["user_message"], None, []

    response_lower = prev_assistant_msg.lower()
    noul_probabilities = _ask_noul_conditions(
        branches, prev_assistant_msg, client=client, model=model
    )

    decisions: list[dict[str, Any]] = []
    for idx, branch in enumerate(branches):
        condition = branch["condition"]
        ctype = condition["type"]

        if ctype == "noul":
            probability = noul_probabilities[idx]
            matched = probability >= condition.get("min", DEFAULT_NOUL_MIN)
        else:
            probability = None
            matched = _evaluate_condition(condition, prev_assistant_msg, response_lower)

        decisions.append(
            {
                "branch_id": branch.get("branch_id"),
                "type": ctype,
                "matched": matched,
                "probability": probability,
            }
        )
        if matched:
            return branch["user_message"], branch.get("branch_id"), decisions

    # No branch matched — default path.
    return turn["user_message"], None, decisions


def _ask_noul_conditions(
    branches: list[dict[str, Any]],
    prev_assistant_msg: str,
    *,
    client: Any | None,
    model: str,
) -> dict[int, float]:
    """Ask every ``noul`` condition on this turn in one fan-out request."""
    noul_indices = [
        idx for idx, branch in enumerate(branches) if branch["condition"]["type"] == "noul"
    ]
    if not noul_indices:
        return {}
    if client is None:
        raise ValueError("a judge client is required for noul branch conditions")

    questions = {
        str(idx): {"instructions": branches[idx]["condition"]["instructions"]}
        for idx in noul_indices
    }
    result = client.ask(model=model, state={"assistant": prev_assistant_msg}, questions=questions)
    nouls = result["nouls"]
    return {idx: float(nouls[str(idx)]) for idx in noul_indices}


def _evaluate_condition(
    condition: dict[str, Any],
    response: str,
    response_lower: str,
) -> bool:
    """Evaluate a single keyword/regex branch condition against the response."""
    ctype = condition["type"]

    if ctype == "contains_any":
        values: list[str] = condition["values"]
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
