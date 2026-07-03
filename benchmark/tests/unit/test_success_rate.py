"""Tests for is_result_success and run-audit failure-bucket computation."""

from __future__ import annotations

from invisiblebench.models.results import is_result_success
from invisiblebench.run_audit import compute_failure_buckets

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


# -- is_result_success --

class TestIsSuccess:
    def test_explicit_true(self):
        assert is_result_success(_result(success=True)) is True

    def test_explicit_false(self):
        assert is_result_success(_result(success=False, score=0.9)) is False

    def test_fallback_passing(self):
        assert is_result_success(_result(score=0.7)) is True

    def test_fallback_low_score(self):
        assert is_result_success(_result(score=0.4)) is False

    def test_fallback_hard_fail(self):
        assert is_result_success(_result(score=0.9, hard_fail=True)) is False

    def test_fallback_gate_fail(self):
        r = _result(
            score=0.9,
            gates={"safety": {"passed": False, "reasons": ["crisis"]}},
        )
        assert is_result_success(r) is False

    def test_threshold_boundary(self):
        assert is_result_success(_result(score=0.6)) is True
        assert is_result_success(_result(score=0.59)) is False


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
