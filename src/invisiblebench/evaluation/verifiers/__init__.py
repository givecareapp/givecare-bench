"""Verifier pattern — per-check verdict producers for InvisibleBench.

Separates regex / LLM / corpus roles so each answers one question:
    regex:   "Did this surface form appear?"
    llm:     "Did this behavior happen in context?"
    corpus:  "Is this factual claim true in ground-truth data?"

All verifiers return `VerdictResult` with the same shape; `mode_engine`
aggregates them into raw/internal rows that project into safety-care/v1.
"""

from invisiblebench.evaluation.verifiers.base import (
    CORE_VERDICTS,
    EvidenceSpan,
    Verdict,
    VerdictResult,
    Verifier,
    collect_scenario_tags,
)
from invisiblebench.evaluation.verifiers.corpus_verifier import CorpusVerifier
from invisiblebench.evaluation.verifiers.llm_verifier import LLMVerifier
from invisiblebench.evaluation.verifiers.regex_verifier import RegexVerifier
from invisiblebench.evaluation.verifiers.scenario_rule_verifier import ScenarioRuleVerifier
from invisiblebench.models._types import (
    ModeConfig,
    RoutingConfig,
    ScenarioData,
    Transcript,
)

__all__ = [
    "CORE_VERDICTS",
    "collect_scenario_tags",
    "VerdictResult",
    "Verifier",
    "Verdict",
    "EvidenceSpan",
    "ModeConfig",
    "RoutingConfig",
    "ScenarioData",
    "Transcript",
    "RegexVerifier",
    "LLMVerifier",
    "CorpusVerifier",
    "ScenarioRuleVerifier",
]
