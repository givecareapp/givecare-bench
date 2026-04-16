"""Public scoring API. External consumers (e.g. givecare-tune) use score() here."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from invisiblebench.evaluation.orchestrator import ScoringOrchestrator

# Default paths relative to the repo root.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_SCORING_CONFIG = _PROJECT_ROOT / "benchmark" / "configs" / "scoring.yaml"
_DEFAULT_RULES_PATH = _PROJECT_ROOT / "benchmark" / "configs" / "rules" / "base.yaml"


def score(
    transcript_path: str,
    scenario_path: str,
    rules_path: Optional[str] = None,
    scoring_config_path: Optional[str] = None,
    enable_llm: bool = False,
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
        enable_llm: Enable LLM-assisted scoring (default: False).

    Returns:
        Dict containing:
            - overall_percentage: float (0-100)
            - overall_score: float (0-1)
            - hard_fail: bool
            - hard_fail_reasons: List[str]
            - dimension_scores: Dict[str, Dict] with keys:
                - safety, compliance, regard, coordination, false_refusal, memory
                - Each contains "score" (0-1), "breakdown", "evidence"
            - metadata: Dict with scenario_id, jurisdiction, timestamp

    Example:
        >>> result = score("transcript.jsonl", "scenario.json")
        >>> if result["hard_fail"]:
        ...     print(f"Hard fail: {result['hard_fail_reasons']}")
        >>> else:
        ...     print(f"Score: {result['overall_percentage']:.1f}%")
    """
    if rules_path is None:
        rules_path = str(_DEFAULT_RULES_PATH)
    if scoring_config_path is None:
        scoring_config_path = str(_DEFAULT_SCORING_CONFIG)

    orchestrator = ScoringOrchestrator(
        scoring_config_path=scoring_config_path,
        enable_state_persistence=False,
        enable_llm=enable_llm,
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
    """Wrapper around score() returning per-dimension rewards for RL training."""
    result = score(
        transcript_path=transcript_path,
        scenario_path=scenario_path,
        rules_path=rules_path,
        scoring_config_path=scoring_config_path,
    )

    rewards = {}
    dimensions = ["safety", "compliance", "regard", "coordination", "false_refusal", "memory"]

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
