"""Pin: LLM verifier sources rationale_code from a *winning-verdict* repetition.

Exercises the real ``LLMVerifier.verify`` code path — not a mirror of the
selection expression. The regression this guards: rationale_code used to be
read from ``parsed_results[0]`` regardless of the aggregated verdict, so a
minority PASS repetition could stamp its rationale onto a majority FAIL.

A stubbed API client returns one canned judge response per repetition; the
verifier aggregates them by majority vote and must then source rationale_code
from a repetition whose verdict matches the winner, falling back to any
repetition only when no winning-verdict repetition carries a code.
"""

from __future__ import annotations

import json
from typing import Any

from invisiblebench.evaluation.verifiers.base import Verdict, VerdictResult
from invisiblebench.evaluation.verifiers.llm_verifier import LLMVerifier

# Assistant-turn evidence keeps a FAIL out of the consistency guard's R1
# (fail_without_assistant_evidence) so the verdict under test stays FAIL.
_ASSISTANT_EVIDENCE = [{"role": "assistant", "turn": 1, "quote": "You are just tired."}]


def _response(
    verdict: str,
    rationale: str | None = None,
    *,
    evidence: list[dict[str, Any]] | None = None,
) -> str:
    obj: dict[str, Any] = {"verdict": verdict}
    if rationale is not None:
        obj["rationale_code"] = rationale
    obj["evidence"] = evidence if evidence is not None else []
    return json.dumps(obj)


class _ScriptedClient:
    """Returns one canned judge response per repetition, in order."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls = 0

    def call_model(self, **_kwargs: Any) -> dict[str, str]:
        response = self._responses[self.calls]
        self.calls += 1
        return {"response": response}


def _verify(responses: list[str], *, dimension: str = "crisis") -> VerdictResult:
    verifier = LLMVerifier(_ScriptedClient(responses), model="test-judge")
    return verifier.verify(
        transcript=[{"turn": 1, "role": "assistant", "content": "You are just tired."}],
        scenario={"scenario_id": "s1", "category": "safety"},
        mode_config={
            "id": f"{dimension}.test-check",
            "scope": "universal",
            "severity": "S3",
            "layer": "safety",
            "dimension": dimension,
            "prompt": "Judge one failure mode.",
        },
        routing_config={"repetitions": len(responses)},
    )


def test_rationale_code_sourced_from_winning_fail_not_first_repetition() -> None:
    """[PASS, FAIL, FAIL]: majority is FAIL, so rationale_code must come from a
    FAIL repetition — never the leading PASS (the parsed_results[0] bug)."""
    result = _verify(
        [
            _response("PASS", "criteria_met"),
            _response("FAIL", "missed_direct_ideation", evidence=_ASSISTANT_EVIDENCE),
            _response("FAIL", "missed_signal_two", evidence=_ASSISTANT_EVIDENCE),
        ]
    )

    assert result.verdict is Verdict.FAIL
    assert result.rationale_code in {"missed_direct_ideation", "missed_signal_two"}
    assert result.rationale_code != "criteria_met"


def test_rationale_code_falls_back_to_any_when_winner_has_none() -> None:
    """Winning FAIL repetitions carry no rationale_code → fall back to the only
    repetition that has one (the minority PASS)."""
    result = _verify(
        [
            _response("PASS", "criteria_met"),
            _response("FAIL", None, evidence=_ASSISTANT_EVIDENCE),
            _response("FAIL", None, evidence=_ASSISTANT_EVIDENCE),
        ]
    )

    assert result.verdict is Verdict.FAIL
    assert result.rationale_code == "criteria_met"


def test_rationale_code_none_when_no_repetition_has_one() -> None:
    result = _verify(
        [
            _response("FAIL", None, evidence=_ASSISTANT_EVIDENCE),
            _response("FAIL", None, evidence=_ASSISTANT_EVIDENCE),
        ]
    )

    assert result.verdict is Verdict.FAIL
    assert result.rationale_code is None


def test_rationale_code_single_pass_repetition() -> None:
    result = _verify([_response("PASS", "criteria_met")])

    assert result.verdict is Verdict.PASS
    assert result.rationale_code == "criteria_met"
