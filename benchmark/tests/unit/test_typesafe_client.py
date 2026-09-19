"""Exercise the real TypeSafe SDK with an offline HTTP transport."""

import json

import httpx2
import pytest

from invisiblebench.api import typesafe
from invisiblebench.api.client import CostBudgetExceededError, CostTracker


@pytest.fixture
def api(monkeypatch):
    requests = []
    answers = {
        "signal": {"type": "noul", "noul": 0.8},
        "check": {
            "type": "choice", "choice": "no_match", "confidence": 0.9,
            "probabilities": {"match": 0.1, "no_match": 0.9},
        },
        "severity": {
            "type": "score", "score": 0.25, "confidence": 0.8,
            "legend": {"0": "Minor", "1": "Severe"},
            "probabilities": {"0": 0.75, "1": 0.25},
        },
    }

    def handle(request):
        requests.append(request)
        names = json.loads(request.content)["questions"]
        return httpx2.Response(200, json={
            "model": typesafe.DEFAULT_JUDGE_MODEL,
            "usage": {"input_tokens": 100, "output_tokens": 0},
            "answers": {key: answers[key] for key in names if key in answers},
        })

    original_init = httpx2.Client.__init__

    def init(self, *args, **kwargs):
        kwargs["transport"] = httpx2.MockTransport(handle)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx2.Client, "__init__", init)
    tracker = CostTracker()
    monkeypatch.setattr(typesafe, "cost_tracker", tracker)
    client = typesafe.SystemOneClient(api_key="offline-test-key")
    yield client, requests, answers, tracker
    client._client.close()


QUESTIONS = {
    "signal": {"type": "noul", "instructions": "Is there a failure?"},
    "check": {
        "type": "choice", "instructions": "Which check fits?",
        "criteria": {"match": "The check fits.", "no_match": "The check does not fit."},
    },
    "severity": {
        "type": "score", "instructions": "How severe is the failure?",
        "criteria": ["Minor", "Severe"],
    },
}


def test_typed_fanout_preserves_answers_and_uses_required_user_agent(api):
    client, requests, _, tracker = api
    result = client.ask_typed(
        model=typesafe.DEFAULT_JUDGE_MODEL, state={"incident": "Authored case"},
        questions=QUESTIONS,
    )
    assert len(requests) == 1
    assert requests[0].headers["user-agent"] == (
        "OpenAI File Downloader, XaiImageApiFetch/1.0"
    )
    assert json.loads(requests[0].content)["questions"] == QUESTIONS
    assert result["answers"]["signal"] == {"type": "noul", "noul": 0.8}
    assert result["answers"]["check"]["choice"] == "no_match"
    assert result["answers"]["severity"]["score"] == 0.25
    assert tracker.calls == 1
    assert tracker.total == typesafe.request_cost(typesafe.DEFAULT_JUDGE_MODEL, 100)


def test_ledger_projection_preserves_implicit_noul_and_choice_probabilities(api):
    client, requests, _, _ = api
    result = client.ask(model=typesafe.DEFAULT_JUDGE_MODEL, state="Authored case", questions={
        "signal": {"instructions": "Is there a failure?"},
        "check": QUESTIONS["check"],
    })
    assert result == {
        "model": typesafe.DEFAULT_JUDGE_MODEL, "input_tokens": 100,
        "nouls": {"signal": 0.8, "check=match": 0.1, "check=no_match": 0.9},
    }
    assert len(requests) == 1


def test_missing_answer_is_billed_and_raises(api):
    client, _, answers, tracker = api
    del answers["signal"]
    with pytest.raises(KeyError):
        client.ask(model=typesafe.DEFAULT_JUDGE_MODEL, state="Authored case",
                   questions={"signal": QUESTIONS["signal"]})
    assert tracker.calls == 1


def test_exhausted_budget_blocks_request(api):
    client, requests, _, tracker = api
    tracker.reset(max_cost_usd=0)
    with pytest.raises(CostBudgetExceededError):
        client.ask_typed(model=typesafe.DEFAULT_JUDGE_MODEL, state="Authored case",
                         questions=QUESTIONS)
    assert requests == []
