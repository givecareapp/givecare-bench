"""Scenario models and shared enums."""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, computed_field


class CategoryLevel(str, Enum):
    """Benchmark scenario categories."""

    SAFETY = "safety"
    EMPATHY = "empathy"
    CONTEXT = "context"
    CONTINUITY = "continuity"
    CONFIDENTIAL = "confidential"


class DimensionType(str, Enum):
    """Scenario sub-dimensions used for rubric metadata."""

    CRISIS_SAFETY = "crisis_safety"
    REGULATORY_FITNESS = "regulatory_fitness"
    TRAUMA_INFORMED_FLOW = "trauma_informed_flow"
    BELONGING_CULTURAL_FITNESS = "belonging_cultural_fitness"
    RELATIONAL_QUALITY = "relational_quality"
    ACTIONABLE_SUPPORT = "actionable_support"
    LONGITUDINAL_CONSISTENCY = "longitudinal_consistency"
    MEMORY_HYGIENE = "memory_hygiene"
    BOUNDARIES = "boundaries"
    GRAY_ZONE = "gray_zone"


JsonMap = dict[str, Any]


def _normalize_turn_data(data: JsonMap) -> JsonMap:
    normalized = dict(data)
    turn_number = normalized.get("turn_number", normalized.get("t"))
    if turn_number is None:
        raise KeyError("turn_number")
    normalized["turn_number"] = turn_number
    return normalized


def _normalize_session_data(data: JsonMap) -> JsonMap:
    normalized = dict(data)
    normalized["turns"] = [_normalize_turn_data(turn) for turn in normalized.get("turns", [])]
    return normalized


def _normalize_scenario_data(
    data: JsonMap,
    *,
    source_path: Optional[str] = None,
) -> JsonMap:
    normalized = dict(data)
    if "tier" in normalized and "category" not in normalized:
        raise ValueError("Scenario uses 'tier' field. Use 'category' instead.")
    if source_path is not None:
        normalized["source_path"] = source_path
    if "turns" in normalized:
        normalized["turns"] = [_normalize_turn_data(turn) for turn in normalized.get("turns", [])]
    if "sessions" in normalized:
        normalized["sessions"] = [
            _normalize_session_data(session) for session in normalized.get("sessions", [])
        ]
    return normalized


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

    @classmethod
    def from_dict(cls, data: JsonMap) -> "PersonaModel":
        return cls.model_validate(data)


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

    @property
    def t(self) -> int:
        return self.turn_number

    @classmethod
    def from_dict(cls, data: JsonMap) -> "TurnModel":
        return cls.model_validate(_normalize_turn_data(data))


class SessionModel(BaseModel):
    session_number: int
    time_elapsed: str
    turns: list[TurnModel]
    session_context: Optional[str] = None

    @classmethod
    def from_dict(cls, data: JsonMap) -> "SessionModel":
        return cls.model_validate(_normalize_session_data(data))


class ScenarioModel(BaseModel):
    scenario_id: str
    title: str
    persona: PersonaModel
    category: CategoryLevel
    turns: list[TurnModel] = Field(default_factory=list)
    sessions: list[SessionModel] = Field(default_factory=list)
    scoring_dimensions: dict[DimensionType, int] = Field(default_factory=dict)
    dif_variables: list[str] = Field(default_factory=list)
    probes: list[dict[str, Any]] = Field(default_factory=list)
    risk_triggers: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
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
            turns: list[TurnModel] = []
            for session in self.sessions:
                turns.extend(session.turns)
            return turns
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
        scenario_path = Path(path)
        with open(scenario_path) as f:
            data = json.load(f)
        return cls.from_dict(data, source_path=str(scenario_path))

    @classmethod
    def from_dict(
        cls,
        data: JsonMap,
        source_path: Optional[str] = None,
    ) -> "ScenarioModel":
        return cls.model_validate(_normalize_scenario_data(data, source_path=source_path))
