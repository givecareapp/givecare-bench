"""Verifier pattern — per-mode verdict producers for InvisibleBench v3.

Separates regex / LLM / corpus roles so each answers one question:
    regex:   "Did this surface form appear?"
    llm:     "Did this behavior happen in context?"
    corpus:  "Is this factual claim true in ground-truth data?"

All verifiers return `VerdictResult` with the same shape; `mode_engine`
aggregates them into dimension scores + blindspot profile.
"""

from invisiblebench.evaluation.verifiers.base import (
    EvidenceSpan,
    Verdict,
    VerdictResult,
    Verifier,
)
from invisiblebench.evaluation.verifiers.corpus_verifier import CorpusVerifier
from invisiblebench.evaluation.verifiers.llm_verifier import LLMVerifier
from invisiblebench.evaluation.verifiers.regex_verifier import RegexVerifier

__all__ = [
    "VerdictResult",
    "Verifier",
    "Verdict",
    "EvidenceSpan",
    "RegexVerifier",
    "LLMVerifier",
    "CorpusVerifier",
]
