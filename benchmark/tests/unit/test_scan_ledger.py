"""A scan retains each judgment and remains usable after its bundle moves."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from invisiblebench.api.client import DEFAULT_JUDGE_MODEL, cost_tracker
from invisiblebench.judge import load_scan, plan_scan, replay_scan, run_scan
from invisiblebench.utils.manifest import generate_manifest


def source_run(root: Path) -> Path:
    run = root / "source"
    transcripts = run / "transcripts"
    transcripts.mkdir(parents=True)
    (transcripts / "case.jsonl").write_text(
        '{"role":"user","turn":1,"content":"Hello."}\n'
        '{"role":"assistant","turn":1,"content":"I can help."}\n'
    )
    manifest = generate_manifest(
        Path(__file__).resolve().parents[3], ["fixture/model"], ["fixture-case"],
        transcript_policy={"temperature": 0.7}, run_id="fixture", harness="fixture",
        mode="transcript_only",
    )
    (run / "run_manifest.json").write_text(json.dumps(manifest))
    (run / "transcript_run.json").write_text(json.dumps({
        "artifact_type": "transcript_run/v1", "run_id": "fixture", "status": "complete",
        "model_ids": ["fixture/model"], "expected_transcripts": 1, "transcript_count": 1,
        "error_count": 0, "missing_count": 0, "resolved_model_ids": ["fixture/model"],
        "resolved_providers": ["fixture"], "transcripts": [{
            "model": "Fixture", "model_id": "fixture/model", "scenario_id": "fixture-case",
            "category": "context", "transcript_path": "transcripts/case.jsonl",
        }],
    }))
    return run


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
        return {"response": '{"verdict":"PASS","rationale":"Fixture decision.","evidence":[]}',
                "raw": {"model": kwargs["model"], "provider": "fixture"}}


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
        return {"response": '{"verdict":"PASS","rationale":"Fixture decision.","evidence":[]}',
                "raw": {"model": kwargs["model"], "provider": "fixture"}}
