"""Scan requests are validated before dispatch and never truncate evidence."""

import json

import pytest


def test_scan_preflights_later_requests_before_any_dispatch(tmp_path):
    from invisiblebench.judge import execute_requests

    class NeverCalled:
        def ask(self, **kwargs):
            pytest.fail("scan dispatched before validating all requests")

    requests = {
        ("model", "scenario"): {
            ("assistant", 1): {"state": "small", "questions": {}},
            ("assistant", 2): {"state": "x" * 100_000, "questions": {}},
        }
    }
    with pytest.raises(ValueError, match="longest question"):
        with execute_requests(
            tmp_path,
            model="jev-1.13.0",
            plan_sha256="0" * 64,
            requests=requests,
            estimate=0.01,
            max_cost_usd=0.01,
            client=NeverCalled(),
        ):
            pass
    assert not (tmp_path / "answers.jsonl").exists()


def test_oversized_crisis_evidence_is_rejected_not_truncated(published_checks):
    from invisiblebench.evaluation.check_registry import load_checks
    from invisiblebench.evaluation.requests import build_requests

    turns = [
        entry
        for n in range(1, 19)
        for entry in (
            {"role": "user", "turn": n, "content": f"Caregiver {n}: I need help."},
            {"role": "assistant", "turn": n, "content": f"Reply-{n:02d} " + "support " * 2000},
        )
    ]
    frozen = json.dumps(turns, sort_keys=True)
    with pytest.raises(ValueError, match="longest question"):
        build_requests(list(load_checks().values()), turns, "assistant", 18)
    assert json.dumps(turns, sort_keys=True) == frozen
