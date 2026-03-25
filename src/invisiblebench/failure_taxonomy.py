"""Quality vs reliability classification helpers for benchmark results."""
from __future__ import annotations

from typing import Any, Dict, List

SUCCESS_THRESHOLD = 0.6


def result_counts_as_quality_pass(result: Dict[str, Any], threshold: float = SUCCESS_THRESHOLD) -> bool:
    """Return True when a scenario counts as a benchmark quality pass."""
    success = result.get("success")
    if isinstance(success, bool):
        return success

    if result.get("status") == "error":
        return False
    if result.get("hard_fail"):
        return False

    gates = result.get("gates") or {}
    for gate in gates.values():
        if isinstance(gate, dict) and not gate.get("passed", True):
            return False

    score = result.get("overall_score", 0.0)
    return isinstance(score, (int, float)) and float(score) >= threshold


def classify_reliability_issue(result: Dict[str, Any]) -> str | None:
    """Classify operational reliability failures for a scenario row."""
    if result.get("status") != "error":
        return None

    reason_text = " | ".join(str(x) for x in result.get("hard_fail_reasons", []))
    if not reason_text and result.get("error"):
        reason_text = str(result.get("error"))
    lower = reason_text.lower()

    if "transcript generation failed" in lower:
        return "transcript_generation"
    if "scoring failed" in lower:
        return "scoring"
    if "no runs completed" in lower:
        return "execution"
    if "unexpected scenario run failure" in lower:
        return "execution"
    if "no response" in lower or "empty response" in lower:
        return "no_response"
    if "credit" in lower:
        return "credits"
    if any(token in lower for token in ["timeout", "timed out"]):
        return "timeout"
    if any(token in lower for token in ["convex", "playground", "gc cli", "simulate"]):
        return "provider_runtime"
    return "runtime"


def compute_quality_summary(
    results: List[Dict[str, Any]], threshold: float = SUCCESS_THRESHOLD
) -> Dict[str, Any]:
    """Compute benchmark quality summary separate from reliability errors."""
    total = len(results)
    passes = sum(1 for r in results if result_counts_as_quality_pass(r, threshold=threshold))
    fails = total - passes
    return {
        "total": total,
        "pass": passes,
        "fail": fails,
        "pass_rate": passes / total if total else 0.0,
        "threshold": threshold,
    }


def compute_reliability_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute operational reliability summary for a result set."""
    total = len(results)
    error_results = [r for r in results if r.get("status") == "error"]
    buckets: Dict[str, int] = {}
    for result in error_results:
        bucket = classify_reliability_issue(result) or "runtime"
        buckets[bucket] = buckets.get(bucket, 0) + 1

    return {
        "total": total,
        "ok": total - len(error_results),
        "error": len(error_results),
        "error_rate": len(error_results) / total if total else 0.0,
        "buckets": buckets,
    }
