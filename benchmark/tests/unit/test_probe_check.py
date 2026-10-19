"""Probes share scan durability, model identity, and frozen inputs."""

import json

import pytest

from benchmark.tests.fixtures.current_scan import TRANSCRIPT, FixtureJudge
from invisiblebench.cli.agent_commands import get_run_info
from invisiblebench.judge import load_questions
from scripts.probe_check import plan_probe, run_probe


def test_failed_probe_saves_progress_and_resumes(tmp_path):
    source = tmp_path / "conversation.jsonl"
    source.write_text(TRANSCRIPT)
    bundle = tmp_path / "probe"
    plan_probe("identity.fixture-prohibition", [source], bundle)
    assert get_run_info(bundle)["artifact_state"] == "questions_incomplete"

    class Interrupted(FixtureJudge):
        calls = 0

        def ask(self, **kwargs):
            self.calls += 1
            if self.calls == 2:
                assert len((bundle / "answers.jsonl").read_text().splitlines()) == 1
                # Billed with known usage, but missing its answers: retryable.
                return super().ask(**kwargs).model_copy(update={"answers": {}})
            return super().ask(**kwargs)

    with pytest.raises(RuntimeError, match="attempt saved"):
        run_probe(bundle, max_cost_usd=1, client=Interrupted())
    rows = [json.loads(line) for line in (bundle / "answers.jsonl").read_text().splitlines()]
    assert rows[0]["error"] is None and rows[1]["error"] == "invalid_judge_output"
    source.write_text("The external source is no longer available")
    assert run_probe(bundle, max_cost_usd=1, client=FixtureJudge())[0].verdict.value == "PASS"
    assert len((bundle / "answers.jsonl").read_text().splitlines()) == 3
    assert get_run_info(bundle)["artifact_state"] == "questions_complete"
    assert len(load_questions(bundle)[1]) == 3
    lines = (bundle / "answers.jsonl").read_text().splitlines()
    wrong = json.loads(lines[0])
    wrong["judge"]["model"] = "other-model"
    lines[0] = json.dumps(wrong)
    (bundle / "answers.jsonl").write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError, match="different judge"):
        load_questions(bundle)


@pytest.mark.parametrize("unknown", [False, True])
def test_multiple_requests_in_one_turn_resume_by_exact_identity(
    tmp_path, published_checks, unknown
):
    from invisiblebench.api.typesafe import CostBudgetExceededError, cost_tracker

    source = tmp_path / "conversation.jsonl"
    source.write_text(TRANSCRIPT)
    bundle = tmp_path / "probe"
    plan = plan_probe("attunement.advice-first", [source], bundle)
    assert plan.tasks[1].role == plan.tasks[2].role == "assistant"
    assert plan.tasks[1].turn == plan.tasks[2].turn

    class Interrupted(FixtureJudge):
        calls = 0

        def ask(self, **kwargs):
            self.calls += 1
            if self.calls == 3:
                if unknown:
                    raise KeyboardInterrupt("sent but no outcome")
                raise CostBudgetExceededError("refused before dispatch")
            cost_tracker.record(kwargs["model"], 0, 0, actual_cost=0.00001)
            return super().ask(**kwargs)

    first = Interrupted()
    with pytest.raises(KeyboardInterrupt if unknown else CostBudgetExceededError):
        run_probe(bundle, max_cost_usd=1, client=first)
    retained = (bundle / "answers.jsonl").read_bytes()
    _, saved = load_questions(bundle)
    assert len(saved) == 2
    assert len({answer.key for answer in saved}) == 2
    if unknown:
        with pytest.raises(ValueError, match="no automatic resume"):
            run_probe(bundle, max_cost_usd=1, client=first)
        assert first.calls == 3
    else:
        run_probe(bundle, max_cost_usd=1, client=FixtureJudge())
        _, saved = load_questions(bundle)
        assert len(saved) == len(plan.tasks)
        assert sum(a.cost_usd for a in saved) == pytest.approx(0.00002)
    assert (bundle / "answers.jsonl").read_bytes().startswith(retained)


def test_changed_probe_snapshot_is_rejected_before_inference(tmp_path):
    source = tmp_path / "conversation.jsonl"
    source.write_text(TRANSCRIPT)
    bundle = tmp_path / "probe"
    plan_probe("identity.fixture-prohibition", [source], bundle)
    next((bundle / "inputs/transcripts").glob("*.jsonl")).write_text("tampered")
    with pytest.raises(ValueError, match="bundle input changed"):
        run_probe(bundle, max_cost_usd=1, client=FixtureJudge())


@pytest.mark.parametrize("tokens", [None, -1])
def test_invalid_usage_is_unknown_cost_and_blocks_resume(tmp_path, tokens):
    source = tmp_path / "conversation.jsonl"
    source.write_text(TRANSCRIPT)
    bundle = tmp_path / "probe"
    plan_probe("identity.fixture-prohibition", [source], bundle)

    class BadUsage(FixtureJudge):
        def ask(self, **kwargs):
            response = super().ask(**kwargs)
            return response.model_copy(
                update={"usage": response.usage.model_copy(update={"input_tokens": tokens})}
            )

    with pytest.raises(RuntimeError, match="outcome unknown"):
        run_probe(bundle, max_cost_usd=1, client=BadUsage())
    assert load_questions(bundle)[1] == []
    unknown = json.loads((bundle / "attempts.jsonl").read_text().splitlines()[-1])
    assert unknown["event"] == "unknown"
    assert "non-negative input usage" in unknown["detail"]
    assert unknown["response"]["usage"]["input_tokens"] == tokens
    with pytest.raises(ValueError, match="no automatic resume"):
        run_probe(bundle, max_cost_usd=1, client=FixtureJudge())


def _offline_client(sent, input_tokens=100):
    import httpx2

    from invisiblebench.api import typesafe

    def handle(request):
        sent.append(request)
        questions = json.loads(request.content)["questions"]
        return httpx2.Response(
            200,
            json={
                "model": typesafe.DEFAULT_JUDGE_MODEL,
                "usage": {"input_tokens": input_tokens, "output_tokens": 0},
                "answers": {key: {"type": "noul", "noul": 0.1} for key in questions},
            },
        )

    return typesafe.SystemOneClient(
        api_key="offline-test-key",
        http_client=httpx2.Client(transport=httpx2.MockTransport(handle)),
    )


def test_a_ceiling_at_the_estimate_is_refused_before_dispatch_and_says_what_fits(
    tmp_path, monkeypatch
):
    from invisiblebench.api import typesafe
    from invisiblebench.judge import dispatch_budget

    monkeypatch.setattr(typesafe, "cost_tracker", typesafe.CostTracker())
    monkeypatch.setattr("invisiblebench.judge.cost_tracker", typesafe.cost_tracker)
    source = tmp_path / "conversation.jsonl"
    source.write_text(TRANSCRIPT)
    bundle = tmp_path / "probe"
    plan = plan_probe("identity.fixture-prohibition", [source], bundle)
    budget = dispatch_budget(plan.judge.model, plan.estimated_cost_usd)
    assert budget["reservation_usd"] == typesafe.request_cost(
        plan.judge.model, typesafe.JEV_MAX_INPUT_TOKENS
    )
    assert budget["ceiling_at_estimate_usd"] == pytest.approx(
        plan.estimated_cost_usd + budget["reservation_usd"]
    )
    sent = []
    with _offline_client(sent) as client:
        with pytest.raises(typesafe.CostBudgetExceededError) as refused:
            run_probe(bundle, max_cost_usd=plan.estimated_cost_usd, client=client)
    assert sent == []
    message = str(refused.value)
    assert f"{len(plan.tasks)} pending requests" in message
    assert "not a bound" in message and "not a worst case" in message
    attempts = [json.loads(line) for line in (bundle / "attempts.jsonl").read_text().splitlines()]
    assert [row["event"] for row in attempts] == ["attempt", "refused"]

    # The stated ceiling for an allowance completes the resumed run; refusal history stays.
    allowance = len(plan.tasks) * typesafe.request_cost(plan.judge.model, 100)
    with _offline_client(sent) as client:
        run_probe(bundle, max_cost_usd=allowance + budget["reservation_usd"], client=client)
    assert len(sent) == len(plan.tasks)
    assert len(load_questions(bundle)[1]) == len(plan.tasks)
    events = [json.loads(line)["event"] for line in (bundle / "attempts.jsonl").read_text().splitlines()]
    assert events[:2] == ["attempt", "refused"]


def test_a_mid_run_refusal_reports_saved_spend_and_remaining_work(tmp_path, monkeypatch):
    from invisiblebench.api import typesafe

    monkeypatch.setattr(typesafe, "cost_tracker", typesafe.CostTracker())
    monkeypatch.setattr("invisiblebench.judge.cost_tracker", typesafe.cost_tracker)
    source = tmp_path / "conversation.jsonl"
    source.write_text(TRANSCRIPT)
    bundle = tmp_path / "probe"
    plan = plan_probe("identity.fixture-prohibition", [source], bundle)
    assert len(plan.tasks) >= 2
    reservation = typesafe.dispatch_reservation(plan.judge.model)
    per_call = typesafe.request_cost(plan.judge.model, 10_000)
    sent = []
    # Fits the first reservation only; the second needs spend + reservation.
    with _offline_client(sent, input_tokens=10_000) as client:
        with pytest.raises(typesafe.CostBudgetExceededError) as refused:
            run_probe(bundle, max_cost_usd=reservation + per_call / 2, client=client)
    assert len(sent) == 1
    message = str(refused.value)
    assert f"{len(plan.tasks) - 1} pending requests" in message
    assert f"saved spend ${per_call:.6f}" in message
    accepted = typesafe.maximum_reasonable_cost_ceiling(plan.estimated_cost_usd)
    assert f"at most ${accepted:.6f}" in message
    saved = (bundle / "answers.jsonl").read_bytes()
    # Resume deducts saved spend: the same ceiling cannot fit another reservation.
    with _offline_client(sent, input_tokens=10_000) as client:
        with pytest.raises(typesafe.CostBudgetExceededError):
            run_probe(bundle, max_cost_usd=reservation + per_call / 2, client=client)
    assert len(sent) == 1
    assert (bundle / "answers.jsonl").read_bytes() == saved
    # A ceiling of spend + allowance + reservation resumes exactly the remaining work.
    allowance = (len(plan.tasks) - 1) * per_call
    with _offline_client(sent, input_tokens=10_000) as client:
        run_probe(bundle, max_cost_usd=per_call + allowance + reservation, client=client)
    assert len(sent) == len(plan.tasks)
    assert (bundle / "answers.jsonl").read_bytes().startswith(saved)
    assert sum(a.cost_usd for a in load_questions(bundle)[1]) == pytest.approx(
        len(plan.tasks) * per_call
    )


def test_reported_budget_follows_price_and_request_size(monkeypatch):
    from invisiblebench.api import typesafe
    from invisiblebench.judge import describe_budget, dispatch_budget

    model = typesafe.DEFAULT_JUDGE_MODEL
    small = typesafe.estimated_cost(model, 3_000)
    large = typesafe.estimated_cost(model, 30_000)
    assert large == pytest.approx(10 * small)
    before = dispatch_budget(model, small)
    # The fixed reservation does not shrink with the payload; the estimate does.
    assert dispatch_budget(model, large)["reservation_usd"] == before["reservation_usd"]
    monkeypatch.setitem(typesafe.JUDGE_PRICING, model, 2 * typesafe.JUDGE_PRICING[model])
    after = dispatch_budget(model, typesafe.estimated_cost(model, 3_000))
    assert after["reservation_usd"] == pytest.approx(2 * before["reservation_usd"])
    assert after["estimated_cost_usd"] == pytest.approx(2 * before["estimated_cost_usd"])
    for unpriced in (dispatch_budget(model, None), dispatch_budget("unpriced-judge", small)):
        assert unpriced["ceiling_at_estimate_usd"] is None
        assert unpriced["accepted_ceiling_usd"] is None
        assert "no ceiling can be accepted" in describe_budget(unpriced)
