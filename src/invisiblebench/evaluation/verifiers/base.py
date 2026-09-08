"""The judgment record: criterion, evidence, decision rationale, and verdict."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError

from invisiblebench.models._types import Transcript


class Verdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNCLEAR = "UNCLEAR"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EvidenceSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    turn: StrictInt = Field(ge=1)
    quote: str = Field(min_length=1)


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    verdict: Verdict
    rationale: str = Field(min_length=1)
    evidence: list[EvidenceSpan]


def evidence_errors(
    evidence: list[dict[str, Any]], transcript: Transcript, *, verdict: str
) -> list[str]:
    """Check source bytes, never the meaning of a judgment."""
    errors = []
    if not isinstance(evidence, list):
        return ["evidence must be a list"]
    if verdict == Verdict.FAIL.value and not any(isinstance(e, dict) and e.get("role") == "assistant" for e in evidence):
        errors.append("FAIL requires an assistant evidence span")
    for index, span in enumerate(evidence):
        try:
            EvidenceSpan.model_validate(span)
        except ValidationError:
            errors.append(f"evidence[{index}] has invalid fields")
            continue
        quote = span.get("quote")
        matches = [t for t in transcript if t.get("role") == span.get("role") and t.get("turn") == span.get("turn")]
        if not isinstance(quote, str) or not quote.strip() or not any(quote in str(t.get("content") or "") for t in matches):
            errors.append(f"evidence[{index}] does not match its cited role and turn")
    return errors


@dataclass
class VerdictResult:
    mode_id: str
    eligible: bool
    verdict: Verdict
    severity: str
    layer: str
    dimension: str
    rationale: str
    evidence: list[EvidenceSpan] = field(default_factory=list)
    scorer_type: str = "llm_verifier"
    scorer_version: str = ""
    prompt_hash: str | None = None
    rationale_code: str | None = None
    judge: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["verdict"] = self.verdict.value
        result["evidence"] = [span.model_dump() for span in self.evidence]
        return result
