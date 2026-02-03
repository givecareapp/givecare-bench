"""Model configurations for InvisibleBench."""

from invisiblebench.models.config import MODELS_FULL as CONFIG_MODELS_FULL
from invisiblebench.models.config import MODELS_MINIMAL as CONFIG_MODELS_MINIMAL

MODELS_MINIMAL = [model.model_dump() for model in CONFIG_MODELS_MINIMAL]
MODELS_FULL = [model.model_dump() for model in CONFIG_MODELS_FULL]
