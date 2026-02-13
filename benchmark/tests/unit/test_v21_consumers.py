"""Tests for v2.1 consumer changes — success signal, judge metadata in outputs."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# runner._compute_success
# ---------------------------------------------------------------------------

class TestComputeSuccess:
    def test_pass_all_gates_above_threshold(self):
        from invisiblebench.cli.runner import _compute_success

        gates = {
            "safety": {"passed": True, "reasons": []},
            "compliance": {"passed": True, "reasons": []},
        }
        assert _compute_success(0.75, False, gates) is True

    def test_fail_hard_fail(self):
        from invisiblebench.cli.runner import _compute_success

        assert _compute_success(0.9, True, {}) is False

    def test_fail_gate_failed(self):
        from invisiblebench.cli.runner import _compute_success

        gates = {
            "safety": {"passed": False, "reasons": ["crisis"]},
            "compliance": {"passed": True, "reasons": []},
        }
        assert _compute_success(0.9, False, gates) is False

    def test_fail_below_threshold(self):
        from invisiblebench.cli.runner import _compute_success

        gates = {
            "safety": {"passed": True, "reasons": []},
            "compliance": {"passed": True, "reasons": []},
        }
        assert _compute_success(0.5, False, gates) is False

    def test_pass_at_threshold(self):
        from invisiblebench.cli.runner import _compute_success

        assert _compute_success(0.6, False, {}) is True

    def test_empty_gates_no_hard_fail(self):
        from invisiblebench.cli.runner import _compute_success

        assert _compute_success(0.8, False, {}) is True

    def test_custom_threshold(self):
        from invisiblebench.cli.runner import _compute_success

        assert _compute_success(0.85, False, {}, threshold=0.9) is False
        assert _compute_success(0.95, False, {}, threshold=0.9) is True


# ---------------------------------------------------------------------------
# runner._make_error_result includes v2.1 fields
# ---------------------------------------------------------------------------

class TestMakeErrorResult:
    def test_includes_v21_fields(self):
        from invisiblebench.cli.runner import _make_error_result

        model = {"name": "Test Model", "id": "test/model-v1"}
        result = _make_error_result(model, "Test Scenario", "test_001", "safety", "boom")

        assert result["contract_version"] == "2.0.0"
        assert result["success"] is False


# ---------------------------------------------------------------------------
# stats/analysis — success rate and judge_model
# ---------------------------------------------------------------------------

class TestStatsV21:
    def test_success_rate_in_stats(self):
        from invisiblebench.stats.analysis import compute_stats

        results = [
            {"model": "A", "overall_score": 0.8, "category": "safety", "success": True, "judge_model": "gemini-2.5-flash-lite"},
            {"model": "A", "overall_score": 0.4, "category": "empathy", "success": False, "judge_model": "gemini-2.5-flash-lite"},
            {"model": "A", "overall_score": 0.7, "category": "context", "success": True},
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(results, f)
            f.flush()
            stats = compute_stats(f.name, n_bootstrap=500)

        model_stats = stats["models"]["A"]
        assert model_stats["success_count"] == 2
        assert model_stats["success_rate"] == pytest.approx(2 / 3, abs=0.01)
        assert model_stats["judge_model"] == "gemini-2.5-flash-lite"

    def test_success_rate_zero_when_absent(self):
        from invisiblebench.stats.analysis import compute_stats

        results = [
            {"model": "B", "overall_score": 0.8, "category": "safety"},
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(results, f)
            f.flush()
            stats = compute_stats(f.name, n_bootstrap=500)

        assert stats["models"]["B"]["success_count"] == 0
        assert stats["models"]["B"]["success_rate"] == 0.0
        assert stats["models"]["B"]["judge_model"] is None

    def test_format_report_includes_success(self):
        from invisiblebench.stats.analysis import compute_stats, format_stats_report

        results = [
            {"model": "A", "overall_score": 0.8, "category": "safety", "success": True, "judge_model": "test-judge"},
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(results, f)
            f.flush()
            stats = compute_stats(f.name, n_bootstrap=500)

        report = format_stats_report(stats)
        assert "Success Rates" in report
        assert "Judge: test-judge" in report


# ---------------------------------------------------------------------------
# health — v2.1 warnings
# ---------------------------------------------------------------------------

class TestHealthV21:
    def test_v21_warnings_for_missing_fields(self):
        from invisiblebench.cli.health import analyze_leaderboard

        data = {
            "metadata": {"total_scenarios": 2},
            "overall_leaderboard": [
                {
                    "model": "Model A",
                    "overall_score": 0.8,
                    "scenarios": [
                        {"scenario": "S1", "status": "pass"},
                        {"scenario": "S2", "status": "pass", "contract_version": "2.0.0", "judge_model": "gemini"},
                    ],
                },
            ],
        }

        analysis = analyze_leaderboard(data)
        assert len(analysis["v21_warnings"]) == 2  # one for contract_version, one for judge_model

    def test_no_v21_warnings_when_all_present(self):
        from invisiblebench.cli.health import analyze_leaderboard

        data = {
            "metadata": {"total_scenarios": 1},
            "overall_leaderboard": [
                {
                    "model": "Model A",
                    "overall_score": 0.8,
                    "scenarios": [
                        {"scenario": "S1", "status": "pass", "contract_version": "2.0.0", "judge_model": "gemini"},
                    ],
                },
            ],
        }

        analysis = analyze_leaderboard(data)
        assert len(analysis["v21_warnings"]) == 0


# ---------------------------------------------------------------------------
# reports — batch report includes success count
# ---------------------------------------------------------------------------

class TestBatchReportV21:
    def test_batch_html_includes_success_and_judge(self):
        from invisiblebench.export.reports import ReportGenerator

        results = [
            {"scenario": "S1", "overall_score": 0.8, "success": True, "judge_model": "gemini", "contract_version": "2.0.0"},
            {"scenario": "S2", "overall_score": 0.3, "hard_fail": True, "success": False, "judge_model": "gemini", "contract_version": "2.0.0"},
        ]

        gen = ReportGenerator()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            gen.generate_batch_report(results, f.name, metadata={"model": "Test", "mode": "full"})
            html_content = Path(f.name).read_text()

        assert "Success" in html_content
        assert "Judge: gemini" in html_content
        assert "Contract: 2.0.0" in html_content


# ---------------------------------------------------------------------------
# reports — single scenario report includes judge metadata
# ---------------------------------------------------------------------------

class TestSingleReportV21:
    def test_html_includes_judge_model(self):
        from invisiblebench.export.reports import ReportGenerator

        results = {
            "overall_score": 0.8,
            "hard_fail": False,
            "judge_model": "gemini-2.5-flash-lite",
            "contract_version": "2.0.0",
            "metadata": {"scenario_id": "test", "jurisdiction": "ca", "timestamp": "2026-02-13", "llm_mode": "llm"},
            "dimension_scores": {},
        }

        gen = ReportGenerator()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            gen.generate_html(results, f.name)
            html_content = Path(f.name).read_text()

        assert "gemini-2.5-flash-lite" in html_content
        assert "2.0.0" in html_content
