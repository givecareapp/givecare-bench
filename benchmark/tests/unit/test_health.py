from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path

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


def test_local_web_release_missing_is_reported_without_writing(tmp_path: Path) -> None:
    analysis = health_module.analyze_leaderboard(_minimal_safety_care_payload())
    health_module.append_local_web_release_health(analysis, root=tmp_path)
    assert any("local_web_release_missing" in warning for warning in analysis["schema_warnings"])


def test_local_web_release_manifest_is_read_only_healthy(tmp_path: Path) -> None:
    archive = tmp_path / "data" / "releases" / "web-bench-release.tar.gz"
    archive.parent.mkdir(parents=True)
    manifest = json.dumps({"schema_version": "gc-bench.web-benchmark-release/v1"}).encode()
    with tarfile.open(archive, "w:gz") as release:
        info = tarfile.TarInfo("release-manifest.json")
        info.size = len(manifest)
        release.addfile(info, io.BytesIO(manifest))
    before = archive.read_bytes()
    analysis = health_module.analyze_leaderboard(_minimal_safety_care_payload())
    health_module.append_local_web_release_health(analysis, root=tmp_path)
    assert analysis["schema_warnings"] == []
    assert archive.read_bytes() == before
