"""Tests for ScenarioResult v2.1 schema — judge metadata, success signal, from_dict."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from invisiblebench.models.results import (
    SUCCESS_THRESHOLD,
    GateResult,
    ScenarioResult,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _minimal_result(**overrides) -> dict:
    """Return minimal valid ScenarioResult dict."""
    base = {
        "scenario_id": "test_001",
        "scenario": "Test Scenario",
        "model": "Test Model",
        "overall_score": 0.75,
    }
    base.update(overrides)
    return base


def _full_v21_result(**overrides) -> dict:
    """Return a ScenarioResult dict with all v2.1 fields populated."""
    base = _minimal_result(
        model_id="test/model-v1",
        category="safety",
        run_id="abc-123-def",
        judge_model="gemini-2.5-flash-lite",
        judge_prompt_hash="sha256:abcdef1234567890",
        judge_temp=0.0,
        contract_version="2.0.0",
        success=True,
        uncertainty={"low_confidence_dimensions": ["regard"]},
        gates={
            "safety": {"passed": True, "reasons": []},
            "compliance": {"passed": True, "reasons": []},
        },
        dimensions={"regard": 0.8, "coordination": 0.7},
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# v2.1 fields round-trip
# ---------------------------------------------------------------------------

class TestV21Fields:
    def test_all_v21_fields_populated(self) -> None:
        data = _full_v21_result()
        result = ScenarioResult(**data)

        assert result.run_id == "abc-123-def"
        assert result.judge_model == "gemini-2.5-flash-lite"
        assert result.judge_prompt_hash == "sha256:abcdef1234567890"
        assert result.judge_temp == 0.0
        assert result.contract_version == "2.0.0"
        assert result.success is True
        assert result.uncertainty == {"low_confidence_dimensions": ["regard"]}

    def test_v21_fields_default_to_none(self) -> None:
        result = ScenarioResult(**_minimal_result())

        assert result.run_id is None
        assert result.judge_model is None
        assert result.judge_prompt_hash is None
        assert result.judge_temp is None
        assert result.contract_version == "2.0.0"
        assert result.success is None
        assert result.uncertainty is None

    def test_json_round_trip(self) -> None:
        data = _full_v21_result()
        result = ScenarioResult(**data)
        dumped = json.loads(result.model_dump_json())
        restored = ScenarioResult.model_validate(dumped)

        assert restored.run_id == result.run_id
        assert restored.judge_model == result.judge_model
        assert restored.judge_prompt_hash == result.judge_prompt_hash
        assert restored.judge_temp == result.judge_temp
        assert restored.contract_version == result.contract_version
        assert restored.success == result.success
        assert restored.uncertainty == result.uncertainty


# ---------------------------------------------------------------------------
# success computation
# ---------------------------------------------------------------------------

class TestSuccessComputation:
    def test_success_gates_pass_score_above_threshold(self) -> None:
        result = ScenarioResult(**_minimal_result(
            overall_score=0.75,
            gates={
                "safety": {"passed": True, "reasons": []},
                "compliance": {"passed": True, "reasons": []},
            },
        ))
        assert result.compute_success() is True
        assert result.success is True

    def test_failure_gate_fails(self) -> None:
        result = ScenarioResult(**_minimal_result(
            overall_score=0.9,
            gates={
                "safety": {"passed": False, "reasons": ["Missed crisis"]},
                "compliance": {"passed": True, "reasons": []},
            },
        ))
        assert result.compute_success() is False
        assert result.success is False

    def test_failure_score_below_threshold(self) -> None:
        result = ScenarioResult(**_minimal_result(
            overall_score=0.5,
            gates={
                "safety": {"passed": True, "reasons": []},
                "compliance": {"passed": True, "reasons": []},
            },
        ))
        assert result.compute_success() is False
        assert result.success is False

    def test_failure_score_at_threshold(self) -> None:
        result = ScenarioResult(**_minimal_result(
            overall_score=SUCCESS_THRESHOLD,
            gates={
                "safety": {"passed": True, "reasons": []},
                "compliance": {"passed": True, "reasons": []},
            },
        ))
        assert result.compute_success() is True

    def test_failure_hard_fail_no_gates(self) -> None:
        result = ScenarioResult(**_minimal_result(
            overall_score=0.9,
            hard_fail=True,
        ))
        assert result.compute_success() is False
        assert result.success is False

    def test_success_no_gates_no_hard_fail(self) -> None:
        result = ScenarioResult(**_minimal_result(overall_score=0.8))
        assert result.compute_success() is True
        assert result.success is True

    def test_custom_threshold(self) -> None:
        result = ScenarioResult(**_minimal_result(overall_score=0.85))
        assert result.compute_success(threshold=0.9) is False
        assert result.compute_success(threshold=0.8) is True

    def test_success_with_gate_result_objects(self) -> None:
        result = ScenarioResult(
            **_minimal_result(overall_score=0.75),
            gates={
                "safety": GateResult(passed=True),
                "compliance": GateResult(passed=True),
            },
        )
        assert result.compute_success() is True


# ---------------------------------------------------------------------------
# from_dict — backward compatibility
# ---------------------------------------------------------------------------

class TestFromDict:
    def test_from_dict_with_current_format(self) -> None:
        data = _full_v21_result()
        result = ScenarioResult.from_dict(data)

        assert result.run_id == "abc-123-def"
        assert result.judge_model == "gemini-2.5-flash-lite"
        assert result.contract_version == "2.0.0"
        assert result.success is True

    def test_from_dict_legacy_no_judge_fields(self) -> None:
        """Old-format data (no v2.1 judge fields) should still deserialize."""
        data = {
            "scenario_id": "tier1_001",
            "scenario": "Legacy Scenario",
            "model": "Old Model",
            "overall_score": 0.85,
            "hard_fail": False,
            "status": "pass",
            "dimension_scores": {
                "safety": 1.0,
                "compliance": 1.0,
                "attunement": 0.8,
                "belonging": 0.9,
                "memory": 0.95,
                "false_refusal": 1.0,
            },
        }
        result = ScenarioResult.from_dict(data)

        assert result.scenario_id == "tier1_001"
        assert result.contract_version == "2.0.0"
        assert result.run_id is None
        assert result.judge_model is None
        # Legacy attunement/belonging normalized to regard in dimension_scores
        assert result.success is True  # gates pass (no gates/no hard_fail), score >= 0.6

    def test_from_dict_legacy_tier_to_category(self) -> None:
        data = {
            "scenario_id": "tier2_001",
            "scenario": "Tier Scenario",
            "model": "Model",
            "overall_score": 0.7,
            "tier": "safety",
        }
        result = ScenarioResult.from_dict(data)
        assert result.category == "safety"

    def test_from_dict_legacy_dimension_normalization(self) -> None:
        """Legacy attunement/belonging/consistency keys are normalized."""
        data = {
            "scenario_id": "tier1_legacy",
            "scenario": "Legacy Dims",
            "model": "Model",
            "overall_score": 0.8,
            "dimension_scores": {
                "attunement": 0.7,
                "belonging": 0.85,
                "consistency": 0.9,
                "safety": 1.0,
                "compliance": 1.0,
                "false_refusal": 1.0,
            },
        }
        result = ScenarioResult.from_dict(data)
        # attunement maps to regard, belonging also maps to regard (first wins)
        assert result.dimensions.regard == 0.7
        # consistency maps to memory
        assert result.dimensions.memory == 0.9

    def test_from_dict_computes_success_automatically(self) -> None:
        data = _minimal_result(overall_score=0.4)
        result = ScenarioResult.from_dict(data)
        assert result.success is False

    def test_from_dict_preserves_explicit_success(self) -> None:
        data = _minimal_result(overall_score=0.4, success=True)
        result = ScenarioResult.from_dict(data)
        # from_dict recomputes if success is None; here it's explicitly True
        # but from_dict computes because the raw dict value won't survive model_validate
        # as a non-None — actually it will, so from_dict skips compute
        assert result.success is True  # Preserved from input


# ---------------------------------------------------------------------------
# Loading existing result files (integration-style)
# ---------------------------------------------------------------------------

class TestLoadExistingResults:
    @pytest.fixture()
    def leaderboard_dir(self) -> Path:
        return Path("results/leaderboard_ready")

    @pytest.fixture()
    def run_results_path(self) -> Path:
        return Path("results/run_20260213_000851/all_results.json")

    def test_load_leaderboard_file(self, leaderboard_dir: Path) -> None:
        """At least one leaderboard file loads through from_dict without error."""
        files = list(leaderboard_dir.glob("*.json"))
        if not files:
            pytest.skip("No leaderboard files found")

        data = json.loads(files[0].read_text())
        # Leaderboard files have a different shape (model-level with scenarios list)
        scenarios = data.get("scenarios", [])
        if not scenarios:
            pytest.skip("No scenarios in leaderboard file")

        # Inject model name if not present in scenario dicts
        model_name = data.get("model", data.get("model_name", "Unknown"))
        for s in scenarios[:3]:
            s.setdefault("model", model_name)
            s.setdefault("scenario_id", s.get("scenario", "unknown").lower().replace(" ", "_"))
            result = ScenarioResult.from_dict(s)
            assert result.contract_version == "2.0.0"
            assert result.success is not None

    def test_load_run_results(self, run_results_path: Path) -> None:
        """Run results file loads through from_dict."""
        if not run_results_path.exists():
            pytest.skip("Run results file not found")

        items = json.loads(run_results_path.read_text())
        if not isinstance(items, list) or not items:
            pytest.skip("Empty or non-list results")

        result = ScenarioResult.from_dict(items[0])
        assert result.contract_version == "2.0.0"
        assert result.success is not None
