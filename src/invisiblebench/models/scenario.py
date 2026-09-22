"""One scenario contract for authoring and transcript generation.

Criteria are author notes. Only check definitions can change a verdict.
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


class Criterion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = Field(min_length=1)
    expect: bool = True
    examples: list[str] = Field(default_factory=list)


class BranchCondition(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    type: Literal["contains_any", "contains_all", "not_contains", "regex", "noul"]
    values: list[str] | None = None
    pattern: str | None = None
    instructions: str | dict[str, Any] | None = None
    min: float = Field(default=0.65, gt=0, lt=1)

    @model_validator(mode="after")
    def condition_shape(self):
        field = "instructions" if self.type == "noul" else "pattern" if self.type == "regex" else "values"
        allowed = {"type", field} | ({"min"} if self.type == "noul" else set())
        if self.model_fields_set - allowed or not getattr(self, field):
            raise ValueError(f"{self.type} condition requires {field} and no unrelated fields")
        return self


class Branch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    branch_id: str | None = None
    condition: BranchCondition
    user_message: str
    criteria: list[Criterion] = Field(default_factory=list)


class Turn(BaseModel):
    model_config = ConfigDict(extra="allow")
    turn_number: StrictInt = Field(ge=1)
    user_message: str
    branches: list[Branch] = Field(default_factory=list)
    criteria: list[Criterion] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def one_authoring_contract(cls, data):
        if isinstance(data, dict) and set(data) & {"t", "rubric", "expected_behaviors", "autofail_triggers", "autofail_rubric", "rubric_criteria", "gray_zone_scoring"}:
            raise ValueError("retired turn fields; use turn_number and descriptive criteria")
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
    eligible_modes: list[str] = Field(default_factory=list)
    contrast_group: str | None = None
    contrast_variable: str | None = None

    @model_validator(mode="before")
    @classmethod
    def no_retired_scoring(cls, data):
        if isinstance(data, dict) and set(data) & {"tier", "scoring_dimensions"}:
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
        return [t for session in self.sessions for t in session.turns] if self.sessions else self.turns
