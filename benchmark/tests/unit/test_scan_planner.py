"""Scan plans bind paid work to exact inputs and retain completed rows."""

import hashlib
import json
import sys

import pytest

from invisiblebench.api import CostBudgetExceededError
from invisiblebench.api.client import DEFAULT_JUDGE_MODEL
from invisiblebench.evaluation.check_registry import check_definition_hashes, load_checks
from invisiblebench.evaluation.mode_engine import ModeEngine
from invisiblebench.judge import (
    REPO_ROOT,
    attach_scan_provenance,
    build_scan_plan,
    transcripts_for_run,
)
from invisiblebench.utils.manifest import scenario_corpus_hash
from invisiblebench.version import BENCHMARK_VERSION
from scripts import run_scan
from scripts.rescore_diff import replay_row


@pytest.fixture
def run_dir(tmp_path):
    root = tmp_path / "run"
    (root / "transcripts").mkdir(parents=True)
    transcript = [{"role": "user", "turn": 1, "content": "Hello"},
                  {"role": "assistant", "turn": 1, "content": "Hello back"}]
    entries = []
    for scenario in ("s1", "s2"):
        path = root / "transcripts" / f"{scenario}.jsonl"
        path.write_text("".join(json.dumps(t) + "\n" for t in transcript))
        entries.append({"model": "Model", "model_id": "provider/model", "scenario_id": scenario,
                        "category": "context", "transcript_path": f"transcripts/{scenario}.jsonl"})
    manifest = {
        "schema": "invisiblebench-run-manifest/v2", "run_id": "test-run",
        "git_sha": "a" * 40, "git_dirty": False, "benchmark_version": BENCHMARK_VERSION,
        "scenario_hash": scenario_corpus_hash(REPO_ROOT), "scenario_ids": ["s1", "s2"],
        "scoring_config_hash": hashlib.sha256((REPO_ROOT / "benchmark/configs/scoring.yaml").read_bytes()).hexdigest(),
        "check_definition_hashes": check_definition_hashes(), "model_ids": ["provider/model"],
        "harness": "llm", "mode": "raw", "transcript_policy": {"temperature": 0.7},
    }
    (root / "run_manifest.json").write_text(json.dumps(manifest))
    (root / "transcript_run.json").write_text(json.dumps({
        "artifact_type": "transcript_run/v1", "run_id": "test-run", "status": "complete",
        "model_ids": ["provider/model"], "expected_transcripts": 2, "transcript_count": 2,
        "error_count": 0, "missing_count": 0, "resolved_model_ids": ["provider/snapshot"],
        "resolved_providers": ["provider"], "transcripts": entries,
    }))
    return root


def invoke(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["run_scan.py", *map(str, args)])
    return run_scan.main()


def dry_plan(monkeypatch, run_dir, tmp_path):
    output = tmp_path / "plans"
    assert invoke(monkeypatch, run_dir, "--dry-run", "--output-root", output) == 0
    return next(output.glob("*/scan_plan.json"))


def test_plan_counts_all_checks_and_binds_source_bytes(run_dir):
    pairs = transcripts_for_run(run_dir)
    plan = attach_scan_provenance(build_scan_plan(pairs, load_checks(), judge_model=DEFAULT_JUDGE_MODEL),
                                  run_dirs=[run_dir], transcript_pairs=pairs)
    assert plan["schema"] == "invisiblebench-scan-plan/v3"
    assert plan["provenance_complete"] is True
    assert plan["planned_llm_calls"] == 2 * len(load_checks())
    assert len(plan["transcript_hashes"]) == 2
    assert plan["estimated_cost_usd"] > 0
    assert plan["judge_contract"]["context_policy"] == "full_ordered"
    assert "profile" not in plan
    (run_dir / "run_manifest.json").unlink()
    assert attach_scan_provenance(plan, run_dirs=[run_dir], transcript_pairs=pairs)["provenance_complete"] is False


def test_dry_run_never_initializes_a_client_and_live_requires_a_plan(run_dir, tmp_path, monkeypatch):
    def forbidden_client():
        pytest.fail("A dry run or missing plan must not initialize the API client")
    monkeypatch.setattr(run_scan, "ModelAPIClient", forbidden_client)
    dry_plan(monkeypatch, run_dir, tmp_path)
    assert invoke(monkeypatch, run_dir, "--max-cost-usd", "1") == 2


@pytest.mark.parametrize("ceiling", ["nan", "inf", "-1", "0"])
def test_invalid_budget_cannot_initialize_api(run_dir, tmp_path, monkeypatch, ceiling):
    plan = dry_plan(monkeypatch, run_dir, tmp_path)
    monkeypatch.setattr(run_scan, "ModelAPIClient", lambda: pytest.fail("invalid budget reached API"))
    assert invoke(monkeypatch, run_dir, "--plan", plan, "--max-cost-usd", ceiling) == 2


def test_changed_transcript_invalidates_saved_plan(run_dir, tmp_path, monkeypatch):
    plan = dry_plan(monkeypatch, run_dir, tmp_path)
    transcript = run_dir / "transcripts/s1.jsonl"
    transcript.write_text(transcript.read_text().replace("Hello back", "Changed response"))
    monkeypatch.setattr(run_scan, "ModelAPIClient", lambda: pytest.fail("stale plan reached API"))
    assert invoke(monkeypatch, run_dir, "--plan", plan, "--max-cost-usd", "1") == 2


def test_missing_stage_metadata_or_transcript_fails_closed(run_dir):
    (run_dir / "transcripts/s1.jsonl").unlink()
    with pytest.raises(ValueError, match="Missing transcript"):
        transcripts_for_run(run_dir)
    (run_dir / "transcript_run.json").unlink()
    with pytest.raises(FileNotFoundError):
        transcripts_for_run(run_dir)


class StubClient:
    def call_model(self, **kwargs):
        return {"response": json.dumps({"verdict": "UNCLEAR", "rationale": "Insufficient context.", "evidence": []}),
                "raw": {"model": "judge/snapshot", "provider": "provider"}}


def test_saved_response_replay_proves_current_engine_and_detects_changes(run_dir):
    from invisiblebench.judge import scan_run
    rows, _ = scan_run(run_dir, ModeEngine(llm_api_client=StubClient()))
    assert replay_row(rows[0]) == []
    rows[0]["mode_results"][0]["verdict"] = "PASS"
    assert replay_row(rows[0])
    rows[0]["contract_version"] = "3.2.0"
    with pytest.raises(ValueError, match="retired contract"):
        replay_row(rows[0])


def test_cost_stop_resumes_completed_rows_once(run_dir, tmp_path, monkeypatch):
    plan = dry_plan(monkeypatch, run_dir, tmp_path)
    ceiling = json.loads(plan.read_text())["estimated_cost_usd"]
    original = run_scan.scan_run
    monkeypatch.setattr(run_scan, "ModelAPIClient", StubClient)
    def stopped(*args, progress_callback, **kwargs):
        def stop_after_first(record, output):
            progress_callback(record, output)
            raise CostBudgetExceededError("simulated budget stop")
        return original(*args, progress_callback=stop_after_first, **kwargs)
    monkeypatch.setattr(run_scan, "scan_run", stopped)
    output = tmp_path / "scans"
    args = [run_dir, "--plan", plan, "--max-cost-usd", ceiling, "--output-root", output]
    assert invoke(monkeypatch, *args) == 4
    scan = next(output.iterdir())
    assert json.loads((scan / "scan_state.json").read_text())["completed_rows"] == 1
    monkeypatch.setattr(run_scan, "scan_run", original)
    assert invoke(monkeypatch, *args, "--resume", scan) == 0
    rows = [json.loads(line) for line in (scan / "per_run.jsonl").read_text().splitlines()]
    assert {row["scenario_id"] for row in rows} == {"s1", "s2"}
    assert len(rows) == 2
    assert not (scan / "per_run.partial.jsonl").exists()
