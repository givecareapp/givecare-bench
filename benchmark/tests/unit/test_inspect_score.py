"""Inspect scores retain uncertainty and refuse uncertain judge spend."""

import json
from types import SimpleNamespace

import pytest

from invisiblebench.models.scan import Judgment, Verdict
from invisiblebench.scorers.core import inspect_score
from invisiblebench.scorers.inspect import _saved_cost


def test_unclear_score_records_settled_possibilities():
    judgment = Judgment(
        model_id="target/model",
        scenario_id="fixture",
        check_id="attunement.advice-first",
        plan_sha256="0" * 64,
        verdict=Verdict.UNCLEAR,
        rationale="The cue is unresolved.",
        evidence=[],
        answers={},
    )

    score = inspect_score([(judgment, {Verdict.FAIL, Verdict.PASS})])

    assert score.value == {"attunement.advice-first": "UNCLEAR"}
    assert score.metadata["checks"][0]["possible_verdicts"] == ["FAIL", "PASS"]
    assert score.metadata["checks"][0]["plan_sha256"] == "0" * 64


def test_inspect_eval_saves_scored_log_with_fixture_judge(tmp_path, monkeypatch):
    from inspect_ai import eval as inspect_eval
    from inspect_ai import score as inspect_rescore
    from inspect_ai.model import ModelCost, ModelInfo, ModelOutput, get_model, set_model_info

    from invisiblebench import judge
    from invisiblebench.inspect_task import safety_care, serving_policy
    from invisiblebench.scorers.inspect import safety_care_scorer
    from invisiblebench.synthetic import FixtureJudge

    class OfflineJudge(FixtureJudge):
        def __init__(self, *, tracker=None):
            self.tracker = tracker

    monkeypatch.setattr(judge, "SystemOneClient", OfflineJudge)
    model = get_model(
        "mockllm/model",
        custom_outputs=lambda *_: ModelOutput.from_content(
            model="mockllm/model", content="I hear you. Please stay with someone you trust."
        ),
        provider=serving_policy({})["provider"],
    )
    set_model_info(
        "mockllm/model",
        ModelInfo(
            cost=ModelCost(input=0.0, output=0.0, input_cache_write=0.0, input_cache_read=0.0)
        ),
    )
    options = {
        "scenario": "safety_crisis_disengagement_001",
        "judge_dir": str(tmp_path / "judge"),
        "judge_max_cost_usd": 1.0,
    }
    [planned] = inspect_eval(
        safety_care(**options),
        model=model,
        log_dir=str(tmp_path / "preflight"),
        display="none",
    )
    assert planned.status == "success", planned.error
    assert not any(
        (message.metadata or {}).get("branch_decisions")
        for sample in planned.samples or []
        for message in sample.messages
    )
    rescored = inspect_rescore(
        planned,
        safety_care_scorer(str(tmp_path / "judge"), 1.0, plan_only=False),
        model=model,
        display="none",
    )
    assert rescored.samples and rescored.samples[0].scores
    [log] = inspect_eval(
        safety_care(
            **options,
            judge_plan_only=False,
        ),
        model=model,
        log_dir=str(tmp_path / "inspect"),
        display="none",
    )

    assert log.status == "success", log.error
    assert log.samples and log.samples[0].scores
    [score] = log.samples[0].scores.values()
    assert score.value
    assert len(score.metadata["checks"]) == len(score.value)


def test_unsettled_attempt_in_one_sample_stops_other_sample_dispatch(tmp_path):
    first = tmp_path / "first"
    first.mkdir()
    (first / "attempts.jsonl").write_text(
        json.dumps({"event": "attempt", "key": ["target", "case", "assistant", 1, "0" * 64]})
        + "\n"
    )

    with pytest.raises(ValueError, match="no saved outcome"):
        _saved_cost(tmp_path)


def test_run_ceiling_is_shared_across_inspect_samples(tmp_path, monkeypatch):
    from inspect_ai.model import ChatMessageAssistant, ChatMessageUser

    from invisiblebench import judge
    from invisiblebench.api.typesafe import (
        DEFAULT_JUDGE_MODEL,
        CostBudgetExceededError,
        dispatch_reservation,
    )
    from invisiblebench.models.scan import Check, Clause, Question
    from invisiblebench.scorers import inspect as inspect_scorer
    from invisiblebench.synthetic import FixtureJudge

    check = Check(
        id="crisis.fixture",
        name="fixture_rule",
        severity="S5",
        summary="A fixture check.",
        questions={"routing": Question(instructions="Does the assistant route?")},
        fail_if=[Clause(question="routing", is_=True)],
        layer="safety",
        dimension="crisis",
        definition_sha256="0" * 64,
    )
    monkeypatch.setattr(inspect_scorer, "load_checks", lambda: {check.id: check})
    calls = []

    class BilledJudge(FixtureJudge):
        def __init__(self, *, tracker):
            self.tracker = tracker

        def ask(self, **kwargs):
            token = self.tracker.reserve(dispatch_reservation(kwargs["model"]))
            calls.append(kwargs)
            self.tracker.settle(token, kwargs["model"], 0, 0, actual_cost=0.002)
            return super().ask(**kwargs)

    monkeypatch.setattr(judge, "SystemOneClient", BilledJudge)

    def state(sample_id):
        return SimpleNamespace(
            model="fixture/model",
            sample_id=sample_id,
            epoch=1,
            messages=[
                ChatMessageUser(content="I need help.", metadata={"turn": 1}),
                ChatMessageAssistant(content="Please call someone.", metadata={"turn": 1}),
            ],
        )

    with pytest.raises(ValueError, match="saved dry-run"):
        inspect_scorer._score_sync(
            state("first"),
            ledger_dir=tmp_path,
            judge_model=DEFAULT_JUDGE_MODEL,
            max_cost_usd=0.003,
            plan_only=False,
        )
    assert not calls
    inspect_scorer._score_sync(
        state("first"), ledger_dir=tmp_path, judge_model=DEFAULT_JUDGE_MODEL, max_cost_usd=0.003
    )
    inspect_scorer._score_sync(
        state("first"),
        ledger_dir=tmp_path,
        judge_model=DEFAULT_JUDGE_MODEL,
        max_cost_usd=0.003,
        plan_only=False,
    )
    assert _saved_cost(tmp_path) == pytest.approx(0.002)
    inspect_scorer._score_sync(
        state("second"),
        ledger_dir=tmp_path,
        judge_model=DEFAULT_JUDGE_MODEL,
        max_cost_usd=0.003,
    )
    with pytest.raises(CostBudgetExceededError) as refused:
        inspect_scorer._score_sync(
            state("second"),
            ledger_dir=tmp_path,
            judge_model=DEFAULT_JUDGE_MODEL,
            max_cost_usd=0.003,
            plan_only=False,
        )
    assert "ceiling" in str(refused.value)
    assert len(calls) == 1
    assert _saved_cost(tmp_path) == pytest.approx(0.002)
