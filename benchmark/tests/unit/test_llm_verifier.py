"""Tests for LLM verifier parsing robustness."""

from __future__ import annotations

from invisiblebench.evaluation.verifiers.base import Verdict
from invisiblebench.evaluation.verifiers.llm_verifier import LLMVerifier, _parse_verdict_json


class FakeClient:
    def __init__(self, verdict: str = "PASS", verdicts: list[str] | None = None) -> None:
        self.verdict = verdict
        self.verdicts = list(verdicts or [])
        self.calls = 0

    def call_model(self, **kwargs):
        verdict = self.verdicts.pop(0) if self.verdicts else self.verdict
        self.calls += 1
        return {
            "response": (
                '{"eligible": true, '
                f'"verdict": "{verdict}", '
                f'"evidence": [{{"role": "assistant", "turn": 1, "quote": "{verdict.lower()}"}}], '
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
            "id": "attunement.test-check",
            "scope": "universal",
            "severity": "S2",
            "layer": "care",
            "dimension": "attunement",
            "scorer": {"verifier_prompt": "prompt.txt"},
        },
        routing_config={"repetitions": 3, "adaptive_repetitions": True},
    )

    assert result.verdict is Verdict.PASS
    assert client.calls == 1
    assert result.extra["repetitions"] == 1
    assert result.extra["planned_repetitions"] == 3


def test_llm_verifier_tiebreak_repetitions_resolve_split_vote(tmp_path) -> None:
    (tmp_path / "prompt.txt").write_text("Judge one thing.", encoding="utf-8")
    client = FakeClient(verdicts=["PASS", "FAIL", "NOT_APPLICABLE", "PASS", "PASS"])
    verifier = LLMVerifier(client, prompt_dir=tmp_path)

    result = verifier.verify(
        transcript=[{"turn": 1, "role": "assistant", "content": "I can help."}],
        scenario={"scenario_id": "s1"},
        mode_config={
            "id": "attunement.test-check",
            "scope": "universal",
            "severity": "S2",
            "layer": "care",
            "dimension": "attunement",
            "scorer": {"verifier_prompt": "prompt.txt"},
        },
        routing_config={"repetitions": 3, "unclear_tiebreak_repetitions": 2},
    )

    assert result.verdict is Verdict.PASS
    assert client.calls == 5
    assert result.confidence == 0.6
    assert result.extra["repetitions"] == 5
    assert result.extra["planned_repetitions"] == 3
    assert result.extra["tiebreak_repetitions"] == 2
    assert result.extra["all_verdicts"] == [
        "PASS",
        "FAIL",
        "NOT_APPLICABLE",
        "PASS",
        "PASS",
    ]


def test_llm_verifier_automated_adjudication_resolves_after_tiebreak(tmp_path) -> None:
    (tmp_path / "prompt.txt").write_text("Judge one thing.", encoding="utf-8")
    client = FakeClient(
        verdicts=[
            "PASS",
            "FAIL",
            "NOT_APPLICABLE",
            "PASS",
            "FAIL",
            "FAIL",
            "FAIL",
            "PASS",
        ]
    )
    verifier = LLMVerifier(client, prompt_dir=tmp_path)

    result = verifier.verify(
        transcript=[{"turn": 1, "role": "assistant", "content": "I can help."}],
        scenario={"scenario_id": "s1"},
        mode_config={
            "id": "attunement.test-check",
            "scope": "universal",
            "severity": "S2",
            "layer": "care",
            "dimension": "attunement",
            "scorer": {"verifier_prompt": "prompt.txt"},
        },
        routing_config={
            "repetitions": 3,
            "unclear_tiebreak_repetitions": 2,
            "unclear_adjudication_repetitions": 3,
        },
    )

    assert result.verdict is Verdict.FAIL
    assert client.calls == 8
    assert result.confidence == 2 / 3
    assert result.extra["repetitions"] == 5
    assert result.extra["tiebreak_repetitions"] == 2
    assert result.extra["all_verdicts"] == [
        "PASS",
        "FAIL",
        "NOT_APPLICABLE",
        "PASS",
        "FAIL",
    ]
    assert result.extra["automated_adjudication"] == {
        "repetitions": 3,
        "all_verdicts": ["FAIL", "FAIL", "PASS"],
        "resolved": True,
    }
