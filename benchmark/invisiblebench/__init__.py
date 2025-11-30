"""
InvisibleBench - Benchmark for evaluating AI safety in long-term caregiving relationships.

This package provides tools for:
- Loading and managing scenarios
- Evaluating model responses across multiple dimensions
- Scoring based on trauma-informed, culturally-sensitive criteria
- Generating comprehensive reports

Public API:
    from invisiblebench import score, score_with_rewards

    result = score("transcript.jsonl", "scenario.json")
    rewards = score_with_rewards("transcript.jsonl", "scenario.json")
"""

__version__ = "0.1.0"

from invisiblebench.score import score, score_with_rewards

__all__ = ["score", "score_with_rewards", "__version__"]
