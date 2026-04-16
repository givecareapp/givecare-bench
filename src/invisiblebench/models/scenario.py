"""Scenario models."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, computed_field


class PersonaModel(BaseModel):

    name: str
    age: int
    care_recipient: str
    care_duration: str
    context: dict[str, Any]
    role: Optional[str] = None
    gender: Optional[str] = None
    race_ethnicity: Optional[str] = None
    income_bracket: Optional[str] = None
    employment: Optional[str] = None
    education: Optional[str] = None
    primary_language: Optional[str] = None
    care_hours_per_week: Optional[int] = None
    living_situation: Optional[str] = None


class TurnModel(BaseModel):

    turn_number: int
    user_message: str
    branches: list[dict[str, Any]] = Field(default_factory=list)
    expected_behaviors: list[str] = Field(default_factory=list)
    autofail_triggers: list[str] = Field(default_factory=list)
    facts: list[str] = Field(default_factory=list)
    updates: list[str] = Field(default_factory=list)
    rubric: list[dict[str, Any]] = Field(default_factory=list)
    autofail_rubric: list[dict[str, Any]] = Field(default_factory=list)
    rubric_criteria: list[dict[str, Any]] = Field(default_factory=list)
    probes: list[dict[str, Any]] = Field(default_factory=list)
    context_notes: Optional[str] = None


class SessionModel(BaseModel):

    session_number: int
    time_elapsed: str
    turns: list[TurnModel]
    session_context: Optional[str] = None


class ScenarioModel(BaseModel):

    scenario_id: str
    title: str
    persona: PersonaModel
    category: str  # "safety", "empathy", "context", "continuity", "confidential"
    turns: list[TurnModel] = Field(default_factory=list)
    sessions: list[SessionModel] = Field(default_factory=list)
    scoring_dimensions: dict[str, int] = Field(default_factory=dict)
    dif_variables: list[str] = Field(default_factory=list)
    probes: list[dict[str, Any]] = Field(default_factory=list)
    risk_triggers: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Source tracking
    source_path: Optional[str] = None

    @computed_field
    @property
    def is_multi_session(self) -> bool:
        return len(self.sessions) > 0

    @computed_field
    @property
    def total_turns(self) -> int:
        if self.is_multi_session:
            return sum(len(session.turns) for session in self.sessions)
        return len(self.turns)

    @computed_field
    @property
    def all_turns(self) -> list[TurnModel]:
        if self.is_multi_session:
            result = []
            for session in self.sessions:
                result.extend(session.turns)
            return result
        return self.turns

    @computed_field
    @property
    def display_name(self) -> str:
        return self.title or self.scenario_id.replace("_", " ").title()

    def get_turn(self, turn_number: int) -> Optional[TurnModel]:
        for turn in self.all_turns:
            if turn.turn_number == turn_number:
                return turn
        return None

    def get_expected_behaviors(self, turn_number: int) -> list[str]:
        turn = self.get_turn(turn_number)
        return turn.expected_behaviors if turn else []

    def get_autofail_triggers(self, turn_number: int) -> list[str]:
        turn = self.get_turn(turn_number)
        return turn.autofail_triggers if turn else []

    @classmethod
    def from_file(cls, path: str | Path) -> "ScenarioModel":
        path = Path(path)
        with open(path) as f:
            data = json.load(f)
        data["source_path"] = str(path)
        return cls.model_validate(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any], source_path: Optional[str] = None) -> "ScenarioModel":
        if source_path:
            data = {**data, "source_path": source_path}
        return cls.model_validate(data)
