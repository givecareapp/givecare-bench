"""Paid work requires a frozen plan, bounded cost, and intact input files."""

import json
import sys
from pathlib import Path

import pytest

from benchmark.tests.fixtures.current_scan import FixtureJudge, write_source_run
from invisiblebench import judge
from invisiblebench.api.client import DEFAULT_JUDGE_MODEL
from invisiblebench.evaluation.check_registry import load_checks
from scripts import run_scan


@pytest.fixture
def source(tmp_path):
    return write_source_run(tmp_path, roster=[("s1", "context"), ("s2", "context")])


def invoke(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["run_scan.py", *map(str, args)])
    return run_scan.main()


def test_plan_freezes_all_checks_without_a_client(source, tmp_path, monkeypatch):
    monkeypatch.setattr(judge, "ModelAPIClient", lambda: pytest.fail("planning reached the API"))
    bundle = tmp_path / "scan"
    assert invoke(monkeypatch, "plan", source, "--output", bundle) == 0
    plan, records = judge.load_scan(bundle)
    assert not records
    assert {check.id for check in plan.checks} == set(load_checks())
    assert plan.planned_calls == len(plan.checks) * 2
    assert plan.estimated_cost_usd > 0
    assert plan.judge.model == DEFAULT_JUDGE_MODEL
    assert all(not ref.path.startswith("/") for ref in plan.transcripts)


@pytest.mark.parametrize("ceiling", ["nan", "inf", "-1", "0"])
def test_invalid_budget_cannot_initialize_api(source, tmp_path, monkeypatch, ceiling):
    bundle = tmp_path / "scan"
    judge.plan_scan([source], bundle)
    monkeypatch.setattr(judge, "ModelAPIClient", lambda: pytest.fail("invalid budget reached API"))
    assert (
        invoke(monkeypatch, "run", "--plan", bundle / judge.PLAN_FILE, "--max-cost-usd", ceiling)
        == 2
    )


def test_changed_bundle_input_is_rejected_before_api(source, tmp_path, monkeypatch):
    bundle = tmp_path / "scan"
    plan = judge.plan_scan([source], bundle)
    path = bundle / plan.transcripts[0].path
    path.write_bytes(path.read_bytes() + b"\n")
    monkeypatch.setattr(judge, "ModelAPIClient", lambda: pytest.fail("changed source reached API"))
    assert (
        invoke(
            monkeypatch,
            "run",
            "--plan",
            bundle / judge.PLAN_FILE,
            "--max-cost-usd",
            plan.estimated_cost_usd,
        )
        == 2
    )


def test_missing_or_retired_source_stage_cannot_make_a_plan(source, tmp_path):
    (source / "run_manifest.json").write_text('{"schema":"invisiblebench-run-manifest/v2"}')
    with pytest.raises(ValueError, match="run-manifest/v3"):
        judge.plan_scan([source], tmp_path / "scan")
    assert not (tmp_path / "scan").exists()
    (source / "transcript_run.json").unlink()
    with pytest.raises(FileNotFoundError):
        judge.plan_scan([source], tmp_path / "scan")


def test_unknown_judge_price_cannot_initialize_api(source, tmp_path, monkeypatch):
    bundle = tmp_path / "scan"
    judge.plan_scan([source], bundle, judge_model="unpriced/judge")
    monkeypatch.setattr(judge, "ModelAPIClient", lambda: pytest.fail("unknown price reached API"))
    with pytest.raises(ValueError, match="unknown pricing"):
        judge.run_scan(bundle, max_cost_usd=1)


def test_current_cli_plan_run_and_replay(source, tmp_path, monkeypatch):
    bundle = tmp_path / "scan"
    assert invoke(monkeypatch, "plan", source, "--output", bundle) == 0
    plan, _ = judge.load_scan(bundle)
    monkeypatch.setattr(judge, "ModelAPIClient", FixtureJudge)
    assert (
        invoke(
            monkeypatch,
            "run",
            "--plan",
            bundle / judge.PLAN_FILE,
            "--max-cost-usd",
            plan.estimated_cost_usd,
        )
        == 0
    )
    assert judge.replay_scan(bundle) == []
    ledger = bundle / judge.LEDGER_FILE
    saved = ledger.read_bytes()
    monkeypatch.setattr(judge, "ModelAPIClient", lambda: pytest.fail("completed scan reached API"))
    assert (
        invoke(
            monkeypatch,
            "run",
            "--plan",
            bundle / judge.PLAN_FILE,
            "--max-cost-usd",
            plan.estimated_cost_usd,
        )
        == 0
    )
    assert ledger.read_bytes() == saved
    records = [json.loads(line) for line in saved.splitlines()]
    records[0]["verdict"] = "UNCLEAR"
    ledger.write_text("".join(json.dumps(record) + "\n" for record in records))
    with pytest.raises(ValueError, match="raw judge decision"):
        judge.replay_scan(bundle)


def test_plan_in_place_keeps_one_copy_and_preserves_source_on_error(source, monkeypatch):
    saved = {p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()}
    assert invoke(monkeypatch, "plan", source) == 0
    plan, _ = judge.load_scan(source)
    assert plan.sources[0].manifest.path == "run_manifest.json"
    assert not (source / "inputs").exists()
    assert {p.relative_to(source) for p in source.rglob("*") if p.is_file()} == {
        *saved, Path(judge.PLAN_FILE),
    }
    for path, content in saved.items():
        assert (source / path).read_bytes() == content
    before = (source / judge.PLAN_FILE).read_bytes()
    assert invoke(monkeypatch, "plan", source) == 2
    assert (source / judge.PLAN_FILE).read_bytes() == before
    monkeypatch.setattr(judge, "ModelAPIClient", FixtureJudge)
    assert invoke(
        monkeypatch, "run", "--plan", source / judge.PLAN_FILE,
        "--max-cost-usd", plan.estimated_cost_usd,
    ) == 0
    assert (source / "jury-card.md").is_file()
    assert judge.replay_scan(source) == []
    assert not (source / "inputs").exists()
    for path, content in saved.items():
        assert (source / path).read_bytes() == content


def test_failed_in_place_plan_never_removes_transcripts(source, monkeypatch):
    monkeypatch.setattr(judge, "load_checks", lambda: (_ for _ in ()).throw(ValueError("bad check")))
    saved = {p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match="bad check"):
        judge.plan_scan([source], source)
    assert {p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()} == saved
