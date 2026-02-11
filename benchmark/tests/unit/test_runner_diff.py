from __future__ import annotations

from pathlib import Path

import pytest

from invisiblebench.cli.runner import aggregate_results_by_model, compute_run_diff, load_run_results


PROJECT_ROOT = Path(__file__).resolve().parents[3]
FIXTURES_DIR = PROJECT_ROOT / "benchmark" / "tests" / "fixtures"


def _comparison_by_model(comparisons):
    return {row["model"]: row for row in comparisons}


def test_aggregate_results_by_model_uses_fixture_data() -> None:
    base_rows = load_run_results(FIXTURES_DIR / "diff_base_all_results.json")
    aggregated = aggregate_results_by_model(base_rows)

    assert aggregated["model-alpha"]["avg_overall_score"] == 0.7
    assert aggregated["model-alpha"]["status_counts"] == {"pass": 2, "fail": 0, "error": 0}
    assert aggregated["model-alpha"]["hard_failure_count"] == 0

    assert aggregated["model-gamma"]["avg_overall_score"] == 0.45
    assert aggregated["model-gamma"]["status_counts"] == {"pass": 1, "fail": 1, "error": 0}
    assert aggregated["model-gamma"]["hard_failure_count"] == 1


def test_compute_run_diff_with_fixtures_handles_regressions_and_missing_models() -> None:
    base_rows = load_run_results(FIXTURES_DIR / "diff_base_all_results.json")
    new_rows = load_run_results(FIXTURES_DIR / "diff_new_all_results.json")

    base_by_model = aggregate_results_by_model(base_rows)
    new_by_model = aggregate_results_by_model(new_rows)
    comparisons = compute_run_diff(base_by_model, new_by_model)
    by_model = _comparison_by_model(comparisons)

    assert [row["model"] for row in comparisons] == [
        "model-alpha",
        "model-beta",
        "model-delta",
        "model-gamma",
    ]

    alpha = by_model["model-alpha"]
    assert alpha["base_avg_overall_score"] == 0.7
    assert alpha["new_avg_overall_score"] == 0.6
    assert alpha["delta_avg_overall_score"] == pytest.approx(-0.1)
    assert alpha["regressed"] is True

    beta = by_model["model-beta"]
    assert beta["delta_avg_overall_score"] == pytest.approx(0.3)
    assert beta["base_status_counts"] == {"pass": 2, "fail": 0, "error": 0}
    assert beta["new_status_counts"] == {"pass": 1, "fail": 0, "error": 1}
    assert beta["regressed"] is True

    delta = by_model["model-delta"]
    assert delta["base_avg_overall_score"] is None
    assert delta["new_avg_overall_score"] == 0.88
    assert delta["delta_avg_overall_score"] is None
    assert delta["base_status_counts"] is None
    assert delta["regressed"] is False

    gamma = by_model["model-gamma"]
    assert gamma["new_avg_overall_score"] is None
    assert gamma["delta_avg_overall_score"] is None
    assert gamma["new_status_counts"] is None
    assert gamma["regressed"] is False
