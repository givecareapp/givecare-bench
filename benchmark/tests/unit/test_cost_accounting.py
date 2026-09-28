"""Cost accounting must prefer provider billing over local price guesses."""

from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path
from typing import Any

import pytest

from invisiblebench.api.client import (
    APIConfig,
    CostBudgetExceededError,
    CostTracker,
    ModelAPIClient,
    UnpricedModelCostError,
    maximum_reasonable_cost_ceiling,
)
from invisiblebench.cli.run_command import estimate_cost
from invisiblebench.cli.transcript import evaluate_scenario_async


@pytest.mark.parametrize("amount", [float("nan"), float("inf"), -float("inf"), -1.0])
def test_invalid_budget_values_are_rejected_without_resetting_spend(amount):
    tracker = CostTracker()
    tracker.record("fixture", 0, 0, actual_cost=0.2)
    with pytest.raises(ValueError):
        tracker.reset(max_cost_usd=amount)
    assert tracker.total == 0.2
    with pytest.raises(ValueError):
        tracker.reserve(amount)
    with pytest.raises(ValueError):
        maximum_reasonable_cost_ceiling(amount)


def test_settlement_keeps_the_reservation_until_cost_is_recorded(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    tracker = CostTracker()
    tracker.reset(max_cost_usd=1.0)
    token = tracker.reserve(0.6)
    recording, proceed, attempted, finished = (threading.Event() for _ in range(4))
    record = tracker.record

    def paused_record(*args, **kwargs):
        recording.set()
        assert proceed.wait(2)
        return record(*args, **kwargs)

    def competing_reservation():
        attempted.set()
        try:
            return tracker.reserve(0.6)
        finally:
            finished.set()

    monkeypatch.setattr(tracker, "record", paused_record)
    with ThreadPoolExecutor(max_workers=2) as executor:
        settled = executor.submit(tracker.settle, token, "fixture", 0, 0, actual_cost=0.6)
        assert recording.wait(2)
        competing = executor.submit(competing_reservation)
        assert attempted.wait(2)
        try:
            assert not finished.wait(0.1), "reservation observed an unrecorded settlement"
        finally:
            proceed.set()
        assert settled.result() == 0.6
        with pytest.raises(CostBudgetExceededError):
            competing.result()
    assert tracker.total == 0.6


def test_a_reservation_can_only_be_settled_once():
    tracker = CostTracker()
    token = tracker.reserve(0.6)
    tracker.settle(token, "fixture", 0, 0, actual_cost=0.6)
    with pytest.raises(ValueError, match="reservation"):
        tracker.settle(token, "fixture", 0, 0, actual_cost=0.6)
    assert tracker.calls == 1
    assert tracker.total == 0.6


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
        "reported_total": 0.012345,
        "estimated_total": 0.0,
        "unknown_calls": 0,
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


def test_async_client_does_not_retry_ambiguous_provider_json(monkeypatch) -> None:
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

        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self):
            if isinstance(self.payload, Exception):
                raise self.payload
            return self.payload

    class FakeAsyncClient:
        def __init__(self, **_kwargs) -> None:
            pass

        async def aclose(self) -> None:
            return None

        async def post(self, *_args, **_kwargs):
            nonlocal calls
            payload = responses[calls]
            calls += 1
            return FakeResponse(payload)

    monkeypatch.setattr(client_module.httpx, "AsyncClient", FakeAsyncClient)
    client = ModelAPIClient(APIConfig(timeout=1))

    async def run():
        try:
            with pytest.raises(json.JSONDecodeError):
                await client.call_model_async(
                    "provider/model", [{"role": "user", "content": "hello"}]
                )
        finally:
            await client.aclose()

    asyncio.run(run())
    assert calls == 1


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
        "openai/gpt-5-mini",
        prompt_tokens=1_000_000,
        completion_tokens=1_000_000,
    )

    assert charged == 2.25


def test_reasonable_cost_ceiling_allows_headroom_without_unbounded_approval() -> None:
    assert maximum_reasonable_cost_ceiling(10.0) == 15.0
    assert maximum_reasonable_cost_ceiling(0.1) == 1.1


def test_unpriced_call_is_counted_as_unknown_not_a_fake_zero() -> None:
    tracker = CostTracker()

    charged = tracker.record("provider/unpriced-model", prompt_tokens=100, completion_tokens=50)

    assert charged == 0.0
    snapshot = tracker.snapshot()
    assert snapshot["calls"] == 1
    assert snapshot["unknown_calls"] == 1
    assert snapshot["total"] == 0.0
    # An unknown call must not appear as a zero-cost known entry.
    assert "provider/unpriced-model" not in snapshot["by_model"]


def test_reserve_refuses_unpriced_model_under_a_ceiling_without_opt_in() -> None:
    tracker = CostTracker()
    tracker.reset(max_cost_usd=1.0)

    with pytest.raises(UnpricedModelCostError):
        tracker.reserve(None)

    # Refused reservations must not hold any budget.
    assert tracker._reserved == 0.0  # noqa: SLF001 — verifying no leaked hold


def test_reserve_opt_in_allows_unpriced_dispatch_and_settle_records_unknown() -> None:
    tracker = CostTracker()
    tracker.reset(max_cost_usd=1.0)

    token = tracker.reserve(None, allow_unknown=True)
    cost = tracker.settle(token, "provider/unpriced-model", 100, 50)

    assert cost == 0.0
    snapshot = tracker.snapshot()
    assert snapshot["calls"] == 1
    assert snapshot["unknown_calls"] == 1
    assert snapshot["total"] == 0.0


def test_reported_and_estimated_costs_are_tracked_separately() -> None:
    tracker = CostTracker()

    tracker.record("provider/reported-model", 0, 0, actual_cost=0.5)
    tracker.record("openai/gpt-5-mini", prompt_tokens=1_000_000, completion_tokens=1_000_000)

    snapshot = tracker.snapshot()
    assert snapshot["reported_total"] == pytest.approx(0.5)
    assert snapshot["estimated_total"] == pytest.approx(2.25)
    assert snapshot["total"] == pytest.approx(2.75)
    assert snapshot["unknown_calls"] == 0


def test_concurrent_reservations_cannot_overshoot_the_ceiling() -> None:
    """Ten concurrent requests against a ceiling that only fits three."""
    # 0.25 is an exact binary fraction, so three reservations sum to exactly
    # the ceiling with no floating-point rounding surprises.
    tracker = CostTracker()
    tracker.reset(max_cost_usd=0.75)  # each reservation costs 0.25 -> room for 3

    accepted: list[int] = []
    refused = 0
    lock = threading.Lock()

    def worker() -> None:
        nonlocal refused
        try:
            token = tracker.reserve(0.25)
        except CostBudgetExceededError:
            with lock:
                refused += 1
            return
        with lock:
            accepted.append(token)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(accepted) == 3
    assert refused == 7

    # Settling the accepted reservations must land exactly on the ceiling,
    # never above it.
    for token in accepted:
        tracker.settle(token, "provider/model", 0, 0, actual_cost=0.25)
    assert tracker.total == pytest.approx(0.75)
    assert tracker.total <= 0.75 + 1e-9


def _write_min_scenario(path: Path, scenario_id: str, num_turns: int) -> None:
    path.write_text(
        json.dumps(
            {
                "scenario_id": scenario_id,
                "category": "context",
                "title": scenario_id,
                "persona": {
                    "name": "Jamie",
                    "age": 40,
                    "care_recipient": "Mother",
                    "care_duration": "a year",
                    "context": {},
                },
                "turns": [
                    {"turn_number": i + 1, "user_message": f"Turn {i + 1}?"}
                    for i in range(num_turns)
                ],
            }
        )
    )


def test_per_scenario_cost_is_isolated_under_interleaving(tmp_path: Path) -> None:
    """Two scenarios run concurrently; neither's cost absorbs the other's."""

    class InterleavingClient:
        def __init__(self, cost_per_call: float) -> None:
            self.cost_per_call = cost_per_call

        async def call_model_async(self, **_kwargs: Any) -> dict[str, Any]:
            # Yield control so both scenarios' turns interleave on the
            # shared event loop, the way concurrent scenario tasks do.
            await asyncio.sleep(0)
            return {
                "response": "ok",
                "finish_reason": "stop",
                "tokens": 8,
                "prompt_tokens": 4,
                "completion_tokens": 4,
                "model": "test/model",
                "raw": {},
                "cost": self.cost_per_call,
            }

    scenario_a = tmp_path / "a.json"
    scenario_b = tmp_path / "b.json"
    _write_min_scenario(scenario_a, "scenario_a", num_turns=3)
    _write_min_scenario(scenario_b, "scenario_b", num_turns=5)

    async def _run() -> tuple[dict[str, Any], dict[str, Any]]:
        semaphore = asyncio.Semaphore(2)
        return await asyncio.gather(
            evaluate_scenario_async(
                model={"id": "test/model", "name": "Test Model"},
                scenario={"path": str(scenario_a), "name": "A", "category": "context"},
                api_client=InterleavingClient(cost_per_call=0.01),
                output_dir=tmp_path / "run",
                semaphore=semaphore,
            ),
            evaluate_scenario_async(
                model={"id": "test/model", "name": "Test Model"},
                scenario={"path": str(scenario_b), "name": "B", "category": "context"},
                api_client=InterleavingClient(cost_per_call=0.02),
                output_dir=tmp_path / "run",
                semaphore=semaphore,
            ),
        )

    row_a, row_b = asyncio.run(_run())

    assert row_a["status"] == "transcript_ready"
    assert row_b["status"] == "transcript_ready"
    assert row_a["cost"] == pytest.approx(0.01 * 3)
    assert row_b["cost"] == pytest.approx(0.02 * 5)


def test_a_call_without_a_token_count_is_counted_as_unknown() -> None:
    tracker = CostTracker()
    token = tracker.reserve(0.01)

    assert tracker.settle(token, "jev-1.13.0", None, 0) == 0.0

    snapshot = tracker.snapshot()
    assert (snapshot["calls"], snapshot["unknown_calls"], snapshot["total"]) == (1, 1, 0.0)


def test_model_client_uses_the_required_user_agent(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "offline-test-key")
    monkeypatch.delenv("INVISIBLEBENCH_DISABLE_LLM", raising=False)

    headers = ModelAPIClient(APIConfig()).headers

    assert headers["User-Agent"] == "OpenAI File Downloader, XaiImageApiFetch/1.0"
