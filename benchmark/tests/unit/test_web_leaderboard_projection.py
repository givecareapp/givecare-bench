"""Tests for sync_web_bench.py — safety-care/v1 lean web projection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

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
        "_deprecated_v3": {"overall_leaderboard": [], "models": []},
    }


def test_project_leaderboard_emits_lean_shape() -> None:
    """Projected web payload must be the lean {schema, notes, scan_metadata, models} contract."""
    projected = project_leaderboard(_minimal_source())

    # Top-level keys: public fields only — no deprecated or private keys
    assert "schema" in projected
    assert "notes" in projected
    assert "scan_metadata" in projected
    assert "models" in projected
    assert "_deprecated_v3" not in projected

    assert projected["schema"] == "safety-care/v1"
    assert len(projected["models"]) == 1

    # Models carry safety lines and care qualities unchanged
    model = projected["models"][0]
    assert "safety" in model
    assert "care" in model
    assert set(model["safety"]["lines"]) >= {"crisis", "scope", "identity", "autonomy"}
    assert "belonging" in model["care"]["qualities"]


def test_project_leaderboard_strips_deprecated_v3() -> None:
    """_deprecated_v3 must never appear in the public output."""
    projected = project_leaderboard(_minimal_source())
    assert "_deprecated_v3" not in projected


def test_project_leaderboard_strips_all_private_keys() -> None:
    """No retired composite fields appear in the projection."""
    projected = project_leaderboard(_minimal_source())
    assert "findings" not in projected
    assert "themes" not in projected
    assert "overall_score" not in projected
    assert "dimensions" not in projected


def test_project_leaderboard_care_qualities_present() -> None:
    """Projected care qualities must carry pass_rate, n, calibration_status unchanged."""
    projected = project_leaderboard(_minimal_source(belonging_pass_rate=0.75))
    belonging = projected["models"][0]["care"]["qualities"]["belonging"]
    assert belonging["pass_rate"] == 0.75
    assert belonging["n"] == 10
    assert belonging["calibration_status"] == "provisional"


def test_project_leaderboard_safety_lines_present() -> None:
    """Safety lines must be passed through with rate, ci95, n."""
    projected = project_leaderboard(_minimal_source(crisis_rate=0.3))
    crisis = projected["models"][0]["safety"]["lines"]["crisis"]
    assert crisis["rate"] == 0.3
    assert crisis["n"] == 10


def test_project_leaderboard_rejects_wrong_schema() -> None:
    """project_leaderboard must reject non-safety-care/v1 sources."""
    with pytest.raises(ValueError, match="safety-care/v1"):
        project_leaderboard({"schema": "v3-legacy", "overall_leaderboard": []})


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


def test_checked_in_leaderboard_passes_lean_contract() -> None:
    """The canonical leaderboard.json must pass lean-projection validation."""
    source = json.loads((PROJECT_ROOT / "data/leaderboard/leaderboard.json").read_text())
    projected = project_leaderboard(source)

    assert projected["schema"] == "safety-care/v1"
    assert isinstance(projected["models"], list)
    assert len(projected["models"]) > 0
    assert "_deprecated_v3" not in projected
    assert "findings" not in projected
    assert "themes" not in projected
    assert "overall_score" not in projected

    for model in projected["models"]:
        assert "safety" in model, f"Model {model.get('model')!r} missing safety"
        assert "care" in model, f"Model {model.get('model')!r} missing care"
        assert "lines" in model["safety"], f"Model {model.get('model')!r} safety missing lines"
        assert "qualities" in model["care"], f"Model {model.get('model')!r} care missing qualities"
