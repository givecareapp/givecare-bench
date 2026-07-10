"""Benchmark configuration models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ModelConfig(BaseModel):

    id: str = Field(..., description="Model ID (e.g., 'deepseek/deepseek-chat')")
    name: str = Field(..., description="Display name (e.g., 'DeepSeek V3')")
    provider: Literal["openrouter", "anthropic", "openai"] = Field(
        default="openrouter", description="API provider"
    )
    cost_per_m_input: float = Field(..., ge=0, description="Cost per million input tokens")
    cost_per_m_output: float = Field(..., ge=0, description="Cost per million output tokens")

    @property
    def safe_id(self) -> str:
        return self.id.replace("/", "_")



# Default model configurations
#
# 15 models × 3 metadata axes: class (frontier/flash/small), origin (US/China),
# access (closed/open). Each model carries all three tags; slice results any way.
#
#   Frontier (9)  — top from each major lab (safety ceiling)
#   Flash (3)     — cost-optimized from US labs (does speed hurt safety?)
#   Small (3)     — edge-class open models (safety floor, what breaks first?)
#
# Exact IDs and list prices verified against OpenRouter on 2026-07-10.
# Grok 4.5 is excluded because xAI rejects it in the benchmark run region;
# Grok 4.3 is the newest xAI model that passes the live transcript canary.
#
MODELS_FULL = [
    # ── Frontier ──
    # US closed
    ModelConfig(
        id="openai/gpt-5.6-sol",
        name="GPT-5.6 Sol",
        provider="openrouter",
        cost_per_m_input=5.00,
        cost_per_m_output=30.00,
    ),
    ModelConfig(
        id="anthropic/claude-fable-5",
        name="Claude Fable 5",
        provider="openrouter",
        cost_per_m_input=10.00,
        cost_per_m_output=50.00,
    ),
    ModelConfig(
        id="google/gemini-3.1-pro-preview",
        name="Gemini 3.1 Pro",
        provider="openrouter",
        cost_per_m_input=2.00,
        cost_per_m_output=12.00,
    ),
    ModelConfig(
        id="x-ai/grok-4.3",
        name="Grok 4.3",
        provider="openrouter",
        cost_per_m_input=1.25,
        cost_per_m_output=2.50,
    ),
    # China closed
    ModelConfig(
        id="moonshotai/kimi-k2.6",
        name="Kimi K2.6",
        provider="openrouter",
        cost_per_m_input=0.66,
        cost_per_m_output=3.41,
    ),
    ModelConfig(
        id="minimax/minimax-m3",
        name="MiniMax M3",
        provider="openrouter",
        cost_per_m_input=0.30,
        cost_per_m_output=1.20,
    ),
    # China open
    ModelConfig(
        id="deepseek/deepseek-v4-pro",
        name="DeepSeek V4 Pro",
        provider="openrouter",
        cost_per_m_input=0.435,
        cost_per_m_output=0.87,
    ),
    ModelConfig(
        id="qwen/qwen3.7-max",
        name="Qwen 3.7 Max",
        provider="openrouter",
        cost_per_m_input=1.25,
        cost_per_m_output=3.75,
    ),
    ModelConfig(
        id="z-ai/glm-5.2",
        name="GLM-5.2",
        provider="openrouter",
        cost_per_m_input=0.54,
        cost_per_m_output=1.76,
    ),
    # ── Flash ──
    ModelConfig(
        id="anthropic/claude-haiku-4.5",
        name="Claude Haiku 4.5",
        provider="openrouter",
        cost_per_m_input=1.00,
        cost_per_m_output=5.00,
    ),
    ModelConfig(
        id="openai/gpt-5.6-luna",
        name="GPT-5.6 Luna",
        provider="openrouter",
        cost_per_m_input=1.00,
        cost_per_m_output=6.00,
    ),
    ModelConfig(
        id="google/gemini-3.5-flash",
        name="Gemini 3.5 Flash",
        provider="openrouter",
        cost_per_m_input=1.50,
        cost_per_m_output=9.00,
    ),
    # ── Small ──
    ModelConfig(
        id="nvidia/nemotron-3-super-120b-a12b",
        name="Nemotron 3 Super 120B",
        provider="openrouter",
        cost_per_m_input=0.08,
        cost_per_m_output=0.45,
    ),
    ModelConfig(
        id="qwen/qwen3.6-35b-a3b",
        name="Qwen 3.6 35B",
        provider="openrouter",
        cost_per_m_input=0.14,
        cost_per_m_output=1.00,
    ),
    ModelConfig(
        id="google/gemma-4-26b-a4b-it",
        name="Gemma 4 26B A4B",
        provider="openrouter",
        cost_per_m_input=0.06,
        cost_per_m_output=0.33,
    ),
]
