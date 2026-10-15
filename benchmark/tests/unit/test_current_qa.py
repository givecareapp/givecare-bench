"""The public projection derives exactly from a complete, current scan."""

from __future__ import annotations

import json
from contextlib import contextmanager

import pytest

from benchmark.tests.fixtures.current_scan import (
    FixtureJudge,
    ScriptedJudge,
    write_candidate,
    write_current_qa_fixture,
)
from invisiblebench.judge import load_scan, run_scan
from invisiblebench.models.scan import Verdict
from invisiblebench.scoring import _observation, check_leaderboard


def validate_leaderboard(bundle, candidate):
    try:
        check_leaderboard(bundle, candidate)
    except (OSError, ValueError, KeyError) as exc:
        return [str(exc)]
    return []


def load_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


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


def test_safety_weighs_each_check_equally_and_care_includes_unclear(current_fixture):
    saved = load_scan(current_fixture["scan"])[2][0]
    records = [
        saved.model_copy(
            update={"check_id": check, "scenario_id": scenario, "verdict": Verdict(verdict)}
        )
        for check, scenario, verdict in [
            ("x", "a", "PASS"),
            ("x", "b", "FAIL"),
            ("y", "a", "UNCLEAR"),
            ("y", "b", "PASS"),
            ("y", "c", "PASS"),
            ("z", "a", "NOT_APPLICABLE"),
        ]
    ]
    safety = _observation(records, "safety")
    assert safety == {
        "observed_failure_rate": 0.25,
        "check_failure_rates": {"x": 0.5, "y": 0.0},
        "failed_scenarios": 1,
        "applicable_scenarios": 3,
        "counts": {"PASS": 3, "FAIL": 1, "UNCLEAR": 1, "NOT_APPLICABLE": 1},
    }
    assert _observation(records[2:], "care") == {
        "pass_rate": 0.6667,
        "applicable_checks": 3,
        "counts": {"PASS": 2, "FAIL": 0, "UNCLEAR": 1, "NOT_APPLICABLE": 1},
    }
    assert _observation([records[5]], "care")["pass_rate"] is None
    assert _observation([records[5]], "safety")["observed_failure_rate"] is None


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
            first = next(iter(rows[0]["answers"]))
            rows[0]["answers"][first]["noul"] = 0.99
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
            if row["answers"]:
                row["answers"] = {key: {"type": "noul", "noul": 0.5} for key in row["answers"]}
        write_rows(answers, rows)
        ledger.unlink()  # judgments are derived; edited answers need a fresh derivation
        judgments = run_scan(scan, max_cost_usd=1.0, client=FixtureJudge())
        assert {judgment.verdict for judgment in judgments} == {Verdict.UNCLEAR}
        write_candidate(scan, board)
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
    candidate = write_candidate(bundle)
    errors = validate_leaderboard(bundle, candidate)
    assert errors and "complete current scenario roster" in errors[0]
