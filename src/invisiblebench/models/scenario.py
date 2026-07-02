"""Canonical scenario models for the benchmark."""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, computed_field

from invisiblebench.models._types import JsonMap


class ScenarioCategory(str, Enum):
    """Top-level benchmark categories."""

    SAFETY = "safety"
    EMPATHY = "empathy"
    CONTEXT = "context"
    CONTINUITY = "continuity"
    CONFIDENTIAL = "confidential"


class ScoringDimension(str, Enum):
    """Scenario-level scoring dimensions carried in scenario metadata."""

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


def retired_rubric_paths(value: Any, path: str = "") -> list[str]:
    """Find retired scenario rubric keys anywhere in a JSON-like payload."""
    hits: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            next_path = f"{path}.{key}" if path else str(key)
            if key in {"autofail_rubric", "rubric_criteria"}:
                hits.append(next_path)
            hits.extend(retired_rubric_paths(nested, next_path))
    elif isinstance(value, list):
        for idx, nested in enumerate(value):
            hits.extend(retired_rubric_paths(nested, f"{path}[{idx}]"))
    return hits


def _normalize_turn_data(data: JsonMap) -> JsonMap:
    normalized = dict(data)
    turn_number = normalized.get("turn_number")
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
    source_path: str | None = None,
) -> JsonMap:
    normalized = dict(data)
    if "tier" in normalized:
        raise ValueError("Scenario uses 'tier' field. Use 'category' instead.")
    retired_rubrics = retired_rubric_paths(normalized)
    if retired_rubrics:
        joined = ", ".join(retired_rubrics)
        raise ValueError(
            f"Scenario uses retired rubric dialect at {joined}; fold it into "
            "`rubric` criteria with kind: binary|ordinal|autofail."
        )
    if source_path is not None:
        normalized["source_path"] = source_path
    if "turns" in normalized:
        normalized["turns"] = [_normalize_turn_data(turn) for turn in normalized.get("turns", [])]
    if "sessions" in normalized:
        normalized["sessions"] = [
            _normalize_session_data(session) for session in normalized.get("sessions", [])
        ]
    return normalized


class Persona(BaseModel):
    name: str
    age: int
    care_recipient: str
    care_duration: str
    context: dict[str, Any]
    role: str | None = None
    gender: str | None = None
    race_ethnicity: str | None = None
    income_bracket: str | None = None
    employment: str | None = None
    education: str | None = None
    primary_language: str | None = None
    care_hours_per_week: int | None = None
    living_situation: str | None = None

    @classmethod
    def from_dict(cls, data: JsonMap) -> "Persona":
        return cls.model_validate(data)


class Turn(BaseModel):
    turn_number: int
    user_message: str
    branches: list[dict[str, Any]] = Field(default_factory=list)
    expected_behaviors: list[str] = Field(default_factory=list)
    autofail_triggers: list[str] = Field(default_factory=list)
    facts: list[str] = Field(default_factory=list)
    updates: list[str] = Field(default_factory=list)
    # Unified rubric: criteria objects with kind: binary | ordinal | autofail.
    rubric: list[dict[str, Any]] = Field(default_factory=list)
    probes: list[dict[str, Any]] = Field(default_factory=list)
    context_notes: str | None = None

    @classmethod
    def from_dict(cls, data: JsonMap) -> "Turn":
        return cls.model_validate(_normalize_turn_data(data))


class Session(BaseModel):
    session_number: int
    time_elapsed: str
    turns: list[Turn]
    session_context: str | None = None

    @classmethod
    def from_dict(cls, data: JsonMap) -> "Session":
        return cls.model_validate(_normalize_session_data(data))


class Scenario(BaseModel):
    scenario_id: str
    title: str
    persona: Persona
    category: ScenarioCategory
    turns: list[Turn] = Field(default_factory=list)
    sessions: list[Session] = Field(default_factory=list)
    scoring_dimensions: dict[ScoringDimension, int] = Field(default_factory=dict)
    dif_variables: list[str] = Field(default_factory=list)
    probes: list[dict[str, Any]] = Field(default_factory=list)
    risk_triggers: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_path: str | None = None
    contrast_group: str | None = None
    contrast_variable: str | None = None

    @computed_field
    @property
    def is_multi_session(self) -> bool:
        return bool(self.sessions)

    @computed_field
    @property
    def total_turns(self) -> int:
        if self.is_multi_session:
            return sum(len(session.turns) for session in self.sessions)
        return len(self.turns)

    @computed_field
    @property
    def all_turns(self) -> list[Turn]:
        if self.is_multi_session:
            turns: list[Turn] = []
            for session in self.sessions:
                turns.extend(session.turns)
            return turns
        return self.turns

    @computed_field
    @property
    def display_name(self) -> str:
        return self.title or self.scenario_id.replace("_", " ").title()

    def get_turn(self, turn_number: int) -> Turn | None:
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
    def from_file(cls, path: str | Path) -> "Scenario":
        scenario_path = Path(path)
        with open(scenario_path) as f:
            data = json.load(f)
        return cls.from_dict(data, source_path=str(scenario_path))

    @classmethod
    def from_dict(
        cls,
        data: JsonMap,
        source_path: str | None = None,
    ) -> "Scenario":
        return cls.model_validate(_normalize_scenario_data(data, source_path=source_path))
