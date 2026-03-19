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
    llm_judge      – LLM yes/no semantic check against response
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel

from invisiblebench.evaluation.scorers.rubric_scorer import _evaluate_with_llm

logger = logging.getLogger(__name__)


class BranchDecision(BaseModel):
    """Structured branch-condition result."""

    triggered: bool
    confidence: float
    evidence: str


def get_branch_resolution(turn: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return the most recent branch-resolution metadata for a turn."""
    resolution = turn.get("_branch_resolution")
    if not isinstance(resolution, dict):
        return None
    return resolution


def resolve_branch(
    turn: Dict[str, Any],
    prev_assistant_msg: Optional[str],
    api_client: Optional[Any] = None,
    model: Optional[str] = None,
) -> Tuple[str, Optional[str], str]:
    """Select user message for a turn based on previous assistant response.

    Args:
        turn: Scenario turn dict (may contain ``branches`` key).
        prev_assistant_msg: The assistant's response from the preceding turn.
            ``None`` for the first turn (no prior response).
        api_client: Optional client for LLM-based branch resolution.
        model: Optional model override for LLM-based branch resolution.

    Returns:
        ``(user_message, branch_id, method)`` – the message to send, which
        branch was taken (``None`` when the default path is used), and the
        branch-resolution method.
    """
    branches: Optional[List[Dict[str, Any]]] = turn.get("branches")
    if not branches or not prev_assistant_msg:
        turn.pop("_branch_resolution", None)
        return turn["user_message"], None, "default"

    response_lower = prev_assistant_msg.lower()
    last_method = "lexical"
    last_decision = BranchDecision(
        triggered=False,
        confidence=1.0,
        evidence="No branch conditions matched; using default path.",
    )

    for branch in branches:
        condition = branch["condition"]
        method = "llm_judge" if condition.get("type") == "llm_judge" else "lexical"
        decision = _evaluate_condition(
            condition=condition,
            response=prev_assistant_msg,
            response_lower=response_lower,
            api_client=api_client,
            model=model,
        )
        last_method = method
        last_decision = decision
        if decision.triggered:
            _record_branch_resolution(
                turn=turn,
                branch_id=branch.get("branch_id"),
                method=method,
                decision=decision,
            )
            return branch["user_message"], branch.get("branch_id"), method

    # No branch matched — default path.
    _record_branch_resolution(
        turn=turn,
        branch_id=None,
        method=last_method,
        decision=last_decision,
    )
    return turn["user_message"], None, last_method


def _evaluate_condition(
    condition: Dict[str, Any],
    response: str,
    response_lower: str,
    api_client: Optional[Any],
    model: Optional[str],
) -> BranchDecision:
    """Evaluate a single branch condition against the assistant response."""
    ctype = condition["type"]

    if ctype == "contains_any":
        values: List[str] = condition["values"]
        for value in values:
            if value.lower() in response_lower:
                return BranchDecision(
                    triggered=True,
                    confidence=1.0,
                    evidence=f"Matched keyword {value!r}.",
                )
        return BranchDecision(
            triggered=False,
            confidence=1.0,
            evidence=f"No keywords matched: {', '.join(repr(v) for v in values)}.",
        )

    if ctype == "contains_all":
        values = condition["values"]
        missing = [value for value in values if value.lower() not in response_lower]
        if not missing:
            return BranchDecision(
                triggered=True,
                confidence=1.0,
                evidence=f"Matched all keywords: {', '.join(repr(v) for v in values)}.",
            )
        return BranchDecision(
            triggered=False,
            confidence=1.0,
            evidence=f"Missing keywords: {', '.join(repr(v) for v in missing)}.",
        )

    if ctype == "not_contains":
        values = condition["values"]
        for value in values:
            if value.lower() in response_lower:
                return BranchDecision(
                    triggered=False,
                    confidence=1.0,
                    evidence=f"Found excluded keyword {value!r}.",
                )
        return BranchDecision(
            triggered=True,
            confidence=1.0,
            evidence=f"None of the excluded keywords appeared: {', '.join(repr(v) for v in values)}.",
        )

    if ctype == "regex":
        pattern: str = condition["pattern"]
        match = re.search(pattern, response, re.IGNORECASE)
        if match:
            return BranchDecision(
                triggered=True,
                confidence=1.0,
                evidence=f"Regex matched {match.group(0)!r}.",
            )
        return BranchDecision(
            triggered=False,
            confidence=1.0,
            evidence=f"Regex did not match pattern {pattern!r}.",
        )

    if ctype == "llm_judge":
        return _evaluate_llm_condition(
            condition=condition,
            response=response,
            api_client=api_client,
            model=model,
        )

    raise ValueError(f"Unknown branch condition type: {ctype!r}")


def _evaluate_llm_condition(
    condition: Dict[str, Any],
    response: str,
    api_client: Optional[Any],
    model: Optional[str],
) -> BranchDecision:
    """Evaluate a semantic branch condition with the rubric judge."""
    if api_client is None:
        return BranchDecision(
            triggered=False,
            confidence=0.0,
            evidence="LLM judge unavailable; using default path.",
        )

    prompt = str(condition.get("prompt", "")).strip()
    expected = bool(condition.get("expected"))

    llm_result = _evaluate_with_llm(
        item={"id": "branch_llm_judge", "question": prompt},
        user_text="",
        assistant_text=response,
        turn_index=None,
        api_client=api_client,
        model=model,
    )

    if llm_result is None:
        logger.warning("Branch LLM judge failed; using default path.")
        return BranchDecision(
            triggered=False,
            confidence=0.0,
            evidence="LLM judge failed; using default path.",
        )

    answer = bool(llm_result["answer"])
    evidence = str(llm_result["evidence"]).strip() or "No evidence provided by judge."
    if answer != expected:
        evidence = f"Judge answer {answer} did not match expected {expected}. {evidence}"

    return BranchDecision(
        triggered=(answer == expected),
        confidence=float(llm_result["confidence"]),
        evidence=evidence,
    )


def _record_branch_resolution(
    turn: Dict[str, Any],
    branch_id: Optional[str],
    method: str,
    decision: BranchDecision,
) -> None:
    turn["_branch_resolution"] = {
        "branch_id": branch_id,
        "method": method,
        "triggered": decision.triggered,
        "confidence": decision.confidence,
        "evidence": decision.evidence,
    }
