"""Inspect scores retain uncertainty and refuse uncertain judge spend."""

import json
from types import SimpleNamespace

import pytest
from inspect_ai.scorer import SampleScore

from invisiblebench.metrics.dimensions import dimension_observation
from invisiblebench.models.scan import EvidenceSpan, Judgment, Verdict
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


def test_inspect_metric_reports_safety_bounds_and_matching_epoch_se():
    rows = []
    for epoch, verdict in ((1, "FAIL"), (2, "PASS")):
        for number in range(5):
            score = inspect_score(
                [
                    (
                        Judgment(
                            model_id="target/model", scenario_id=f"fixture-{number}",
                            check_id="crisis.fixture", plan_sha256="0" * 64,
                            verdict=Verdict(verdict), rationale="fixture",
                            evidence=[EvidenceSpan(role="assistant", turn=1, quote="fixture")]
                            if verdict == "FAIL" else [],
                            answers={},
                        ),
                        {Verdict(verdict)},
                    )
                ]
            )
            score.metadata["epoch"] = epoch
            rows.append(SampleScore(sample_id=f"fixture-{number}", score=score))
    result = dimension_observation(layer="safety", dimension="crisis")(rows)
    assert result["settled"] == 10
    assert result["included_checks"] == 1
    assert result["rate_low"] == 0.5
    assert result["epoch_standard_error"] == pytest.approx(0.5)


def test_inspect_care_metric_preserves_unclear_fail_possibility():
    score = inspect_score(
        [
            (
                Judgment(
                    model_id="target/model", scenario_id="fixture",
                    check_id="attunement.fixture", plan_sha256="0" * 64,
                    verdict=Verdict.UNCLEAR, rationale="fixture", evidence=[], answers={},
                ),
                {Verdict.PASS, Verdict.FAIL},
            )
        ]
    )
    result = dimension_observation(layer="care", dimension="attunement")(
        [SampleScore(sample_id="fixture", score=score)]
    )
    assert result["rate_low"] == 0
    assert result["rate_high"] == 1
    assert result["unclear_fail_possible"] == 1
    assert result["settled"] == 0


def test_repeated_epochs_do_not_create_safety_check_coverage():
    score = inspect_score(
        [
            (
                Judgment(
                    model_id="target/model", scenario_id="fixture",
                    check_id="crisis.fixture", plan_sha256="0" * 64,
                    verdict=Verdict.PASS, rationale="fixture", evidence=[], answers={},
                ),
                {Verdict.PASS},
            )
        ]
    )
    scores = [SampleScore(sample_id="fixture", score=score) for _ in range(5)]
    result = dimension_observation(layer="safety", dimension="crisis")(scores)
    assert result["settled"] == 5
    assert result["included_checks"] == 0
    assert result["rate_low"] is None


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

    def forbid_judge(*_args, **_kwargs):
        raise AssertionError("saved answers must replay without constructing a judge client")

    monkeypatch.setattr(judge, "SystemOneClient", forbid_judge)
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
    assert log.results and log.results.scores
    assert {
        (metric.params["layer"], metric.params["dimension"])
        for metric in log.results.scores[0].metrics.values()
    } == {
        ("safety", "crisis"), ("safety", "scope"),
        ("safety", "identity"), ("safety", "autonomy"),
        ("care", "belonging"), ("care", "attunement"),
        ("care", "relational"), ("care", "advocacy"),
    }


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


def _fixture_scoring(monkeypatch):
    from inspect_ai.model import ChatMessageAssistant, ChatMessageUser

    from invisiblebench import judge
    from invisiblebench.api.typesafe import DEFAULT_JUDGE_MODEL, dispatch_reservation
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
            self.tracker.settle(token, kwargs["model"], 0, 0, actual_cost=0.001)
            return super().ask(**kwargs)

    def forbid(*_args, **_kwargs):
        raise AssertionError("no judge client may be constructed")

    monkeypatch.setattr(judge, "SystemOneClient", BilledJudge)

    def state(sample_id, reply_metadata=None):
        return SimpleNamespace(
            model="fixture/model",
            sample_id=sample_id,
            epoch=1,
            messages=[
                ChatMessageUser(content="I need help.", metadata={"turn": 1}),
                ChatMessageAssistant(
                    content="Please call someone.", metadata={"turn": 1, **(reply_metadata or {})}
                ),
            ],
        )

    def score(root, sample_id, *, plan_only=False):
        return inspect_scorer._score_sync(
            state(sample_id),
            ledger_dir=root,
            judge_model=DEFAULT_JUDGE_MODEL,
            max_cost_usd=0.01,
            plan_only=plan_only,
        )

    return inspect_scorer, judge, calls, state, score, forbid


def test_truncated_reply_is_unscored_before_plan_or_dispatch(tmp_path, monkeypatch):
    from invisiblebench.api.typesafe import DEFAULT_JUDGE_MODEL

    scorer, judge, calls, state, _score, forbid = _fixture_scoring(monkeypatch)
    monkeypatch.setattr(judge, "SystemOneClient", forbid)
    for plan_only in (True, False):
        result = scorer._score_sync(
            state("cut", {"truncated": True}),
            ledger_dir=tmp_path,
            judge_model=DEFAULT_JUDGE_MODEL,
            max_cost_usd=0.01,
            plan_only=plan_only,
        )
        assert result.metadata["truncated_turns"] == [1]
    assert not tmp_path.exists() or not any(tmp_path.iterdir())
    assert not calls
    rows = [SampleScore(sample_id="cut", score=result)]
    assert dimension_observation(layer="safety", dimension="crisis")(rows)["settled"] == 0


def test_solver_marks_max_tokens_reply_truncated(tmp_path):
    from inspect_ai import eval as inspect_eval
    from inspect_ai.model import ModelOutput, get_model

    from invisiblebench.inspect_task import safety_care, serving_policy

    def outputs(*_):
        output = ModelOutput.from_content(model="mockllm/model", content="Cut off")
        output.choices[0].stop_reason = "max_tokens"
        return output

    model = get_model(
        "mockllm/model", custom_outputs=outputs, provider=serving_policy({})["provider"]
    )
    [log] = inspect_eval(
        safety_care(
            scenario="safety_crisis_disengagement_001",
            judge_dir=str(tmp_path / "judge"),
            judge_max_cost_usd=1.0,
        ),
        model=model,
        log_dir=str(tmp_path / "log"),
        display="none",
    )
    assert log.status == "success", log.error
    replies = [m for m in log.samples[0].messages if m.role == "assistant"]
    assert replies and all(m.metadata["truncated"] is True for m in replies)
    [score] = log.samples[0].scores.values()
    assert score.metadata["truncated_turns"]


def test_journal_loss_refuses_dispatch_but_not_replay(tmp_path, monkeypatch):
    from inspect_ai.model import ChatMessageAssistant, ChatMessageUser

    from invisiblebench.api.typesafe import DEFAULT_JUDGE_MODEL

    scorer, judge, calls, state, score, forbid = _fixture_scoring(monkeypatch)

    def two_turns(sample_id):
        done = state(sample_id)
        done.messages += [
            ChatMessageUser(content="Still here.", metadata={"turn": 2}),
            ChatMessageAssistant(content="Call a friend.", metadata={"turn": 2}),
        ]
        return done

    def run(done, *, plan_only=False):
        return scorer._score_sync(
            done, ledger_dir=tmp_path, judge_model=DEFAULT_JUDGE_MODEL, max_cost_usd=0.01,
            plan_only=plan_only,
        )

    first = two_turns("first")
    run(first, plan_only=True)
    complete = run(first)
    bundle = scorer._sample_dir(tmp_path.resolve(), first)
    answers = (bundle / "answers.jsonl").read_bytes().splitlines(keepends=True)
    assert len(answers) == 2
    (bundle / "attempts.jsonl").unlink()

    # Nothing pending: replay needs no journal and gives the same score.
    dispatched = len(calls)
    monkeypatch.setattr(judge, "SystemOneClient", forbid)
    assert run(first) == complete

    # One request pending beside a saved answer with no journal: refused.
    (bundle / "judgments.jsonl").unlink()
    (bundle / "answers.jsonl").write_bytes(answers[0])
    with pytest.raises(ValueError, match="without a recorded attempt"):
        run(first)
    assert len(calls) == dispatched

    # Another sample's missing journal refuses dispatch of this one.
    (bundle / "answers.jsonl").write_bytes(b"".join(answers))
    (bundle / "attempts.jsonl").unlink(missing_ok=True)
    second = two_turns("second")
    run(second, plan_only=True)
    with pytest.raises(ValueError, match="attempts.jsonl is missing"):
        run(second)
    assert len(calls) == dispatched
