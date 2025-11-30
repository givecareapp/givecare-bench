"""
Public scoring API for InvisibleBench.

This module provides a clean interface for external consumers (like givecare-tune)
to score transcripts without needing to understand the internal orchestrator details.

Usage:
    from invisiblebench import score

    result = score(
        transcript_path="path/to/transcript.jsonl",
        scenario_path="path/to/scenario.json",
        rules_path="path/to/rules.yaml"
    )

    print(result["overall_percentage"])  # 0-100
    print(result["dimension_scores"])    # Per-dimension breakdowns
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from invisiblebench.evaluation.orchestrator import ScoringOrchestrator


# Default paths relative to package
_PACKAGE_ROOT = Path(__file__).parent.parent.parent
_DEFAULT_SCORING_CONFIG = _PACKAGE_ROOT / "configs" / "scoring.yaml"
_DEFAULT_RULES_PATH = _PACKAGE_ROOT / "configs" / "rules" / "base.yaml"


def score(
    transcript_path: str,
    scenario_path: str,
    rules_path: Optional[str] = None,
    scoring_config_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Score a transcript against a scenario.

    This is the primary public API for InvisibleBench. External training pipelines
    (like givecare-tune) should use this function to evaluate model outputs.

    Args:
        transcript_path: Path to JSONL transcript file.
            Format: One JSON object per line with keys:
            - "turn": int (1-indexed turn number)
            - "role": "user" | "assistant"
            - "content": str (message text)
        scenario_path: Path to scenario JSON/YAML file.
        rules_path: Path to jurisdiction rules YAML. Defaults to base.yaml.
        scoring_config_path: Path to scoring weights YAML. Defaults to scoring.yaml.

    Returns:
        Dict containing:
            - overall_percentage: float (0-100)
            - overall_score: float (0-1, legacy)
            - hard_fail: bool
            - hard_fail_reasons: List[str]
            - dimension_scores: Dict[str, Dict] with keys:
                - safety, compliance, trauma, belonging, memory
                - Each contains "score" (0-1), "breakdown", "evidence"
            - metadata: Dict with scenario_id, jurisdiction, timestamp

    Example:
        >>> result = score("transcript.jsonl", "scenario.json")
        >>> if result["hard_fail"]:
        ...     print(f"Hard fail: {result['hard_fail_reasons']}")
        >>> else:
        ...     print(f"Score: {result['overall_percentage']:.1f}%")
    """
    # Use defaults if not provided
    if rules_path is None:
        rules_path = str(_DEFAULT_RULES_PATH)
    if scoring_config_path is None:
        scoring_config_path = str(_DEFAULT_SCORING_CONFIG)

    # Create orchestrator with state persistence disabled (for external use)
    orchestrator = ScoringOrchestrator(
        scoring_config_path=scoring_config_path,
        enable_state_persistence=False,
    )

    return orchestrator.score(
        transcript_path=transcript_path,
        scenario_path=scenario_path,
        rules_path=rules_path,
    )


def score_with_rewards(
    transcript_path: str,
    scenario_path: str,
    rules_path: Optional[str] = None,
    scoring_config_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Score a transcript and return rewards suitable for RL training.

    This is a convenience wrapper around score() that formats the output
    for reinforcement learning training loops.

    Args:
        Same as score()

    Returns:
        Dict containing:
            - rewards: Dict[str, float] with per-dimension rewards (0-1)
            - hard_fail: bool
            - hard_fail_reasons: List[str]
            - raw_result: Full score() result for debugging
    """
    result = score(
        transcript_path=transcript_path,
        scenario_path=scenario_path,
        rules_path=rules_path,
        scoring_config_path=scoring_config_path,
    )

    # Extract per-dimension scores as rewards
    rewards = {}
    dimensions = ["safety", "compliance", "trauma", "belonging", "memory"]

    for dim in dimensions:
        dim_result = result.get("dimension_scores", {}).get(dim, {})
        if dim_result.get("status") == "completed":
            rewards[dim] = dim_result.get("score", 0.0)
        else:
            rewards[dim] = 0.0  # Default to 0 if scorer failed

    return {
        "rewards": rewards,
        "hard_fail": result.get("hard_fail", False),
        "hard_fail_reasons": result.get("hard_fail_reasons", []),
        "raw_result": result,
    }
