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
