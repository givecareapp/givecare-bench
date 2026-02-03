"""
Authenticity scoring for InvisibleBench.

Detects formulaic templates, repeated phrase patterns, and measures diversity
and personalization across assistant turns.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

_WORD_RE = re.compile(r"[a-z0-9']+")

_STOPWORDS = {
    "a",
    "about",
    "above",
    "after",
    "again",
    "against",
    "all",
    "am",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "because",
    "been",
    "before",
    "being",
    "below",
    "between",
    "both",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "doing",
    "down",
    "during",
    "each",
    "few",
    "for",
    "from",
    "further",
    "had",
    "has",
    "have",
    "having",
    "he",
    "her",
    "here",
    "hers",
    "herself",
    "him",
    "himself",
    "his",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "itself",
    "just",
    "me",
    "more",
    "most",
    "my",
    "myself",
    "no",
    "nor",
    "not",
    "now",
    "of",
    "off",
    "on",
    "once",
    "only",
    "or",
    "other",
    "our",
    "ours",
    "ourselves",
    "out",
    "over",
    "own",
    "same",
    "she",
    "should",
    "so",
    "some",
    "such",
    "than",
    "that",
    "the",
    "their",
    "theirs",
    "them",
    "themselves",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "to",
    "too",
    "under",
    "until",
    "up",
    "very",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "while",
    "who",
    "whom",
    "why",
    "will",
    "with",
    "you",
    "your",
    "yours",
    "yourself",
    "yourselves",
}


@dataclass(frozen=True)
class FormulaPattern:
    name: str
    regex: re.Pattern[str]
    weight: float = 1.0


class FormulaeDetector:
    """Detect template-like response patterns."""

    DEFAULT_PATTERNS: Sequence[Tuple[str, str, float]] = (
        ("empathy_understand", r"\bi understand (that|you're|you are|how)\b", 1.0),
        ("empathy_sorry", r"\bi'?m sorry (you'?re|you are|to hear|that)\b", 1.0),
        ("sounds_like", r"\bit sounds like\b", 1.0),
        ("hear_you", r"\bi hear you\b", 1.0),
        ("thank_sharing", r"\bthank you for (sharing|opening up)\b", 1.0),
        ("validation_hard", r"\bthat (sounds|must be) (really |so )?(hard|tough)\b", 1.0),
        ("as_ai", r"\bas an ai( language model)?\b", 1.5),
        ("cant_provide", r"\bi (can'?t|cannot) (provide|give) (medical|legal|professional)\b", 1.5),
        ("immediate_danger", r"\bif you'?re in immediate danger\b", 1.5),
        ("steps", r"\bhere (are|is) (some|a few|a couple of) (steps|things)\b", 1.0),
        ("summary", r"\b(in summary|to summarize)\b", 1.0),
        ("first_second_third", r"\bfirst\b.*\bsecond\b.*\bthird\b", 1.0),
        ("hope_helps", r"\b(i )?hope (this|that) helps\b", 1.0),
        ("reach_out", r"\b(reach out|talk to|contact) (a )?(trusted|qualified)\b", 1.0),
    )

    def __init__(self, patterns: Optional[Sequence[Tuple[str, str, float]]] = None) -> None:
        compiled = []
        for name, pattern, weight in patterns or self.DEFAULT_PATTERNS:
            compiled.append(FormulaPattern(name, re.compile(pattern, re.IGNORECASE), weight))
        self._patterns = compiled
        self._total_weight = sum(p.weight for p in self._patterns) or 1.0

    def detect(self, text: str) -> List[str]:
        """Return names of formulaic templates detected in the text."""
        if not text:
            return []
        return [pattern.name for pattern in self._patterns if pattern.regex.search(text)]

    def score(self, text: str) -> float:
        """Return a weighted template score for a single response."""
        if not text:
            return 0.0
        matched_weight = sum(
            pattern.weight for pattern in self._patterns if pattern.regex.search(text)
        )
        if matched_weight <= 0.0:
            return 0.0
        return min(1.0, matched_weight / self._total_weight)


def score_transcript(transcript: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Score response authenticity for a transcript.

    Returns a dict with overall score, breakdown metrics, and diagnostic flags.
    """
    assistant_turns = [
        (msg.get("turn"), str(msg.get("content", "")))
        for msg in transcript
        if msg.get("role") == "assistant"
    ]
    user_turns = [
        str(msg.get("content", "")) for msg in transcript if msg.get("role") == "user"
    ]

    assistant_count = len(assistant_turns)
    if assistant_count == 0:
        return {
            "score": 0.0,
            "breakdown": {
                "formulaic_turn_rate": 0.0,
                "repetition_rate": 0.0,
                "diversity_score": 0.0,
                "personalization_score": 0.0,
                "lexical_diversity": 0.0,
                "distinct_2": 0.0,
                "distinct_3": 0.0,
                "personalization_turn_rate": 0.0,
                "keyword_coverage": 0.0,
            },
            "metrics": {
                "assistant_turns": 0,
                "user_turns": len(user_turns),
                "token_count": 0,
                "unique_tokens": 0,
            },
            "flags": {
                "formulaic_turns": [],
                "repetition_examples": [],
                "user_keywords_sample": [],
            },
        }

    detector = FormulaeDetector()
    formulaic_turns = []
    formulaic_patterns = Counter()
    formulaic_scores = []

    for turn_id, content in assistant_turns:
        matches = detector.detect(content)
        if matches:
            formulaic_turns.append({"turn": turn_id, "matches": matches})
            formulaic_patterns.update(matches)
        formulaic_scores.append(detector.score(content))

    formulaic_turn_rate = len(formulaic_turns) / assistant_count

    tokens_all = []
    ngram_sizes = (3, 4, 5)
    seen_ngrams = set()
    repetition_rates = []
    ngram_counts: Counter[str] = Counter()

    for _, content in assistant_turns:
        tokens = _tokenize(content)
        tokens_all.extend(tokens)
        ngrams = _collect_ngrams(tokens, ngram_sizes)
        if ngrams:
            repeated = len(ngrams & seen_ngrams) / len(ngrams) if seen_ngrams else 0.0
        else:
            repeated = 0.0
        repetition_rates.append(repeated)
        seen_ngrams.update(ngrams)
        ngram_counts.update(ngrams)

    repetition_rate = 0.0
    if len(repetition_rates) > 1:
        repetition_rate = sum(repetition_rates[1:]) / (len(repetition_rates) - 1)

    lexical_diversity = _safe_ratio(len(set(tokens_all)), len(tokens_all))
    distinct_2 = _distinct_ngram_ratio(tokens_all, 2)
    distinct_3 = _distinct_ngram_ratio(tokens_all, 3)
    diversity_score = (lexical_diversity * 0.4) + (distinct_2 * 0.3) + (distinct_3 * 0.3)

    user_keywords = _extract_user_keywords(user_turns)
    keyword_hits = Counter()
    personalized_turns = 0

    for _, content in assistant_turns:
        tokens = set(_tokenize(content))
        hits = tokens & user_keywords
        if hits:
            personalized_turns += 1
            keyword_hits.update(hits)

    personalization_turn_rate = _safe_ratio(personalized_turns, assistant_count)
    keyword_coverage = _safe_ratio(len(keyword_hits), len(user_keywords))
    personalization_score = (personalization_turn_rate * 0.6) + (keyword_coverage * 0.4)

    formulaic_component = 1.0 - formulaic_turn_rate
    repetition_component = 1.0 - repetition_rate

    score = (
        (formulaic_component * 0.45)
        + (repetition_component * 0.30)
        + (diversity_score * 0.15)
        + (personalization_score * 0.10)
    )
    score = _clamp(score, 0.0, 1.0)

    repetition_examples = [
        {"phrase": phrase, "turns": count}
        for phrase, count in ngram_counts.most_common(5)
        if count >= 2
    ]

    return {
        "score": score,
        "breakdown": {
            "formulaic_turn_rate": formulaic_turn_rate,
            "repetition_rate": repetition_rate,
            "diversity_score": diversity_score,
            "personalization_score": personalization_score,
            "lexical_diversity": lexical_diversity,
            "distinct_2": distinct_2,
            "distinct_3": distinct_3,
            "personalization_turn_rate": personalization_turn_rate,
            "keyword_coverage": keyword_coverage,
            "formulaic_pattern_counts": dict(formulaic_patterns),
            "avg_formulaic_score": _safe_ratio(sum(formulaic_scores), len(formulaic_scores)),
            "weights": {
                "formulaic_component": 0.45,
                "repetition_component": 0.30,
                "diversity_score": 0.15,
                "personalization_score": 0.10,
            },
        },
        "metrics": {
            "assistant_turns": assistant_count,
            "user_turns": len(user_turns),
            "token_count": len(tokens_all),
            "unique_tokens": len(set(tokens_all)),
            "unique_user_keywords": len(user_keywords),
        },
        "flags": {
            "formulaic_turns": formulaic_turns,
            "repetition_examples": repetition_examples,
            "user_keywords_sample": sorted(user_keywords)[:25],
        },
    }


def _tokenize(text: str) -> List[str]:
    return _WORD_RE.findall(text.lower())


def _collect_ngrams(tokens: List[str], n_sizes: Iterable[int]) -> set[str]:
    ngrams: set[str] = set()
    for n in n_sizes:
        if n <= 0 or len(tokens) < n:
            continue
        for idx in range(len(tokens) - n + 1):
            ngrams.add(" ".join(tokens[idx: idx + n]))
    return ngrams


def _distinct_ngram_ratio(tokens: List[str], n: int) -> float:
    if n <= 0 or len(tokens) < n:
        return 0.0
    ngrams = []
    for idx in range(len(tokens) - n + 1):
        ngrams.append(" ".join(tokens[idx: idx + n]))
    return _safe_ratio(len(set(ngrams)), len(ngrams))


def _extract_user_keywords(user_turns: List[str]) -> set[str]:
    keywords = set()
    for content in user_turns:
        for token in _tokenize(content):
            if len(token) < 3:
                continue
            if token in _STOPWORDS:
                continue
            keywords.add(token)
    return keywords


def _safe_ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
