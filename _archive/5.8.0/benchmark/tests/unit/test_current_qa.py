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
from invisiblebench.scoring import _observation, check_leaderboard, mean_checks


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


def test_rates_are_ranges_over_permitted_resolutions(current_fixture):
    """UNCLEAR is not applicable by default; its possible verdicts bound the rate."""
    saved = load_scan(current_fixture["scan"])[2][0]
    rows = [
        ("x", "a", "PASS"),
        ("x", "b", "FAIL"),
        ("x", "c", "PASS"),
        ("x", "d", "PASS"),
        ("x", "e", "PASS"),
        ("x", "f", "UNCLEAR"),
        ("y", "a", "FAIL"),
        ("y", "b", "UNCLEAR"),
        ("z", "a", "NOT_APPLICABLE"),
        ("z", "b", "UNCLEAR"),
    ]
    records = [
        saved.model_copy(
            update={"check_id": check, "scenario_id": scenario, "verdict": Verdict(verdict)}
        )
        for check, scenario, verdict in rows
    ]
    outcomes = {
        records[5].key: {Verdict.PASS, Verdict.FAIL},
        records[7].key: {Verdict.FAIL, Verdict.NOT_APPLICABLE},
        records[9].key: {Verdict.PASS, Verdict.NOT_APPLICABLE},
    }
    safety = _observation(records, "safety", outcomes, {"x"})
    # x: 1/6 when f passes, 2/6 when it fails. y: both resolutions fail every
    # applicable case, so 50% (UNCLEAR counted as applicable) matches neither.
    assert safety["checks"]["x"]["failure_rate_range"] == [0.1667, 0.3333]
    assert safety["checks"]["y"]["failure_rate_range"] == [1.0, 1.0]
    assert safety["checks"]["z"]["failure_rate_range"] == [0.0, 0.0]
    assert [entry["in_mean"] for entry in safety["checks"].values()] == [True, False, False]
    assert safety["failure_rate_range"] == [0.1667, 0.3333]
    # The included set is fixed per scan: x has 5 settled cases, y only 1.
    assert mean_checks(records, [saved.model_id]) == {"x"}
    other = [r.model_copy(update={"model_id": "other/model"}) for r in records[:4]]
    assert mean_checks(records + other, [saved.model_id, "other/model"]) == set()
    assert safety["failed_scenarios"] == 2
    assert safety["counts"]["UNCLEAR_FAIL_POSSIBLE"] == 2
    assert safety["counts"]["UNCLEAR_APPLICABILITY_ONLY"] == 1
    care = _observation(records[6:], "care", outcomes, set())
    assert care["pass_rate_range"] == [0.0, 0.5]
    assert care["settled_checks"] == 1
    only_unclear = _observation([records[9]], "care", outcomes, set())
    assert only_unclear["pass_rate_range"] == [1.0, 1.0]
    assert _observation([records[8]], "safety", outcomes, set())["failure_rate_range"] is None


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
