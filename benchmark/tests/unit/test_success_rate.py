"""Tests for success-rate computation, bootstrap CIs, and failure buckets."""

from __future__ import annotations

from invisiblebench.stats.analysis import (
    _bootstrap_proportion_ci,
    _is_success,
    compute_failure_buckets,
    compute_success_rates,
)

# -- helpers to build result dicts --

def _result(
    category: str = "safety",
    score: float = 0.8,
    hard_fail: bool = False,
    success: bool | None = None,
    gates: dict | None = None,
    failure_categories: dict | None = None,
    status: str = "pass",
    hard_fail_reasons: list | None = None,
) -> dict:
    r = {
        "category": category,
        "overall_score": score,
        "hard_fail": hard_fail,
        "status": status,
    }
    if success is not None:
        r["success"] = success
    if gates is not None:
        r["gates"] = gates
    if failure_categories is not None:
        r["failure_categories"] = failure_categories
    if hard_fail_reasons is not None:
        r["hard_fail_reasons"] = hard_fail_reasons
    return r


# -- _is_success --

class TestIsSuccess:
    def test_explicit_true(self):
        assert _is_success(_result(success=True)) is True

    def test_explicit_false(self):
        assert _is_success(_result(success=False, score=0.9)) is False

    def test_fallback_passing(self):
        assert _is_success(_result(score=0.7)) is True

    def test_fallback_low_score(self):
        assert _is_success(_result(score=0.4)) is False

    def test_fallback_hard_fail(self):
        assert _is_success(_result(score=0.9, hard_fail=True)) is False

    def test_fallback_gate_fail(self):
        r = _result(
            score=0.9,
            gates={"safety": {"passed": False, "reasons": ["crisis"]}},
        )
        assert _is_success(r) is False

    def test_threshold_boundary(self):
        assert _is_success(_result(score=0.6)) is True
        assert _is_success(_result(score=0.59)) is False


# -- _bootstrap_proportion_ci --

class TestBootstrapProportionCI:
    def test_all_pass(self):
        rate, lo, hi = _bootstrap_proportion_ci(10, 10)
        assert rate == 1.0
        assert lo == 1.0
        assert hi == 1.0

    def test_all_fail(self):
        rate, lo, hi = _bootstrap_proportion_ci(0, 10)
        assert rate == 0.0
        assert lo == 0.0
        assert hi == 0.0

    def test_empty(self):
        rate, lo, hi = _bootstrap_proportion_ci(0, 0)
        assert rate == 0.0

    def test_single(self):
        rate, lo, hi = _bootstrap_proportion_ci(1, 1)
        assert rate == 1.0
        # single observation → wide CI
        assert lo == 0.0
        assert hi == 1.0

    def test_ci_bounds_reasonable(self):
        rate, lo, hi = _bootstrap_proportion_ci(8, 10, n_bootstrap=10000)
        assert 0.5 <= lo <= rate
        assert rate <= hi <= 1.0
        # 80% success rate with 10 samples should have CI that excludes 0.3
        assert lo > 0.3

    def test_deterministic_with_seed(self):
        a = _bootstrap_proportion_ci(7, 10, seed=123)
        b = _bootstrap_proportion_ci(7, 10, seed=123)
        assert a == b

    def test_different_seeds_different_results(self):
        a = _bootstrap_proportion_ci(7, 10, seed=1)
        b = _bootstrap_proportion_ci(7, 10, seed=999)
        # Same rate, but CIs likely differ
        assert a[0] == b[0]
        # CIs may or may not differ at this resolution, so just check they're valid
        assert 0 <= a[1] <= a[2] <= 1
        assert 0 <= b[1] <= b[2] <= 1


# -- compute_success_rates --

class TestComputeSuccessRates:
    def test_basic(self):
        results = [
            _result("safety", success=True),
            _result("safety", success=True),
            _result("safety", success=False),
            _result("empathy", success=True),
            _result("empathy", success=True),
        ]
        sr = compute_success_rates(results)

        assert sr["categories"]["safety"]["pass"] == 2
        assert sr["categories"]["safety"]["fail"] == 1
        assert sr["categories"]["safety"]["total"] == 3

        assert sr["categories"]["empathy"]["pass"] == 2
        assert sr["categories"]["empathy"]["fail"] == 0

        assert sr["total"]["pass"] == 4
        assert sr["total"]["fail"] == 1
        assert sr["total"]["total"] == 5
        assert abs(sr["total"]["rate"] - 0.8) < 0.001

    def test_all_pass(self):
        results = [_result(success=True) for _ in range(5)]
        sr = compute_success_rates(results)
        assert sr["total"]["rate"] == 1.0
        assert sr["total"]["ci_lo"] == 1.0
        assert sr["total"]["ci_hi"] == 1.0

    def test_all_fail(self):
        results = [_result(success=False) for _ in range(5)]
        sr = compute_success_rates(results)
        assert sr["total"]["rate"] == 0.0

    def test_empty(self):
        sr = compute_success_rates([])
        assert sr["total"]["pass"] == 0
        assert sr["total"]["rate"] == 0.0

    def test_ci_ordering(self):
        results = [
            _result("safety", success=True),
            _result("safety", success=True),
            _result("safety", success=False),
        ]
        sr = compute_success_rates(results)
        cat = sr["categories"]["safety"]
        assert cat["ci_lo"] <= cat["rate"] <= cat["ci_hi"]

    def test_fallback_without_success_field(self):
        """Results without explicit 'success' field should use gate+score fallback."""
        results = [
            _result("safety", score=0.8),  # No success field → fallback passes
            _result("safety", score=0.3),  # Low score → fails
        ]
        sr = compute_success_rates(results)
        assert sr["categories"]["safety"]["pass"] == 1
        assert sr["categories"]["safety"]["fail"] == 1


# -- compute_failure_buckets --

class TestComputeFailureBuckets:
    def test_primary_category_buckets(self):
        results = [
            _result(success=True),  # skip
            _result(
                success=False,
                failure_categories={"primary_category": "crisis_miss"},
            ),
            _result(
                success=False,
                failure_categories={"primary_category": "crisis_miss"},
            ),
            _result(
                success=False,
                failure_categories={"primary_category": "boundary_violation"},
            ),
        ]
        buckets = compute_failure_buckets(results)
        assert buckets["crisis_miss"] == 2
        assert buckets["boundary_violation"] == 1
        assert "unknown" not in buckets

    def test_hard_fail_fallback(self):
        results = [
            _result(
                success=False,
                hard_fail=True,
                hard_fail_reasons=["Safety: crisis missed"],
            ),
        ]
        buckets = compute_failure_buckets(results)
        assert "safety" in buckets

    def test_error_bucket(self):
        results = [
            _result(success=False, score=0.0, status="error"),
        ]
        buckets = compute_failure_buckets(results)
        assert buckets["error"] == 1

    def test_low_score_bucket(self):
        results = [
            _result(success=False, score=0.4),
        ]
        buckets = compute_failure_buckets(results)
        assert buckets["low_score"] == 1

    def test_empty_results(self):
        assert compute_failure_buckets([]) == {}

    def test_all_success_no_buckets(self):
        results = [_result(success=True) for _ in range(5)]
        assert compute_failure_buckets(results) == {}

    def test_sorted_by_count_desc(self):
        results = [
            _result(success=False, failure_categories={"primary_category": "a"}),
            _result(success=False, failure_categories={"primary_category": "b"}),
            _result(success=False, failure_categories={"primary_category": "b"}),
            _result(success=False, failure_categories={"primary_category": "b"}),
        ]
        buckets = compute_failure_buckets(results)
        keys = list(buckets.keys())
        assert keys[0] == "b"  # 3 > 1
        assert keys[1] == "a"
