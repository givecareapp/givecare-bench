from __future__ import annotations

import json
from pathlib import Path

from invisiblebench.results_io import write_json, write_model_results
from invisiblebench.run_audit import audit_results_source


def _write_manifest(path: Path, *, harness: str = "llm", mode: str = "raw") -> None:
    write_json(
        path / "run_manifest.json",
        {
            "run_id": "run-123",
            "scenario_hash": "hash-a",
            "scoring_config_hash": "score-hash-a",
            "contract_version": "2.0.0",
            "benchmark_version": "1.2.0",
            "harness": harness,
            "mode": mode,
            "model_ids": ["provider/model-a"],
        },
    )


def _write_transcript(path: Path, name: str) -> None:
    transcript_path = path / "transcripts" / f"{name}.jsonl"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text(
        json.dumps({"turn": 1, "role": "user", "content": "hi"})
        + "\n"
        + json.dumps({"turn": 1, "role": "assistant", "content": "hello"})
        + "\n"
    )


def test_audit_valid_run_is_publishable(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    rows = [
        {
            "model": "Model A",
            "model_id": "provider/model-a",
            "scenario": "Scenario 1",
            "scenario_id": "s1",
            "category": "safety",
            "overall_score": 0.8,
            "dimensions": {"regard": 0.9, "coordination": 0.7},
            "status": "pass",
            "success": True,
            "judge_model": "judge-x",
            "judge_prompt_hash": "prompt-hash-a",
            "contract_version": "2.0.0",
            "run_id": "run-123",
        },
        {
            "model": "Model A",
            "model_id": "provider/model-a",
            "scenario": "Scenario 2",
            "scenario_id": "s2",
            "category": "context",
            "overall_score": 0.7,
            "dimensions": {"regard": 0.8, "coordination": 0.6},
            "status": "pass",
            "success": True,
            "judge_model": "judge-x",
            "judge_prompt_hash": "prompt-hash-a",
            "contract_version": "2.0.0",
            "run_id": "run-123",
        },
    ]
    write_json(tmp_path / "all_results.json", rows)
    write_model_results(rows, tmp_path / "model_results", benchmark_version="1.2.0")
    _write_transcript(tmp_path, "t1")
    _write_transcript(tmp_path, "t2")

    audit = audit_results_source(tmp_path, expected_scenario_count=2)

    assert audit["run_valid"] is True
    assert audit["publishable"] is True
    assert audit["summary_status"] == "PASS"
    assert audit["checks"]["run_integrity"]["status"] == "PASS"
    assert audit["checks"]["provider_health"]["status"] == "PASS"
    assert audit["checks"]["judge_health"]["status"] == "PASS"


def test_audit_partial_run_blocks_publishability(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    rows = [
        {
            "model": "Model A",
            "model_id": "provider/model-a",
            "scenario": "Scenario 1",
            "scenario_id": "s1",
            "category": "safety",
            "overall_score": 0.8,
            "dimensions": {"regard": 0.9, "coordination": 0.7},
            "status": "pass",
            "success": True,
            "judge_model": "judge-x",
            "judge_prompt_hash": "prompt-hash-a",
            "contract_version": "2.0.0",
            "run_id": "run-123",
        }
    ]
    write_json(tmp_path / "all_results.json", rows)
    write_model_results(rows, tmp_path / "model_results", benchmark_version="1.2.0")
    _write_transcript(tmp_path, "t1")

    audit = audit_results_source(tmp_path, expected_scenario_count=2)

    assert audit["run_valid"] is False
    assert audit["publishable"] is False
    assert audit["summary_status"] == "BLOCK"
    assert audit["primary_owner"] == "benchmark"
    assert audit["checks"]["run_integrity"]["status"] == "BLOCK"


def test_audit_provider_and_scoring_failures_are_classified(tmp_path: Path) -> None:
    _write_manifest(tmp_path, harness="givecare", mode="live")
    rows = [
        {
            "model": "GiveCare (Mira)",
            "model_id": "givecare/mira",
            "provider": "givecare",
            "scenario": "Scenario 1",
            "scenario_id": "s1",
            "category": "safety",
            "overall_score": 0.0,
            "dimensions": {},
            "status": "error",
            "hard_fail": True,
            "hard_fail_reasons": ["Transcript generation failed: Convex timeout"],
            "contract_version": "2.0.0",
            "run_id": "run-123",
        },
        {
            "model": "GiveCare (Mira)",
            "model_id": "givecare/mira",
            "provider": "givecare",
            "scenario": "Scenario 2",
            "scenario_id": "s2",
            "category": "context",
            "overall_score": 0.0,
            "dimensions": {},
            "status": "error",
            "hard_fail": True,
            "hard_fail_reasons": ["Scoring failed: judge unavailable"],
            "contract_version": "2.0.0",
            "run_id": "run-123",
        },
    ]
    write_json(tmp_path / "all_results.json", rows)
    write_model_results(rows, tmp_path / "model_results", benchmark_version="1.2.0")
    _write_transcript(tmp_path, "t1")
    _write_transcript(tmp_path, "t2")

    audit = audit_results_source(tmp_path, expected_scenario_count=2)

    assert audit["checks"]["provider_health"]["status"] in {"WARN", "BLOCK"}
    assert audit["checks"]["provider_health"]["details"]["buckets"]["transcript_generation"] == 1
    assert audit["checks"]["judge_health"]["status"] == "BLOCK"
    assert audit["checks"]["judge_health"]["details"]["scoring_error_count"] == 1
