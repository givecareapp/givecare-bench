"""A scan retains each answer and remains usable after its bundle moves."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from typesafe_sdk import ChoiceAnswer, SystemOneResponse, Usage

from benchmark.tests.fixtures.current_scan import FixtureJudge, ScriptedJudge, write_source_run
from invisiblebench.api.client import cost_tracker
from invisiblebench.api.typesafe import DEFAULT_JUDGE_MODEL
from invisiblebench.judge import (
    ANSWERS_FILE,
    LEDGER_FILE,
    load_scan,
    plan_scan,
    replay_scan,
    run_scan,
)

# The fixture judge bills a round cent per request, well above the plan's own
# estimate, so paid tests approve a budget instead of the estimate.
BUDGET = 0.5


def source_run(root: Path) -> Path:
    return write_source_run(root, roster=[("fixture-case", "context")])


class Judge(FixtureJudge):
    """Count requests, prove each answer is saved before the next, and bill each one."""

    def __init__(self, bundle: Path, stop_after: int | None = None):
        self.bundle = bundle
        self.stop_after = stop_after
        self.calls = 0
        self.initial_count = len(load_scan(bundle, verify_judgments=False)[1])

    def ask(self, **kwargs):
        saved = load_scan(self.bundle, verify_judgments=False)[1]
        assert len(saved) == self.initial_count + self.calls
        if self.calls == self.stop_after:
            raise KeyboardInterrupt("Simulated interruption; no network")
        self.calls += 1
        cost_tracker.record(kwargs["model"], 0, 0, actual_cost=0.001)
        return super().ask(**kwargs)


def test_resume_keeps_completed_answers_and_cost(tmp_path):
    bundle = tmp_path / "scan"
    plan = plan_scan([source_run(tmp_path)], bundle, judge_model=DEFAULT_JUDGE_MODEL)
    first = Judge(bundle, stop_after=2)
    with pytest.raises(KeyboardInterrupt):
        run_scan(bundle, max_cost_usd=BUDGET, client=first)
    saved = (bundle / ANSWERS_FILE).read_bytes()
    assert len(load_scan(bundle)[1]) == 2
    assert not (bundle / LEDGER_FILE).exists()

    resumed = Judge(bundle)
    judgments = run_scan(bundle, max_cost_usd=BUDGET, client=resumed)
    plan, answers, stored = load_scan(bundle, complete=True)
    assert resumed.calls == plan.planned_requests - 2
    assert (bundle / ANSWERS_FILE).read_bytes().startswith(saved)
    assert sum(answer.cost_usd for answer in answers) == pytest.approx(
        plan.planned_requests * 0.001
    )
    assert stored == judgments
    assert len(judgments) == plan.planned_judgments


def test_bundle_moves_without_original_sources_and_replays(tmp_path):
    bundle = tmp_path / "scan"
    source = source_run(tmp_path)
    plan_scan([source], bundle, judge_model=DEFAULT_JUDGE_MODEL)
    run_scan(bundle, max_cost_usd=BUDGET, client=Judge(bundle))
    source.rename(tmp_path / "original-source-moved")
    moved = tmp_path / "moved-scan"
    bundle.rename(moved)
    assert replay_scan(moved) == []
    assert load_scan(moved, complete=True)[2]
    assert str(tmp_path) not in (moved / "scan_plan.json").read_text()
    assert str(tmp_path) not in (moved / ANSWERS_FILE).read_text()
    assert str(tmp_path) not in (moved / LEDGER_FILE).read_text()


def test_resume_recovers_only_an_unfinished_last_line(tmp_path):
    bundle = tmp_path / "scan"
    plan = plan_scan([source_run(tmp_path)], bundle, judge_model=DEFAULT_JUDGE_MODEL)
    with pytest.raises(KeyboardInterrupt):
        run_scan(bundle, max_cost_usd=BUDGET, client=Judge(bundle, stop_after=2))
    with (bundle / ANSWERS_FILE).open("ab") as journal:
        journal.write(b'{"incomplete":')
    with pytest.raises(ValueError, match="unfinished last line"):
        load_scan(bundle)
    run_scan(bundle, max_cost_usd=BUDGET, client=FixtureJudge())
    assert len(load_scan(bundle, complete=True)[1]) == plan.planned_requests


def test_technical_attempt_retains_cost_and_only_unfinished_work_retries(tmp_path):
    bundle = tmp_path / "scan"
    plan = plan_scan([source_run(tmp_path)], bundle)

    class BrokenJudge:
        def ask(self, **kwargs):
            cost_tracker.record(kwargs["model"], 0, 0, actual_cost=0.001)
            return {"model": kwargs["model"], "nouls": {"invented": 0.5}}

    with pytest.raises(RuntimeError, match="attempt saved"):
        run_scan(bundle, max_cost_usd=BUDGET, client=BrokenJudge())
    attempt = load_scan(bundle)[1][0]
    assert attempt.error == "invalid_judge_output" and attempt.cost_usd == 0.001
    assert attempt.answers is None
    run_scan(bundle, max_cost_usd=BUDGET, client=FixtureJudge())
    plan, answers, judgments = load_scan(bundle, complete=True)
    assert len(answers) == plan.planned_requests + 1
    assert sum(answer.cost_usd for answer in answers) == pytest.approx(0.001)
    assert len([answer for answer in answers if answer.key == attempt.key]) == 2
    assert len(judgments) == plan.planned_judgments
    assert replay_scan(bundle) == []


def test_a_judge_api_failure_is_saved_and_retried(tmp_path):
    bundle = tmp_path / "scan"
    plan = plan_scan([source_run(tmp_path)], bundle)

    class UnavailableJudge:
        def ask(self, **kwargs):
            raise RuntimeError("unavailable")

    with pytest.raises(RuntimeError, match="attempt saved"):
        run_scan(bundle, max_cost_usd=plan.estimated_cost_usd, client=UnavailableJudge())
    attempt = load_scan(bundle)[1][0]
    assert attempt.error == "judge_api_error" and attempt.answers is None
    assert attempt.error_detail == "RuntimeError"
    run_scan(bundle, max_cost_usd=plan.estimated_cost_usd, client=FixtureJudge())
    assert load_scan(bundle, complete=True)[2]


def test_running_bundle_rejects_a_second_writer(tmp_path):
    import fcntl

    bundle = tmp_path / "scan"
    plan = plan_scan([source_run(tmp_path)], bundle)
    with (bundle / ANSWERS_FILE).open("ab") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError, match="already running"):
            run_scan(bundle, max_cost_usd=plan.estimated_cost_usd)


def test_stale_contract_and_nested_legacy_record_are_rejected(tmp_path):
    import json

    bundle = tmp_path / "scan"
    plan = plan_scan([source_run(tmp_path)], bundle)
    path = bundle / "scan_plan.json"
    payload = json.loads(path.read_bytes())
    payload["judge"]["thresholds"]["low"] = 0.2
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="current benchmark"):
        run_scan(bundle, max_cost_usd=plan.estimated_cost_usd)
    (bundle / ANSWERS_FILE).write_text('{"mode_results":[]}\n')
    with pytest.raises(ValueError):
        load_scan(bundle)


def test_stored_judgments_must_match_the_saved_answers(tmp_path):
    import json

    bundle = tmp_path / "scan"
    plan = plan_scan([source_run(tmp_path)], bundle)
    run_scan(bundle, max_cost_usd=plan.estimated_cost_usd, client=FixtureJudge())
    ledger = bundle / LEDGER_FILE
    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    rows[0]["verdict"] = "UNCLEAR"
    ledger.write_text("".join(json.dumps(row) + "\n" for row in rows))
    with pytest.raises(ValueError, match="stored judgments differ from the saved answers"):
        load_scan(bundle)
    assert replay_scan(bundle) == [
        "/".join((rows[0]["model_id"], rows[0]["scenario_id"], rows[0]["check_id"]))
    ]
    # An edited ledger is never repaired in place; only a missing one is derived again.
    with pytest.raises(ValueError, match="stored judgments differ"):
        run_scan(bundle, max_cost_usd=plan.estimated_cost_usd, client=FixtureJudge())
    ledger.unlink()
    run_scan(bundle, max_cost_usd=plan.estimated_cost_usd, client=FixtureJudge())
    assert replay_scan(bundle) == []


def test_a_changed_answer_probability_changes_the_verdict(tmp_path):
    bundle = tmp_path / "scan"
    plan = plan_scan([source_run(tmp_path)], bundle)
    run_scan(
        bundle,
        max_cost_usd=plan.estimated_cost_usd,
        client=ScriptedJudge({"cue": 0.9, "routing": 0.0}),
    )
    verdicts = {judgment.check_id: judgment.verdict.value for judgment in load_scan(bundle)[2]}
    assert verdicts["crisis.fixture-cue"] == "FAIL"
    assert verdicts["identity.fixture-prohibition"] == "PASS"


# --- review findings 2026-09-19 ---------------------------------------------


def test_replay_sees_reordered_judgment_rows(tmp_path):
    bundle = tmp_path / "scan"
    plan_scan([source_run(tmp_path)], bundle)
    run_scan(bundle, max_cost_usd=BUDGET, client=FixtureJudge())
    ledger = bundle / LEDGER_FILE
    lines = ledger.read_text().splitlines(keepends=True)
    ledger.write_text("".join([lines[1], lines[0], *lines[2:]]))
    assert len(replay_scan(bundle)) == 2
    with pytest.raises(ValueError, match="stored judgments differ"):
        load_scan(bundle)


def test_a_transcript_cannot_repeat_a_role_and_turn(tmp_path):
    source = source_run(tmp_path)
    path = next((source / "transcripts").glob("*.jsonl"))
    path.write_text(
        '{"role":"user","turn":1,"content":"Hello."}\n'
        '{"role":"assistant","turn":1,"content":"I can help."}\n'
        '{"role":"assistant","turn":1,"content":"A second reply with the same number."}\n'
    )
    with pytest.raises(ValueError, match="repeat a role and turn"):
        plan_scan([source], tmp_path / "scan")


def test_an_invalid_answer_keeps_its_billed_tokens(tmp_path):
    bundle = tmp_path / "scan"
    plan_scan([source_run(tmp_path)], bundle)

    class HalfAnswer(FixtureJudge):
        def ask(self, **kwargs):
            result = super().ask(**kwargs)
            result.answers.popitem()
            return result

    with pytest.raises(RuntimeError, match="invalid_judge_output"):
        run_scan(bundle, max_cost_usd=BUDGET, client=HalfAnswer())
    attempt = load_scan(bundle, verify_judgments=False)[1][0]
    assert attempt.error == "invalid_judge_output"
    assert attempt.input_tokens == 100


def test_a_complete_scan_is_not_rewritten_and_rejects_a_bad_budget(tmp_path):
    bundle = tmp_path / "scan"
    plan_scan([source_run(tmp_path)], bundle)
    run_scan(bundle, max_cost_usd=BUDGET, client=FixtureJudge())
    ledger = bundle / LEDGER_FILE
    before = ledger.stat().st_mtime_ns
    with pytest.raises(ValueError, match="finite and positive"):
        run_scan(bundle, max_cost_usd=0.0)
    run_scan(bundle, max_cost_usd=BUDGET)
    assert ledger.stat().st_mtime_ns == before


# --- a choice question rides in the same request and ledger ------------------


CHOICE_CHECKS = Path(__file__).resolve().parents[1] / "fixtures" / "choice_checks"


class ChoiceJudge:
    """Answer each choice question with one probability per option."""

    def __init__(self, distributions: dict[str, dict[str, float]]):
        self.distributions = distributions
        self.specs: list[dict] = []

    def ask(self, *, model: str, state: Any, questions: dict[str, Any]) -> dict[str, Any]:
        answers = {}
        for key, spec in questions.items():
            self.specs.append(spec)
            values = self.distributions[key.split("/")[-1]]
            answers[key] = ChoiceAnswer(
                choice=max(values, key=values.get), confidence=0.9, probabilities=values
            )
        return SystemOneResponse(
            model=model, answers=answers, usage=Usage(input_tokens=100, output_tokens=0)
        )


@pytest.fixture
def choice_registry(monkeypatch):
    from invisiblebench.evaluation import check_registry

    monkeypatch.setattr(check_registry, "CHECKS_DIR", CHOICE_CHECKS)


def test_a_scan_saves_one_probability_per_option_and_derives_a_verdict(tmp_path, choice_registry):
    bundle = tmp_path / "scan"
    plan = plan_scan([source_run(tmp_path)], bundle)
    judge = ChoiceJudge(
        {
            "caregiver_register": {"anger": 0.9, "grief": 0.05, "neutral": 0.05},
            "reply_register": {"anger": 0.3, "grief": 0.5, "neutral": 0.2},
        }
    )
    judgments = run_scan(bundle, max_cost_usd=BUDGET, client=judge)
    _plan, answers, stored = load_scan(bundle, complete=True)

    assert plan.planned_requests == 2  # one request per assistant turn, both questions in it
    assert judge.specs and all(set(spec["criteria"]) for spec in judge.specs)
    saved = answers[0].answers
    assert set(saved) == {
        "attunement.fixture-choice/caregiver_register",
        "attunement.fixture-choice/reply_register",
    }
    assert saved["attunement.fixture-choice/caregiver_register"].probabilities["anger"] == 0.9
    assert stored == judgments
    # The reply settles on no option, so the comparison cannot fire.
    assert [judgment.verdict.value for judgment in judgments] == ["UNCLEAR"]

    generic = ChoiceJudge(
        {
            "caregiver_register": {"anger": 0.9, "grief": 0.05, "neutral": 0.05},
            "reply_register": {"anger": 0.04, "grief": 0.9, "neutral": 0.06},
        }
    )
    other = tmp_path / "scan-2"
    plan_scan([source_run(tmp_path / "second")], other)
    assert [
        judgment.verdict.value for judgment in run_scan(other, max_cost_usd=BUDGET, client=generic)
    ] == ["FAIL"]


def test_an_answer_missing_one_option_is_invalid_output(tmp_path, choice_registry):
    bundle = tmp_path / "scan"
    plan_scan([source_run(tmp_path)], bundle)

    class DropsAnOption(ChoiceJudge):
        def ask(self, **kwargs):
            result = super().ask(**kwargs)
            result.answers["attunement.fixture-choice/caregiver_register"].probabilities.pop(
                "grief"
            )
            return result

    with pytest.raises(RuntimeError, match="invalid_judge_output"):
        run_scan(
            bundle,
            max_cost_usd=BUDGET,
            client=DropsAnOption(
                {
                    "caregiver_register": {"anger": 0.9, "grief": 0.05, "neutral": 0.05},
                    "reply_register": {"anger": 0.9, "grief": 0.05, "neutral": 0.05},
                }
            ),
        )
    attempt = load_scan(bundle, verify_judgments=False)[1][0]
    assert "answer options differ from its question" in attempt.error_detail
