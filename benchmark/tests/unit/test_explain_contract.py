from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from invisiblebench.cli.explain import explain_command
from invisiblebench.evaluation.check_registry import check_prompt_hashes


def _write_scan(path: Path) -> None:
    row = {
        "model": "Model A",
        "model_id": "provider/model-a",
        "scenario_id": "scenario-1",
        "category": "safety",
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
                "rationale": "The response gives a diagnosis.",
                "judge": {"model": "judge/model"},
                "rationale_code": "patient_specific_prescribing",
                "prompt_hash": check_prompt_hashes()["scope.diagnosis"],
                "evidence": [{"role": "assistant", "turn": 1, "quote": "restart the medicine"}],
            }
        ],
    }
    path.write_text(json.dumps(row) + "\n")


def test_explain_json_exposes_the_rule_and_decision_rationale(tmp_path: Path, capsys) -> None:
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

    assert "overall_score" not in item
    assert item["checks"][0]["rationale"] == "The response gives a diagnosis."
    assert item["checks"][0]["criterion"]
    assert item["checks"][0]["judge"]["model"] == "judge/model"
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


def test_explain_reports_historical_unverified_instead_of_bare_not_found(
    tmp_path: Path, capsys
) -> None:
    """A leaderboard whose source scans were retired to a historical snapshot
    (docs/publishing-audit.md) must say so in words, not print a bare
    'scan artifact not found' as if the path were merely misconfigured."""
    leaderboard = tmp_path / "leaderboard.json"
    leaderboard.write_text(
        json.dumps(
            {
                "schema": "safety-care/v1",
                "models": [],
                "provenance_status": "historical-unverified",
                "provenance_note": "source scans not preserved",
                "scan_metadata": {"source_artifact": "results/publication_v4_release/per_run.jsonl"},
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

    assert explain_command(args) == 1
    payload = json.loads(capsys.readouterr().out)

    assert payload["error"] == (
        "leaderboard is historical-unverified: source scans were not preserved"
    )


def test_explain_text_exposes_the_rule_and_decision_rationale(tmp_path: Path, capsys) -> None:
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

    assert "Criterion:" in output
    assert "Decision rationale: The response gives a diagnosis." in output
    assert "assistant turn 1" in output
    assert "overall_score" not in output
    assert "dimension=scope" in output
    assert "legacy_bucket" not in output
    assert "primary_bucket" not in output
