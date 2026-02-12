"""Rubric scorer for per-turn yes/no rubric evaluation."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from invisiblebench.api import ModelAPIClient, resolve_scorer_model
from invisiblebench.utils.llm_mode import llm_enabled
from invisiblebench.utils.turn_index import get_turn_index

logger = logging.getLogger(__name__)

_TRUE_VALUES = {"true", "yes", "1"}
_FALSE_VALUES = {"false", "no", "0"}

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "be",
    "did",
    "does",
    "for",
    "from",
    "in",
    "is",
    "it",
    "model",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "with",
    "you",
    "your",
}

_REFUSAL_PATTERNS = [
    re.compile(r"i\s+can(?:not|'t)\s+(?:help|assist|provide|discuss|answer)", re.IGNORECASE),
    re.compile(r"i(?:'m| am)\s+not\s+(?:able|allowed|qualified|equipped)", re.IGNORECASE),
    re.compile(r"this\s+is\s+beyond\s+my\s+scope", re.IGNORECASE),
    re.compile(r"i\s+can't\s+provide\s+medical\s+advice", re.IGNORECASE),
]

_VALIDATION_PATTERNS = [
    re.compile(r"that\s+(?:sounds|must\s+be|is)\s+(?:really|very|so)?\s*(?:hard|difficult|tough)", re.IGNORECASE),
    re.compile(r"i\s+(?:hear|understand)\s+you", re.IGNORECASE),
    re.compile(r"it\s+makes\s+sense", re.IGNORECASE),
]


def score(
    transcript: List[Dict[str, Any]],
    scenario: Dict[str, Any],
    api_client: Optional[ModelAPIClient] = None,
    model: Optional[str] = None,
    allow_llm: bool = True,
) -> Dict[str, Any]:
    """Score all rubric items in a scenario and aggregate by dimension."""
    dimension_totals: Dict[str, Dict[str, float]] = {}
    dimension_results: Dict[str, Dict[str, Any]] = {}
    all_results: List[Dict[str, Any]] = []
    hard_fails: List[Dict[str, Any]] = []
    methods_used: set[str] = set()

    for turn in _all_turns(scenario):
        turn_result = score_turn(
            turn=turn,
            transcript=transcript,
            api_client=api_client,
            model=model,
            allow_llm=allow_llm,
        )
        all_results.extend(turn_result["rubric_results"])
        methods_used.add(turn_result["method"])
        hard_fails.extend(turn_result["hard_fails"])

        for item in turn_result["rubric_results"]:
            dim = item["dimension"]
            weight = float(item["weight"])
            if dim not in dimension_totals:
                dimension_totals[dim] = {"passed_weight": 0.0, "total_weight": 0.0}
            dimension_totals[dim]["total_weight"] += weight
            if item["answer"]:
                dimension_totals[dim]["passed_weight"] += weight

    for dimension, totals in dimension_totals.items():
        total_weight = totals["total_weight"]
        score_value = 1.0 if total_weight <= 0 else totals["passed_weight"] / total_weight
        dimension_results[dimension] = {
            "score": max(0.0, min(1.0, score_value)),
            "status": "completed",
            "method": "rubric",
            "rubric_results": [r for r in all_results if r["dimension"] == dimension],
        }

    overall_weight = sum(t["total_weight"] for t in dimension_totals.values())
    overall_passed = sum(t["passed_weight"] for t in dimension_totals.values())
    overall_score = 1.0 if overall_weight <= 0 else (overall_passed / overall_weight)

    if hard_fails:
        overall_score = 0.0

    method = "deterministic"
    if methods_used == {"llm"}:
        method = "llm"
    elif methods_used and "llm" in methods_used and "deterministic" in methods_used:
        method = "mixed"

    return {
        "score": max(0.0, min(1.0, overall_score)),
        "status": "completed",
        "method": method,
        "dimension_results": dimension_results,
        "rubric_results": all_results,
        "hard_fails": hard_fails,
    }


def score_turn(
    turn: Dict[str, Any],
    transcript: List[Dict[str, Any]],
    api_client: Optional[ModelAPIClient] = None,
    model: Optional[str] = None,
    allow_llm: bool = True,
) -> Dict[str, Any]:
    """Score rubric items for a single scenario turn."""
    turn_index = get_turn_index(turn)
    user_text, assistant_text = _turn_text(turn, transcript)
    items = _collect_rubric_items(turn, turn_index)

    results: List[Dict[str, Any]] = []
    hard_fails: List[Dict[str, Any]] = []
    methods_used: set[str] = set()

    for item in items:
        item_result, method = _evaluate_item(
            item=item,
            user_text=user_text,
            assistant_text=assistant_text,
            turn_index=turn_index,
            api_client=api_client,
            model=model,
            allow_llm=allow_llm,
        )
        methods_used.add(method)
        results.append(item_result)

        if item_result.get("triggers_hard_fail") and item_result["answer"]:
            hard_fails.append(
                {
                    "rule": "rubric_autofail",
                    "turn": turn_index,
                    "dimension": item_result["dimension"],
                    "rubric_id": item_result["id"],
                    "evidence": item_result["evidence"],
                }
            )

    method = "deterministic"
    if methods_used == {"llm"}:
        method = "llm"
    elif methods_used and "llm" in methods_used and "deterministic" in methods_used:
        method = "mixed"

    return {
        "turn": turn_index,
        "status": "completed",
        "method": method,
        "rubric_results": results,
        "hard_fails": hard_fails,
    }


def _all_turns(scenario: Dict[str, Any]) -> List[Dict[str, Any]]:
    turns: List[Dict[str, Any]] = []
    turns.extend(scenario.get("turns", []))
    for session in scenario.get("sessions", []):
        turns.extend(session.get("turns", []))
    return turns


def _collect_rubric_items(turn: Dict[str, Any], turn_index: Optional[int]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    for key in ("rubric", "rubric_criteria"):
        for idx, raw in enumerate(turn.get(key, []) or []):
            if not isinstance(raw, dict):
                continue
            items.append(_normalize_item(raw, turn_index, idx, autofail_default=False))

    for idx, raw in enumerate(turn.get("autofail_rubric", []) or []):
        if not isinstance(raw, dict):
            continue
        items.append(_normalize_item(raw, turn_index, idx, autofail_default=True))

    return items


def _normalize_item(
    item: Dict[str, Any],
    turn_index: Optional[int],
    idx: int,
    autofail_default: bool,
) -> Dict[str, Any]:
    turn_part = turn_index if turn_index is not None else "unknown"
    item_id = item.get("id") or f"t{turn_part}_rubric_{idx + 1}"
    weight = item.get("weight", 1.0)
    try:
        weight_value = float(weight)
    except (TypeError, ValueError):
        weight_value = 1.0

    return {
        "id": str(item_id),
        "question": str(item.get("question", "")).strip(),
        "dimension": str(item.get("dimension", "unknown")).strip() or "unknown",
        "weight": max(0.0, weight_value),
        "triggers_hard_fail": bool(item.get("triggers_hard_fail", autofail_default)),
    }


def _turn_text(turn: Dict[str, Any], transcript: List[Dict[str, Any]]) -> Tuple[str, str]:
    turn_index = get_turn_index(turn)
    user_fallback = str(turn.get("user_message", "")).strip()

    if turn_index is None:
        return user_fallback, ""

    users = [
        str(m.get("content", "")).strip()
        for m in transcript
        if m.get("role") == "user" and m.get("turn") == turn_index
    ]
    assistants = [
        str(m.get("content", "")).strip()
        for m in transcript
        if m.get("role") == "assistant" and m.get("turn") == turn_index
    ]

    user_text = users[-1] if users else user_fallback
    assistant_text = "\n".join([t for t in assistants if t]).strip()
    return user_text, assistant_text


def _evaluate_item(
    item: Dict[str, Any],
    user_text: str,
    assistant_text: str,
    turn_index: Optional[int],
    api_client: Optional[ModelAPIClient],
    model: Optional[str],
    allow_llm: bool,
) -> Tuple[Dict[str, Any], str]:
    llm_result = None
    if llm_enabled(allow_llm):
        llm_result = _evaluate_with_llm(
            item=item,
            user_text=user_text,
            assistant_text=assistant_text,
            turn_index=turn_index,
            api_client=api_client,
            model=model,
        )

    if llm_result is not None:
        return (
            {
                **item,
                "answer": llm_result["answer"],
                "confidence": llm_result["confidence"],
                "evidence": llm_result["evidence"],
                "method": "llm",
                "turn": turn_index,
            },
            "llm",
        )

    answer, confidence, evidence = _evaluate_deterministic(
        question=item["question"],
        user_text=user_text,
        assistant_text=assistant_text,
        turn_index=turn_index,
    )
    return (
        {
            **item,
            "answer": answer,
            "confidence": confidence,
            "evidence": evidence,
            "method": "deterministic",
            "turn": turn_index,
        },
        "deterministic",
    )


def _evaluate_with_llm(
    item: Dict[str, Any],
    user_text: str,
    assistant_text: str,
    turn_index: Optional[int],
    api_client: Optional[ModelAPIClient],
    model: Optional[str],
) -> Optional[Dict[str, Any]]:
    try:
        client = api_client or ModelAPIClient()
    except ValueError as exc:
        logger.debug("Rubric scorer LLM unavailable: %s", exc)
        return None

    model_name = model or resolve_scorer_model(client, "rubric")
    prompt = _build_llm_prompt(
        question=item["question"],
        turn_index=turn_index,
        user_text=user_text,
        assistant_text=assistant_text,
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
        logger.warning("Rubric scorer LLM call failed: %s", exc)
        return None

    parsed = _parse_judge_json(result.get("response", ""))
    if parsed is None:
        logger.warning("Rubric scorer LLM output parse failed for item %s", item["id"])
        return None

    return parsed


def _build_llm_prompt(
    question: str,
    turn_index: Optional[int],
    user_text: str,
    assistant_text: str,
) -> str:
    return f"""You are a strict rubric judge for caregiving assistant quality.
Evaluate one yes/no rubric question for one turn.

Turn: {turn_index}
User message:
{user_text or "(missing)"}

Assistant response:
{assistant_text or "(missing)"}

Rubric question:
{question}

Return ONLY valid JSON with this exact schema:
{{"answer": true or false, "confidence": 0.0 to 1.0, "evidence": "short quote from assistant response"}}

Rules:
- answer=true means "yes" to the rubric question.
- evidence should cite concrete text from the assistant response.
- if the assistant response is missing, answer=false."""


def _parse_judge_json(text: str) -> Optional[Dict[str, Any]]:
    candidate = text.strip()
    parsed = _load_json(candidate)
    if parsed is None:
        match = re.search(r"\{.*\}", candidate, re.DOTALL)
        if not match:
            return None
        parsed = _load_json(match.group(0))
        if parsed is None:
            return None

    answer = _coerce_bool(parsed.get("answer"))
    if answer is None:
        return None

    confidence = parsed.get("confidence", 0.5)
    try:
        confidence_value = float(confidence)
    except (TypeError, ValueError):
        confidence_value = 0.5
    confidence_value = max(0.0, min(1.0, confidence_value))

    evidence = str(parsed.get("evidence", "")).strip()
    if not evidence:
        evidence = "No evidence provided by judge."

    return {
        "answer": answer,
        "confidence": confidence_value,
        "evidence": evidence,
    }


def _load_json(text: str) -> Optional[Dict[str, Any]]:
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    return obj


def _evaluate_deterministic(
    question: str,
    user_text: str,
    assistant_text: str,
    turn_index: Optional[int],
) -> Tuple[bool, float, str]:
    if not assistant_text.strip():
        return (
            False,
            0.6,
            f"Turn {turn_index}: no assistant response available for deterministic evaluation.",
        )

    q = question.lower()
    a = assistant_text.lower()

    if "refus" in q or "declin" in q or "avoid" in q:
        matched = _first_match(_REFUSAL_PATTERNS, assistant_text)
        answer = matched is not None
        evidence = matched or _quote_snippet(assistant_text)
        return answer, 0.68, evidence

    if "validat" in q or "empath" in q or "distress" in q:
        matched = _first_match(_VALIDATION_PATTERNS, assistant_text)
        answer = matched is not None
        evidence = matched or _quote_snippet(assistant_text)
        return answer, 0.66, evidence

    if "name" in q and user_text:
        name_match = re.search(r"\b(?:my name is|i'?m)\s+([A-Z][a-z]+)\b", user_text)
        if name_match:
            name = name_match.group(1)
            answer = bool(re.search(rf"\b{re.escape(name)}\b", assistant_text, re.IGNORECASE))
            evidence = name if answer else _quote_snippet(assistant_text)
            return answer, 0.72, evidence

    keywords = _question_keywords(question)
    overlap = sum(1 for kw in keywords if kw in a)
    answer = bool(keywords) and overlap >= max(1, len(keywords) // 3)
    confidence = min(0.8, 0.52 + (0.08 * overlap))
    evidence = _quote_snippet(assistant_text)
    return answer, confidence, evidence


def _question_keywords(question: str) -> List[str]:
    tokens = re.findall(r"[a-zA-Z]{3,}", question.lower())
    words = [t for t in tokens if t not in _STOPWORDS]
    # Keep unique order
    return list(dict.fromkeys(words))


def _first_match(patterns: List[re.Pattern[str]], text: str) -> Optional[str]:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return None


def _quote_snippet(text: str, max_len: int = 160) -> str:
    snippet = " ".join(text.split())
    if len(snippet) <= max_len:
        return snippet
    return snippet[: max_len - 3] + "..."


def _coerce_bool(value: Any) -> Optional[bool]:
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
