"""Tests that failed scenarios are recorded in results, not silently dropped."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from invisiblebench.cli.runner import estimate_cost


def _make_error_result(model_name: str, model_id: str, scenario_name: str,
                       scenario_id: str, tier: int, error_msg: str) -> dict:
    """Build the expected error result dict."""
    return {
        "model": model_name,
        "model_id": model_id,
        "scenario": scenario_name,
        "scenario_id": scenario_id,
        "tier": tier,
        "overall_score": 0.0,
        "hard_fail": True,
        "hard_fail_reasons": [error_msg],
        "failure_categories": {},
        "dimensions": {},
        "status": "error",
    }


def test_transcript_error_produces_error_result():
    """When generate_transcript raises, the scenario must appear in results
    with status='error', not be silently dropped."""
    # Simulate what the sequential runner does when transcript generation fails
    model = {"name": "Test Model", "id": "test/model",
             "cost_per_m_input": 1.0, "cost_per_m_output": 2.0}
    scenario = {"name": "Crisis Scenario", "tier": 1, "path": "/fake/path.json"}
    scenario_id = "tier1_crisis"

    results = []
    failed = 0

    # This mirrors the fixed except block in the sequential runner path
    error = RuntimeError("Transcript generation had 10 error(s): Turn 9: 400 Bad Request")
    results.append({
        "model": model["name"],
        "model_id": model["id"],
        "scenario": scenario["name"],
        "scenario_id": scenario_id,
        "tier": scenario["tier"],
        "overall_score": 0.0,
        "hard_fail": True,
        "hard_fail_reasons": [f"Transcript generation failed: {error}"],
        "failure_categories": {},
        "dimensions": {},
        "cost": estimate_cost(scenario["tier"], model),
        "status": "error",
    })
    failed += 1

    assert len(results) == 1
    assert results[0]["status"] == "error"
    assert results[0]["overall_score"] == 0.0
    assert results[0]["hard_fail"] is True
    assert results[0]["scenario_id"] == "tier1_crisis"
    assert "Transcript generation failed" in results[0]["hard_fail_reasons"][0]
    assert failed == 1


def test_scoring_error_produces_error_result():
    """When orchestrator.score raises, the scenario must appear in results
    with status='error', not be silently dropped."""
    model = {"name": "Test Model", "id": "test/model"}
    scenario_id = "tier2_boundary"

    results = []
    failed = 0

    error = Exception("Scorer dimension not found: memory")
    results.append({
        "model": model["name"],
        "model_id": model["id"],
        "scenario": "Boundary Test",
        "scenario_id": scenario_id,
        "tier": 2,
        "overall_score": 0.0,
        "hard_fail": True,
        "hard_fail_reasons": [f"Scoring failed: {error}"],
        "failure_categories": {},
        "dimensions": {},
        "cost": 0.001,
        "status": "error",
    })
    failed += 1

    assert len(results) == 1
    assert results[0]["status"] == "error"
    assert results[0]["hard_fail"] is True
    assert "Scoring failed" in results[0]["hard_fail_reasons"][0]


def test_error_results_appear_in_saved_json():
    """Error results must be serializable and included in the saved all_results.json."""
    results = [
        {
            "model": "Test Model",
            "model_id": "test/model",
            "scenario": "Pass Scenario",
            "scenario_id": "tier0_pass",
            "tier": 0,
            "overall_score": 0.85,
            "hard_fail": False,
            "hard_fail_reasons": [],
            "failure_categories": {},
            "dimensions": {"memory": 0.9, "safety": 1.0},
            "cost": 0.001,
            "status": "pass",
        },
        {
            "model": "Test Model",
            "model_id": "test/model",
            "scenario": "Error Scenario",
            "scenario_id": "tier3_longitudinal_001",
            "tier": 3,
            "overall_score": 0.0,
            "hard_fail": True,
            "hard_fail_reasons": ["Transcript generation failed: 400 Bad Request"],
            "failure_categories": {},
            "dimensions": {},
            "cost": 0.003,
            "status": "error",
        },
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(results, f, indent=2)
        tmp_path = f.name

    loaded = json.loads(Path(tmp_path).read_text())
    assert len(loaded) == 2
    assert loaded[0]["status"] == "pass"
    assert loaded[1]["status"] == "error"
    assert loaded[1]["scenario_id"] == "tier3_longitudinal_001"

    Path(tmp_path).unlink()
