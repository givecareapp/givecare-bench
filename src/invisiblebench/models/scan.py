"""The scan contract: frozen inputs and one durable record per judgment."""

from __future__ import annotations

from enum import Enum
from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StringConstraints, field_validator, model_validator

DIMENSIONS = {
    "safety": ("crisis", "scope", "identity", "autonomy"),
    "care": ("belonging", "attunement", "relational", "advocacy"),
}
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Verdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNCLEAR = "UNCLEAR"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EvidenceSpan(Record):
    role: Literal["user", "assistant"]
    turn: StrictInt = Field(ge=1)
    quote: str = Field(min_length=1)


class Decision(Record):
    verdict: Verdict
    rationale: Text
    evidence: list[EvidenceSpan]


class CheckDefinition(Record):
    id: Text
    name: Text
    severity: Literal["S1", "S2", "S3", "S4", "S5"]
    criteria: Text
    source_grounding: list[str] = Field(default_factory=list)


class Check(CheckDefinition):
    layer: Literal["safety", "care"]
    dimension: Text
    definition_sha256: Digest

    @model_validator(mode="after")
    def check_identity(self):
        if self.dimension not in DIMENSIONS[self.layer] or not self.id.startswith(self.dimension + "."):
            raise ValueError("check ID, layer, and dimension disagree")
        return self


class JudgeSettings(Record):
    model: Text
    temperature: float = 0.0
    max_tokens: StrictInt = Field(default=4000, gt=0)
    context_policy: Literal["full_ordered"] = "full_ordered"


class JudgeObservation(Record):
    model: Text | None = None
    provider: Text | None = None
    finish_reason: Text | None = None


class FileRef(Record):
    path: str
    sha256: Digest

    @field_validator("path")
    @classmethod
    def relative_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if not value or "\\" in value or path.is_absolute() or any(part in {"", ".", ".."} for part in value.split("/")):
            raise ValueError("input path must be relative to the scan bundle")
        return value


class TranscriptSource(FileRef):
    model: Text
    model_id: Text
    scenario_id: Text
    category: Text


class SourceRun(Record):
    manifest: FileRef
    summary: FileRef
    transcripts: list[TranscriptSource] = Field(min_length=1)


class ScanPlan(Record):
    schema_version: Literal["invisiblebench-scan/v1"] = "invisiblebench-scan/v1"
    benchmark_version: Text
    engine_version: Text
    scenario_corpus_sha256: Digest
    judge: JudgeSettings
    instructions: Text
    checks: list[Check] = Field(min_length=1)
    sources: list[SourceRun] = Field(min_length=1)
    input_token_envelope: StrictInt = Field(ge=0)
    estimated_cost_usd: float | None = Field(ge=0)

    @model_validator(mode="after")
    def unique_tasks(self):
        checks = [check.id for check in self.checks]
        transcripts = [(t.model_id, t.scenario_id) for source in self.sources for t in source.transcripts]
        if len(checks) != len(set(checks)) or len(transcripts) != len(set(transcripts)):
            raise ValueError("scan contains duplicate checks or model/scenario pairs")
        return self

    @property
    def transcripts(self) -> list[TranscriptSource]:
        return [transcript for source in self.sources for transcript in source.transcripts]

    @property
    def planned_calls(self) -> int:
        return len(self.transcripts) * len(self.checks)


class Judgment(Decision):
    model_id: Text
    scenario_id: Text
    check_id: Text
    plan_sha256: Digest
    input_sha256: Digest
    raw_response: str | None
    judge: JudgeObservation
    error: Literal["judge_api_error", "invalid_judge_output"] | None = None
    error_detail: str | None = None
    cost_usd: float = Field(ge=0)

    @model_validator(mode="after")
    def error_verdict(self):
        if self.error is not None and self.verdict != Verdict.UNCLEAR:
            raise ValueError("a technical judge error must remain UNCLEAR")
        return self

    @property
    def key(self) -> tuple[str, str, str]:
        return self.model_id, self.scenario_id, self.check_id
