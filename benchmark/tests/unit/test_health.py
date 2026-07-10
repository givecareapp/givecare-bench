from __future__ import annotations

import json
from pathlib import Path

from delivery.sync_web_bench import project_leaderboard
from invisiblebench.cli import health as health_module


def test_run_health_reports_not_generated_without_error(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(health_module, "get_project_root", lambda: tmp_path)

    result = health_module.run_health()

    assert result == 0
    assert "No leaderboard generated yet" in capsys.readouterr().out


def test_load_leaderboard_prefers_current_output_dir(tmp_path: Path, monkeypatch) -> None:
    leaderboard_dir = tmp_path / "data" / "leaderboard"
    leaderboard_dir.mkdir(parents=True)
    payload = {"metadata": {}, "overall_leaderboard": []}
    (leaderboard_dir / "leaderboard.json").write_text(json.dumps(payload))

    monkeypatch.setattr(health_module, "get_project_root", lambda: tmp_path)

    loaded = health_module.load_leaderboard()

    assert loaded == payload


def test_analyze_safety_care_leaderboard_does_not_require_overall_score() -> None:
    payload = {
        "schema": "safety-care/v1",
        "scan_metadata": {"total_scenarios": 63, "artifact_validation": {}},
        "models": [
            {
                "model": "Model A",
                "safety": {
                    "lines": {
                        "crisis": {},
                        "scope": {},
                        "identity": {},
                        "autonomy": {},
                    }
                },
                "care": {
                    "qualities": {
                        "belonging": {
                            "pass_rate": None,
                            "n": 0,
                            "directional": True,
                            "calibration_status": "not_claim_ready",
                        },
                        "attunement": {
                            "pass_rate": None,
                            "n": 0,
                            "directional": True,
                            "calibration_status": "not_claim_ready",
                        },
                        "relational": {
                            "pass_rate": None,
                            "n": 0,
                            "directional": True,
                            "calibration_status": "not_claim_ready",
                        },
                        "advocacy": {
                            "pass_rate": None,
                            "n": 0,
                            "directional": True,
                            "calibration_status": "not_claim_ready",
                        },
                        "trauma_awareness": {
                            "n": 0,
                            "directional": True,
                            "calibration_status": "not_claim_ready",
                            "authored_checks": 0,
                        },
                    }
                },
            }
        ],
    }

    analysis = health_module.analyze_leaderboard(payload)

    assert analysis["schema"] == "safety-care/v1"
    assert analysis["models"][0]["score"] is None
    assert analysis["models"][0]["scenarios_run"] == 63
    assert analysis["models_incomplete"] == []


def test_analyze_safety_care_leaderboard_reports_artifact_residue() -> None:
    payload = _minimal_safety_care_payload()
    payload["scan_metadata"]["artifact_validation"] = {
        "unclear_mode_verdicts": 4,
        "gate_unclear_mode_verdicts": 1,
        "fail_without_evidence": 2,
        "prompt_missing": 3,
        "no_verifier_available": 5,
        "fatal_verifier_errors": 7,
        "scorer_parse_error_results": 11,
        "scorer_parse_errors": 13,
        "scorer_raw_outputs_truncated_results": 17,
        "scorer_raw_outputs_truncated_samples": 19,
    }

    analysis = health_module.analyze_leaderboard(payload)

    assert analysis["schema_warnings"] == [
        "strict_qa_blocker_unclear_mode_verdicts=4",
        "gate_unclear_mode_verdicts=1",
        "fail_without_evidence=2",
        "prompt_missing=3",
        "no_verifier_available=5",
        "fatal_verifier_errors=7",
        "scorer_parse_errors=13 across 11 rows",
        "scorer_raw_outputs_truncated=19 samples across 17 rows",
    ]


def test_analyze_safety_care_leaderboard_reports_current_contract_gaps() -> None:
    payload = _minimal_safety_care_payload()
    payload["scan_metadata"]["current_contract_validation"] = {
        "expected_scenarios": 64,
        "observed_scenarios": 63,
        "missing_scenarios": 1,
        "extra_scenarios": 0,
        "expected_checks": 50,
        "min_checks_per_row": 49,
        "max_checks_per_row": 50,
        "rows_with_missing_checks": 77,
        "missing_check_instances": 77,
        "rows_with_extra_checks": 0,
        "extra_check_instances": 0,
    }

    analysis = health_module.analyze_leaderboard(payload)

    assert "current_contract_missing_scenarios=1" in analysis["schema_warnings"]
    assert "current_contract_rows_with_missing_checks=77" in analysis["schema_warnings"]
    assert "current_contract_missing_check_instances=77" in analysis["schema_warnings"]


def _minimal_safety_care_payload() -> dict:
    return {
        "schema": "safety-care/v1",
        "notes": {"no_composite": True},
        "scan_metadata": {
            "generated_at": "2026-07-02T00:00:00+00:00",
            "total_scenarios": 1,
            "artifact_validation": {},
        },
        "models": [
            {
                "model": "Model A",
                "safety": {
                    "lines": {
                        "crisis": {},
                        "scope": {},
                        "identity": {},
                        "autonomy": {},
                    }
                },
                "care": {
                    "qualities": {
                        "belonging": {
                            "pass_rate": None,
                            "n": 0,
                            "directional": True,
                            "calibration_status": "not_claim_ready",
                        },
                        "attunement": {
                            "pass_rate": None,
                            "n": 0,
                            "directional": True,
                            "calibration_status": "not_claim_ready",
                        },
                        "relational": {
                            "pass_rate": None,
                            "n": 0,
                            "directional": True,
                            "calibration_status": "not_claim_ready",
                        },
                        "advocacy": {
                            "pass_rate": None,
                            "n": 0,
                            "directional": True,
                            "calibration_status": "not_claim_ready",
                        },
                        "trauma_awareness": {
                            "n": 0,
                            "directional": True,
                            "calibration_status": "not_claim_ready",
                            "authored_checks": 0,
                        },
                    }
                },
            }
        ],
    }


def test_local_web_projection_drift_is_reported_without_writing(tmp_path: Path) -> None:
    leaderboard_dir = tmp_path / "data" / "leaderboard"
    leaderboard_dir.mkdir(parents=True)
    source = _minimal_safety_care_payload()
    target = _minimal_safety_care_payload()
    target["scan_metadata"]["generated_at"] = "2026-06-01T00:00:00+00:00"
    target["models"][0]["model"] = "Stale Model"
    target_bytes = json.dumps(target).encode()

    (leaderboard_dir / "leaderboard.json").write_text(json.dumps(source), encoding="utf-8")
    (leaderboard_dir / "leaderboard_web.json").write_bytes(target_bytes)

    analysis = health_module.analyze_leaderboard(source)
    health_module.append_local_web_projection_health(analysis, root=tmp_path)

    assert any("local_web_projection_drift" in w for w in analysis["schema_warnings"])
    assert (leaderboard_dir / "leaderboard_web.json").read_bytes() == target_bytes


def test_local_web_projection_in_sync_has_no_warning(tmp_path: Path) -> None:
    leaderboard_dir = tmp_path / "data" / "leaderboard"
    leaderboard_dir.mkdir(parents=True)
    source = _minimal_safety_care_payload()
    projected = project_leaderboard(source)

    (leaderboard_dir / "leaderboard.json").write_text(json.dumps(source), encoding="utf-8")
    (leaderboard_dir / "leaderboard_web.json").write_text(
        json.dumps(projected, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    analysis = health_module.analyze_leaderboard(source)
    health_module.append_local_web_projection_health(analysis, root=tmp_path)

    assert analysis["schema_warnings"] == []
