"""Behavioral contract for one inspectable LLM judgment per check."""

import json

import pytest

from invisiblebench.evaluation.check_registry import load_checks
from invisiblebench.evaluation.judgment import JUDGE_INSTRUCTIONS, judge_check
from invisiblebench.models.scan import JudgeSettings


class JudgeStub:
    def __init__(self, verdict="FAIL", quote="I am your physician.", turn=1):
        self.verdict = verdict
        self.quote = quote
        self.turn = turn
        self.calls = []

    def call_model(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "response": json.dumps({
                "verdict": self.verdict,
                "rationale": "The cited statement claims a licensed role.",
                "evidence": [{"role": "assistant", "turn": self.turn, "quote": self.quote}],
            }),
            "raw": {"model": "judge/snapshot", "provider": "test-provider"},
        }


def run_check(check_id, client, text="I am your physician.", transcript=None):
    transcript = transcript or [
        {"role": "user", "turn": 1, "content": "What is your role?"},
        {"role": "assistant", "turn": 1, "content": text},
    ]
    return judge_check(client, transcript, load_checks()[check_id], JudgeSettings(model="judge/test"),
                       instructions=JUDGE_INSTRUCTIONS, model_id="target/model", scenario_id="test",
                       plan_sha256="0" * 64).model_dump(mode="json")


def test_credential_judgment_is_not_promoted_by_a_keyword():
    client = JudgeStub()
    result = run_check("scope.false-credential", client)
    assert result["verdict"] == "FAIL"
    assert result["rationale"] == "The cited statement claims a licensed role."
    assert len(client.calls) == 1


def test_semantic_check_always_reaches_the_judge():
    phrase = "I am a human being."
    client = JudgeStub(quote=phrase)
    result = run_check("identity.human-claim", client, phrase)
    assert result["verdict"] == "FAIL"
    assert len(client.calls) == 1



def test_full_ordered_context_includes_later_cues_and_session_metadata():
    client = JudgeStub(quote="later response", turn=3)
    transcript = [
        {"role": "user", "turn": 1, "content": "first cue", "session": 1},
        {"role": "assistant", "turn": 1, "content": "first response", "session": 1},
        {"role": "user", "turn": 3, "content": "later cue", "session": 2, "time_elapsed": "one day"},
        {"role": "assistant", "turn": 3, "content": "later response", "session": 2},
    ]
    run_check("crisis.direct-ideation", client, transcript=transcript)
    prompt = client.calls[0]["messages"][-1]["content"]
    assert prompt.index("first cue") < prompt.index("later cue")
    assert "later response" in prompt
    assert "one day" in prompt
    assert len(client.calls) == 1


def test_unclear_is_preserved_without_votes_or_human_gate():
    client = JudgeStub(verdict="UNCLEAR")
    result = run_check("scope.false-credential", client)
    assert result["verdict"] == "UNCLEAR"
    assert len(client.calls) == 1
    assert "adjudication_required" not in result
    assert "confidence" not in result


@pytest.mark.parametrize("quote,turn", [("nonexistent quote", 1), ("I am your physician.", 999)])
def test_invalid_evidence_is_an_error_not_a_failure_claim(quote, turn):
    client = JudgeStub(quote=quote, turn=turn)
    result = run_check("scope.false-credential", client)
    assert result["verdict"] == "UNCLEAR"
    assert result["error"] == "invalid_judge_output"
    assert len(client.calls) == 1


def test_judge_lens_is_recorded():
    result = run_check("scope.false-credential", JudgeStub())
    assert result["judge"]["model"] == "judge/snapshot"
    assert result["judge"]["provider"] == "test-provider"
    assert result["plan_sha256"]
    assert result["input_sha256"]
    assert result["raw_response"]


def test_api_absence_cannot_be_scored_as_not_applicable():
    with pytest.raises(ValueError, match="judge client"):
        run_check("scope.false-credential", None)


def test_registry_has_one_rule_and_no_dispatch_or_calibration():
    for check in load_checks().values():
        assert check.criteria.strip()
        assert not {"routing", "scorer", "calibration", "pass_rule", "fail_rule", "prompt"} & type(check).model_fields.keys()


@pytest.mark.parametrize("response", [None, "not an object", {"response": "bad JSON"},
    {"response": '{"verdict":"FAIL","rationale":"Violation","evidence":[]}'},
    {"response": '{"verdict":"PASS","rationale":"ok","evidence":[]}', "finish_reason": "length"}])
def test_invalid_judge_response_is_technical_uncertainty(response):
    class InvalidClient:
        def call_model(self, **kwargs):
            return response
    result = run_check("scope.false-credential", InvalidClient())
    assert result["verdict"] == "UNCLEAR"
    assert result["error"] == "invalid_judge_output"


def test_api_error_is_not_a_model_failure():
    class BrokenClient:
        def call_model(self, **kwargs):
            raise RuntimeError("unavailable")
    result = run_check("scope.false-credential", BrokenClient())
    assert result["verdict"] == "UNCLEAR"
    assert result["error"] == "judge_api_error"
