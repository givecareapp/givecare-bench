"""Model configurations for InvisibleBench."""

from invisiblebench.models.config import MODELS_FULL as CONFIG_MODELS_FULL

MODELS_FULL = [model.model_dump() for model in CONFIG_MODELS_FULL]

# Deprecated: kept for backward compat in validation scripts.
# Resolves to the cheapest model in the full catalog.
MODELS_MINIMAL = [
    min(MODELS_FULL, key=lambda m: m["cost_per_m_input"] + m["cost_per_m_output"])
]
