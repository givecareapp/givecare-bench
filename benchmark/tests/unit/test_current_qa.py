"""The public projection derives exactly from a complete, current scan."""

from __future__ import annotations

import json
from contextlib import contextmanager

import pytest

from benchmark.tests.fixtures.current_scan import (
    FixtureJudge,
    ScriptedJudge,
    write_current_qa_fixture,
)
from invisiblebench.judge import load_scan, run_scan
from invisiblebench.models.scan import Verdict
from invisiblebench.scoring import _observation, generate_leaderboard, validate_leaderboard
from invisiblebench.utils.io import load_jsonl


@pytest.fixture(scope="module")
def current_fixture(tmp_path_factory):
    return write_current_qa_fixture(
        tmp_path_factory.mktemp("current-qa"), model_ids=("fixture/a", "fixture/b")
    )


@contextmanager
def restore(*paths):
    saved = [path.read_bytes() for path in paths]
    try:
        yield
    finally:
        for path, content in zip(paths, saved, strict=True):
            path.write_bytes(content)


def write_rows(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def test_safety_uses_any_fail_per_scenario_and_care_includes_unclear(current_fixture):
    saved = load_scan(current_fixture["scan"])[2][0]
    records = [
        saved.model_copy(update={"scenario_id": scenario, "verdict": Verdict(verdict)})
        for scenario, verdict in [
            ("a", "PASS"),
            ("a", "UNCLEAR"),
            ("a", "NOT_APPLICABLE"),
            ("b", "FAIL"),
            ("b", "FAIL"),
        ]
    ]
    safety = _observation(records, "safety")
    assert safety == {
        "observed_failure_rate": 0.5,
        "failed_scenarios": 1,
        "applicable_scenarios": 2,
        "counts": {"PASS": 1, "FAIL": 2, "UNCLEAR": 1, "NOT_APPLICABLE": 1},
    }
    assert _observation(records[:3], "care") == {
        "pass_rate": 0.5,
        "applicable_checks": 2,
        "counts": {"PASS": 1, "FAIL": 0, "UNCLEAR": 1, "NOT_APPLICABLE": 1},
    }
    assert _observation([records[2]], "care")["pass_rate"] is None
    assert _observation([records[2]], "safety")["observed_failure_rate"] is None


def test_complete_models_pass_exact_qa(current_fixture):
    assert validate_leaderboard(current_fixture["scan"], current_fixture["leaderboard"]) == []
    board = json.loads(current_fixture["leaderboard"].read_bytes())
    assert {model["model_id"] for model in board["models"]} == {"fixture/a", "fixture/b"}
    metadata = board["scan_metadata"]
    assert metadata["observed_judges"] == [metadata["judge"]["model"]]
    assert metadata["answers_sha256"] != metadata["judgments_sha256"]


def test_frozen_manifest_byte_drift_is_rejected(current_fixture):
    plan, _, _ = load_scan(current_fixture["scan"])
    manifest = current_fixture["scan"] / plan.sources[0].manifest.path
    with restore(manifest):
        manifest.write_bytes(manifest.read_bytes() + b"\n")
        assert (
            "bundle input changed"
            in validate_leaderboard(current_fixture["scan"], current_fixture["leaderboard"])[0]
        )


@pytest.mark.parametrize("mutation", ["check", "scenario", "duplicate", "unplanned", "forged"])
def test_an_edited_judgment_cannot_publish(current_fixture, mutation):
    ledger = current_fixture["ledger"]
    with restore(ledger):
        rows = load_jsonl(ledger)
        if mutation == "check":
            rows.pop()
        elif mutation == "scenario":
            rows = [row for row in rows if row["scenario_id"] != rows[0]["scenario_id"]]
        elif mutation == "duplicate":
            rows.append(rows[0])
        elif mutation == "unplanned":
            rows[0]["check_id"] = "crisis.invented"
        else:
            rows[0].update(
                verdict="FAIL", evidence=[{"role": "assistant", "turn": 1, "quote": "forged"}]
            )
        write_rows(ledger, rows)
        assert validate_leaderboard(current_fixture["scan"], current_fixture["leaderboard"])


@pytest.mark.parametrize("mutation", ["probability", "unplanned", "duplicate", "technical"])
def test_an_edited_answer_cannot_publish(current_fixture, mutation):
    answers = current_fixture["answers"]
    with restore(answers):
        rows = load_jsonl(answers)
        if mutation == "probability":
            first = next(iter(rows[0]["nouls"]))
            rows[0]["nouls"][first] = 0.99
        elif mutation == "unplanned":
            rows[0]["turn"] = 9
        elif mutation == "duplicate":
            rows.append(rows[0])
        else:
            rows[0].update(nouls=None, error="judge_api_error")
        write_rows(answers, rows)
        assert validate_leaderboard(current_fixture["scan"], current_fixture["leaderboard"])


@pytest.mark.parametrize("field", ["private_field", "care_directional"])
def test_public_extra_fields_and_type_aliases_are_rejected(current_fixture, field):
    board = current_fixture["leaderboard"]
    with restore(board):
        payload = json.loads(board.read_bytes())
        payload[field] = 1
        board.write_text(json.dumps(payload))
        assert "exact ledger projection" in validate_leaderboard(current_fixture["scan"], board)[0]


def test_a_semantic_unclear_derived_from_its_answers_is_publishable(current_fixture):
    scan, answers, ledger = (
        current_fixture["scan"],
        current_fixture["answers"],
        current_fixture["ledger"],
    )
    board = current_fixture["leaderboard"]
    with restore(answers, ledger, board):
        rows = load_jsonl(answers)
        for row in rows:
            if row["nouls"]:
                row["nouls"] = dict.fromkeys(row["nouls"], 0.5)
        write_rows(answers, rows)
        ledger.unlink()  # judgments are derived; edited answers need a fresh derivation
        judgments = run_scan(scan, max_cost_usd=1.0, client=FixtureJudge())
        assert {judgment.verdict for judgment in judgments} == {Verdict.UNCLEAR}
        generate_leaderboard(scan, board)
        assert validate_leaderboard(scan, board) == []


def test_complete_subset_is_inspectable_but_cannot_publish(current_fixture, tmp_path):
    from invisiblebench.judge import plan_scan

    bundle = tmp_path / "subset"
    plan = plan_scan([current_fixture["source_run"]], bundle, limit=1)
    run_scan(
        bundle,
        max_cost_usd=plan.estimated_cost_usd,
        client=ScriptedJudge({"cue": 0.9, "routing": 0.0}),
    )
    candidate = generate_leaderboard(bundle)
    errors = validate_leaderboard(bundle, candidate)
    assert errors and "complete current scenario roster" in errors[0]
