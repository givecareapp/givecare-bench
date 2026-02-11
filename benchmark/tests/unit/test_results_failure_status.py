from __future__ import annotations

from invisiblebench.export.reports import ReportGenerator
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


def test_batch_report_counts_error_as_failure() -> None:
    generator = ReportGenerator()
    results = [
        {
            "scenario": "Ok scenario",
            "category": "safety",
            "overall_score": 0.9,
            "hard_fail": False,
            "status": "pass",
        },
        {
            "scenario": "Error scenario",
            "category": "safety",
            "overall_score": 0.9,
            "hard_fail": False,
            "status": "error",
        },
    ]

    html = generator._build_batch_html(results, {"model": "Test", "mode": "benchmark"})

    assert "<div class='stat-value pass'>1</div>" in html
    assert "<div class='stat-value fail'>1</div>" in html
    assert "Error scenario" in html
