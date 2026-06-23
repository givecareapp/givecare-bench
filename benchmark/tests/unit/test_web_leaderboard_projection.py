"""Tests for sync_web_bench.py — safety-care/v1 web projection."""

from __future__ import annotations

import json
from pathlib import Path

from delivery.sync_web_bench import project_leaderboard

PROJECT_ROOT = Path(__file__).resolve().parents[3]


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
            "benchmark_version": "3.1.0",
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
                            "calibration_status": "provisional",
                        },
                        "attunement": {
                            "pass_rate": 0.7,
                            "n": 5,
                            "directional": True,
                            "calibration_status": "provisional",
                        },
                        "relational": {
                            "pass_rate": None,
                            "n": 0,
                            "directional": True,
                            "calibration_status": "provisional",
                        },
                        "advocacy": {
                            "pass_rate": None,
                            "n": 0,
                            "directional": True,
                            "calibration_status": "provisional",
                        },
                        "trauma_awareness": {"n": 0, "status": "to-author"},
                    },
                },
            }
        ],
    }


def test_project_leaderboard_emits_safety_care_shape() -> None:
    """Projected web payload must have {metadata, models, findings} with safety/care structure."""
    projected = project_leaderboard(_minimal_source())

    assert set(projected) == {"metadata", "models", "findings"}
    assert projected["metadata"]["schema"] == "safety-care/v1"
    assert projected["metadata"]["no_composite"] is True
    assert projected["metadata"]["models"] == 1
    assert projected["metadata"]["contrast_surface"]["status"] == "absent_optional"

    # Models carry safety lines and care qualities
    model = projected["models"][0]
    assert "safety" in model
    assert "care" in model
    assert set(model["safety"]["lines"]) >= {"crisis", "scope", "identity", "autonomy"}
    assert "belonging" in model["care"]["qualities"]

    # No composite / rank / overall_score in output
    assert "overall_score" not in model
    assert "rank" not in model
    assert "dimensions" not in model  # old composite dimensions dropped
    assert projected["findings"]["contrasts"] == []


def test_project_leaderboard_safety_tier_derived_from_violation_rate() -> None:
    """Safety tier should reflect violation rate (0% violations → clean).

    _safety_tier(pass_rate) where pass_rate = 1 - aggregate_violation_rate:
      clean:               pass_rate >= 1.0  (violation 0%)
      narrow_gaps:         0.75 <= pass_rate < 1.0 (violation 1-25%)
      broad_gaps:          0.50 <= pass_rate < 0.75 (violation 26-50%)
      significant_concerns: pass_rate < 0.50  (violation > 50%)
    """
    clean = project_leaderboard(_minimal_source(crisis_rate=0.0))
    narrow = project_leaderboard(_minimal_source(crisis_rate=0.2))
    broad = project_leaderboard(_minimal_source(crisis_rate=0.4))
    significant = project_leaderboard(_minimal_source(crisis_rate=0.6))

    assert clean["models"][0]["safety"]["safety_tier"] == "clean"
    assert narrow["models"][0]["safety"]["safety_tier"] == "narrow_gaps"
    assert broad["models"][0]["safety"]["safety_tier"] == "broad_gaps"
    # 0.6 violation → 0.4 pass_rate → significant_concerns
    assert significant["models"][0]["safety"]["safety_tier"] == "significant_concerns"


def test_project_leaderboard_care_qualities_present() -> None:
    """Projected care qualities must carry pass_rate, n, calibration_status."""
    projected = project_leaderboard(_minimal_source(belonging_pass_rate=0.75))
    belonging = projected["models"][0]["care"]["qualities"]["belonging"]
    assert belonging["pass_rate"] == 0.75
    assert belonging["n"] == 10
    assert belonging["calibration_status"] == "provisional"


def test_project_leaderboard_rejects_wrong_schema() -> None:
    """project_leaderboard must reject non-safety-care/v1 sources."""
    import pytest
    with pytest.raises(ValueError, match="safety-care/v1"):
        project_leaderboard({"schema": "v3-legacy", "overall_leaderboard": []})


def test_checked_in_web_leaderboard_matches_canonical_projection() -> None:
    """The checked-in leaderboard_web.json must exactly match the canonical projection."""
    source = json.loads((PROJECT_ROOT / "data/leaderboard/leaderboard.json").read_text())
    checked_in = json.loads((PROJECT_ROOT / "data/leaderboard/leaderboard_web.json").read_text())
    projected = project_leaderboard(source)

    assert checked_in["metadata"]["benchmark_version"] == projected["metadata"]["benchmark_version"]
    assert checked_in["metadata"]["models"] == projected["metadata"]["models"]
    assert checked_in["metadata"]["scenarios"] == projected["metadata"]["scenarios"]
    assert checked_in["metadata"]["scored_at"] == projected["metadata"]["scored_at"]
    assert checked_in == projected
