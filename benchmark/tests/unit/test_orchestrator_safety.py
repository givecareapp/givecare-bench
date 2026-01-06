from __future__ import annotations

from invisiblebench.evaluation.orchestrator import _safety_hard_fail_reasons


def test_safety_critical_failure_on_missed_crisis_hard_fails() -> None:
    safety_result = {
        "score": 0.0,
        "crisis_detected": False,
        "critical_failure": True,
        "breakdown": {},
    }

    reasons = _safety_hard_fail_reasons(safety_result)

    assert "Critical safety failure" in reasons
