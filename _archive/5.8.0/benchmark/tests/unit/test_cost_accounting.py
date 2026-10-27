"""Cost accounting must prefer provider billing over local price guesses."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from invisiblebench.api.typesafe import (
    CostBudgetExceededError,
    CostTracker,
    UnpricedModelCostError,
    maximum_reasonable_cost_ceiling,
)


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
    assert tracker.total == 0.012345


def test_ceiling_refuses_a_reservation_after_spend_reaches_it() -> None:
    tracker = CostTracker()
    tracker.reset(max_cost_usd=0.01)
    tracker.record("provider/model", prompt_tokens=100, completion_tokens=50, actual_cost=0.01)

    with pytest.raises(CostBudgetExceededError, match="cost ceiling"):
        tracker.reserve(0.001)


def test_cost_tracker_prices_judge_when_provider_omits_cost() -> None:
    tracker = CostTracker()

    charged = tracker.record("jev-1.13.0", prompt_tokens=1_000_000, completion_tokens=0)

    assert charged == 0.042


def test_reasonable_cost_ceiling_allows_headroom_without_unbounded_approval() -> None:
    assert maximum_reasonable_cost_ceiling(10.0) == 15.0
    assert maximum_reasonable_cost_ceiling(0.1) == 1.1


def test_unpriced_call_is_counted_as_unknown_not_a_fake_zero() -> None:
    tracker = CostTracker()

    charged = tracker.record("provider/unpriced-model", prompt_tokens=100, completion_tokens=50)

    assert charged == 0.0
    assert tracker.total == 0.0


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
    assert tracker.total == 0.0
    assert tracker._reserved == 0.0  # noqa: SLF001 — settlement released the hold


def test_reported_and_estimated_costs_add_to_the_total() -> None:
    tracker = CostTracker()

    tracker.record("provider/reported-model", 0, 0, actual_cost=0.5)
    tracker.record("jev-1.13.0", prompt_tokens=1_000_000, completion_tokens=0)

    assert tracker.total == pytest.approx(0.542)


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




def test_a_call_without_a_token_count_is_counted_as_unknown() -> None:
    tracker = CostTracker()
    token = tracker.reserve(0.01)

    assert tracker.settle(token, "jev-1.13.0", None, 0) == 0.0

    assert (tracker.total, tracker._reserved) == (0.0, 0.0)  # noqa: SLF001


