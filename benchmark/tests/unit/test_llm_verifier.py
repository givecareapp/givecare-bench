"""Tests for LLM verifier parsing robustness."""

from __future__ import annotations

from invisiblebench.evaluation.verifiers.base import Verdict
from invisiblebench.evaluation.verifiers.llm_verifier import LLMVerifier, _parse_verdict_json


class FakeClient:
    def __init__(self, verdict: str = "PASS") -> None:
        self.verdict = verdict
        self.calls = 0

    def call_model(self, **kwargs):
        self.calls += 1
        return {
            "response": (
                '{"eligible": true, '
                f'"verdict": "{self.verdict}", '
                '"evidence": [], '
                '"rationale_code": "ok", '
                '"confidence": 1.0}'
            )
        }


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


def test_llm_verifier_adaptive_repetitions_stop_after_clear_pass(tmp_path) -> None:
    (tmp_path / "prompt.txt").write_text("Judge one thing.", encoding="utf-8")
    client = FakeClient("PASS")
    verifier = LLMVerifier(client, prompt_dir=tmp_path)

    result = verifier.verify(
        transcript=[{"turn": 1, "role": "assistant", "content": "I can help."}],
        scenario={"scenario_id": "s1"},
        mode_config={
            "id": "IB-X",
            "scope": "universal",
            "severity": "S2",
            "primary_bucket": "C",
            "scorer": {"verifier_prompt": "prompt.txt"},
        },
        routing_config={"repetitions": 3, "adaptive_repetitions": True},
    )

    assert result.verdict is Verdict.PASS
    assert client.calls == 1
    assert result.extra["repetitions"] == 1
    assert result.extra["planned_repetitions"] == 3
