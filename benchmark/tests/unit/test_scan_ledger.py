"""A scan retains each judgment and remains usable after its bundle moves."""

from __future__ import annotations

from pathlib import Path

import pytest

from benchmark.tests.fixtures.current_scan import write_source_run
from invisiblebench.api.client import DEFAULT_JUDGE_MODEL, cost_tracker
from invisiblebench.judge import load_scan, plan_scan, replay_scan, run_scan


def source_run(root: Path) -> Path:
    return write_source_run(root, roster=[("fixture-case", "context")])


class Judge:
    def __init__(self, bundle: Path, stop_after: int | None = None):
        self.bundle = bundle
        self.stop_after = stop_after
        self.calls = 0
        self.initial_count = len(load_scan(bundle)[1])

    def call_model(self, **kwargs):
        assert len(load_scan(self.bundle)[1]) == self.initial_count + self.calls
        if self.calls == self.stop_after:
            raise KeyboardInterrupt("Simulated interruption; no network")
        self.calls += 1
        cost_tracker.record(kwargs["model"], 0, 0, actual_cost=0.001)
        return {
            "response": '{"verdict":"PASS","rationale":"Fixture decision.","evidence":[]}',
            "raw": {"model": kwargs["model"], "provider": "fixture"},
        }


def test_resume_keeps_completed_judgments_and_cost(tmp_path):
    bundle = tmp_path / "scan"
    plan = plan_scan([source_run(tmp_path)], bundle, judge_model=DEFAULT_JUDGE_MODEL)
    first = Judge(bundle, stop_after=2)
    with pytest.raises(KeyboardInterrupt):
        run_scan(bundle, max_cost_usd=plan.estimated_cost_usd, client=first)
    saved = (bundle / "judgments.jsonl").read_bytes()
    assert len(load_scan(bundle)[1]) == 2

    resumed = Judge(bundle)
    run_scan(bundle, max_cost_usd=plan.estimated_cost_usd, client=resumed)
    judgments = load_scan(bundle, complete=True)[1]
    assert resumed.calls == len(plan.checks) - 2
    assert (bundle / "judgments.jsonl").read_bytes().startswith(saved)
    assert sum(j.cost_usd for j in judgments) == pytest.approx(len(plan.checks) * 0.001)


def test_bundle_moves_without_original_sources_and_replays(tmp_path):
    bundle = tmp_path / "scan"
    source = source_run(tmp_path)
    plan = plan_scan([source], bundle, judge_model=DEFAULT_JUDGE_MODEL)
    run_scan(bundle, max_cost_usd=plan.estimated_cost_usd, client=Judge(bundle))
    source.rename(tmp_path / "original-source-moved")
    moved = tmp_path / "moved-scan"
    bundle.rename(moved)
    assert replay_scan(moved) == []
    assert load_scan(moved, complete=True)[1]
    assert str(tmp_path) not in (moved / "scan_plan.json").read_text()
    assert str(tmp_path) not in (moved / "judgments.jsonl").read_text()


def test_resume_recovers_only_an_unfinished_last_line(tmp_path):
    bundle = tmp_path / "scan"
    plan = plan_scan([source_run(tmp_path)], bundle, judge_model=DEFAULT_JUDGE_MODEL)
    with pytest.raises(KeyboardInterrupt):
        run_scan(bundle, max_cost_usd=plan.estimated_cost_usd, client=Judge(bundle, stop_after=2))
    with (bundle / "judgments.jsonl").open("ab") as journal:
        journal.write(b'{"incomplete":')
    run_scan(bundle, max_cost_usd=plan.estimated_cost_usd, client=JudgeAfterRecovery())
    assert len(load_scan(bundle, complete=True)[1]) == len(plan.checks)


class JudgeAfterRecovery:
    def call_model(self, **kwargs):
        return {
            "response": '{"verdict":"PASS","rationale":"Fixture decision.","evidence":[]}',
            "raw": {"model": kwargs["model"], "provider": "fixture"},
        }


def test_technical_attempt_retains_cost_and_only_unfinished_work_retries(tmp_path):
    from benchmark.tests.fixtures.current_scan import FixtureJudge

    bundle = tmp_path / "scan"
    plan = plan_scan([source_run(tmp_path)], bundle)

    class BrokenJudge:
        def call_model(self, **kwargs):
            cost_tracker.record(kwargs["model"], 0, 0, actual_cost=0.001)
            return {"response": "not valid JSON"}

    with pytest.raises(RuntimeError, match="attempt saved"):
        run_scan(bundle, max_cost_usd=plan.estimated_cost_usd, client=BrokenJudge())
    attempt = load_scan(bundle)[1][0]
    assert attempt.error == "invalid_judge_output" and attempt.cost_usd == 0.001
    assert attempt.verdict == "UNCLEAR"
    run_scan(bundle, max_cost_usd=plan.estimated_cost_usd, client=FixtureJudge())
    records = load_scan(bundle, complete=True)[1]
    assert len(records) == plan.planned_calls + 1
    assert sum(r.cost_usd for r in records) == pytest.approx(0.001)
    assert len([r for r in records if r.key == attempt.key]) == 2
    assert replay_scan(bundle) == []


def test_running_bundle_rejects_a_second_writer(tmp_path):
    import fcntl

    bundle = tmp_path / "scan"
    plan = plan_scan([source_run(tmp_path)], bundle)
    with (bundle / "judgments.jsonl").open("ab") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError, match="already running"):
            run_scan(bundle, max_cost_usd=plan.estimated_cost_usd)


def test_stale_contract_and_nested_legacy_record_are_rejected(tmp_path):
    import json

    bundle = tmp_path / "scan"
    plan = plan_scan([source_run(tmp_path)], bundle)
    path = bundle / "scan_plan.json"
    payload = json.loads(path.read_bytes())
    payload["judge"]["temperature"] = 1.0
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="current benchmark"):
        run_scan(bundle, max_cost_usd=plan.estimated_cost_usd)
    (bundle / "judgments.jsonl").write_text('{"mode_results":[]}\n')
    with pytest.raises(ValueError):
        load_scan(bundle)
