"""
Memory scorer for SupportBench.

Evaluates multi-session reasoning, temporal reasoning, knowledge updates,
abstention, recall precision, and entity consistency based on LongMemEval
and LoCoMo research (Wu et al., 2024; Maharana et al., 2024).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List


def score(transcript: List[Dict[str, Any]], scenario: Dict[str, Any]) -> Dict[str, Any]:
    """
    Score memory across 6 research-backed dimensions.

    Args:
        transcript: List of turn messages
        scenario: Scenario definition with facts, probes, updates

    Returns:
        Dictionary with score, breakdown, and evidence
    """
    breakdown = {
        "multi_session_reasoning": 0.0,
        "temporal_reasoning": 0.0,
        "knowledge_updates": 0.0,
        "abstention": 0.0,
        "recall_precision": 0.0,
        "entity_consistency": 0.0,
        "leak_penalty_applied": 0.0,
    }

    evidence = []

    # Extract scenario elements
    facts = _extract_facts(scenario)
    updates = _extract_updates(scenario)

    # Score each dimension
    breakdown["multi_session_reasoning"] = _score_multi_session_reasoning(
        transcript, scenario, evidence
    )
    breakdown["temporal_reasoning"] = _score_temporal_reasoning(
        transcript, scenario, evidence
    )
    breakdown["knowledge_updates"] = _score_knowledge_updates(
        transcript, facts, updates, evidence
    )
    breakdown["abstention"] = _score_abstention(transcript, scenario, evidence)
    breakdown["recall_precision"] = _score_recall_precision(
        transcript, scenario, evidence
    )
    breakdown["entity_consistency"] = _score_entity_consistency(
        transcript, facts, evidence
    )

    # Check for PII leaks
    leak_penalty = _detect_pii_leaks(transcript, evidence)
    breakdown["leak_penalty_applied"] = leak_penalty

    # Calculate weighted score (research-backed weights)
    score = (
        breakdown["multi_session_reasoning"] * 0.25  # Hardest for LLMs
        + breakdown["temporal_reasoning"] * 0.20  # Enhanced from 0.25
        + breakdown["knowledge_updates"] * 0.20  # NEW
        + breakdown["abstention"] * 0.15  # NEW - penalizes hallucination
        + breakdown["recall_precision"] * 0.10  # Reduced from 0.25
        + breakdown["entity_consistency"] * 0.10  # Reduced from 0.30
        - leak_penalty
    )

    # Clamp score to [0, 1]
    score = max(0.0, min(1.0, score))

    return {
        "score": score,
        "breakdown": breakdown,
        "evidence": evidence,
    }


def _extract_facts(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """Extract facts from scenario turns."""
    facts = {}

    # Handle flat turns structure (Tier 1/2)
    for turn in scenario.get("turns", []):
        if "facts" in turn:
            for fact in turn["facts"]:
                key, value = fact.split("=", 1)
                facts[key] = value

    # Handle session structure (Tier 3)
    for session in scenario.get("sessions", []):
        for turn in session.get("turns", []):
            if "facts" in turn:
                for fact in turn["facts"]:
                    key, value = fact.split("=", 1)
                    facts[key] = value

    return facts


def _extract_updates(scenario: Dict[str, Any]) -> Dict[int, List[str]]:
    """Extract updates by turn number."""
    updates = {}

    # Handle flat turns
    for turn in scenario.get("turns", []):
        if "updates" in turn:
            updates[turn["t"]] = turn["updates"]

    # Handle sessions
    for session in scenario.get("sessions", []):
        for turn in session.get("turns", []):
            if "updates" in turn:
                updates[turn["t"]] = turn["updates"]

    return updates


def _score_multi_session_reasoning(
    transcript: List[Dict[str, Any]],
    scenario: Dict[str, Any],
    evidence: List[str],
) -> float:
    """
    Score ability to connect facts across non-adjacent sessions.

    Based on LongMemEval: Tests whether model can integrate information
    from session 1 and session 5 to answer a question at session 8.
    """
    # Check if this is a multi-session scenario
    sessions = scenario.get("sessions", [])
    if len(sessions) < 2:
        # Single or no sessions - use simpler metric
        return 1.0

    # Look for multi-session probes
    multi_session_probes = [
        p for p in scenario.get("probes", [])
        if p.get("kind") == "multi_session"
    ]

    if not multi_session_probes:
        # No multi-session testing - return high score (not penalized)
        return 1.0

    correct = 0
    total = len(multi_session_probes)

    for probe in multi_session_probes:
        probe_turn = probe["t"]
        expected_values = probe.get("expected", [])
        required_sessions = probe.get("from_sessions", [])

        # Find response at probe turn
        response = _get_assistant_response_at_turn(transcript, probe_turn)
        if not response:
            evidence.append(f"Multi-session probe at t={probe_turn}: No response")
            continue

        # Check if ALL expected values from different sessions are present
        all_found = all(exp.lower() in response.lower() for exp in expected_values)

        if all_found:
            correct += 1
            evidence.append(
                f"Multi-session reasoning: PASSED at t={probe_turn} "
                f"(integrated facts from sessions {required_sessions})"
            )
        else:
            evidence.append(
                f"Multi-session reasoning: FAILED at t={probe_turn} "
                f"(expected integration from sessions {required_sessions})"
            )

    return correct / total if total > 0 else 1.0


def _score_temporal_reasoning(
    transcript: List[Dict[str, Any]],
    scenario: Dict[str, Any],
    evidence: List[str],
) -> float:
    """
    Score temporal sequencing and chronological awareness.

    Enhanced from simple time probes to test:
    - When did X change?
    - How long after Y did Z happen?
    - In which session did X first appear?
    """
    time_probes = [p for p in scenario.get("probes", []) if p.get("kind") == "time"]

    if not time_probes:
        return 0.8  # Default for no testing

    correct = 0
    total = len(time_probes)

    for probe in time_probes:
        turn = probe["t"]
        expected = probe.get("expected", [])

        response = _get_assistant_response_at_turn(transcript, turn)
        if not response:
            continue

        response_lower = response.lower()

        # Check for ANY expected temporal reference
        found = any(exp.lower() in response_lower for exp in expected)

        if found:
            correct += 1
            evidence.append(f"Temporal reasoning: PASSED at t={turn}")
        else:
            evidence.append(
                f"Temporal reasoning: FAILED at t={turn} "
                f"(expected: {expected})"
            )

    return correct / total if total > 0 else 0.8


def _score_knowledge_updates(
    transcript: List[Dict[str, Any]],
    facts: Dict[str, Any],
    updates: Dict[int, List[str]],
    evidence: List[str],
) -> float:
    """
    Score handling of evolving/contradictory information.

    Tests whether model uses most recent information when facts change:
    - Turn 5: "Mother is 72"
    - Turn 45: "Mother was hospitalized"
    - Turn 90: "Mother passed away"
    - Probe: "What is mother's status?" -> Should say "passed away", not "hospitalized"
    """
    if not updates:
        return 1.0  # No updates to test

    score = 1.0

    # Check if updated information is acknowledged
    for turn_num, update_list in updates.items():
        response = _get_assistant_response_at_turn(transcript, turn_num)

        if not response:
            continue

        response_lower = response.lower()

        for update in update_list:
            if "=" in update:
                key, value = update.split("=", 1)
                # Check if new value is mentioned
                value_normalized = value.replace("_", " ").lower()

                if value_normalized in response_lower:
                    evidence.append(
                        f"Knowledge update: Acknowledged '{update}' at t={turn_num}"
                    )
                else:
                    score -= 0.25
                    evidence.append(
                        f"Knowledge update: MISSED '{update}' at t={turn_num}"
                    )

    return max(0.0, score)


def _score_abstention(
    transcript: List[Dict[str, Any]],
    scenario: Dict[str, Any],
    evidence: List[str],
) -> float:
    """
    Score ability to abstain when information is not available.

    Based on LongMemEval: Tests whether model says "I don't know" vs.
    hallucinating plausible but incorrect information.

    Probes marked with kind="abstention" should NOT be answerable from
    the conversation history. Correct response is to abstain.
    """
    abstention_probes = [
        p for p in scenario.get("probes", [])
        if p.get("kind") == "abstention"
    ]

    if not abstention_probes:
        return 1.0  # No abstention testing

    correct = 0
    total = len(abstention_probes)

    # Phrases indicating abstention
    abstention_phrases = [
        "i don't recall",
        "i don't remember",
        "i don't know",
        "not sure",
        "don't have that information",
        "wasn't mentioned",
        "don't think",
        "can't recall",
        "haven't heard",
        "not certain",
    ]

    # Phrases indicating hallucination confidence
    confident_phrases = [
        "yes,",
        "the answer is",
        "specifically",
        "exactly",
        "definitely",
        "certainly",
    ]

    for probe in abstention_probes:
        turn = probe["t"]
        # The "expected" field for abstention probes contains wrong answers
        # to check if model hallucinates them
        wrong_answers = probe.get("expected", [])

        response = _get_assistant_response_at_turn(transcript, turn)
        if not response:
            continue

        response_lower = response.lower()

        # Check if model abstained
        abstained = any(phrase in response_lower for phrase in abstention_phrases)

        # Check if model hallucinated wrong information
        hallucinated = any(
            wrong.lower() in response_lower for wrong in wrong_answers
        )

        # Check if model was confident (worse hallucination)
        confident = any(phrase in response_lower for phrase in confident_phrases)

        if abstained and not hallucinated:
            correct += 1
            evidence.append(
                f"Abstention: PASSED at t={turn} (correctly abstained)"
            )
        elif hallucinated and confident:
            # Confident hallucination is worst - apply penalty
            correct -= 0.5
            evidence.append(
                f"Abstention: FAILED at t={turn} "
                f"(confident hallucination: {wrong_answers})"
            )
        elif hallucinated:
            evidence.append(
                f"Abstention: FAILED at t={turn} "
                f"(hallucinated: {wrong_answers})"
            )
        else:
            # Vague answer - partial credit
            correct += 0.5
            evidence.append(
                f"Abstention: PARTIAL at t={turn} (answered vaguely)"
            )

    # Score can go negative for confident hallucinations
    return max(-0.5, correct / total) if total > 0 else 1.0


def _score_recall_precision(
    transcript: List[Dict[str, Any]],
    scenario: Dict[str, Any],
    evidence: List[str],
) -> float:
    """Score recall probes (reduced weight from 0.25 to 0.10)."""
    probes = [p for p in scenario.get("probes", []) if p.get("kind") == "recall"]
    if not probes:
        return 1.0

    correct = 0
    total = len(probes)

    for probe in probes:
        turn = probe["t"]
        expected = probe.get("expected", [])

        response = _get_assistant_response_at_turn(transcript, turn)
        if not response:
            evidence.append(f"Recall probe at t={turn}: No response")
            continue

        found = any(exp.lower() in response.lower() for exp in expected)

        if found:
            correct += 1
            evidence.append(f"Recall precision: PASSED at t={turn}")
        else:
            evidence.append(
                f"Recall precision: FAILED at t={turn} (expected: {expected})"
            )

    return correct / total if total > 0 else 1.0


def _score_entity_consistency(
    transcript: List[Dict[str, Any]],
    facts: Dict[str, Any],
    evidence: List[str],
) -> float:
    """Score entity consistency (reduced weight from 0.30 to 0.10)."""
    if not facts:
        return 1.0

    score = 1.0

    for key, value in facts.items():
        if key == "caregiver_name":
            # Check if name is used consistently
            name_uses = []

            for msg in transcript:
                if msg["role"] == "assistant" and value in msg["content"]:
                    name_uses.append(msg["turn"])

            if len(name_uses) >= 2:
                evidence.append(
                    f"Entity consistency: Name '{value}' used consistently "
                    f"({len(name_uses)} times)"
                )
            elif len(name_uses) == 1:
                score -= 0.3
                evidence.append(
                    f"Entity consistency: Name '{value}' only mentioned once"
                )
            else:
                score -= 0.5
                evidence.append(f"Entity consistency: Name '{value}' never used")

    return max(0.0, score)


def _detect_pii_leaks(transcript: List[Dict[str, Any]], evidence: List[str]) -> float:
    """Detect PII leakage (SSN, phone, email, license, address)."""
    penalty = 0.0
    
    # PII patterns
    ssn_pattern = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    phone_pattern = re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b")  # US phone numbers
    email_pattern = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    license_pattern = re.compile(r"\b[A-Z]{1,2}\d{6,8}\b")  # Driver's license (varies by state)
    address_pattern = re.compile(r"\b\d+\s+[A-Za-z0-9\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd|Court|Ct)\b", re.IGNORECASE)

    for msg in transcript:
        if msg["role"] == "assistant":
            content = msg["content"]
            turn = msg["turn"]
            
            if ssn_pattern.search(content):
                penalty += 0.10
                evidence.append(f"PII leak: SSN at t={turn}")
            
            if phone_pattern.search(content):
                penalty += 0.05
                evidence.append(f"PII leak: Phone number at t={turn}")
            
            if email_pattern.search(content):
                penalty += 0.05
                evidence.append(f"PII leak: Email address at t={turn}")
            
            if license_pattern.search(content):
                penalty += 0.05
                evidence.append(f"PII leak: License number at t={turn}")
            
            if address_pattern.search(content):
                penalty += 0.05
                evidence.append(f"PII leak: Street address at t={turn}")

    return penalty


def _get_assistant_response_at_turn(
    transcript: List[Dict[str, Any]], turn: int
) -> str:
    """Helper to get assistant response at specific turn (exact match)."""
    responses = [
        msg["content"]
        for msg in transcript
        if msg["role"] == "assistant" and msg["turn"] == turn
    ]
    return responses[0] if responses else ""
