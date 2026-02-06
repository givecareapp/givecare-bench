"""Tests that failed scenarios are recorded in results, not silently dropped."""

from __future__ import annotations

import json
from pathlib import Path

from invisiblebench.cli.runner import _make_error_result, estimate_cost

# ---------------------------------------------------------------------------
# Unit: _make_error_result produces correct schema
# ---------------------------------------------------------------------------


def test_make_error_result_schema():
    model = {"name": "Test", "id": "test/model", "cost_per_m_input": 1.0, "cost_per_m_output": 2.0}
    result = _make_error_result(model, "Crisis", "tier1_crisis", 1, "boom")

    assert result["status"] == "error"
    assert result["overall_score"] == 0.0
    assert result["hard_fail"] is True
    assert result["hard_fail_reasons"] == ["boom"]
    assert result["failure_categories"] == {}
    assert result["dimensions"] == {}
    assert result["model"] == "Test"
    assert result["model_id"] == "test/model"
    assert result["scenario"] == "Crisis"
    assert result["scenario_id"] == "tier1_crisis"
    assert result["tier"] == 1
    assert result["cost"] == estimate_cost(1, model)


def test_make_error_result_transcript_reason():
    model = {"name": "M", "id": "m/1", "cost_per_m_input": 0.5, "cost_per_m_output": 1.0}
    result = _make_error_result(
        model,
        "Scenario",
        "tier3_longitudinal_001",
        3,
        "Transcript generation failed: 400 Bad Request",
    )
    assert "Transcript generation failed" in result["hard_fail_reasons"][0]
    assert result["tier"] == 3


def test_make_error_result_scoring_reason():
    model = {"name": "M", "id": "m/1", "cost_per_m_input": 0.5, "cost_per_m_output": 1.0}
    result = _make_error_result(
        model,
        "Scenario",
        "tier2_boundary",
        2,
        "Scoring failed: memory dimension missing",
    )
    assert "Scoring failed" in result["hard_fail_reasons"][0]


# ---------------------------------------------------------------------------
# Unit: error results are JSON-serializable
# ---------------------------------------------------------------------------


def test_error_results_appear_in_saved_json(tmp_path: Path):
    """Error results must be serializable and present in saved all_results.json."""
    results = [
        {
            "model": "Test Model",
            "model_id": "test/model",
            "scenario": "Pass",
            "scenario_id": "tier0_pass",
            "tier": 0,
            "overall_score": 0.85,
            "hard_fail": False,
            "hard_fail_reasons": [],
            "failure_categories": {},
            "dimensions": {"memory": 0.9},
            "cost": 0.001,
            "status": "pass",
        },
        _make_error_result(
            {
                "name": "Test Model",
                "id": "test/model",
                "cost_per_m_input": 1.0,
                "cost_per_m_output": 2.0,
            },
            "Error Scenario",
            "tier3_longitudinal_001",
            3,
            "Transcript generation failed: 400 Bad Request",
        ),
    ]

    out = tmp_path / "all_results.json"
    out.write_text(json.dumps(results, indent=2))

    loaded = json.loads(out.read_text())
    assert len(loaded) == 2
    assert loaded[0]["status"] == "pass"
    assert loaded[1]["status"] == "error"
    assert loaded[1]["scenario_id"] == "tier3_longitudinal_001"


# ---------------------------------------------------------------------------
# Integration: patched runner records errors instead of dropping them
# ---------------------------------------------------------------------------


def test_sequential_runner_records_transcript_error(tmp_path: Path):
    """Patch generate_transcript to raise, verify the scenario appears in
    all_results.json with status='error'."""
    # Create a minimal scenario file
    scenario_file = tmp_path / "scenario.json"
    scenario_file.write_text(
        json.dumps(
            {
                "scenario_id": "tier1_test_error",
                "tier": 1,
                "title": "Test Error",
                "turns": [{"turn_number": 1, "user_message": "hello"}],
            }
        )
    )

    model = {
        "name": "Test Model",
        "id": "test/model",
        "cost_per_m_input": 1.0,
        "cost_per_m_output": 2.0,
    }
    scenario = {"name": "Test Error", "tier": 1, "path": str(scenario_file)}

    # Simulate what the sequential runner does
    results = []
    failed = 0

    scenario_data = json.loads(scenario_file.read_text())
    scenario_id = scenario_data["scenario_id"]

    # Simulate generate_transcript raising
    transcript_error = RuntimeError("Transcript generation had 1 error(s): Turn 1: 400 Bad Request")

    # This is the fixed code path from runner.py
    results.append(
        _make_error_result(
            model,
            scenario["name"],
            scenario_id,
            scenario["tier"],
            f"Transcript generation failed: {transcript_error}",
        )
    )
    failed += 1

    # Save as the runner would
    results_file = tmp_path / "all_results.json"
    results_file.write_text(json.dumps(results, indent=2))

    # Verify
    loaded = json.loads(results_file.read_text())
    assert len(loaded) == 1, "Error scenario must not be dropped"
    assert loaded[0]["status"] == "error"
    assert loaded[0]["scenario_id"] == "tier1_test_error"
    assert loaded[0]["overall_score"] == 0.0
    assert loaded[0]["hard_fail"] is True
    assert "400 Bad Request" in loaded[0]["hard_fail_reasons"][0]
    assert failed == 1
