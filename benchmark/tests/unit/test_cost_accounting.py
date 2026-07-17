"""Cost accounting must prefer provider billing over local price guesses."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from invisiblebench.api.client import (
    JUDGE_MODEL_OPENROUTER_ID,
    APIConfig,
    CostBudgetExceededError,
    CostTracker,
    ModelAPIClient,
    maximum_reasonable_cost_ceiling,
)
from invisiblebench.cli.run_command import estimate_cost
from scripts.resolve_unclear_scan import _combined_cost, _load_source_cost


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


def test_async_client_retries_malformed_provider_json(monkeypatch) -> None:
    from invisiblebench.api import client as client_module

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("INVISIBLEBENCH_DISABLE_LLM", raising=False)
    responses = [
        json.JSONDecodeError("unterminated response", "", 0),
        {
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "cost": 0.0001,
            },
        },
    ]
    calls = 0

    class FakeResponse:
        def __init__(self, payload) -> None:
            self.payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self):
            if isinstance(self.payload, Exception):
                raise self.payload
            return self.payload

    class FakeAsyncClient:
        def __init__(self, **_kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args) -> None:
            return None

        async def post(self, *_args, **_kwargs):
            nonlocal calls
            payload = responses[calls]
            calls += 1
            return FakeResponse(payload)

    monkeypatch.setattr(client_module.httpx, "AsyncClient", FakeAsyncClient)
    client = ModelAPIClient(APIConfig(timeout=1, max_retries=2, retry_delay=0))

    result = asyncio.run(
        client.call_model_async(
            "provider/model",
            [{"role": "user", "content": "hello"}],
        )
    )

    assert result["response"] == "ok"
    assert calls == 2


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


def test_reasonable_cost_ceiling_allows_headroom_without_unbounded_approval() -> None:
    assert maximum_reasonable_cost_ceiling(10.0) == 15.0
    assert maximum_reasonable_cost_ceiling(0.1) == 1.1


def test_unclear_resolution_preserves_cumulative_cost_accounting(tmp_path: Path) -> None:
    scan_dir = tmp_path / "scan"
    scan_dir.mkdir()
    scan = scan_dir / "per_run.jsonl"
    scan.write_text("{}\n")
    (scan_dir / "cost_report.json").write_text(
        json.dumps(
            {
                "actual_cost_usd": 5.9,
                "actual_billable_api_calls": 2300,
                "actual_cost_by_model_usd": {"openai/gpt-5-mini": 5.9},
            }
        )
    )

    previous = _load_source_cost(scan)
    combined = _combined_cost(
        previous,
        {
            "total": 0.02,
            "calls": 3,
            "by_model": {"openai/gpt-5-mini": 0.02},
        },
        6.1,
    )

    assert combined == {
        "total": 5.92,
        "calls": 2303,
        "by_model": {"openai/gpt-5-mini": 5.92},
        "max_cost_usd": 6.1,
    }
