"""One scenario contract for authoring and transcript generation.

A scenario is the caregiver script. Only check definitions can change a verdict.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator


class ScenarioCategory(str, Enum):
    SAFETY = "safety"
    EMPATHY = "empathy"
    CONTEXT = "context"
    CONTINUITY = "continuity"
    CONFIDENTIAL = "confidential"


class Persona(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    age: int
    care_recipient: str
    care_duration: str
    context: dict[str, Any]


class TaskEvidence(BaseModel):
    """Visible task instructions selected by the scenario author or source exporter."""

    model_config = ConfigDict(extra="forbid")
    kind: Literal["draft", "grounded_answer"]
    recipient: str = ""
    purpose: str = ""
    required_details: list[str] = Field(default_factory=list)
    excluded_details: list[str] = Field(default_factory=list)
    source_excerpt: str = ""

    @model_validator(mode="after")
    def bounded_task(self):
        if self.kind == "draft" and not (self.recipient and self.purpose):
            raise ValueError("a draft task needs a recipient and purpose")
        if self.kind == "grounded_answer" and not self.source_excerpt:
            raise ValueError("a grounded answer task needs a source excerpt")
        if self.kind == "grounded_answer" and (
            self.recipient or self.purpose or self.required_details or self.excluded_details
        ):
            raise ValueError("draft requirements belong only to draft tasks")
        if set(self.required_details) & set(self.excluded_details):
            raise ValueError("a detail cannot be both required and excluded")
        if any(not text.strip() for text in self.required_details + self.excluded_details):
            raise ValueError("task details must be nonblank")
        return self

    def verify_visible(self, message: str) -> None:
        for text in (
            self.recipient,
            self.purpose,
            self.source_excerpt,
            *self.required_details,
            *self.excluded_details,
        ):
            if text and text not in message:
                raise ValueError("task evidence must quote the caregiver's actual request")


class BranchCondition(BaseModel):
    """A yes/no question the judge answers about the preceding assistant reply."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    # Only a judged question may branch: keyword rules cannot tell endorsement
    # from refusal, acknowledgment, or a quotation of the caregiver.
    type: Literal["noul"]
    instructions: str | dict[str, Any]
    min: float = Field(default=0.65, gt=0, lt=1)

    @model_validator(mode="after")
    def has_question(self):
        text = self.instructions
        if not (text.strip() if isinstance(text, str) else text):
            raise ValueError("noul condition requires instructions")
        return self


class Branch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    branch_id: str | None = None
    condition: BranchCondition
    user_message: str

    @model_validator(mode="after")
    def message_is_nonblank(self):
        if not self.user_message.strip():
            raise ValueError("branch user_message must be nonblank")
        return self


class Turn(BaseModel):
    model_config = ConfigDict(extra="allow")
    turn_number: StrictInt = Field(ge=1)
    user_message: str
    branches: list[Branch] = Field(default_factory=list)
    task: TaskEvidence | None = None

    @model_validator(mode="after")
    def task_is_visible(self):
        if self.task:
            self.task.verify_visible(self.user_message)
            for branch in self.branches:
                self.task.verify_visible(branch.user_message)
        return self

    @model_validator(mode="before")
    @classmethod
    def one_authoring_contract(cls, data):
        if isinstance(data, dict) and set(data) & {
            "t",
            "rubric",
            "expected_behaviors",
            "autofail_triggers",
            "autofail_rubric",
            "rubric_criteria",
            "gray_zone_scoring",
            "criteria",
        }:
            raise ValueError("retired turn fields; use turn_number; check YAML owns grading")
        return data


class Session(BaseModel):
    model_config = ConfigDict(extra="allow")
    session_number: StrictInt = Field(ge=1)
    time_elapsed: str
    turns: list[Turn] = Field(min_length=1)
    session_context: str | None = None


class Scenario(BaseModel):
    model_config = ConfigDict(extra="allow")
    scenario_id: str = Field(min_length=1)
    title: str
    persona: Persona
    category: ScenarioCategory
    turns: list[Turn] = Field(default_factory=list)
    sessions: list[Session] = Field(default_factory=list)
    contrast_group: str | None = None
    contrast_variable: str | None = None

    @model_validator(mode="before")
    @classmethod
    def no_retired_scoring(cls, data):
        if isinstance(data, dict) and set(data) & {
            "tier",
            "scoring_dimensions",
            "eligible_modes",
            "dif_variables",
            "failure_mode_tags",
            "cue_anchors",
            "risk_triggers",
        }:
            raise ValueError("retired scenario fields; use category; check YAML owns scoring")
        return data

    @model_validator(mode="after")
    def one_dialogue(self):
        if bool(self.turns) == bool(self.sessions):
            raise ValueError("a scenario needs either turns or sessions")
        numbers = [t.turn_number for t in self.all_turns]
        if numbers != sorted(set(numbers)):
            raise ValueError("turn numbers must be unique and increasing across sessions")
        return self

    @property
    def all_turns(self) -> list[Turn]:
        return (
            [t for session in self.sessions for t in session.turns] if self.sessions else self.turns
        )
