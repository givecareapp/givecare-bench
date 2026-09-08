"""Health never presents a historical release as current."""

from invisiblebench.cli.health import analyze_leaderboard, append_local_web_release_health
from invisiblebench.version import BENCHMARK_VERSION


def test_historical_scores_are_not_current():
    analysis = analyze_leaderboard({"schema": "safety-care/v1", "models": [{"model": "Old"}]})
    assert analysis["current"] is False
    assert analysis["model_count"] == 0
    assert "historical" in analysis["errors"][0]


def test_current_shape_does_not_need_composite_or_human_validation():
    analysis = analyze_leaderboard({"schema": "safety-care/v3",
        "scan_metadata": {"benchmark_version": BENCHMARK_VERSION}, "models": [{"model": "New"}]})
    assert analysis == {"current": True, "schema": "safety-care/v3", "model_count": 1, "errors": []}


def test_missing_archive_is_reported_without_writes(tmp_path):
    analysis = {"errors": []}
    append_local_web_release_health(analysis, root=tmp_path)
    assert analysis["errors"]
    assert list(tmp_path.iterdir()) == []
