"""The judge has one price owner: planning, billing, and the client share it."""

from invisiblebench import judge
from invisiblebench.api.typesafe import (
    DEFAULT_JUDGE_MODEL,
    ESTIMATED_BYTES_PER_TOKEN,
    JUDGE_PRICING,
    estimated_cost,
    request_cost,
)


def test_planning_and_billing_read_the_same_judge_prices():
    assert judge.estimated_cost is estimated_cost
    assert judge.DEFAULT_JUDGE_MODEL == DEFAULT_JUDGE_MODEL
    assert JUDGE_PRICING[DEFAULT_JUDGE_MODEL] > 0
    assert estimated_cost("unpriced/judge", 1_000) is None


def test_the_dry_run_estimate_stays_above_the_billed_cost():
    """Observed: about 4.3 payload bytes per billed token. The estimate assumes fewer."""
    payload_bytes = 1_000_000
    billed = request_cost(DEFAULT_JUDGE_MODEL, payload_bytes // 4)
    assert ESTIMATED_BYTES_PER_TOKEN < 4
    assert estimated_cost(DEFAULT_JUDGE_MODEL, payload_bytes) > billed


def test_only_input_tokens_are_billed():
    assert request_cost(DEFAULT_JUDGE_MODEL, 1_000_000) == JUDGE_PRICING[DEFAULT_JUDGE_MODEL]
    assert request_cost(DEFAULT_JUDGE_MODEL, 0) == 0
