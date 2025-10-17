"""
Data models for LongitudinalBench scenarios, turns, and evaluation results.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum


class TierLevel(Enum):
    """Benchmark tier levels."""
    TIER_1 = "tier_1"  # 3-5 turns, foundational
    TIER_2 = "tier_2"  # 8-12 turns, attachment
    TIER_3 = "tier_3"  # 20+ turns across 3 sessions, longitudinal


class DimensionType(Enum):
    """Evaluation dimensions."""
    CRISIS_SAFETY = "crisis_safety"
    REGULATORY_FITNESS = "regulatory_fitness"
    TRAUMA_INFORMED_FLOW = "trauma_informed_flow"
    BELONGING_CULTURAL_FITNESS = "belonging_cultural_fitness"
    RELATIONAL_QUALITY = "relational_quality"
    ACTIONABLE_SUPPORT = "actionable_support"
    LONGITUDINAL_CONSISTENCY = "longitudinal_consistency"
    MEMORY_HYGIENE = "memory_hygiene"


@dataclass
class Turn:
    """A single conversational turn in a scenario."""
    turn_number: int
    user_message: str
    expected_behaviors: List[str]
    autofail_triggers: List[str] = field(default_factory=list)
    context_notes: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Turn':
        """Create Turn from dictionary."""
        return cls(
            turn_number=data["turn_number"],
            user_message=data["user_message"],
            expected_behaviors=data["expected_behaviors"],
            autofail_triggers=data.get("autofail_triggers", []),
            context_notes=data.get("context_notes")
        )


@dataclass
class Session:
    """A session within a Tier 3 multi-session scenario."""
    session_number: int
    time_elapsed: str  # e.g., "3 months"
    turns: List[Turn]
    session_context: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Session':
        """Create Session from dictionary."""
        return cls(
            session_number=data["session_number"],
            time_elapsed=data["time_elapsed"],
            turns=[Turn.from_dict(t) for t in data["turns"]],
            session_context=data.get("session_context")
        )


@dataclass
class Persona:
    """User persona with demographic and context information."""
    name: str
    age: int
    role: str
    care_recipient: str
    care_duration: str
    context: Dict[str, Any]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Persona':
        """Create Persona from dictionary."""
        return cls(
            name=data["name"],
            age=data["age"],
            role=data["role"],
            care_recipient=data["care_recipient"],
            care_duration=data["care_duration"],
            context=data["context"]
        )


@dataclass
class Scenario:
    """A complete test scenario."""
    scenario_id: str
    tier: TierLevel
    title: str
    persona: Persona
    turns: List[Turn] = field(default_factory=list)
    sessions: List[Session] = field(default_factory=list)
    scoring_dimensions: Dict[DimensionType, int] = field(default_factory=dict)
    dif_variables: List[str] = field(default_factory=list)

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
    def from_dict(cls, data: Dict[str, Any]) -> 'Scenario':
        """Create Scenario from dictionary."""
        tier = TierLevel(data["tier"])
        persona = Persona.from_dict(data["persona"])

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
            turns=turns,
            sessions=sessions,
            scoring_dimensions=scoring_dimensions,
            dif_variables=data.get("dif_variables", [])
        )


@dataclass
class ModelResponse:
    """A model's response to a user message."""
    model_name: str
    response_text: str
    turn_number: int
    session_number: Optional[int] = None
    latency_ms: Optional[float] = None
    tokens_used: Optional[int] = None


@dataclass
class JudgeEvaluation:
    """Evaluation from a single judge."""
    judge_name: str
    judge_model: str
    dimension_scores: Dict[DimensionType, float]
    reasoning: str
    autofail_triggered: bool = False
    autofail_reason: Optional[str] = None
    raw_response: Optional[str] = None


@dataclass
class TurnEvaluation:
    """Complete evaluation of a single turn."""
    turn_number: int
    session_number: Optional[int]
    model_response: ModelResponse
    judge_evaluations: List[JudgeEvaluation]
    aggregated_scores: Dict[DimensionType, float] = field(default_factory=dict)
    autofail: bool = False
    autofail_reason: Optional[str] = None


@dataclass
class ScenarioResult:
    """Complete results for a scenario evaluation."""
    scenario_id: str
    model_name: str
    tier: TierLevel
    turn_evaluations: List[TurnEvaluation]
    final_scores: Dict[DimensionType, float] = field(default_factory=dict)
    total_score: float = 0.0
    max_possible_score: float = 0.0
    autofail_count: int = 0
    passed: bool = True
    execution_time_seconds: float = 0.0

    def calculate_totals(self):
        """Calculate total scores and pass/fail status."""
        # Sum up dimension scores
        dimension_totals = {}
        for turn_eval in self.turn_evaluations:
            for dim, score in turn_eval.aggregated_scores.items():
                dimension_totals[dim] = dimension_totals.get(dim, 0) + score

        self.final_scores = dimension_totals
        self.total_score = sum(dimension_totals.values())

        # Count autofails
        self.autofail_count = sum(1 for te in self.turn_evaluations if te.autofail)
        self.passed = self.autofail_count == 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON export."""
        return {
            "scenario_id": self.scenario_id,
            "model_name": self.model_name,
            "tier": self.tier.value,
            "total_score": self.total_score,
            "max_possible_score": self.max_possible_score,
            "final_scores": {dim.value: score for dim, score in self.final_scores.items()},
            "autofail_count": self.autofail_count,
            "passed": self.passed,
            "execution_time_seconds": self.execution_time_seconds,
            "turn_count": len(self.turn_evaluations)
        }


@dataclass
class BenchmarkRun:
    """Complete benchmark run across multiple scenarios and models."""
    run_id: str
    timestamp: str
    models_tested: List[str]
    scenarios: List[str]
    results: List[ScenarioResult] = field(default_factory=list)

    def get_leaderboard(self) -> List[Dict[str, Any]]:
        """Generate leaderboard rankings."""
        model_scores = {}

        for result in self.results:
            if result.model_name not in model_scores:
                model_scores[result.model_name] = {
                    "total_score": 0,
                    "max_possible": 0,
                    "autofails": 0,
                    "scenarios_passed": 0,
                    "scenarios_total": 0
                }

            model_scores[result.model_name]["total_score"] += result.total_score
            model_scores[result.model_name]["max_possible"] += result.max_possible_score
            model_scores[result.model_name]["autofails"] += result.autofail_count
            model_scores[result.model_name]["scenarios_passed"] += 1 if result.passed else 0
            model_scores[result.model_name]["scenarios_total"] += 1

        # Convert to list and sort by total score
        leaderboard = []
        for model_name, scores in model_scores.items():
            leaderboard.append({
                "model": model_name,
                "score": scores["total_score"],
                "max_possible": scores["max_possible"],
                "percentage": round((scores["total_score"] / scores["max_possible"] * 100) if scores["max_possible"] > 0 else 0, 1),
                "autofails": scores["autofails"],
                "scenarios_passed": f"{scores['scenarios_passed']}/{scores['scenarios_total']}"
            })

        leaderboard.sort(key=lambda x: x["score"], reverse=True)

        # Add rank
        for idx, entry in enumerate(leaderboard, 1):
            entry["rank"] = idx

        return leaderboard
