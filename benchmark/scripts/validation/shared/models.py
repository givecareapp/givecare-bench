"""
Model configurations for InvisibleBench.

Pricing from OpenRouter API (January 2026).
https://openrouter.ai/api/v1/models
"""
from typing import Dict, List

# Cheapest model for full scenario validation
MODELS_MINIMAL: List[Dict] = [
    {
        "id": "deepseek/deepseek-v3.2-20251201",
        "name": "DeepSeek V3.2",
        "provider": "openrouter",
        "cost_per_m_input": 0.25,
        "cost_per_m_output": 0.38
    }
]

# Full set for comprehensive benchmark (10 models)
# Tiers: Frontier ($5+), Mid ($1-3), Budget (<$1), Open (open-source/weights)
MODELS_FULL: List[Dict] = [
    # Frontier tier
    {
        "id": "anthropic/claude-opus-4.5",
        "name": "Claude Opus 4.5",
        "provider": "openrouter",
        "cost_per_m_input": 5.00,
        "cost_per_m_output": 25.00
    },
    {
        "id": "openai/gpt-5.2-20251211",
        "name": "GPT-5.2",
        "provider": "openrouter",
        "cost_per_m_input": 1.75,
        "cost_per_m_output": 14.00
    },
    {
        "id": "google/gemini-3-pro-preview-20251117",
        "name": "Gemini 3 Pro Preview",
        "provider": "openrouter",
        "cost_per_m_input": 2.00,
        "cost_per_m_output": 12.00
    },
    # Mid tier
    {
        "id": "anthropic/claude-sonnet-4.5",
        "name": "Claude Sonnet 4.5",
        "provider": "openrouter",
        "cost_per_m_input": 3.00,
        "cost_per_m_output": 15.00
    },
    {
        "id": "x-ai/grok-4",
        "name": "Grok 4",
        "provider": "openrouter",
        "cost_per_m_input": 3.00,
        "cost_per_m_output": 15.00
    },
    {
        "id": "openai/gpt-5-mini",
        "name": "GPT-5 Mini",
        "provider": "openrouter",
        "cost_per_m_input": 0.25,
        "cost_per_m_output": 2.00
    },
    # Budget tier
    {
        "id": "deepseek/deepseek-v3.2-20251201",
        "name": "DeepSeek V3.2",
        "provider": "openrouter",
        "cost_per_m_input": 0.25,
        "cost_per_m_output": 0.38
    },
    {
        "id": "google/gemini-2.5-flash",
        "name": "Gemini 2.5 Flash",
        "provider": "openrouter",
        "cost_per_m_input": 0.30,
        "cost_per_m_output": 2.50
    },
    # Open tier (open-source/open-weights)
    {
        "id": "minimax/minimax-m2.1",
        "name": "MiniMax M2.1",
        "provider": "openrouter",
        "cost_per_m_input": 0.27,
        "cost_per_m_output": 1.12
    },
    {
        "id": "qwen/qwen3-235b-a22b",
        "name": "Qwen3 235B",
        "provider": "openrouter",
        "cost_per_m_input": 0.20,
        "cost_per_m_output": 0.60
    }
]
