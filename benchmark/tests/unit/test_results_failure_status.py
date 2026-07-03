from __future__ import annotations

from invisiblebench.models.results import ScenarioResult


def test_scenario_result_error_status_is_failure() -> None:
    result = ScenarioResult(
        scenario_id="tier1_error",
        scenario="Error scenario",
        model="Test Model",
        category="safety",
        overall_score=1.0,
        status="error",
    )

    assert result.is_failure is True
