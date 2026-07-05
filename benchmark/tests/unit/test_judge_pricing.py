"""Pin: judge/scorer pricing must resolve for the default judge model under
BOTH backend spellings.

The judge id has one canonical owner — DEFAULT_JUDGE_MODEL /
DEFAULT_SCORER_MODEL in src/invisiblebench/api/client.py, resolved
backend-conditionally (direct-OpenAI vs OpenRouter). judge.py's MODEL_PRICING
table used to hardcode both spellings as bare string literals; a future judge
swap that updated client.py's ids without also updating judge.py's pricing
table would silently drop cost estimation (``_estimate_call_cost`` returns
``None`` on a pricing miss — no error, just a quietly wrong/missing cost
estimate for the new judge).

judge.py now keys MODEL_PRICING off api.client's JUDGE_MODEL_OPENAI_ID /
JUDGE_MODEL_OPENROUTER_ID constants (the same source DEFAULT_JUDGE_MODEL
resolves from) instead of re-typed literals, so the two can't drift apart at
the id level. This test is the second half of the guarantee: it pins that a
priced entry actually exists for both spellings, the same way
test_intake_probe_models.py pins PROBE_MODELS against the live model catalog
so a rename fails tests instead of a timer.
"""

from __future__ import annotations

from invisiblebench.api.client import (
    DEFAULT_JUDGE_MODEL,
    DEFAULT_SCORER_MODEL,
    JUDGE_MODEL_OPENAI_ID,
    JUDGE_MODEL_OPENROUTER_ID,
)
from invisiblebench.judge import MODEL_PRICING, _estimate_call_cost


def test_default_judge_model_is_one_of_the_known_spellings() -> None:
    """DEFAULT_JUDGE_MODEL is resolved backend-conditionally at import time;
    it must always be exactly one of the two known judge-id spellings, and
    DEFAULT_SCORER_MODEL must track it (single owner, no independent drift)."""
    assert DEFAULT_JUDGE_MODEL in (JUDGE_MODEL_OPENAI_ID, JUDGE_MODEL_OPENROUTER_ID)
    assert DEFAULT_SCORER_MODEL == DEFAULT_JUDGE_MODEL


def test_pricing_resolves_for_default_judge_model_under_both_backend_spellings() -> None:
    """A future judge swap that updates client.py's spellings without also
    updating judge.py's MODEL_PRICING must fail here — not silently return
    None from cost estimation for whichever spelling is active at runtime."""
    for judge_id in (JUDGE_MODEL_OPENAI_ID, JUDGE_MODEL_OPENROUTER_ID):
        assert judge_id in MODEL_PRICING, (
            f"{judge_id!r} has no MODEL_PRICING entry in judge.py — a judge "
            "model swap silently lost cost estimation for this spelling."
        )
        cost = _estimate_call_cost(judge_id, input_tokens=1_000_000, output_tokens=1_000_000)
        assert cost is not None, f"_estimate_call_cost returned None for {judge_id!r}"
        assert cost > 0


def test_pricing_resolves_for_the_currently_active_default() -> None:
    """Whichever spelling is actually active in this process (DEFAULT_JUDGE_MODEL)
    must itself resolve — the direct end-to-end check, not just both spellings
    in isolation."""
    assert DEFAULT_JUDGE_MODEL in MODEL_PRICING
    cost = _estimate_call_cost(DEFAULT_JUDGE_MODEL, input_tokens=1000, output_tokens=1000)
    assert cost is not None
