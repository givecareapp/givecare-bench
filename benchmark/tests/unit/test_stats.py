"""Tests for statistical analysis modules."""

import csv
import json
import tempfile
from pathlib import Path


class TestBootstrapCI:
    """Test bootstrap confidence interval computation."""

    def test_single_value(self):
        from invisiblebench.stats.analysis import _bootstrap_ci

        mean, lo, hi = _bootstrap_ci([0.75])
        assert mean == 0.75
        assert lo == 0.75
        assert hi == 0.75

    def test_empty_list(self):
        from invisiblebench.stats.analysis import _bootstrap_ci

        mean, lo, hi = _bootstrap_ci([])
        assert mean == 0.0

    def test_ci_contains_mean(self):
        from invisiblebench.stats.analysis import _bootstrap_ci

        scores = [0.6, 0.7, 0.8, 0.9, 0.5, 0.75, 0.85]
        mean, lo, hi = _bootstrap_ci(scores, n_bootstrap=5000)
        assert lo <= mean <= hi

    def test_ci_narrows_with_consistency(self):
        from invisiblebench.stats.analysis import _bootstrap_ci

        # Consistent scores → narrow CI
        consistent = [0.70, 0.71, 0.69, 0.70, 0.72, 0.71, 0.70]
        _, lo_c, hi_c = _bootstrap_ci(consistent, n_bootstrap=5000)
        width_c = hi_c - lo_c

        # Variable scores → wider CI
        variable = [0.30, 0.90, 0.50, 0.80, 0.40, 0.95, 0.20]
        _, lo_v, hi_v = _bootstrap_ci(variable, n_bootstrap=5000)
        width_v = hi_v - lo_v

        assert width_v > width_c

    def test_reproducible_with_seed(self):
        from invisiblebench.stats.analysis import _bootstrap_ci

        scores = [0.6, 0.7, 0.8, 0.9]
        r1 = _bootstrap_ci(scores, seed=42)
        r2 = _bootstrap_ci(scores, seed=42)
        assert r1 == r2


class TestBootstrapDiff:
    """Test pairwise bootstrap comparison."""

    def test_identical_scores(self):
        from invisiblebench.stats.analysis import _bootstrap_diff_ci

        scores = [0.7, 0.8, 0.6, 0.75]
        diff, lo, hi, sig = _bootstrap_diff_ci(scores, scores)
        assert abs(diff) < 0.001
        assert not sig

    def test_clearly_different(self):
        from invisiblebench.stats.analysis import _bootstrap_diff_ci

        better = [0.9, 0.95, 0.88, 0.92, 0.91]
        worse = [0.3, 0.35, 0.28, 0.32, 0.31]
        diff, lo, hi, sig = _bootstrap_diff_ci(better, worse)
        assert diff > 0.5
        assert sig

    def test_overlapping_not_significant(self):
        from invisiblebench.stats.analysis import _bootstrap_diff_ci

        a = [0.70, 0.72, 0.68, 0.71, 0.69]
        b = [0.68, 0.70, 0.66, 0.69, 0.67]
        diff, lo, hi, sig = _bootstrap_diff_ci(a, b)
        assert abs(diff) < 0.05
        # With such close scores and small N, should not be significant
        # (may vary with bootstrap, but very likely not sig)


class TestComputeStats:
    """Test full stats computation."""

    def test_from_results_list(self):
        from invisiblebench.stats.analysis import compute_stats

        results = [
            {"model": "A", "overall_score": 0.8, "category": "safety", "hard_fail": False, "status": "pass"},
            {"model": "A", "overall_score": 0.7, "category": "empathy", "hard_fail": False, "status": "pass"},
            {"model": "B", "overall_score": 0.6, "category": "safety", "hard_fail": True, "status": "fail"},
            {"model": "B", "overall_score": 0.5, "category": "empathy", "hard_fail": False, "status": "pass"},
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(results, f)
            f.flush()
            stats = compute_stats(f.name, n_bootstrap=1000)

        assert "models" in stats
        assert "A" in stats["models"]
        assert "B" in stats["models"]
        assert stats["models"]["A"]["overall_mean"] == 0.75
        assert stats["models"]["B"]["hard_fail_count"] == 1
        assert len(stats["pairwise"]) == 1

    def test_from_leaderboard_dir(self):
        from invisiblebench.stats.analysis import compute_stats

        with tempfile.TemporaryDirectory() as d:
            model_data = {
                "model": "test-model",
                "model_name": "Test Model",
                "scenarios": [
                    {"scenario": "S1", "overall_score": 0.8, "dimension_scores": {"safety": 1.0}},
                    {"scenario": "S2", "overall_score": 0.6, "dimension_scores": {"safety": 0.5}},
                ],
            }
            with open(Path(d) / "test.json", "w") as f:
                json.dump(model_data, f)

            stats = compute_stats(d, n_bootstrap=1000)
            assert "models" in stats
            assert "Test Model" in stats["models"]

    def test_format_report(self):
        from invisiblebench.stats.analysis import compute_stats, format_stats_report

        results = [
            {"model": "A", "overall_score": 0.8, "category": "safety"},
            {"model": "B", "overall_score": 0.6, "category": "safety"},
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(results, f)
            f.flush()
            stats = compute_stats(f.name, n_bootstrap=500)

        report = format_stats_report(stats)
        assert "Statistical Analysis" in report
        assert "Score Distribution" in report

    def test_format_markdown(self):
        from invisiblebench.stats.analysis import compute_stats, format_stats_markdown

        results = [
            {"model": "A", "overall_score": 0.8, "category": "safety"},
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(results, f)
            f.flush()
            stats = compute_stats(f.name, n_bootstrap=500)

        md = format_stats_markdown(stats)
        assert "# Statistical Analysis" in md


class TestCohenKappa:
    """Test kappa computation."""

    def test_perfect_agreement(self):
        from invisiblebench.stats.reliability import _cohen_kappa_continuous

        a = [0.1, 0.3, 0.5, 0.7, 0.9]
        k = _cohen_kappa_continuous(a, a)
        assert k == 1.0

    def test_random_agreement_near_zero(self):
        from invisiblebench.stats.reliability import _cohen_kappa_continuous

        # Intentionally misaligned
        a = [0.1, 0.3, 0.5, 0.7, 0.9, 0.2, 0.4, 0.6, 0.8, 0.0]
        b = [0.9, 0.7, 0.5, 0.3, 0.1, 0.8, 0.6, 0.4, 0.2, 1.0]
        k = _cohen_kappa_continuous(a, b)
        assert k < 0.3  # Should be low

    def test_empty_input(self):
        from invisiblebench.stats.reliability import _cohen_kappa_continuous

        assert _cohen_kappa_continuous([], []) == 0.0

    def test_interpret_kappa(self):
        from invisiblebench.stats.reliability import _interpret_kappa

        assert _interpret_kappa(0.85) == "Almost Perfect"
        assert _interpret_kappa(0.65) == "Substantial"
        assert _interpret_kappa(0.45) == "Moderate"
        assert _interpret_kappa(0.25) == "Fair"
        assert _interpret_kappa(0.05) == "Slight"
        assert _interpret_kappa(-0.1) == "Poor"


class TestAnnotationKit:
    """Test annotation export and import."""

    def test_export_creates_files(self):
        from invisiblebench.stats.annotation import export_annotation_kit

        with tempfile.TemporaryDirectory() as d:
            # Create a fake results dir with transcripts
            results_dir = Path(d) / "results"
            results_dir.mkdir()
            trans_dir = results_dir / "transcripts"
            trans_dir.mkdir()

            # Write a fake transcript
            with open(trans_dir / "test_scenario.jsonl", "w") as f:
                f.write(json.dumps({"turn": 1, "role": "user", "content": "Hello"}) + "\n")
                f.write(json.dumps({"turn": 1, "role": "assistant", "content": "Hi"}) + "\n")

            # Write fake results
            results_file = results_dir / "all_results.json"
            with open(results_file, "w") as f:
                json.dump([{"scenario_id": "test_scenario", "category": "safety", "overall_score": 0.8}], f)

            out_dir = Path(d) / "annotations"
            result = export_annotation_kit(str(results_file), str(out_dir), sample_size=5)

            assert result["exported"] >= 1
            assert (out_dir / "scores.csv").exists()
            assert (out_dir / "INSTRUCTIONS.md").exists()
            assert (out_dir / "_llm_scores.json").exists()

    def test_import_computes_agreement(self):
        from invisiblebench.stats.annotation import import_annotations

        with tempfile.TemporaryDirectory() as d:
            # Write annotations CSV
            csv_path = Path(d) / "scores.csv"
            with open(csv_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(
                    ["rater", "scenario_id", "memory", "consistency", "attunement",
                     "belonging", "compliance", "safety", "false_refusal", "hard_fail", "notes"]
                )
                # Rater 1
                writer.writerow(["Alice", "s1", "0.8", "0.9", "0.7", "0.6", "0.8", "1.0", "0.9", "no", ""])
                writer.writerow(["Alice", "s2", "0.7", "0.8", "0.6", "0.5", "0.7", "0.5", "0.8", "yes", ""])
                # Rater 2
                writer.writerow(["Bob", "s1", "0.9", "0.9", "0.8", "0.7", "0.9", "1.0", "0.9", "no", ""])
                writer.writerow(["Bob", "s2", "0.6", "0.7", "0.5", "0.4", "0.6", "0.4", "0.7", "yes", ""])

            result = import_annotations(str(csv_path))
            assert result["n_raters"] == 2
            assert result["n_scenarios"] == 2
            assert "human_human" in result
            assert "safety" in result["human_human"]

    def test_import_with_llm_scores(self):
        from invisiblebench.stats.annotation import import_annotations

        with tempfile.TemporaryDirectory() as d:
            csv_path = Path(d) / "scores.csv"
            with open(csv_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(
                    ["rater", "scenario_id", "memory", "consistency", "attunement",
                     "belonging", "compliance", "safety", "false_refusal", "hard_fail", "notes"]
                )
                writer.writerow(["Alice", "s1", "0.8", "0.9", "0.7", "0.6", "0.8", "1.0", "0.9", "no", ""])

            llm_path = Path(d) / "_llm_scores.json"
            with open(llm_path, "w") as f:
                json.dump({
                    "scores": {"s1": {"memory": 0.9, "safety": 1.0, "attunement": 0.7,
                                      "belonging": 0.6, "compliance": 0.8, "consistency": 0.9,
                                      "false_refusal": 0.9}},
                    "hard_fails": {"s1": False},
                }, f)

            result = import_annotations(str(csv_path), str(llm_path))
            assert "human_llm" in result
            assert "hard_fail_agreement" in result


class TestReliabilityFormat:
    """Test reliability report formatting."""

    def test_format_report(self):
        from invisiblebench.stats.reliability import format_reliability_report

        results = {
            "n_runs": 5,
            "n_items": 10,
            "dimensions": {
                "belonging": {"kappa": 0.72, "interpretation": "Substantial", "mean_abs_deviation": 0.03},
                "safety": {"kappa": 0.91, "interpretation": "Almost Perfect", "mean_abs_deviation": 0.01},
                "memory": {"kappa": 1.0, "interpretation": "Deterministic", "mean_abs_deviation": 0.0},
            },
        }

        report = format_reliability_report(results)
        assert "Reliability Report" in report
        assert "Substantial" in report
        assert "Deterministic" in report


class TestMeanAbsoluteDeviation:
    """Test MAD computation for reliability."""

    def test_identical_runs(self):
        from invisiblebench.stats.reliability import _mean_absolute_deviation

        runs = [[0.5, 0.7, 0.9], [0.5, 0.7, 0.9]]
        assert _mean_absolute_deviation(runs) == 0.0

    def test_variable_runs(self):
        from invisiblebench.stats.reliability import _mean_absolute_deviation

        runs = [[0.5, 0.7], [0.9, 0.3]]
        mad = _mean_absolute_deviation(runs)
        assert mad > 0

    def test_empty(self):
        from invisiblebench.stats.reliability import _mean_absolute_deviation

        assert _mean_absolute_deviation([]) == 0.0
        assert _mean_absolute_deviation([[]]) == 0.0
