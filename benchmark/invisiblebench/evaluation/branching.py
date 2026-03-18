"""Conditional branching for adaptive multi-turn scenarios.

Evaluates branch conditions against the previous assistant response to select
the next user message. This enables adaptive conversations where the user's
behavior depends on how the model responded.

Branch conditions are evaluated in order; the first match wins.
If no branch matches, the turn's default ``user_message`` is used.

Condition types:
    contains_any   - any keyword present (case-insensitive)
    contains_all   - all keywords present (case-insensitive)
    not_contains   - none of the keywords present (case-insensitive)
    regex          - regex search against response (case-insensitive)
    llm_judge      - semantic yes/no judge against response
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel

from invisiblebench.api import ModelAPIClient, resolve_scorer_model
from invisiblebench.evaluation.scorers.rubric_scorer import _parse_judge_json
from invisiblebench.utils.llm_mode import llm_enabled

logger = logging.getLogger(__name__)


class BranchDecision(BaseModel):
    """Normalized branch decision for lexical and LLM-based conditions."""

    triggered: bool
    confidence: float
    evidence: str


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
        api_client: Optional API client used for ``llm_judge`` branch evaluation.
        model: Optional judge model override for ``llm_judge`` conditions.

    Returns:
        ``(user_message, branch_id, method)`` - the message to send, which
        branch was taken (``None`` when the default path is used), and the
        method used for the last evaluated branch condition.
    """
    turn.pop("_branch_decision", None)
    branches: Optional[List[Dict[str, Any]]] = turn.get("branches")
    if not branches or not prev_assistant_msg:
        return turn["user_message"], None, "default"

    response_lower = prev_assistant_msg.lower()
    last_method = "default"
    last_decision: Optional[BranchDecision] = None

    for branch in branches:
        condition = branch["condition"]
        method, decision = _evaluate_condition(
            condition=condition,
            response=prev_assistant_msg,
            response_lower=response_lower,
            api_client=api_client,
            model=model,
        )
        last_method = method
        last_decision = decision

        if decision.triggered:
            turn["_branch_decision"] = {
                "method": method,
                "confidence": decision.confidence,
                "evidence": decision.evidence,
                "triggered": True,
            }
            return branch["user_message"], branch.get("branch_id"), method

    if last_decision is not None:
        turn["_branch_decision"] = {
            "method": last_method,
            "confidence": last_decision.confidence,
            "evidence": last_decision.evidence,
            "triggered": False,
        }
    return turn["user_message"], None, last_method


def _evaluate_condition(
    condition: Dict[str, Any],
    response: str,
    response_lower: str,
    api_client: Optional[Any] = None,
    model: Optional[str] = None,
) -> Tuple[str, BranchDecision]:
    """Evaluate a single branch condition against the assistant response."""
    ctype = condition["type"]

    if ctype == "contains_any":
        values: List[str] = condition["values"]
        matched = next((value for value in values if value.lower() in response_lower), None)
        if matched is not None:
            return "lexical", BranchDecision(
                triggered=True,
                confidence=1.0,
                evidence=f"Matched keyword: {matched}",
            )
        return "lexical", BranchDecision(
            triggered=False,
            confidence=1.0,
            evidence=f"No keyword match in response for values: {', '.join(values)}",
        )

    if ctype == "contains_all":
        values = condition["values"]
        missing = [value for value in values if value.lower() not in response_lower]
        if not missing:
            return "lexical", BranchDecision(
                triggered=True,
                confidence=1.0,
                evidence=f"Matched all keywords: {', '.join(values)}",
            )
        return "lexical", BranchDecision(
            triggered=False,
            confidence=1.0,
            evidence=f"Missing keywords: {', '.join(missing)}",
        )

    if ctype == "not_contains":
        values = condition["values"]
        present = [value for value in values if value.lower() in response_lower]
        if not present:
            return "lexical", BranchDecision(
                triggered=True,
                confidence=1.0,
                evidence=f"No forbidden keywords matched: {', '.join(values)}",
            )
        return "lexical", BranchDecision(
            triggered=False,
            confidence=1.0,
            evidence=f"Found forbidden keywords: {', '.join(present)}",
        )

    if ctype == "regex":
        pattern: str = condition["pattern"]
        match = re.search(pattern, response, re.IGNORECASE)
        if match:
            return "lexical", BranchDecision(
                triggered=True,
                confidence=1.0,
                evidence=f"Regex matched: {match.group(0)}",
            )
        return "lexical", BranchDecision(
            triggered=False,
            confidence=1.0,
            evidence=f"Regex did not match pattern: {pattern}",
        )

    if ctype == "llm_judge":
        return "llm_judge", _evaluate_llm_condition(
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
    """Resolve a branch semantically using the scorer LLM judge infrastructure."""
    if not llm_enabled(True):
        return BranchDecision(
            triggered=False,
            confidence=0.0,
            evidence="LLM judge disabled; using default path.",
        )

    try:
        client = api_client or ModelAPIClient()
    except ValueError as exc:
        logger.debug("Branch LLM judge unavailable: %s", exc)
        return BranchDecision(
            triggered=False,
            confidence=0.0,
            evidence=f"LLM judge unavailable: {exc}",
        )

    model_name = model or resolve_scorer_model(client, "branching")
    prompt = _build_llm_branch_prompt(
        question=str(condition["prompt"]).strip(),
        assistant_text=response,
    )

    try:
        result = client.call_model(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=300,
            use_cache=True,
        )
    except Exception as exc:
        logger.warning("Branch LLM judge call failed: %s", exc)
        return BranchDecision(
            triggered=False,
            confidence=0.0,
            evidence=f"LLM judge call failed: {exc}",
        )

    parsed = _parse_judge_json(result.get("response", ""))
    if parsed is None:
        logger.warning("Branch LLM judge output parse failed")
        return BranchDecision(
            triggered=False,
            confidence=0.0,
            evidence="LLM judge returned invalid JSON; using default path.",
        )

    expected = bool(condition.get("expected", True))
    answer = bool(parsed["answer"])
    return BranchDecision(
        triggered=answer is expected,
        confidence=float(parsed["confidence"]),
        evidence=str(parsed["evidence"]),
    )


def _build_llm_branch_prompt(question: str, assistant_text: str) -> str:
    return f"""You are a strict branch-routing judge for caregiving assistant transcripts.
Evaluate whether the assistant response satisfies one yes/no routing question.

Assistant response:
{assistant_text or "(missing)"}

Routing question:
{question}

Return ONLY valid JSON with this exact schema:
{{"answer": true or false, "confidence": 0.0 to 1.0, "evidence": "short quote from assistant response"}}

Rules:
- answer=true means "yes" to the routing question.
- evidence should cite concrete text from the assistant response.
- if the assistant response is missing, answer=false."""
