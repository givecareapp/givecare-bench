"""The default judge has the same price owner in planning and billing."""

from invisiblebench.api.client import (
    _MODEL_PRICING,
    DEFAULT_JUDGE_MODEL,
    JUDGE_MODEL_OPENAI_ID,
    JUDGE_MODEL_OPENROUTER_ID,
)
from invisiblebench.judge import MODEL_PRICING


def test_default_judge_prices_are_shared_with_runtime_accounting():
    assert MODEL_PRICING is _MODEL_PRICING
    assert DEFAULT_JUDGE_MODEL in {JUDGE_MODEL_OPENAI_ID, JUDGE_MODEL_OPENROUTER_ID}
    for model in (JUDGE_MODEL_OPENAI_ID, JUDGE_MODEL_OPENROUTER_ID):
        assert all(price > 0 for price in MODEL_PRICING[model])
