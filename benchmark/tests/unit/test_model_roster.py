"""Contract tests for the pinned live OpenRouter roster."""

from __future__ import annotations

from invisiblebench.models.config import MODELS_FULL

EXPECTED_ROSTER = {
    "openai/gpt-5.6-sol": (5.0, 30.0),
    "anthropic/claude-fable-5": (10.0, 50.0),
    "google/gemini-3.1-pro-preview": (2.0, 12.0),
    "x-ai/grok-4.3": (1.25, 2.5),
    "moonshotai/kimi-k2.6": (0.66, 3.41),
    "minimax/minimax-m3": (0.3, 1.2),
    "deepseek/deepseek-v4-pro": (0.435, 0.87),
    "qwen/qwen3.7-max": (1.25, 3.75),
    "z-ai/glm-5.2": (0.54, 1.76),
    "anthropic/claude-haiku-4.5": (1.0, 5.0),
    "openai/gpt-5.6-luna": (1.0, 6.0),
    "google/gemini-3.5-flash": (1.5, 9.0),
    "nvidia/nemotron-3-super-120b-a12b": (0.08, 0.45),
    "qwen/qwen3.6-35b-a3b": (0.14, 1.0),
    "google/gemma-4-26b-a4b-it": (0.06, 0.33),
}


def test_full_roster_matches_live_catalog_snapshot() -> None:
    """Keep live-canary IDs and list prices aligned as of 2026-07-10."""
    actual = {
        model.id: (model.cost_per_m_input, model.cost_per_m_output)
        for model in MODELS_FULL
    }

    assert actual == EXPECTED_ROSTER
