"""
Decorators for declarative scorer registration.

Usage:
    from invisiblebench.evaluation.decorators import rubric, ScorerRegistry

    @rubric(
        name="safety",
        weight=0.25,
        dimension="safety",
        hard_fail_on_zero=True,
        description="Evaluates crisis detection and response"
    )
    def safety_score(transcript, scenario, rules, **kwargs) -> float:
        # Scoring logic
        return 0.85

    # Get all registered scorers
    registry = ScorerRegistry()
    for scorer in registry.scorers:
        result = scorer(transcript, scenario, rules)
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from typing import Callable, Optional


@dataclass
class ScorerMetadata:
    """Metadata for a registered scorer."""

    name: str
    weight: float
    dimension: str
    hard_fail_on_zero: bool = False
    description: Optional[str] = None
    requires_llm: bool = False
    order: int = 100  # Lower = runs first


@dataclass
class RegisteredScorer:
    """A scorer function with its metadata."""

    func: Callable[..., float]
    metadata: ScorerMetadata

    def __call__(self, *args, **kwargs) -> float:
        return self.func(*args, **kwargs)


class ScorerRegistry:
    """Registry for decorated scorers. Singleton pattern."""

    _instance: Optional["ScorerRegistry"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._scorers = []
        return cls._instance

    def register(self, scorer: RegisteredScorer) -> None:
        """Register a new scorer."""
        self._scorers.append(scorer)
        # Keep sorted by order
        self._scorers.sort(key=lambda s: s.metadata.order)

    @property
    def scorers(self) -> list[RegisteredScorer]:
        """Get all registered scorers."""
        return self._scorers

    def get(self, name: str) -> Optional[RegisteredScorer]:
        """Get a scorer by name."""
        for scorer in self._scorers:
            if scorer.metadata.name == name:
                return scorer
        return None

    def by_dimension(self, dimension: str) -> list[RegisteredScorer]:
        """Get all scorers for a dimension."""
        return [s for s in self._scorers if s.metadata.dimension == dimension]

    def weights(self) -> dict[str, float]:
        """Get weight mapping for all scorers."""
        return {s.metadata.name: s.metadata.weight for s in self._scorers}

    def clear(self) -> None:
        """Clear all registered scorers (for testing)."""
        self._scorers = []


def rubric(
    name: str,
    weight: float = 0.1,
    dimension: Optional[str] = None,
    hard_fail_on_zero: bool = False,
    description: Optional[str] = None,
    requires_llm: bool = False,
    order: int = 100,
) -> Callable:
    """
    Decorator for registering a scorer function.

    Args:
        name: Unique name for this scorer
        weight: Weight in overall score (0-1)
        dimension: Scoring dimension (e.g., "safety", "memory", "trauma")
        hard_fail_on_zero: If True, zero score triggers hard fail
        description: Human-readable description
        requires_llm: Whether this scorer needs LLM calls
        order: Execution order (lower = first)

    Returns:
        Decorated function registered with the scorer registry

    Example:
        @rubric(name="safety", weight=0.25, hard_fail_on_zero=True)
        def safety_score(transcript, scenario, rules, **kwargs) -> float:
            return 0.85
    """

    def decorator(func: Callable[..., float]) -> RegisteredScorer:
        metadata = ScorerMetadata(
            name=name,
            weight=weight,
            dimension=dimension or name,
            hard_fail_on_zero=hard_fail_on_zero,
            description=description or func.__doc__,
            requires_llm=requires_llm,
            order=order,
        )

        @wraps(func)
        def wrapper(*args, **kwargs) -> float:
            result = func(*args, **kwargs)
            # Ensure result is a float between 0 and 1
            if not isinstance(result, (int, float)):
                raise TypeError(f"Scorer {name} must return a float, got {type(result)}")
            return max(0.0, min(1.0, float(result)))

        registered = RegisteredScorer(func=wrapper, metadata=metadata)
        ScorerRegistry().register(registered)
        return registered

    return decorator


# Convenience function to get the global registry
def get_registry() -> ScorerRegistry:
    """Get the global scorer registry."""
    return ScorerRegistry()
