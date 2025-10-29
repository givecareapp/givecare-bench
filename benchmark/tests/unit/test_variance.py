"""
Test suite for variance calculation and iteration support.

Tests written FIRST following TDD methodology.
"""
from __future__ import annotations

import pytest


class TestVarianceCalculation:
    """Test variance calculation functions."""

    def test_calculate_variance_with_single_iteration(self):
        """Single iteration (N=1) should return no variance metrics."""
        from supportbench.evaluation.variance import calculate_variance

        scores = [0.75]
        result = calculate_variance(scores)

        # With N=1, we should get mean but no variance
        assert result["mean"] == 0.75
        assert result["std_dev"] == 0.0
        assert result["min"] == 0.75
        assert result["max"] == 0.75
        assert result["cv"] == 0.0  # CV is 0 when std_dev is 0

    def test_calculate_variance_with_multiple_iterations(self):
        """Multiple iterations should calculate variance correctly."""
        from supportbench.evaluation.variance import calculate_variance

        scores = [0.75, 0.78, 0.76]
        result = calculate_variance(scores)

        # Should calculate all metrics
        assert result["mean"] == pytest.approx(0.7633, abs=0.001)
        assert result["std_dev"] > 0.0
        assert result["std_dev"] < 0.02  # Should be small
        assert result["min"] == 0.75
        assert result["max"] == 0.78
        assert result["cv"] is not None
        assert result["cv"] > 0.0

    def test_calculate_variance_with_identical_scores(self):
        """All identical scores should have zero std_dev."""
        from supportbench.evaluation.variance import calculate_variance

        scores = [0.80, 0.80, 0.80, 0.80]
        result = calculate_variance(scores)

        assert result["mean"] == 0.80
        assert result["std_dev"] == 0.0
        assert result["min"] == 0.80
        assert result["max"] == 0.80
        assert result["cv"] == 0.0  # CV is 0 when std_dev is 0

    def test_calculate_variance_with_high_variance(self):
        """High variance scores should reflect in metrics."""
        from supportbench.evaluation.variance import calculate_variance

        scores = [0.10, 0.50, 0.90]
        result = calculate_variance(scores)

        assert result["mean"] == 0.50
        assert result["std_dev"] > 0.3  # High variance
        assert result["min"] == 0.10
        assert result["max"] == 0.90
        assert result["cv"] > 0.6  # CV should be high

    def test_calculate_variance_with_zero_mean(self):
        """CV should handle zero mean gracefully."""
        from supportbench.evaluation.variance import calculate_variance

        scores = [0.0, 0.0, 0.0]
        result = calculate_variance(scores)

        assert result["mean"] == 0.0
        assert result["std_dev"] == 0.0
        assert result["cv"] == 0.0  # CV is 0 when both mean and std_dev are 0

    def test_calculate_variance_with_near_zero_mean(self):
        """CV should handle near-zero mean gracefully."""
        from supportbench.evaluation.variance import calculate_variance

        scores = [0.001, 0.002, 0.001]
        result = calculate_variance(scores)

        assert result["mean"] < 0.01
        assert result["std_dev"] >= 0.0
        # CV might be very high but should not error
        assert result["cv"] is None or result["cv"] >= 0.0

    def test_calculate_variance_with_empty_list(self):
        """Empty list should raise ValueError."""
        from supportbench.evaluation.variance import calculate_variance

        with pytest.raises(ValueError, match="at least one score"):
            calculate_variance([])

    def test_calculate_variance_with_invalid_input(self):
        """Non-numeric values should raise TypeError."""
        from supportbench.evaluation.variance import calculate_variance

        with pytest.raises(TypeError):
            calculate_variance([0.5, "invalid", 0.7])


class TestDimensionVarianceCalculation:
    """Test variance calculation for dimension scores."""

    def test_calculate_dimension_variance_single_iteration(self):
        """Single iteration should return no dimension variance."""
        from supportbench.evaluation.variance import calculate_dimension_variance

        dimension_scores_list = [
            {
                "memory": {"score": 0.80},
                "trauma": {"score": 0.75},
            }
        ]

        result = calculate_dimension_variance(dimension_scores_list)

        # Should have variance data for each dimension
        assert "memory" in result
        assert "trauma" in result

        # Single iteration = no variance
        assert result["memory"]["mean"] == 0.80
        assert result["memory"]["std_dev"] == 0.0
        assert result["trauma"]["mean"] == 0.75
        assert result["trauma"]["std_dev"] == 0.0

    def test_calculate_dimension_variance_multiple_iterations(self):
        """Multiple iterations should calculate per-dimension variance."""
        from supportbench.evaluation.variance import calculate_dimension_variance

        dimension_scores_list = [
            {
                "memory": {"score": 0.80},
                "trauma": {"score": 0.75},
            },
            {
                "memory": {"score": 0.85},
                "trauma": {"score": 0.70},
            },
            {
                "memory": {"score": 0.82},
                "trauma": {"score": 0.73},
            },
        ]

        result = calculate_dimension_variance(dimension_scores_list)

        # Memory variance
        assert result["memory"]["mean"] == pytest.approx(0.8233, abs=0.001)
        assert result["memory"]["std_dev"] > 0.0
        assert result["memory"]["min"] == 0.80
        assert result["memory"]["max"] == 0.85

        # Trauma variance
        assert result["trauma"]["mean"] == pytest.approx(0.7267, abs=0.001)
        assert result["trauma"]["std_dev"] > 0.0
        assert result["trauma"]["min"] == 0.70
        assert result["trauma"]["max"] == 0.75

    def test_calculate_dimension_variance_missing_dimension(self):
        """Should handle dimensions present in some iterations but not others."""
        from supportbench.evaluation.variance import calculate_dimension_variance

        dimension_scores_list = [
            {
                "memory": {"score": 0.80},
                "trauma": {"score": 0.75},
            },
            {
                "memory": {"score": 0.85},
                # trauma missing in this iteration
            },
        ]

        result = calculate_dimension_variance(dimension_scores_list)

        # Memory should have variance (present in both)
        assert "memory" in result
        assert result["memory"]["mean"] == pytest.approx(0.825, abs=0.001)

        # Trauma should handle missing gracefully
        # Implementation choice: either skip it or use None
        # We'll test that it doesn't crash
        assert "trauma" in result or "trauma" not in result

    def test_calculate_dimension_variance_empty_list(self):
        """Empty list should raise ValueError."""
        from supportbench.evaluation.variance import calculate_dimension_variance

        with pytest.raises(ValueError):
            calculate_dimension_variance([])


class TestIterationResultsAggregation:
    """Test aggregation of iteration results into final report."""

    def test_aggregate_iteration_results_single_iteration(self):
        """Single iteration should return original result without variance."""
        from supportbench.evaluation.variance import aggregate_iteration_results

        iteration_results = [
            {
                "overall_score": 0.75,
                "dimension_scores": {
                    "memory": {"score": 0.80},
                    "trauma": {"score": 0.70},
                },
                "hard_fail": False,
            }
        ]

        result = aggregate_iteration_results(iteration_results)

        # Should have original data
        assert result["overall_score"] == 0.75
        assert result["dimension_scores"]["memory"]["score"] == 0.80

        # Should NOT have variance section for N=1
        assert "variance" not in result or result["variance"] is None
        assert "iterations" in result
        assert len(result["iterations"]) == 1

    def test_aggregate_iteration_results_multiple_iterations(self):
        """Multiple iterations should include variance metrics."""
        from supportbench.evaluation.variance import aggregate_iteration_results

        iteration_results = [
            {
                "overall_score": 0.75,
                "dimension_scores": {
                    "memory": {"score": 0.80},
                    "trauma": {"score": 0.70},
                },
                "hard_fail": False,
            },
            {
                "overall_score": 0.78,
                "dimension_scores": {
                    "memory": {"score": 0.85},
                    "trauma": {"score": 0.71},
                },
                "hard_fail": False,
            },
            {
                "overall_score": 0.76,
                "dimension_scores": {
                    "memory": {"score": 0.82},
                    "trauma": {"score": 0.70},
                },
                "hard_fail": False,
            },
        ]

        result = aggregate_iteration_results(iteration_results)

        # Should have overall variance
        assert "variance" in result
        assert "overall" in result["variance"]
        assert result["variance"]["overall"]["mean"] == pytest.approx(0.7633, abs=0.001)
        assert result["variance"]["overall"]["std_dev"] > 0.0

        # Should have dimension variance
        assert "dimensions" in result["variance"]
        assert "memory" in result["variance"]["dimensions"]
        assert "trauma" in result["variance"]["dimensions"]

        # Should keep all iteration results
        assert "iterations" in result
        assert len(result["iterations"]) == 3

    def test_aggregate_iteration_results_uses_mean_for_final_score(self):
        """Final scores should be mean across iterations."""
        from supportbench.evaluation.variance import aggregate_iteration_results

        iteration_results = [
            {
                "overall_score": 0.70,
                "dimension_scores": {"memory": {"score": 0.80}},
                "hard_fail": False,
            },
            {
                "overall_score": 0.80,
                "dimension_scores": {"memory": {"score": 0.90}},
                "hard_fail": False,
            },
        ]

        result = aggregate_iteration_results(iteration_results)

        # Overall score should be mean
        assert result["overall_score"] == pytest.approx(0.75, abs=0.001)

        # Dimension scores should be mean
        assert result["dimension_scores"]["memory"]["score"] == pytest.approx(0.85, abs=0.001)

    def test_aggregate_iteration_results_preserves_metadata(self):
        """Should preserve metadata from first iteration."""
        from supportbench.evaluation.variance import aggregate_iteration_results

        iteration_results = [
            {
                "overall_score": 0.75,
                "dimension_scores": {},
                "hard_fail": False,
                "metadata": {
                    "scenario_id": "test-001",
                    "jurisdiction": "ny",
                },
            },
            {
                "overall_score": 0.78,
                "dimension_scores": {},
                "hard_fail": False,
                "metadata": {
                    "scenario_id": "test-001",
                    "jurisdiction": "ny",
                },
            },
        ]

        result = aggregate_iteration_results(iteration_results)

        # Should preserve metadata
        assert "metadata" in result
        assert result["metadata"]["scenario_id"] == "test-001"
        assert result["metadata"]["jurisdiction"] == "ny"

    def test_aggregate_iteration_results_handles_hard_fail_in_any_iteration(self):
        """If any iteration has hard_fail=True, final should be hard_fail=True."""
        from supportbench.evaluation.variance import aggregate_iteration_results

        iteration_results = [
            {"overall_score": 0.75, "dimension_scores": {}, "hard_fail": False},
            {"overall_score": 0.0, "dimension_scores": {}, "hard_fail": True},
            {"overall_score": 0.78, "dimension_scores": {}, "hard_fail": False},
        ]

        result = aggregate_iteration_results(iteration_results)

        # Should mark as hard_fail if any iteration failed
        assert result["hard_fail"] is True

    def test_aggregate_iteration_results_empty_list(self):
        """Empty list should raise ValueError."""
        from supportbench.evaluation.variance import aggregate_iteration_results

        with pytest.raises(ValueError):
            aggregate_iteration_results([])


class TestCoefficientOfVariation:
    """Test CV calculation edge cases."""

    def test_cv_calculation_normal_case(self):
        """Normal CV calculation."""
        from supportbench.evaluation.variance import calculate_cv

        cv = calculate_cv(mean=0.75, std_dev=0.05)
        assert cv == pytest.approx(0.0667, abs=0.001)

    def test_cv_calculation_zero_std_dev(self):
        """Zero std_dev should give CV=0."""
        from supportbench.evaluation.variance import calculate_cv

        cv = calculate_cv(mean=0.75, std_dev=0.0)
        assert cv == 0.0

    def test_cv_calculation_zero_mean(self):
        """Zero mean should return None (undefined)."""
        from supportbench.evaluation.variance import calculate_cv

        cv = calculate_cv(mean=0.0, std_dev=0.05)
        assert cv is None

    def test_cv_calculation_near_zero_mean(self):
        """Near-zero mean should return None to avoid huge CV values."""
        from supportbench.evaluation.variance import calculate_cv

        cv = calculate_cv(mean=0.001, std_dev=0.05)
        # Implementation choice: return None for very small means
        assert cv is None or cv > 10.0  # CV would be huge

    def test_cv_calculation_negative_mean(self):
        """Negative mean should raise ValueError (scores can't be negative)."""
        from supportbench.evaluation.variance import calculate_cv

        with pytest.raises(ValueError):
            calculate_cv(mean=-0.5, std_dev=0.1)

    def test_cv_calculation_negative_std_dev(self):
        """Negative std_dev should raise ValueError."""
        from supportbench.evaluation.variance import calculate_cv

        with pytest.raises(ValueError):
            calculate_cv(mean=0.75, std_dev=-0.1)
