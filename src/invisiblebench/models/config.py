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
# Selection rationale: 3 tiers testing whether safety degrades with cost.
#   Frontier (6)  — best each major lab offers (safety ceiling)
#   Mid-range (4) — cost-optimized flagships (does optimization hurt safety?)
#   Cheap/small (6) — budget and edge models (safety floor, what breaks first?)
#
MODELS_FULL = [
    # ── Frontier ──
    ModelConfig(
        id="openai/gpt-5.4",
        name="GPT-5.4",
        provider="openrouter",
        cost_per_m_input=2.50,
        cost_per_m_output=15.00,
    ),
    ModelConfig(
        id="anthropic/claude-opus-4.6",
        name="Claude Opus 4.6",
        provider="openrouter",
        cost_per_m_input=5.00,
        cost_per_m_output=25.00,
    ),
    ModelConfig(
        id="google/gemini-3.1-pro-preview",
        name="Gemini 3.1 Pro",
        provider="openrouter",
        cost_per_m_input=2.00,
        cost_per_m_output=12.00,
    ),
    ModelConfig(
        id="x-ai/grok-4.1-fast",
        name="Grok 4.1 Fast",
        provider="openrouter",
        cost_per_m_input=0.20,
        cost_per_m_output=0.50,
    ),
    ModelConfig(
        id="deepseek/deepseek-v3.2",
        name="DeepSeek V3.2",
        provider="openrouter",
        cost_per_m_input=0.25,
        cost_per_m_output=0.38,
    ),
    ModelConfig(
        id="z-ai/glm-5",
        name="GLM-5",
        provider="openrouter",
        cost_per_m_input=0.72,
        cost_per_m_output=2.30,
    ),
    # ── Mid-range ──
    ModelConfig(
        id="anthropic/claude-sonnet-4.5",
        name="Claude Sonnet 4.5",
        provider="openrouter",
        cost_per_m_input=3.00,
        cost_per_m_output=15.00,
    ),
    ModelConfig(
        id="moonshotai/kimi-k2.5",
        name="Kimi K2.5",
        provider="openrouter",
        cost_per_m_input=0.45,
        cost_per_m_output=2.25,
    ),
    ModelConfig(
        id="minimax/minimax-m2.5",
        name="MiniMax M2.5",
        provider="openrouter",
        cost_per_m_input=0.27,
        cost_per_m_output=0.95,
    ),
    ModelConfig(
        id="qwen/qwen3.5-397b-a17b",
        name="Qwen3.5 397B",
        provider="openrouter",
        cost_per_m_input=0.39,
        cost_per_m_output=2.34,
    ),
    # ── Cheap / small ──
    ModelConfig(
        id="openai/gpt-5-mini",
        name="GPT-5 Mini",
        provider="openrouter",
        cost_per_m_input=0.25,
        cost_per_m_output=2.00,
    ),
    ModelConfig(
        id="google/gemini-2.5-flash",
        name="Gemini 2.5 Flash",
        provider="openrouter",
        cost_per_m_input=0.30,
        cost_per_m_output=2.50,
    ),
    ModelConfig(
        id="google/gemini-3-flash-preview",
        name="Gemini 3 Flash",
        provider="openrouter",
        cost_per_m_input=0.50,
        cost_per_m_output=3.00,
    ),
    ModelConfig(
        id="openai/gpt-oss-120b",
        name="GPT-OSS 120B",
        provider="openrouter",
        cost_per_m_input=0.04,
        cost_per_m_output=0.19,
    ),
    ModelConfig(
        id="qwen/qwen3.5-35b-a3b",
        name="Qwen3.5 35B",
        provider="openrouter",
        cost_per_m_input=0.16,
        cost_per_m_output=1.30,
    ),
]
