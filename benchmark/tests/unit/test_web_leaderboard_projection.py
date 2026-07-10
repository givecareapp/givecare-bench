"""Tests for sync_web_bench.py — safety-care/v1 lean web projection."""

from __future__ import annotations

import pytest

from delivery.sync_web_bench import project_leaderboard


def _minimal_source(
    *,
    model_name: str = "Test Model",
    crisis_rate: float = 0.2,
    belonging_pass_rate: float = 0.8,
) -> dict:
    """Minimal safety-care/v1 artifact for projection tests."""
    return {
        "schema": "safety-care/v1",
        "notes": {"no_composite": True, "out_of_scope": ["usefulness"]},
        "scan_metadata": {
            "benchmark_version": "4.0.0",
            "generated_at": "2026-04-30T00:00:00+00:00",
            "total_scenarios": 10,
            "active_modes": 53,
            "statistics": {"method": "cluster-robust SEs"},
        },
        "models": [
            {
                "model": model_name,
                "safety": {
                    "lines": {
                        "crisis": {"rate": crisis_rate, "ci95": [0.0, 0.5], "n": 10},
                        "scope": {"rate": 0.1, "ci95": [0.0, 0.3], "n": 10},
                        "identity": {"rate": None, "ci95": None, "n": 0},
                        "autonomy": {"rate": None, "ci95": None, "n": 0},
                    },
                    "aggregate": {"rate": crisis_rate, "ci95": [0.0, 0.5]},
                    "severity_breakdown": {"crisis": {"S5": 2}},
                    "calibrated_only": True,
                },
                "care": {
                    "qualities": {
                        "belonging": {
                            "pass_rate": belonging_pass_rate,
                            "n": 10,
                            "directional": True,
                            "calibration_status": "not_claim_ready",
                        },
                        "attunement": {
                            "pass_rate": 0.7,
                            "n": 5,
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
                    },
                },
            }
        ],
    }


def test_project_leaderboard_emits_lean_shape() -> None:
    """Projected web payload must be the lean {schema, notes, scan_metadata, models} contract."""
    projected = project_leaderboard(_minimal_source())

    assert set(projected) == {"schema", "notes", "scan_metadata", "models"}
    assert projected["schema"] == "safety-care/v1"
    assert len(projected["models"]) == 1

    # Models carry safety lines and care qualities unchanged
    model = projected["models"][0]
    assert "safety" in model
    assert "care" in model
    assert set(model["safety"]["lines"]) >= {"crisis", "scope", "identity", "autonomy"}
    assert "belonging" in model["care"]["qualities"]


def test_project_leaderboard_rejects_deprecated_v3() -> None:
    """_deprecated_v3 must fail before public projection."""
    source = _minimal_source()
    source["_deprecated_v3"] = {"overall_leaderboard": []}

    with pytest.raises(ValueError, match="_deprecated_v3"):
        project_leaderboard(source)


def test_project_leaderboard_rejects_unknown_top_level_keys() -> None:
    """No retired composite or narrative fields can silently pass through."""
    source = _minimal_source()
    source["overall_score"] = 0.9

    with pytest.raises(ValueError, match="overall_score"):
        project_leaderboard(source)


def test_project_leaderboard_rejects_nested_retired_score_keys() -> None:
    """Retired ranking/composite keys cannot hide inside model payloads."""
    source = _minimal_source()
    source["models"][0]["rank"] = 1
    source["models"][0]["safety"]["overall_score"] = 0.9

    with pytest.raises(ValueError, match=r"models\[0\]"):
        project_leaderboard(source)


def test_project_leaderboard_rejects_raw_internal_keys() -> None:
    """Raw runner/verdict diagnostic fields cannot leak into public payloads."""
    source = _minimal_source()
    source["models"][0]["hard_fail"] = True
    source["models"][0]["care"]["qualities"]["belonging"]["primary_bucket"] = "C"

    with pytest.raises(ValueError, match="hard_fail"):
        project_leaderboard(source)


def test_project_leaderboard_rejects_retired_care_status_key() -> None:
    """Care qualities use binary calibration_status, not old status labels."""
    source = _minimal_source()
    trauma = source["models"][0]["care"]["qualities"]["trauma_awareness"]
    del trauma["calibration_status"]
    trauma["status"] = "to-author"

    with pytest.raises(ValueError, match="retired status key"):
        project_leaderboard(source)


def test_project_leaderboard_rejects_invalid_care_claim_status() -> None:
    """Care claim status must stay in the binary claim_ready/not_claim_ready vocabulary."""
    source = _minimal_source()
    source["models"][0]["care"]["qualities"]["belonging"]["calibration_status"] = "validated"

    with pytest.raises(ValueError, match="invalid calibration_status"):
        project_leaderboard(source)


def test_project_leaderboard_care_qualities_present() -> None:
    """Projected care qualities must carry pass_rate, n, calibration_status unchanged."""
    projected = project_leaderboard(_minimal_source(belonging_pass_rate=0.75))
    belonging = projected["models"][0]["care"]["qualities"]["belonging"]
    assert belonging["pass_rate"] == 0.75
    assert belonging["n"] == 10
    assert belonging["calibration_status"] == "not_claim_ready"


def test_project_leaderboard_safety_lines_present() -> None:
    """Safety lines must be passed through with rate, ci95, n."""
    projected = project_leaderboard(_minimal_source(crisis_rate=0.3))
    crisis = projected["models"][0]["safety"]["lines"]["crisis"]
    assert crisis["rate"] == 0.3
    assert crisis["n"] == 10


def test_project_leaderboard_rejects_wrong_schema() -> None:
    """project_leaderboard must reject non-safety-care/v1 sources."""
    with pytest.raises(ValueError, match="safety-care/v1"):
        project_leaderboard({"schema": "retired-v3", "overall_leaderboard": []})


def test_project_leaderboard_rejects_missing_models() -> None:
    """project_leaderboard must reject sources with no models."""
    src = _minimal_source()
    src["models"] = []
    with pytest.raises(ValueError, match="missing or empty models"):
        project_leaderboard(src)


def test_project_leaderboard_rejects_model_missing_safety() -> None:
    """project_leaderboard must reject a model entry without 'safety'."""
    src = _minimal_source()
    del src["models"][0]["safety"]
    with pytest.raises(ValueError, match="missing required 'safety'"):
        project_leaderboard(src)


def test_project_leaderboard_rejects_model_missing_care() -> None:
    """project_leaderboard must reject a model entry without 'care'."""
    src = _minimal_source()
    del src["models"][0]["care"]
    with pytest.raises(ValueError, match="missing required 'care'"):
        project_leaderboard(src)
