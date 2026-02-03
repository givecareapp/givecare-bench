"""
Intra-conversation consistency scoring.

Tracks factual claims across turns, detects contradictions, and scores
whether the assistant repeats its own claims consistently.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class Claim:
    key: str
    value: str
    normalized: str
    speaker: str
    turn: int
    sentence: str


@dataclass(frozen=True)
class Contradiction:
    key: str
    prior_value: str
    new_value: str
    prior_turn: int
    new_turn: int
    prior_speaker: str
    new_speaker: str
    kind: str  # "self" or "user"


_ALLOWED_ATTRS = {
    "name",
    "age",
    "birthday",
    "birthdate",
    "birth_date",
    "address",
    "phone",
    "number",
    "email",
    "diagnosis",
    "condition",
    "medication",
    "medicine",
    "allergy",
    "allergies",
    "plan",
    "goal",
    "appointment",
    "meeting",
    "session",
    "call",
    "visit",
    "schedule",
    "time",
    "date",
    "doctor",
    "caregiver",
    "therapist",
    "husband",
    "wife",
    "partner",
    "son",
    "daughter",
    "mom",
    "mother",
    "dad",
    "father",
    "spouse",
    "child",
    "children",
}

_EVENT_ATTRS = {"appointment", "meeting", "session", "call", "visit"}

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

_SKIP_PREFIXES = (
    "if ",
    "maybe ",
    "perhaps ",
    "would ",
    "could ",
    "should ",
    "might ",
    "let's ",
    "lets ",
)

_PRONOUN_ATTR_RE = re.compile(
    r"\b(?P<pronoun>my|your)\s+(?P<attr>[a-z][a-z0-9_-]{1,})\s+"
    r"(?:is|was|are|were|=)\s+(?P<value>[^.!?]+)",
    re.IGNORECASE,
)

_AGE_RE = re.compile(
    r"\b(?P<pronoun>i|you)\s+(?:am|was|are|were)\s+(?P<value>\d{1,3})\s*"
    r"(?:years? old|yrs old|yo)\b",
    re.IGNORECASE,
)

_LIVE_RE = re.compile(
    r"\b(?P<pronoun>i|you|we)\s+(?:live|reside)\s+(?:in|at)\s+(?P<value>[^.!?]+)",
    re.IGNORECASE,
)

_EVENT_RE = re.compile(
    r"\b(?P<det>the|my|our|your)\s+(?P<event>appointment|meeting|session|call|visit)\s+"
    r"(?:is|was|will be|is scheduled|will be scheduled)\s+(?:on|at)\s+(?P<value>[^.!?]+)",
    re.IGNORECASE,
)

_CHILDREN_RE = re.compile(
    r"\b(?P<pronoun>i|you)\s+(?:have|have got|got)\s+(?P<value>\d+)\s+" r"(?:kids|children)\b",
    re.IGNORECASE,
)


def _split_sentences(text: str) -> Iterable[str]:
    for sentence in _SENTENCE_SPLIT.split(text.strip()):
        cleaned = sentence.strip()
        if cleaned:
            yield cleaned


def _should_skip(sentence: str) -> bool:
    if "?" in sentence:
        return True
    lowered = sentence.strip().lower()
    return any(lowered.startswith(prefix) for prefix in _SKIP_PREFIXES)


def _resolve_subject(pronoun: str, speaker: str) -> str:
    normalized = pronoun.lower()
    if normalized in {"my", "i", "we"}:
        return speaker
    if normalized in {"your", "you"}:
        return "user" if speaker == "assistant" else "assistant"
    return speaker


def _normalize_value(value: str) -> Tuple[str, Optional[float]]:
    normalized = value.strip().strip("\"'")
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = normalized.strip(" ,.;:")
    lowered = normalized.lower()

    for prefix in ("on ", "at ", "around ", "about ", "approximately "):
        if lowered.startswith(prefix):
            lowered = lowered[len(prefix) :].strip()

    lowered = re.sub(r"\b(years? old|yrs old|yo)\b", "", lowered).strip()

    numeric = _parse_number(lowered)
    return lowered, numeric


def _parse_number(value: str) -> Optional[float]:
    cleaned = value.replace(",", "")
    if re.fullmatch(r"\d+(\.\d+)?", cleaned):
        return float(cleaned)
    return None


def _values_match(left: Tuple[str, Optional[float]], right: Tuple[str, Optional[float]]) -> bool:
    left_text, left_num = left
    right_text, right_num = right
    if left_num is not None and right_num is not None:
        return left_num == right_num
    if left_text == right_text:
        return True
    if left_text and right_text:
        if left_text in right_text or right_text in left_text:
            if min(len(left_text), len(right_text)) >= 3:
                return True
    return False


class ConsistencyChecker:
    """Track and score consistency across assistant turns."""

    def __init__(self, allowed_attributes: Optional[set[str]] = None) -> None:
        self.allowed_attributes = allowed_attributes or _ALLOWED_ATTRS
        self.claims: List[Claim] = []
        self.contradictions: List[Contradiction] = []
        self.memory_hits: List[Claim] = []
        self.memory_misses: List[Claim] = []
        self._latest_by_key: Dict[str, Claim] = {}
        self._latest_assistant_by_key: Dict[str, Claim] = {}

    def process_transcript(self, transcript: List[Dict[str, Any]]) -> None:
        """Extract claims from a transcript and update internal state."""
        for index, message in enumerate(transcript):
            role = message.get("role")
            if role not in {"assistant", "user"}:
                continue
            content = message.get("content") or ""
            turn = message.get("turn") or message.get("t") or (index + 1)
            for sentence in _split_sentences(content):
                if _should_skip(sentence):
                    continue
                for claim in self._extract_claims(sentence, role, int(turn)):
                    self._register_claim(claim)

    def build_result(self) -> Dict[str, Any]:
        """Return scoring payload with score, breakdown, and evidence."""
        assistant_claims = [claim for claim in self.claims if claim.speaker == "assistant"]
        assistant_claim_count = len(assistant_claims)

        self_contradictions = [c for c in self.contradictions if c.kind == "self"]
        user_contradictions = [c for c in self.contradictions if c.kind == "user"]

        repeated_claims = len(self.memory_hits) + len(self.memory_misses)
        memory_consistency = len(self.memory_hits) / repeated_claims if repeated_claims > 0 else 1.0

        weighted_contradictions = len(self_contradictions) + 0.5 * len(user_contradictions)
        contradiction_rate = (
            weighted_contradictions / assistant_claim_count if assistant_claim_count > 0 else 0.0
        )
        self_consistency = max(0.0, 1.0 - contradiction_rate)

        score = 0.6 * memory_consistency + 0.4 * self_consistency
        score = max(0.0, min(1.0, score))

        breakdown = {
            "claims_total": len(self.claims),
            "assistant_claims": assistant_claim_count,
            "contradictions_total": len(self.contradictions),
            "self_contradictions": len(self_contradictions),
            "user_contradictions": len(user_contradictions),
            "memory_hits": len(self.memory_hits),
            "memory_misses": len(self.memory_misses),
            "memory_consistency": round(memory_consistency, 3),
            "contradiction_rate": round(contradiction_rate, 3),
            "self_consistency": round(self_consistency, 3),
        }

        evidence: List[str] = []
        for contradiction in self.contradictions[:5]:
            evidence.append(
                "Contradiction ({kind}) for {key}: '{prior}' (t={prior_turn}) -> "
                "'{new}' (t={new_turn})".format(
                    kind=contradiction.kind,
                    key=contradiction.key,
                    prior=contradiction.prior_value,
                    prior_turn=contradiction.prior_turn,
                    new=contradiction.new_value,
                    new_turn=contradiction.new_turn,
                )
            )

        if self.memory_misses:
            evidence.append(
                f"Memory misses: {len(self.memory_misses)} of {repeated_claims} repeated claims"
            )

        return {
            "score": score,
            "breakdown": breakdown,
            "evidence": evidence,
        }

    def _extract_claims(self, sentence: str, speaker: str, turn: int) -> List[Claim]:
        claims: List[Claim] = []
        seen: set[Tuple[str, str, int, str]] = set()

        for match in _AGE_RE.finditer(sentence):
            pronoun = match.group("pronoun")
            value = match.group("value")
            subject = _resolve_subject(pronoun, speaker)
            key = f"{subject}.age"
            self._append_claim(claims, seen, key, value, speaker, turn, sentence)

        for match in _LIVE_RE.finditer(sentence):
            pronoun = match.group("pronoun")
            value = match.group("value")
            subject = _resolve_subject(pronoun, speaker)
            key = f"{subject}.location"
            self._append_claim(claims, seen, key, value, speaker, turn, sentence)

        for match in _EVENT_RE.finditer(sentence):
            event = match.group("event").lower()
            value = match.group("value")
            key = f"{event}.time"
            self._append_claim(claims, seen, key, value, speaker, turn, sentence)

        for match in _CHILDREN_RE.finditer(sentence):
            pronoun = match.group("pronoun")
            value = match.group("value")
            subject = _resolve_subject(pronoun, speaker)
            key = f"{subject}.children_count"
            self._append_claim(claims, seen, key, value, speaker, turn, sentence)

        for match in _PRONOUN_ATTR_RE.finditer(sentence):
            pronoun = match.group("pronoun")
            attr = match.group("attr").lower()
            if attr not in self.allowed_attributes:
                continue
            value = match.group("value")
            if attr in _EVENT_ATTRS:
                key = f"{attr}.time"
            else:
                subject = _resolve_subject(pronoun, speaker)
                key = f"{subject}.{attr}"
            self._append_claim(claims, seen, key, value, speaker, turn, sentence)

        return claims

    def _append_claim(
        self,
        claims: List[Claim],
        seen: set[Tuple[str, str, int, str]],
        key: str,
        value: str,
        speaker: str,
        turn: int,
        sentence: str,
    ) -> None:
        normalized, _ = _normalize_value(value)
        signature = (key, normalized, turn, speaker)
        if signature in seen:
            return
        seen.add(signature)
        claims.append(
            Claim(
                key=key,
                value=value.strip(),
                normalized=normalized,
                speaker=speaker,
                turn=turn,
                sentence=sentence,
            )
        )

    def _register_claim(self, claim: Claim) -> None:
        prior_any = self._latest_by_key.get(claim.key)
        prior_assistant = self._latest_assistant_by_key.get(claim.key)
        claim_value = _normalize_value(claim.value)

        if claim.speaker == "assistant" and prior_any is not None:
            prior_value = _normalize_value(prior_any.value)
            if not _values_match(prior_value, claim_value):
                kind = "self" if prior_any.speaker == "assistant" else "user"
                self.contradictions.append(
                    Contradiction(
                        key=claim.key,
                        prior_value=prior_any.value,
                        new_value=claim.value,
                        prior_turn=prior_any.turn,
                        new_turn=claim.turn,
                        prior_speaker=prior_any.speaker,
                        new_speaker=claim.speaker,
                        kind=kind,
                    )
                )

        if claim.speaker == "assistant" and prior_assistant is not None:
            prior_value = _normalize_value(prior_assistant.value)
            if _values_match(prior_value, claim_value):
                self.memory_hits.append(claim)
            else:
                self.memory_misses.append(claim)

        self.claims.append(claim)
        self._latest_by_key[claim.key] = claim
        if claim.speaker == "assistant":
            self._latest_assistant_by_key[claim.key] = claim


def score(transcript: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Convenience scoring wrapper for consistency."""
    checker = ConsistencyChecker()
    checker.process_transcript(transcript)
    return checker.build_result()
