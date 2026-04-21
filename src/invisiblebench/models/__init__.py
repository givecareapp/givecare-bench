"""Data models for scenarios, results, and config."""

from __future__ import annotations

from pydantic import Field

from invisiblebench.models.config import (
    MODELS_FULL,
    BenchmarkConfig,
    ModelConfig,
    ScoringConfig,
)
from invisiblebench.models.results import (
    BatchResult,
    DimensionScores,
    EvalResult,
    FailureCategory,
    ResultTiming,
    ScenarioResult,
)
from invisiblebench.models.scenario import (
    CategoryLevel,
    DimensionType,
    PersonaModel,
    ScenarioModel,
    SessionModel,
    TurnModel,
)

__all__ = [
    "BenchmarkConfig",
    "ModelConfig",
    "ScoringConfig",
    "MODELS_FULL",
    "BatchResult",
    "DimensionScores",
    "EvalResult",
    "FailureCategory",
    "ResultTiming",
    "ScenarioResult",
    "CategoryLevel",
    "DimensionType",
    "PersonaModel",
    "ScenarioModel",
    "SessionModel",
    "TurnModel",
    "Turn",
    "Session",
    "Persona",
    "Scenario",
]


class Turn(TurnModel):
    """Compatibility wrapper around ``TurnModel``."""


class Session(SessionModel):
    """Compatibility wrapper around ``SessionModel``."""

    turns: list[Turn] = Field(default_factory=list)


class Persona(PersonaModel):
    """Compatibility wrapper around ``PersonaModel``."""


class Scenario(ScenarioModel):
    """Compatibility wrapper around ``ScenarioModel``."""

    persona: Persona
    turns: list[Turn] = Field(default_factory=list)
    sessions: list[Session] = Field(default_factory=list)


Session.model_rebuild()
Scenario.model_rebuild()
