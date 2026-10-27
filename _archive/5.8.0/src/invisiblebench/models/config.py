"""Benchmark configuration models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ModelConfig(BaseModel):

    id: str = Field(..., description="Model ID (e.g., 'deepseek/deepseek-chat')")
    name: str = Field(..., description="Display name (e.g., 'DeepSeek V3')")
    endpoint: str | None = Field(
        default=None,
        min_length=1,
        description="Exact OpenRouter provider slug; absent means the routed service is measured",
    )
    cost_per_m_input: float = Field(
        ..., ge=0, allow_inf_nan=False, description="Cost per million input tokens"
    )
    cost_per_m_output: float = Field(
        ..., ge=0, allow_inf_nan=False, description="Cost per million output tokens"
    )


def serving_policy(model: dict[str, Any]) -> dict[str, Any]:
    """One policy supplies both the frozen contract and the OpenRouter payload."""
    endpoint = model.get("endpoint")
    if endpoint is not None and (not isinstance(endpoint, str) or not endpoint.strip()):
        raise ValueError("endpoint must be a nonempty OpenRouter provider slug")
    return {
        "measurement": "pinned_provider" if endpoint else "routed_service",
        "provider": {
            "allow_fallbacks": endpoint is None,
            "require_parameters": True,
            **({"only": [endpoint]} if endpoint else {}),
        },
    }


# Default model configurations
#
# 16 models × 3 metadata axes: class (frontier/flash/small), origin (US/China),
# access (closed/open). Each model carries all three tags; slice results any way.
#
#   Frontier (9)  — top from each major lab (safety ceiling)
#   Flash (3)     — cost-optimized from US labs (does speed hurt safety?)
#   Small (4)     — edge-class open models (safety floor, what breaks first?)
#
# Exact IDs and list prices verified against OpenRouter on 2026-07-10.
# US-closed frontier IDs and prices refreshed on 2026-09-23.
# Qwen 3.6 35B and Qwen 3.8 27B (the product model) are pinned to one OpenRouter
# provider each, priced at that provider's list price on 2026-10-18, so Inspect's
# --cost-limit counts what the pinned provider bills.
# Grok 4.5 was excluded because xAI rejected it in the benchmark run region;
# Grok 4.7 has not yet passed the live transcript canary.
#
MODELS_FULL = [
    # ── Frontier ──
    # US closed
    ModelConfig(
        id="openai/gpt-6-sol",
        name="GPT-6 Sol",
        cost_per_m_input=2.00,
        cost_per_m_output=10.00,
    ),
    ModelConfig(
        id="anthropic/claude-opus-5.5",
        name="Claude Opus 5.5",
        cost_per_m_input=4.00,
        cost_per_m_output=20.00,
    ),
    ModelConfig(
        id="google/gemini-3.1-pro-preview",
        name="Gemini 3.1 Pro",
        cost_per_m_input=2.00,
        cost_per_m_output=12.00,
    ),
    ModelConfig(
        id="x-ai/grok-4.7",
        name="Grok 4.7",
        cost_per_m_input=1.60,
        cost_per_m_output=4.80,
    ),
    # China closed
    ModelConfig(
        id="moonshotai/kimi-k2.6",
        name="Kimi K2.6",
        cost_per_m_input=0.66,
        cost_per_m_output=3.41,
    ),
    ModelConfig(
        id="minimax/minimax-m3",
        name="MiniMax M3",
        cost_per_m_input=0.30,
        cost_per_m_output=1.20,
    ),
    # China open
    ModelConfig(
        id="deepseek/deepseek-v4-pro",
        name="DeepSeek V4 Pro",
        cost_per_m_input=0.435,
        cost_per_m_output=0.87,
    ),
    ModelConfig(
        id="qwen/qwen3.7-max",
        name="Qwen 3.7 Max",
        cost_per_m_input=1.25,
        cost_per_m_output=3.75,
    ),
    ModelConfig(
        id="z-ai/glm-5.2",
        name="GLM-5.2",
        cost_per_m_input=0.54,
        cost_per_m_output=1.76,
    ),
    # ── Flash ──
    ModelConfig(
        id="anthropic/claude-haiku-4.5",
        name="Claude Haiku 4.5",
        cost_per_m_input=1.00,
        cost_per_m_output=5.00,
    ),
    ModelConfig(
        id="openai/gpt-5.6-luna",
        name="GPT-5.6 Luna",
        cost_per_m_input=1.00,
        cost_per_m_output=6.00,
    ),
    ModelConfig(
        id="google/gemini-3.5-flash",
        name="Gemini 3.5 Flash",
        cost_per_m_input=1.50,
        cost_per_m_output=9.00,
    ),
    # ── Small ──
    ModelConfig(
        id="nvidia/nemotron-3-super-120b-a12b",
        name="Nemotron 3 Super 120B",
        cost_per_m_input=0.08,
        cost_per_m_output=0.45,
    ),
    ModelConfig(
        id="qwen/qwen3.6-35b-a3b",
        name="Qwen 3.6 35B",
        endpoint="parasail",
        cost_per_m_input=0.15,
        cost_per_m_output=1.00,
    ),
    ModelConfig(
        id="qwen/qwen3.8-27b",
        name="Qwen 3.8 27B",
        endpoint="deepinfra",
        cost_per_m_input=0.15,
        cost_per_m_output=1.875,
    ),
    ModelConfig(
        id="google/gemma-4-26b-a4b-it",
        name="Gemma 4 26B A4B",
        cost_per_m_input=0.06,
        cost_per_m_output=0.33,
    ),
]
