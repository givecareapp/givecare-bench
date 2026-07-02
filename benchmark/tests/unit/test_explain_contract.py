from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from invisiblebench.cli.explain import explain_command


def _write_scan(path: Path) -> None:
    row = {
        "model": "Model A",
        "model_id": "provider/model-a",
        "scenario_id": "scenario-1",
        "category": "safety",
        "overall_score": 0.0,
        "hard_fail": True,
        "hard_fail_reasons": [{"mode_id": "scope.diagnosis", "reason": "hard_fail"}],
        "eligible_count": 1,
        "resolved_count": 1,
        "unclear_count": 0,
        "coverage_rate": 1.0,
        "transcript_path": "results/run_x/transcripts/scenario-1.json",
        "mode_results": [
            {
                "mode_id": "scope.diagnosis",
                "verdict": "FAIL",
                "eligible": True,
                "severity": "S4",
                "layer": "safety",
                "dimension": "scope",
                "scorer_type": "llm",
                "scorer_version": "test",
                "confidence": 0.91,
                "rationale_code": "patient_specific_prescribing",
                "prompt_hash": "abc123",
                "evidence": [{"turn": 1, "quote": "restart the medicine"}],
            }
        ],
    }
    path.write_text(json.dumps(row) + "\n")


def test_explain_json_labels_raw_internal_score_surface(tmp_path: Path, capsys) -> None:
    scan = tmp_path / "per_run.jsonl"
    _write_scan(scan)
    args = SimpleNamespace(
        scan=str(scan),
        leaderboard=None,
        model="model-a",
        scenario="scenario-1",
        check=None,
        failures=False,
        json_output=True,
    )

    assert explain_command(args) == 0
    payload = json.loads(capsys.readouterr().out)
    item = payload["data"][0]

    assert item["result_surface"] == "raw/internal"
    assert item["score_model"] == "raw-diagnostic/v1"
    assert item["public_score_model"] == "safety-care/v1"
    assert item["checks"][0]["dimension"] == "scope"
    assert "legacy_bucket" not in item["checks"][0]
    assert "primary_bucket" not in item["checks"][0]


def test_explain_resolves_scan_from_safety_care_leaderboard_metadata(
    tmp_path: Path, capsys
) -> None:
    scan = tmp_path / "per_run.jsonl"
    leaderboard = tmp_path / "leaderboard.json"
    _write_scan(scan)
    leaderboard.write_text(
        json.dumps(
            {
                "schema": "safety-care/v1",
                "models": [],
                "scan_metadata": {"source_artifact": str(scan)},
            }
        )
    )
    args = SimpleNamespace(
        scan=None,
        leaderboard=str(leaderboard),
        model="model-a",
        scenario="scenario-1",
        check=None,
        failures=False,
        json_output=True,
    )

    assert explain_command(args) == 0
    payload = json.loads(capsys.readouterr().out)
    item = payload["data"][0]

    assert item["scan_artifact"] == str(scan)


def test_explain_text_labels_raw_internal_score_surface(tmp_path: Path, capsys) -> None:
    scan = tmp_path / "per_run.jsonl"
    _write_scan(scan)
    args = SimpleNamespace(
        scan=str(scan),
        leaderboard=None,
        model="model-a",
        scenario="scenario-1",
        check=None,
        failures=False,
        json_output=False,
    )

    assert explain_command(args) == 0
    output = capsys.readouterr().out

    assert "surface: raw/internal (raw-diagnostic/v1); public model: safety-care/v1" in output
    assert "raw/internal overall_score: 0.0" in output
    assert "hard_fail diagnostic flag: True" in output
    assert "dimension=scope" in output
    assert "legacy_bucket" not in output
    assert "primary_bucket" not in output
