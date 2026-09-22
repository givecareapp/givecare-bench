"""`bench questions` ranks saved judge answers by how often they land unresolved."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from benchmark.tests.fixtures.current_scan import FixtureJudge, ScriptedJudge, write_source_run
from invisiblebench.cli import agent_commands
from invisiblebench.cli.questions import question_report, questions_command
from invisiblebench.judge import load_scan, plan_scan, run_scan


def args(**overrides):
    return SimpleNamespace(**{"run_id": None, "limit": None, "json_output": True} | overrides)


def test_question_report_ranks_a_half_heavy_question_first(tmp_path):
    """A question scripted to always answer 0.5 is fully unresolved and sorts first."""
    source = write_source_run(tmp_path, roster=[("case-a", "context"), ("case-b", "context")])
    bundle = tmp_path / "scan"
    plan = plan_scan([source], bundle)
    run_scan(bundle, max_cost_usd=plan.estimated_cost_usd, client=ScriptedJudge({"claim": 0.5}))
    _plan, answers, _judgments = load_scan(bundle)

    report = question_report(plan, answers)

    assert [row["question"] for row in report][0] == "identity.fixture-prohibition/claim"
    top = report[0]
    assert top["check_id"] == "identity.fixture-prohibition"
    assert top["kind"] == "question"
    assert top["answers"] == 4  # 2 scenarios x 2 assistant turns
    assert top["unresolved"] == 4
    assert top["unresolved_rate"] == 1.0
    assert top["yes"] == 0 and top["no"] == 0
    assert top["mean"] == 0.5
    assert top["histogram"] == [0, 0, 0, 0, 0, 4, 0, 0, 0, 0]
    assert sum(top["histogram"]) == top["answers"]

    # Every other key was answered 0.0 by the script default: fully resolved.
    for row in report[1:]:
        assert row["unresolved_rate"] == 0.0
        assert row["unresolved"] == 0


@pytest.fixture
def fixture_bundle(tmp_path):
    source = write_source_run(tmp_path, roster=[("case", "context")])
    bundle = tmp_path / "scan"
    plan = plan_scan([source], bundle)
    run_scan(bundle, max_cost_usd=plan.estimated_cost_usd, client=FixtureJudge())
    return bundle


@pytest.fixture(autouse=True)
def empty_results_dir(tmp_path, monkeypatch):
    """Keep `_load_run_metadata`'s prefix scan hermetic across every test here."""
    results = tmp_path / "results"
    results.mkdir()
    monkeypatch.setattr(agent_commands, "_runs_dir", lambda: results)


def test_questions_command_json_envelope(fixture_bundle, capsys):
    assert questions_command(args(run_id=str(fixture_bundle))) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["command"] == "questions"
    keys = {row["question"] for row in payload["data"]}
    assert keys == {
        "identity.fixture-prohibition/claim",
        "crisis.fixture-cue/cue",
        "crisis.fixture-cue/routing",
        "attunement.fixture-required/cue",
        "attunement.fixture-required/acknowledges",
    }
    by_key = {row["question"]: row for row in payload["data"]}
    assert by_key["crisis.fixture-cue/cue"]["kind"] == "cue"
    assert by_key["crisis.fixture-cue/routing"]["kind"] == "question"

    limited = questions_command(args(run_id=str(fixture_bundle), limit=2))
    assert limited == 0
    assert len(json.loads(capsys.readouterr().out)["data"]) == 2


class _FailAfter(FixtureJudge):
    """Succeed for the first `ok_count` requests, then raise."""

    def __init__(self, ok_count: int):
        self.ok_count = ok_count
        self.calls = 0

    def ask(self, *, model: str, state: Any, questions: dict[str, Any]) -> dict[str, Any]:
        self.calls += 1
        if self.calls > self.ok_count:
            raise RuntimeError("simulated interruption")
        return super().ask(model=model, state=state, questions=questions)


def test_questions_command_reports_an_incomplete_scan(tmp_path, capsys):
    source = write_source_run(tmp_path, roster=[("case-a", "context"), ("case-b", "context")])
    bundle = tmp_path / "scan"
    plan = plan_scan([source], bundle)
    with pytest.raises(RuntimeError):
        run_scan(bundle, max_cost_usd=plan.estimated_cost_usd, client=_FailAfter(ok_count=2))

    _plan, answers, _judgments = load_scan(bundle)
    assert len(answers) < plan.planned_requests  # confirms the scan is genuinely partial
    assert not (bundle / "judgments.jsonl").exists()

    assert questions_command(args(run_id=str(bundle))) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["data"]  # still reports rows from the answers saved before the failure


def test_questions_command_unknown_run_is_an_error(capsys):
    assert questions_command(args(run_id="no-such-run-id")) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "status": "error",
        "command": "questions",
        "error": "run not found: no-such-run-id",
    }


# --- a choice question reports one row per option ----------------------------


CHOICE_CHECKS = Path(__file__).resolve().parents[1] / "fixtures" / "choice_checks"


class ChoiceJudge:
    """Answer each choice question with a flat distribution over its options."""

    def ask(self, *, model: str, state: Any, questions: dict[str, Any]) -> dict[str, Any]:
        from typesafe_sdk import ChoiceAnswer, SystemOneResponse, Usage

        answers = {}
        for key, spec in questions.items():
            values = dict.fromkeys(spec["criteria"], 1.0 / len(spec["criteria"]))
            answers[key] = ChoiceAnswer(
                choice=next(iter(values)), probabilities=values, confidence=0.0
            )
        return SystemOneResponse(model=model, answers=answers, usage=Usage(input_tokens=100))


def test_a_choice_question_reports_one_row_per_option(tmp_path, monkeypatch, capsys):
    from invisiblebench.evaluation import check_registry

    monkeypatch.setattr(check_registry, "CHECKS_DIR", CHOICE_CHECKS)
    source = write_source_run(tmp_path, roster=[("case", "context")])
    bundle = tmp_path / "scan"
    plan_scan([source], bundle)
    run_scan(bundle, max_cost_usd=1.0, client=ChoiceJudge())

    assert questions_command(args(run_id=str(bundle))) == 0
    rows = json.loads(capsys.readouterr().out)["data"]
    assert {row["question"] for row in rows} == {
        f"attunement.fixture-choice/{name}={option}"
        for name in ("caregiver_register", "reply_register")
        for option in ("anger", "grief", "neutral")
    }
    assert {row["kind"] for row in rows} == {"choice"}
    anger = next(row for row in rows if row["question"].endswith("caregiver_register=anger"))
    assert anger["check_id"] == "attunement.fixture-choice"
    assert anger["answers"] == 2  # one scenario x two assistant turns
    assert anger["mean"] == pytest.approx(1 / 3, abs=1e-4)
