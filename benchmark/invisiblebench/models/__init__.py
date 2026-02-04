"""
Data models for InvisibleBench scenarios and turns.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

# Re-export Pydantic config models
from invisiblebench.models.config import (
    BenchmarkConfig,
    ModelConfig,
    ScoringConfig,
    MODELS_MINIMAL,
    MODELS_FULL,
)

# Re-export Pydantic result models
from invisiblebench.models.results import (
    BatchResult,
    DimensionScores,
    EvalResult,
    FailureCategory,
    ResultTiming,
    ScenarioResult,
    TierSummary,
)

# Re-export Pydantic scenario models
from invisiblebench.models.scenario import (
    PersonaModel,
    ScenarioModel,
    SessionModel,
    TurnModel,
)

__all__ = [
    # Config models
    "BenchmarkConfig",
    "ModelConfig",
    "ScoringConfig",
    "MODELS_MINIMAL",
    "MODELS_FULL",
    # Result models
    "BatchResult",
    "DimensionScores",
    "EvalResult",
    "FailureCategory",
    "ResultTiming",
    "ScenarioResult",
    "TierSummary",
    # Pydantic scenario models
    "PersonaModel",
    "ScenarioModel",
    "SessionModel",
    "TurnModel",
    # Legacy dataclass models (backwards compatibility)
    "TierLevel",
    "DimensionType",
    "Turn",
    "Session",
    "Persona",
    "Scenario",
]


class TierLevel(Enum):
    """Benchmark tier levels."""

    TIER_0 = "tier_0"  # 1-2 turns, smoke tests
    TIER_1 = "tier_1"  # 3-5 turns, foundational
    TIER_2 = "tier_2"  # 8-12 turns, attachment
    TIER_3 = "tier_3"  # 20+ turns across 3 sessions, longitudinal


class DimensionType(Enum):
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


@dataclass
class Turn:
    """A single conversational turn in a scenario."""

    turn_number: int
    user_message: str
    expected_behaviors: List[str] = field(default_factory=list)
    autofail_triggers: List[str] = field(default_factory=list)
    facts: List[str] = field(default_factory=list)
    updates: List[str] = field(default_factory=list)
    rubric_criteria: List[Dict[str, Any]] = field(default_factory=list)
    probes: List[Dict[str, Any]] = field(default_factory=list)
    context_notes: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Turn":
        """Create Turn from dictionary."""
        turn_number = data.get("turn_number", data.get("t"))
        if turn_number is None:
            raise KeyError("turn_number")
        return cls(
            turn_number=turn_number,
            user_message=data["user_message"],
            expected_behaviors=data.get("expected_behaviors", []),
            autofail_triggers=data.get("autofail_triggers", []),
            facts=data.get("facts", []),
            updates=data.get("updates", []),
            rubric_criteria=data.get("rubric_criteria", []),
            probes=data.get("probes", []),
            context_notes=data.get("context_notes"),
        )


@dataclass
class Session:
    """A session within a Tier 3 multi-session scenario."""

    session_number: int
    time_elapsed: str  # e.g., "3 months"
    turns: List[Turn]
    session_context: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        """Create Session from dictionary."""
        return cls(
            session_number=data["session_number"],
            time_elapsed=data["time_elapsed"],
            turns=[Turn.from_dict(t) for t in data["turns"]],
            session_context=data.get("session_context"),
        )


@dataclass
class Persona:
    """User persona with demographic and context information."""

    name: str
    age: int
    care_recipient: str
    care_duration: str
    context: Dict[str, Any]
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
    def from_dict(cls, data: Dict[str, Any]) -> "Persona":
        """Create Persona from dictionary."""
        return cls(
            name=data["name"],
            age=data["age"],
            care_recipient=data["care_recipient"],
            care_duration=data["care_duration"],
            context=data["context"],
            role=data.get("role"),
            gender=data.get("gender"),
            race_ethnicity=data.get("race_ethnicity"),
            income_bracket=data.get("income_bracket"),
            employment=data.get("employment"),
            education=data.get("education"),
            primary_language=data.get("primary_language"),
            care_hours_per_week=data.get("care_hours_per_week"),
            living_situation=data.get("living_situation"),
        )


@dataclass
class Scenario:
    """A complete test scenario."""

    scenario_id: str
    tier: TierLevel
    title: str
    persona: Persona
    category: Optional[DimensionType] = None
    turns: List[Turn] = field(default_factory=list)
    sessions: List[Session] = field(default_factory=list)
    scoring_dimensions: Dict[DimensionType, int] = field(default_factory=dict)
    dif_variables: List[str] = field(default_factory=list)
    probes: List[Dict[str, Any]] = field(default_factory=list)
    risk_triggers: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_multi_session(self) -> bool:
        """Check if scenario has multiple sessions (Tier 3)."""
        return len(self.sessions) > 0

    @property
    def total_turns(self) -> int:
        """Get total number of turns across all sessions."""
        if self.is_multi_session:
            return sum(len(session.turns) for session in self.sessions)
        return len(self.turns)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Scenario":
        """Create Scenario from dictionary."""
        tier = TierLevel(data["tier"])
        persona = Persona.from_dict(data["persona"])
        category = None
        if "category" in data:
            category = DimensionType(data["category"])

        # Parse turns or sessions based on structure
        turns = []
        sessions = []
        if "sessions" in data:
            sessions = [Session.from_dict(s) for s in data["sessions"]]
        elif "turns" in data:
            turns = [Turn.from_dict(t) for t in data["turns"]]

        # Parse scoring dimensions
        scoring_dimensions = {}
        if "scoring_dimensions" in data:
            for dim_str, max_score in data["scoring_dimensions"].items():
                dim = DimensionType(dim_str)
                scoring_dimensions[dim] = max_score

        return cls(
            scenario_id=data["scenario_id"],
            tier=tier,
            title=data["title"],
            persona=persona,
            category=category,
            turns=turns,
            sessions=sessions,
            scoring_dimensions=scoring_dimensions,
            dif_variables=data.get("dif_variables", []),
            probes=data.get("probes", []),
            risk_triggers=data.get("risk_triggers", []),
            metadata=data.get("metadata", {}),
        )
