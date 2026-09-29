"""Purchased responses survive interruption; ambiguous attempts never auto-retry."""

import asyncio
import json

import pytest

from invisiblebench.api.client import CostBudgetExceededError
from invisiblebench.cli.generation import GenerationJournal


def test_completed_calls_replay_and_refused_calls_can_resume(tmp_path):
    path = tmp_path / "attempts.jsonl"
    calls = []

    async def answer():
        calls.append(1)
        return {"response": "retained", "cost": 0.2}

    async def refused():
        raise CostBudgetExceededError("ceiling")

    async def run():
        with GenerationJournal(path, {"model": "fixture"}) as journal:
            assert await journal.call("1", {"message": "hi"}, answer) == {
                "response": "retained",
                "cost": 0.2,
            }
            with pytest.raises(CostBudgetExceededError):
                await journal.call("2", {}, refused)
        with GenerationJournal(path, {"model": "fixture"}) as journal:
            await journal.call("1", {"message": "hi"}, answer)
            await journal.call("2", {}, answer)

    asyncio.run(run())
    assert calls == [1, 1]
    assert GenerationJournal.inspect(path)["cost"] == 0.4
    with pytest.raises(ValueError, match="contract"):
        with GenerationJournal(path, {"model": "changed"}):
            pass


def test_ambiguous_dispatch_blocks_resume_and_preserves_bytes(tmp_path):
    path = tmp_path / "attempts.jsonl"

    async def interrupted():
        raise asyncio.CancelledError()

    async def run():
        with GenerationJournal(path, {}) as journal:
            with pytest.raises(asyncio.CancelledError):
                await journal.call("1", {}, interrupted)

    asyncio.run(run())
    before = path.read_bytes()
    with pytest.raises(ValueError, match="ambiguous"):
        GenerationJournal.inspect(path)
    assert path.read_bytes() == before


def test_unknown_cost_saves_response_then_stops(tmp_path):
    path = tmp_path / "attempts.jsonl"

    async def answer():
        return {"response": "paid but unpriced", "cost": 0.0, "cost_known": False}

    async def run():
        with GenerationJournal(path, {}) as journal:
            with pytest.raises(ValueError, match="cost is unknown"):
                await journal.call("1", {}, answer)

    asyncio.run(run())
    assert "paid but unpriced" in path.read_text()
    with pytest.raises(ValueError, match="unknown provider cost"):
        GenerationJournal.inspect(path)


def test_partial_record_is_not_silently_discarded(tmp_path):
    path = tmp_path / "attempts.jsonl"
    path.write_text(json.dumps({"contract": {}}) + '\n{"attempt":')
    with pytest.raises(ValueError, match="incomplete"):
        GenerationJournal.inspect(path)


def test_scenario_resumes_after_budget_refusal_without_rebuying_turns(tmp_path):
    from benchmark.tests.unit.test_transcript_only_pipeline import _FakeAsyncClient, _write_scenario
    from invisiblebench.cli.transcript import evaluate_scenario_async

    path = tmp_path / "scenario.json"
    _write_scenario(path)
    data = json.loads(path.read_text())
    data["turns"].append({"turn_number": 2, "user_message": "What next?"})
    path.write_text(json.dumps(data))

    class Interrupted(_FakeAsyncClient):
        async def call_model_async(self, **kwargs):
            if self.calls:
                raise CostBudgetExceededError("stop before turn two")
            return await super().call_model_async(**kwargs)

    first, resumed = Interrupted(), _FakeAsyncClient()

    async def generate(client):
        return await evaluate_scenario_async(
            {"id": "fixture/model", "name": "Fixture"},
            {"path": str(path), "name": "Fixture", "category": "context"},
            client,
            tmp_path / "run",
            asyncio.Semaphore(1),
        )

    with pytest.raises(CostBudgetExceededError):
        asyncio.run(generate(first))
    row = asyncio.run(generate(resumed))
    assert row["status"] == "transcript_ready"
    assert len(first.calls) == len(resumed.calls) == 1
    assert resumed.calls[0][-2]["content"] == "I can help with that."
    replay = _FakeAsyncClient()
    assert asyncio.run(generate(replay))["status"] == "transcript_ready"
    assert replay.calls == []


def test_http_pool_is_reused_and_closed_and_permanent_errors_are_not_retried(monkeypatch):
    import httpx

    from invisiblebench.api import client as module

    monkeypatch.setenv("OPENROUTER_API_KEY", "offline-fixture")
    monkeypatch.delenv("INVISIBLEBENCH_DISABLE_LLM", raising=False)
    made, sent = [], []
    native = httpx.AsyncClient

    def respond(request):
        sent.append(request)
        return httpx.Response(400, json={"error": "invalid model"})

    def create(**kwargs):
        instance = native(transport=httpx.MockTransport(respond), **kwargs)
        made.append(instance)
        return instance

    monkeypatch.setattr(module.httpx, "AsyncClient", create)
    client = module.ModelAPIClient()
    module.cost_tracker.reset()

    async def run():
        try:
            for _ in range(2):
                with pytest.raises(httpx.HTTPStatusError):
                    await client.call_model_async("fixture", [])
        finally:
            await client.aclose()

    asyncio.run(run())
    assert len(made) == 1
    assert len(sent) == 2
    assert all(
        request.headers["User-Agent"] == "OpenAI File Downloader, XaiImageApiFetch/1.0"
        for request in sent
    )
    assert made[0].is_closed


@pytest.mark.parametrize("endpoint", [None, "test-provider"])
def test_serving_policy_is_frozen_and_sent(tmp_path, endpoint):
    from benchmark.tests.unit.test_transcript_only_pipeline import _FakeAsyncClient, _write_scenario
    from invisiblebench.cli.transcript import evaluate_scenario_async, generation_contract

    path = tmp_path / "scenario.json"
    _write_scenario(path)
    model = {"id": "fixture/model", "name": "Fixture", "endpoint": endpoint}
    scenario = {"path": str(path), "name": "Fixture", "category": "context"}
    sent = []

    class Client(_FakeAsyncClient):
        async def call_model_async(self, **kwargs):
            sent.append(kwargs)
            return await super().call_model_async(**kwargs)

    client = Client()
    contract = generation_contract(model, scenario, client)
    policy = contract["policy"]["serving"][model["id"]]
    assert policy["measurement"] == ("pinned_provider" if endpoint else "routed_service")
    assert policy["provider"]["allow_fallbacks"] is (endpoint is None)
    assert policy["provider"]["require_parameters"] is True
    if endpoint:
        assert policy["provider"]["only"] == [endpoint]
    asyncio.run(
        evaluate_scenario_async(model, scenario, client, tmp_path / "run", asyncio.Semaphore(1))
    )
    assert sent[0]["provider"] == policy["provider"]
    changed = dict(model, endpoint="another-provider")
    with pytest.raises(ValueError, match="contract"):
        asyncio.run(
            evaluate_scenario_async(
                changed, scenario, client, tmp_path / "run", asyncio.Semaphore(1)
            )
        )
    assert len(sent) == 1


def test_scan_preflights_later_requests_before_any_dispatch(tmp_path):
    from invisiblebench.judge import execute_requests

    class NeverCalled:
        def ask(self, **kwargs):
            pytest.fail("scan dispatched before validating all requests")

    requests = {
        ("model", "scenario"): {
            ("assistant", 1): {"state": "small", "questions": {}},
            ("assistant", 2): {"state": "x" * 100_000, "questions": {}},
        }
    }
    with pytest.raises(ValueError, match="longest question"):
        with execute_requests(
            tmp_path,
            model="jev-1.13.0",
            plan_sha256="0" * 64,
            requests=requests,
            estimate=0.01,
            max_cost_usd=0.01,
            client=NeverCalled(),
        ):
            pass
    assert not (tmp_path / "answers.jsonl").exists()


def test_runner_restores_costs_and_validates_inputs_before_resuming(tmp_path, monkeypatch):
    from benchmark.tests.unit.test_transcript_only_pipeline import _FakeAsyncClient, _write_scenario
    from invisiblebench.api import client as api
    from invisiblebench.cli import run_command

    path = tmp_path / "scenario.json"
    _write_scenario(path)
    data = json.loads(path.read_text())
    data["turns"].append({"turn_number": 2, "user_message": "What next?"})
    path.write_text(json.dumps(data))
    monkeypatch.setenv("OPENROUTER_API_KEY", "offline-fixture")
    monkeypatch.setattr(
        run_command,
        "get_scenarios",
        lambda **_: [
            {
                "path": str(path),
                "scenario_id": data["scenario_id"],
                "name": "Fixture",
                "category": "context",
            }
        ],
    )
    instances = []

    class Client(_FakeAsyncClient):
        def __init__(self):
            super().__init__()
            self.closed = False
            instances.append(self)

        async def aclose(self):
            self.closed = True

        async def call_model_async(self, **kwargs):
            if len(instances) == 1 and self.calls:
                raise CostBudgetExceededError("offline interruption")
            value = await super().call_model_async(**kwargs)
            value.update(cost=0.001, raw={"usage": {"cost": 0.001}})
            api.cost_tracker.record(kwargs["model"], 4, 4, actual_cost=0.001)
            return value

    monkeypatch.setattr(api, "ModelAPIClient", Client)
    model = {
        "id": "fixture/model",
        "name": "Fixture",
        "cost_per_m_input": 1.0,
        "cost_per_m_output": 1.0,
    }
    kwargs = {
        "models": [model],
        "output_dir": tmp_path / "run",
        "auto_confirm": True,
        "max_cost_usd": 0.1,
    }
    assert run_command.run_benchmark(**kwargs) == 1
    assert run_command.run_benchmark(**kwargs) == 0
    assert [len(c.calls) for c in instances] == [1, 1]
    assert all(c.closed for c in instances)
    assert api.cost_tracker.total == pytest.approx(0.002)
    data["turns"][0]["user_message"] = "Changed evidence"
    path.write_text(json.dumps(data))
    assert run_command.run_benchmark(**kwargs) == 2
    assert instances[-1].calls == []


def test_runner_drains_sibling_tasks_before_closing_client(tmp_path, monkeypatch):
    from benchmark.tests.unit.test_transcript_only_pipeline import _write_scenario
    from invisiblebench.api import client as api
    from invisiblebench.cli import run_command

    path = tmp_path / "scenario.json"
    _write_scenario(path)
    monkeypatch.setenv("OPENROUTER_API_KEY", "offline-fixture")
    monkeypatch.setattr(
        run_command,
        "get_scenarios",
        lambda **_: [
            {
                "path": str(path),
                "scenario_id": "context_unit_test_001",
                "name": "Fixture",
                "category": "context",
            }
        ],
    )
    started = asyncio.Event()
    state = {"drained": False, "closed": False}

    class Client:
        async def aclose(self):
            assert state["drained"]
            state["closed"] = True

    async def evaluate(model, *_args, **_kwargs):
        if model["id"] == "first":
            await started.wait()
            raise CostBudgetExceededError("stop")
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            state["drained"] = True

    monkeypatch.setattr(api, "ModelAPIClient", Client)
    monkeypatch.setattr(run_command, "evaluate_scenario_async", evaluate)
    models = [
        {"id": name, "name": name, "cost_per_m_input": 1.0, "cost_per_m_output": 1.0}
        for name in ("first", "second")
    ]
    assert (
        run_command.run_benchmark(
            models, tmp_path / "run", auto_confirm=True, parallel=2, max_cost_usd=0.1
        )
        == 1
    )
    assert state == {"drained": True, "closed": True}


def test_oversized_crisis_evidence_is_rejected_not_truncated(published_checks):
    from invisiblebench.evaluation.check_registry import load_checks
    from invisiblebench.evaluation.requests import build_requests

    turns = [
        entry
        for n in range(1, 19)
        for entry in (
            {"role": "user", "turn": n, "content": f"Caregiver {n}: I need help."},
            {"role": "assistant", "turn": n, "content": f"Reply-{n:02d} " + "support " * 2000},
        )
    ]
    frozen = json.dumps(turns, sort_keys=True)
    with pytest.raises(ValueError, match="longest question"):
        build_requests(list(load_checks().values()), turns, "assistant", 18)
    assert json.dumps(turns, sort_keys=True) == frozen
