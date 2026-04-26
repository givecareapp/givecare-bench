"""Tests for LLM verifier parsing robustness."""

from __future__ import annotations

from invisiblebench.evaluation.verifiers.llm_verifier import _parse_verdict_json


def test_parse_verdict_json_ignores_braces_before_json_object() -> None:
    parsed = _parse_verdict_json(
        'Reminder: schema is {verdict}. Final answer:\n'
        '{"eligible": true, "verdict": "PASS", "evidence": [], "rationale_code": "ok", "confidence": 1.0}'
    )

    assert parsed["verdict"] == "PASS"


def test_parse_verdict_json_accepts_fenced_json_with_trailing_text() -> None:
    parsed = _parse_verdict_json(
        '```json\n'
        '{"eligible": true, "verdict": "FAIL", "evidence": [], "rationale_code": "bad", "confidence": 0.8}\n'
        '```\nDone.'
    )

    assert parsed["verdict"] == "FAIL"


def test_parse_verdict_json_repairs_trailing_commas() -> None:
    parsed = _parse_verdict_json(
        '{"eligible": true, "verdict": "NOT_APPLICABLE", "evidence": [], "rationale_code": "none", "confidence": 1.0,}'
    )

    assert parsed["verdict"] == "NOT_APPLICABLE"
