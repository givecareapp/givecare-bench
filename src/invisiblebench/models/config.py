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
MODELS_FULL = [
    # ── Frontier ──
    # US closed
    ModelConfig(
        id="openai/gpt-5.5",
        name="GPT-5.5",
        provider="openrouter",
        cost_per_m_input=5.00,
        cost_per_m_output=30.00,
    ),
    ModelConfig(
        id="anthropic/claude-opus-4.7",
        name="Claude Opus 4.7",
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
        cost_per_m_input=0.74,
        cost_per_m_output=3.50,
    ),
    ModelConfig(
        id="minimax/minimax-m2.7",
        name="MiniMax M2.7",
        provider="openrouter",
        cost_per_m_input=0.28,
        cost_per_m_output=1.20,
    ),
    # China open
    ModelConfig(
        id="deepseek/deepseek-v4-pro",
        name="DeepSeek V4 Pro",
        provider="openrouter",
        cost_per_m_input=0.43,
        cost_per_m_output=0.87,
    ),
    ModelConfig(
        id="qwen/qwen3.6-max-preview",
        name="Qwen 3.6 Max",
        provider="openrouter",
        cost_per_m_input=1.04,
        cost_per_m_output=6.24,
    ),
    ModelConfig(
        id="z-ai/glm-5.1",
        name="GLM-5.1",
        provider="openrouter",
        cost_per_m_input=0.98,
        cost_per_m_output=3.08,
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
        id="openai/gpt-5-mini",
        name="GPT-5 Mini",
        provider="openrouter",
        cost_per_m_input=0.25,
        cost_per_m_output=2.00,
    ),
    ModelConfig(
        id="google/gemini-3.1-flash-lite",
        name="Gemini 3.1 Flash Lite",
        provider="openrouter",
        cost_per_m_input=0.25,
        cost_per_m_output=1.50,
    ),
    # ── Small ──
    ModelConfig(
        id="nvidia/nemotron-3-super-120b-a12b",
        name="Nemotron 3 Super 120B",
        provider="openrouter",
        cost_per_m_input=0.09,
        cost_per_m_output=0.45,
    ),
    ModelConfig(
        id="qwen/qwen3.6-35b-a3b",
        name="Qwen 3.6 35B",
        provider="openrouter",
        cost_per_m_input=0.15,
        cost_per_m_output=1.00,
    ),
    ModelConfig(
        id="google/gemma-4-31b-it",
        name="Gemma 4 31B",
        provider="openrouter",
        cost_per_m_input=0.12,
        cost_per_m_output=0.37,
    ),
]
