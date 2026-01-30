"""Pydantic result models for InvisibleBench."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, computed_field


class ResultTiming(BaseModel):
    """Timing information for a result."""

    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    scenario_seconds: float = Field(default=0.0, ge=0)
    tier_seconds: float = Field(default=0.0, ge=0)
    total_seconds: float = Field(default=0.0, ge=0)

    @computed_field
    @property
    def scenario_formatted(self) -> str:
        """Format scenario time as M:SS."""
        return f"{int(self.scenario_seconds // 60)}:{int(self.scenario_seconds % 60):02d}"

    @computed_field
    @property
    def total_formatted(self) -> str:
        """Format total time as M:SS."""
        return f"{int(self.total_seconds // 60)}:{int(self.total_seconds % 60):02d}"


class FailureCategory(BaseModel):
    """Categorized failure information."""

    categories: list[str] = Field(default_factory=list)
    details: dict[str, list[str]] = Field(default_factory=dict)
    primary_category: Optional[str] = None
    count: int = Field(default=0, ge=0)


class DimensionScores(BaseModel):
    """Scores for each evaluation dimension."""

    memory: Optional[float] = Field(default=None, ge=0, le=1)
    trauma: Optional[float] = Field(default=None, ge=0, le=1)
    belonging: Optional[float] = Field(default=None, ge=0, le=1)
    compliance: Optional[float] = Field(default=None, ge=0, le=1)
    safety: Optional[float] = Field(default=None, ge=0, le=1)

    def to_dict(self) -> dict[str, float]:
        """Return non-None scores as a dictionary."""
        return {k: v for k, v in self.model_dump().items() if v is not None}

    def low_scores(self, threshold: float = 0.5) -> dict[str, float]:
        """Return scores below threshold."""
        return {k: v for k, v in self.to_dict().items() if v < threshold}


class ScenarioResult(BaseModel):
    """Result from evaluating a single scenario."""

    # Identification
    scenario_id: str = Field(..., description="Scenario identifier")
    scenario: str = Field(..., description="Scenario display name")
    model: str = Field(..., description="Model display name")
    model_id: str = Field(default="", description="Model identifier")
    tier: int = Field(..., ge=0, le=3, description="Scenario tier")

    # Scores
    overall_score: float = Field(..., ge=0, le=1)
    dimensions: DimensionScores = Field(default_factory=DimensionScores)

    # Failure information
    hard_fail: bool = Field(default=False)
    hard_fail_reasons: list[str] = Field(default_factory=list)
    failure_categories: FailureCategory = Field(default_factory=FailureCategory)
    status: Literal["pass", "fail", "error"] = Field(default="pass")

    # Metadata
    cost: float = Field(default=0.0, ge=0)
    timing: ResultTiming = Field(default_factory=ResultTiming)
    transcript_path: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

    @computed_field
    @property
    def score_percent(self) -> int:
        """Return overall score as percentage."""
        return int(self.overall_score * 100)

    @computed_field
    @property
    def is_failure(self) -> bool:
        """Return True if this result counts as a failure."""
        return self.hard_fail or self.overall_score < 0.5 or self.status in {"fail", "error"}


class TierSummary(BaseModel):
    """Summary statistics for a tier."""

    tier: int
    count: int = Field(default=0, ge=0)
    passed: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    avg_score: float = Field(default=0.0, ge=0, le=1)
    total_cost: float = Field(default=0.0, ge=0)
    elapsed_seconds: float = Field(default=0.0, ge=0)

    @computed_field
    @property
    def score_percent(self) -> int:
        return int(self.avg_score * 100)


class EvalResult(BaseModel):
    """Complete evaluation result for a model across all scenarios."""

    # Model info
    model: str = Field(..., description="Model display name")
    model_id: str = Field(default="", description="Model identifier")

    # Results
    scenarios: list[ScenarioResult] = Field(default_factory=list)
    tier_summaries: dict[int, TierSummary] = Field(default_factory=dict)

    # Aggregate stats
    total_scenarios: int = Field(default=0, ge=0)
    passed: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    overall_score: float = Field(default=0.0, ge=0, le=1)
    total_cost: float = Field(default=0.0, ge=0)
    elapsed_seconds: float = Field(default=0.0, ge=0)

    # Metadata
    mode: str = Field(default="minimal")
    timestamp: datetime = Field(default_factory=datetime.now)

    @computed_field
    @property
    def score_percent(self) -> int:
        return int(self.overall_score * 100)

    @computed_field
    @property
    def failures(self) -> list[ScenarioResult]:
        """Return all failed scenarios."""
        return [s for s in self.scenarios if s.is_failure]

    def compute_summaries(self) -> None:
        """Compute tier summaries and aggregate stats from scenarios."""
        self.total_scenarios = len(self.scenarios)
        self.passed = sum(1 for s in self.scenarios if not s.is_failure)
        self.failed = self.total_scenarios - self.passed
        self.total_cost = sum(s.cost for s in self.scenarios)

        if self.scenarios:
            self.overall_score = sum(s.overall_score for s in self.scenarios) / len(self.scenarios)

        # Group by tier
        by_tier: dict[int, list[ScenarioResult]] = {}
        for s in self.scenarios:
            if s.tier not in by_tier:
                by_tier[s.tier] = []
            by_tier[s.tier].append(s)

        self.tier_summaries = {}
        for tier, results in by_tier.items():
            self.tier_summaries[tier] = TierSummary(
                tier=tier,
                count=len(results),
                passed=sum(1 for r in results if not r.is_failure),
                failed=sum(1 for r in results if r.is_failure),
                avg_score=sum(r.overall_score for r in results) / len(results) if results else 0,
                total_cost=sum(r.cost for r in results),
            )


class BatchResult(BaseModel):
    """Result from a complete benchmark run with multiple models."""

    models: list[EvalResult] = Field(default_factory=list)
    mode: str = Field(default="minimal")
    total_scenarios: int = Field(default=0, ge=0)
    total_cost: float = Field(default=0.0, ge=0)
    elapsed_seconds: float = Field(default=0.0, ge=0)
    timestamp: datetime = Field(default_factory=datetime.now)

    def compute_totals(self) -> None:
        """Compute totals from model results."""
        self.total_scenarios = sum(m.total_scenarios for m in self.models)
        self.total_cost = sum(m.total_cost for m in self.models)
