"""Cost accounting must prefer provider billing over local price guesses."""

from __future__ import annotations

import pytest

from invisiblebench.api.client import (
    JUDGE_MODEL_OPENROUTER_ID,
    CostBudgetExceededError,
    CostTracker,
    ModelAPIClient,
)
from invisiblebench.cli.run_command import estimate_cost


def test_cost_tracker_accepts_provider_reported_cost_for_unknown_model() -> None:
    tracker = CostTracker()

    charged = tracker.record(
        "provider/new-model",
        prompt_tokens=100,
        completion_tokens=50,
        actual_cost=0.012345,
    )

    assert charged == 0.012345
    assert tracker.snapshot() == {
        "total": 0.012345,
        "calls": 1,
        "by_model": {"provider/new-model": 0.012345},
        "max_cost_usd": None,
    }


def test_parse_response_prefers_usage_cost(monkeypatch) -> None:
    from invisiblebench.api import client as client_module

    tracker = CostTracker()
    monkeypatch.setattr(client_module, "cost_tracker", tracker)

    ModelAPIClient._parse_response(
        {
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
                "cost": 0.012345,
            },
        },
        "provider/new-model",
        start_time=0.0,
    )

    assert tracker.total == 0.012345


def test_transcript_estimate_includes_live_cost_safety_margin() -> None:
    model = {"cost_per_m_input": 1.0, "cost_per_m_output": 1.0}

    # Context baseline is 5,500 input + 1,400 output tokens. The live canary
    # exceeded that estimate by 34%, so the public estimate reserves 50%.
    assert estimate_cost("context", model) == 0.01035


def test_cost_tracker_enforces_runtime_budget_after_charge() -> None:
    tracker = CostTracker()
    tracker.reset(max_cost_usd=0.01)
    tracker.record(
        "provider/model",
        prompt_tokens=100,
        completion_tokens=50,
        actual_cost=0.01,
    )

    with pytest.raises(CostBudgetExceededError, match="cost ceiling"):
        tracker.ensure_budget_available()


def test_cost_tracker_prices_judge_when_provider_omits_cost() -> None:
    tracker = CostTracker()

    charged = tracker.record(
        JUDGE_MODEL_OPENROUTER_ID,
        prompt_tokens=1_000_000,
        completion_tokens=1_000_000,
    )

    assert charged == 2.25
