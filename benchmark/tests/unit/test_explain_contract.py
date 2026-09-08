"""Explain uses the retained criterion and flat judgment contract."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from benchmark.tests.fixtures.current_scan import FixtureJudge, write_source_run
from invisiblebench.cli.explain import explain_command
from invisiblebench.judge import plan_scan, run_scan
from invisiblebench.scoring import SCHEMA_VERSION


@pytest.fixture
def scan(tmp_path):
    source = write_source_run(tmp_path, roster=[("case", "context")])
    bundle = tmp_path / "scan"
    plan = plan_scan([source], bundle)
    run_scan(bundle, max_cost_usd=plan.estimated_cost_usd, client=FixtureJudge())
    return bundle


def args(**overrides):
    return SimpleNamespace(
        **{
            "scan": None,
            "leaderboard": None,
            "model": "fixture/model",
            "scenario": "case",
            "check": "scope.diagnosis",
            "failures": False,
            "json_output": True,
        }
        | overrides
    )


def test_explain_exposes_frozen_criterion_and_decision(scan, capsys):
    assert explain_command(args(scan=str(scan))) == 0
    item = json.loads(capsys.readouterr().out)["data"][0]
    assert item["rationale"] == "Synthetic fixture decision."
    assert item["criterion"]
    assert item["judge"]["provider"] == "fixture"
    assert item["check_id"] == "scope.diagnosis"
    assert item["judge_settings"]["context_policy"] == "full_ordered"
    assert "mode_results" not in item


def test_explain_resolves_current_projection(scan, tmp_path, capsys):
    board = tmp_path / "leaderboard.json"
    board.write_text(
        json.dumps({"schema": SCHEMA_VERSION, "scan_metadata": {"source_artifact": str(scan)}})
    )
    assert explain_command(args(leaderboard=str(board))) == 0
    assert json.loads(capsys.readouterr().out)["data"]


def test_explain_rejects_retired_projection(tmp_path, capsys):
    board = tmp_path / "leaderboard.json"
    board.write_text('{"schema":"safety-care/v1"}')
    assert explain_command(args(leaderboard=str(board))) == 1
    assert "pass --scan" in json.loads(capsys.readouterr().out)["error"]


def test_explain_text_and_filter(scan, capsys):
    assert explain_command(args(scan=str(scan), json_output=False)) == 0
    output = capsys.readouterr().out
    assert "Criterion:" in output and "Decision rationale:" in output
    assert "scope.diagnosis: PASS" in output
    assert explain_command(args(scan=str(scan), failures=True)) == 1
    assert "no judgments match" in json.loads(capsys.readouterr().out)["error"]
