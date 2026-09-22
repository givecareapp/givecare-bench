"""Use the real SDK over an offline HTTP transport."""

import json

import httpx2
import pytest
from typesafe_sdk import ChoiceAnswer, NoulAnswer, SystemOneResponse

from invisiblebench.api import typesafe
from invisiblebench.api.client import CostBudgetExceededError, CostTracker


@pytest.fixture
def api(monkeypatch):
    requests = []
    answers = {
        "signal": {"type": "noul", "noul": 0.8},
        "check": {
            "type": "choice",
            "choice": "no_match",
            "confidence": 0.9,
            "probabilities": {"match": 0.1, "no_match": 0.9},
        },
    }

    def handle(request):
        requests.append(request)
        names = json.loads(request.content)["questions"]
        return httpx2.Response(
            200,
            json={
                "model": typesafe.DEFAULT_JUDGE_MODEL,
                "usage": {"input_tokens": 100, "output_tokens": 0},
                "answers": {key: answers[key] for key in names if key in answers},
            },
        )

    tracker = CostTracker()
    monkeypatch.setattr(typesafe, "cost_tracker", tracker)
    with httpx2.Client(transport=httpx2.MockTransport(handle)) as transport:
        with typesafe.SystemOneClient(api_key="offline-test-key", http_client=transport) as client:
            yield client, requests, answers, tracker


QUESTIONS = {
    "signal": {"type": "noul", "instructions": "Is there a failure?"},
    "check": {
        "type": "choice",
        "instructions": "Which check fits?",
        "criteria": {"match": "The check fits.", "no_match": "The check does not fit."},
    },
}


def test_native_answers_survive_the_transport(api):
    client, requests, _, tracker = api
    result = client.ask(
        model=typesafe.DEFAULT_JUDGE_MODEL, state="Authored case", questions=QUESTIONS
    )
    assert isinstance(result, SystemOneResponse)
    assert isinstance(result.answers["signal"], NoulAnswer)
    assert isinstance(result.answers["check"], ChoiceAnswer)
    assert result.answers["check"].probabilities == {"match": 0.1, "no_match": 0.9}
    assert len(requests) == 1
    assert requests[0].headers["user-agent"] == "OpenAI File Downloader, XaiImageApiFetch/1.0"
    assert json.loads(requests[0].content)["questions"] == QUESTIONS
    assert tracker.calls == 1
    assert tracker.total == typesafe.request_cost(typesafe.DEFAULT_JUDGE_MODEL, 100)


@pytest.mark.parametrize(
    "values", [{"match": 0.0, "no_match": 0.0}, {"match": 0.5}, {"match": -0.1, "no_match": 1.1}]
)
def test_invalid_choice_is_billed_and_rejected(api, values):
    client, _, answers, tracker = api
    answers["check"]["probabilities"] = values
    with pytest.raises(ValueError):
        client.ask(model=typesafe.DEFAULT_JUDGE_MODEL, state="Authored case", questions=QUESTIONS)
    assert tracker.calls == 1


def test_missing_answer_is_billed_and_rejected(api):
    client, _, answers, tracker = api
    del answers["signal"]
    with pytest.raises(ValueError):
        client.ask(model=typesafe.DEFAULT_JUDGE_MODEL, state="Authored case", questions=QUESTIONS)
    assert tracker.calls == 1


def test_exhausted_budget_blocks_request(api):
    client, requests, _, tracker = api
    tracker.reset(max_cost_usd=0)
    with pytest.raises(CostBudgetExceededError):
        client.ask(model=typesafe.DEFAULT_JUDGE_MODEL, state="Authored case", questions=QUESTIONS)
    assert requests == []


@pytest.mark.parametrize(
    "probabilities", [{"match": 0.09, "no_match": 0.9}, {"match": 0.11, "no_match": 0.9}]
)
def test_rounded_distribution_is_preserved_not_renormalized(api, probabilities):
    client, _, answers, _ = api
    answers["check"]["probabilities"] = probabilities
    response = client.ask(model=typesafe.DEFAULT_JUDGE_MODEL, state="case", questions=QUESTIONS)
    assert response.answers["check"].probabilities == probabilities


def test_selected_choice_must_be_a_most_likely_option(api):
    client, _, answers, _ = api
    answers["check"]["choice"] = "match"
    with pytest.raises(ValueError, match="largest probability"):
        client.ask(model=typesafe.DEFAULT_JUDGE_MODEL, state="case", questions=QUESTIONS)
