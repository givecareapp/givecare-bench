"""Base classes and shared types for the verifier pattern.

A Verifier answers one narrow question about one failure mode:
"Given this transcript, did failure mode IB-X occur?"

Verifiers return PASS / FAIL / UNCLEAR / NOT_APPLICABLE with evidence.
They do NOT compute scores. The mode_engine aggregates verdicts into
dimension scores and blindspot profiles.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class Verdict(str, Enum):
    """Mode-level verdict. Universal across verifier types."""

    PASS = "PASS"
    FAIL = "FAIL"
    UNCLEAR = "UNCLEAR"
    NOT_APPLICABLE = "NOT_APPLICABLE"

    # Extended verdicts for E-bucket factual modes.
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    WRONG_JURISDICTION = "WRONG_JURISDICTION"
    HALLUCINATED = "HALLUCINATED"
    ELIGIBILITY_OVERCLAIM = "ELIGIBILITY_OVERCLAIM"
    NO_VERIFICATION_PATH = "NO_VERIFICATION_PATH"


# Verdicts that count as failures for dimension aggregation + gate logic.
FAILURE_VERDICTS: frozenset[Verdict] = frozenset(
    {
        Verdict.FAIL,
        Verdict.UNSUPPORTED,
        Verdict.WRONG_JURISDICTION,
        Verdict.HALLUCINATED,
        Verdict.ELIGIBILITY_OVERCLAIM,
        Verdict.NO_VERIFICATION_PATH,
    }
)

# Verdicts that count as passes.
PASS_VERDICTS: frozenset[Verdict] = frozenset({Verdict.PASS, Verdict.SUPPORTED})


@dataclass
class EvidenceSpan:
    """Single piece of evidence supporting a verdict.

    Evidence spans are required for all verdicts per the taxonomy's
    auditability posture. Without spans, the benchmark is a vibe score.
    """

    role: str  # "user" | "assistant" | "system"
    turn: int
    quote: str
    rationale: Optional[str] = None


@dataclass
class VerdictResult:
    """Single mode's verdict for a single scenario run.

    Shape is fixed — mode_engine depends on it. Do not add fields without
    updating the aggregator and the published output schema.
    """

    mode_id: str
    eligible: bool
    verdict: Verdict
    severity: str  # "S1" | "S2" | "S3" | "S4" | "S4_GATE" | "S5"
    primary_bucket: str  # "A" | "B" | "C" | "D" | "E" | "F"
    scorer_type: str
    confidence: float  # 0.0 - 1.0
    evidence: list[EvidenceSpan] = field(default_factory=list)
    rationale_code: Optional[str] = None
    adjudication_required: bool = False
    scorer_version: str = ""
    prompt_hash: Optional[str] = None
    secondary_tags: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def is_failure(self) -> bool:
        return self.eligible and self.verdict in FAILURE_VERDICTS

    def is_pass(self) -> bool:
        return self.eligible and self.verdict in PASS_VERDICTS

    def is_hard_fail(self) -> bool:
        """S5 eligible failures trigger overall=0. S4_GATE also gates."""
        return self.is_failure() and self.severity in {"S5", "S4_GATE"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode_id": self.mode_id,
            "eligible": self.eligible,
            "verdict": self.verdict.value,
            "severity": self.severity,
            "primary_bucket": self.primary_bucket,
            "scorer_type": self.scorer_type,
            "confidence": self.confidence,
            "evidence": [
                {
                    "role": e.role,
                    "turn": e.turn,
                    "quote": e.quote,
                    "rationale": e.rationale,
                }
                for e in self.evidence
            ],
            "rationale_code": self.rationale_code,
            "adjudication_required": self.adjudication_required,
            "scorer_version": self.scorer_version,
            "prompt_hash": self.prompt_hash,
            "secondary_tags": list(self.secondary_tags),
            "extra": dict(self.extra),
        }


class Verifier(ABC):
    """Verifier contract. One verifier class per scorer type."""

    scorer_type: str = "base"

    @abstractmethod
    def verify(
        self,
        transcript: list[dict[str, Any]],
        scenario: dict[str, Any],
        mode_config: dict[str, Any],
        routing_config: dict[str, Any],
    ) -> VerdictResult:
        """Return a verdict for one failure mode given one scenario run.

        Args:
            transcript: ordered list of {"role": ..., "turn": ..., "content": ...}
            scenario: scenario metadata dict (tags, rubrics, persona, etc.)
            mode_config: entry from failure_modes.yaml for this mode
            routing_config: entry from scorer_routing.yaml for this mode

        Returns:
            VerdictResult with eligibility, verdict, evidence, rationale.
        """
        raise NotImplementedError

    def is_eligible(
        self,
        scenario: dict[str, Any],
        mode_config: dict[str, Any],
    ) -> bool:
        """Check if the mode applies to this scenario.

        Default: match any of `eligibility.scenario_tags_any` against the
        scenario's tag set. Override for complex eligibility logic.
        """
        eligibility = mode_config.get("eligibility") or {}
        required_tags = eligibility.get("scenario_tags_any") or []

        if not required_tags or required_tags == ["any"]:
            return True

        scenario_tags: set[str] = set()
        for key in ("failure_mode_tags", "risk_triggers", "tags"):
            for item in scenario.get(key, []) or []:
                if isinstance(item, str):
                    scenario_tags.add(item)
                elif isinstance(item, dict):
                    for k in ("name", "type", "trigger", "id"):
                        v = item.get(k)
                        if isinstance(v, str):
                            scenario_tags.add(v)
                            break

        return bool(scenario_tags.intersection(required_tags))
