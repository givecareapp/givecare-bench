"""A scheduled assistant delivery is context, not an invented caregiver request."""

import pytest

from invisiblebench.evaluation.check_registry import load_checks
from invisiblebench.evaluation.requests import conversation_requests

DIALOGUE = [
    {"role": "assistant", "turn": 1, "content": "Checking in as you asked."},
    {"role": "user", "turn": 2, "content": "I am exhausted. I could use a little support."},
    {"role": "assistant", "turn": 2, "content": "That sounds like a hard day."},
]


def test_reply_window_questions_only_read_the_caregiver_they_answer(published_checks):
    check = load_checks()["attunement.advice-first"]
    requests = conversation_requests([check], DIALOGUE)
    assert not any(role == "assistant" and turn == 1 for role, turn, _ in requests)
    assert any(role == "assistant" and turn == 2 for role, turn, _ in requests)
    for (role, _turn, _), request in requests.items():
        if role == "assistant" and "caregiver" in request["state"]:
            assert request["state"]["caregiver"] == DIALOGUE[1]["content"]


def test_missing_evidence_still_blocks_a_check_that_can_apply_later(published_checks):
    check = load_checks()["attunement.advice-first"].model_copy(update={"window": "after"})
    with pytest.raises(ValueError, match="unavailable evidence fields"):
        conversation_requests([check], DIALOGUE)


def test_cue_free_check_reading_caregiver_skips_scheduled_delivery(published_checks):
    """A check that reads `caregiver` judges replies, never an unpaired delivery."""
    for check_id in ("attunement.clinical-openers", "belonging.othering"):
        check = load_checks()[check_id]
        requests = conversation_requests([check], DIALOGUE)
        assert not any(role == "assistant" and turn == 1 for role, turn, _ in requests)
        assert any(role == "assistant" and turn == 2 for role, turn, _ in requests)


def test_scheduled_delivery_is_outside_a_cue_free_reply_check(published_checks):
    from typesafe_sdk import NoulAnswer

    from invisiblebench.evaluation.rules import derive
    from invisiblebench.models.scan import Thresholds

    check = load_checks()["belonging.othering"]
    answers = {}
    for (role, turn, _), request in conversation_requests([check], DIALOGUE).items():
        for key in request["questions"]:
            answers.setdefault((role, turn), {})[key] = NoulAnswer(type="noul", noul=0.01)
    judgment = derive(
        check, DIALOGUE, answers, Thresholds(), model_id="m", scenario_id="s", plan_sha256="0" * 64
    )
    assert judgment.verdict.value == "PASS"
    assert judgment.answers and all(key.startswith("assistant:2/") for key in judgment.answers)
