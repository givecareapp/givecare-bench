"""TypeSafe transport and the request/answer contract shared by every judge caller."""

from __future__ import annotations

import math
import os
from typing import Any

import httpx2
from typesafe_sdk import (
    Answer,
    ChoiceAnswer,
    NoulAnswer,
    ScoreAnswer,
    SystemOneResponse,
    TypeSafeClient,
)

from invisiblebench.api.client import cost_tracker

DEFAULT_JUDGE_MODEL = "jev-1.13.0"
JUDGE_PRICE_PER_MTOK_INPUT = 0.042
JUDGE_PRICING: dict[str, float] = {DEFAULT_JUDGE_MODEL: JUDGE_PRICE_PER_MTOK_INPUT}
ESTIMATED_BYTES_PER_TOKEN = 3
API_KEY_ENV = "TYPESAFE_API_KEY"
USER_AGENT = "OpenAI File Downloader, XaiImageApiFetch/1.0"


def estimated_cost(model: str, request_bytes: int) -> float | None:
    price = JUDGE_PRICING.get(model)
    return None if price is None else request_bytes / ESTIMATED_BYTES_PER_TOKEN / 1_000_000 * price


def request_cost(model: str, input_tokens: int) -> float:
    if model not in JUDGE_PRICING:
        raise ValueError(f"no pricing is known for judge model: {model}")
    return input_tokens / 1_000_000 * JUDGE_PRICING[model]


def validate_answers(answers: dict[str, Answer], questions: dict[str, Any]) -> None:
    """Validate both live responses and retained records against their frozen questions."""
    if set(answers) != set(questions):
        raise ValueError("judge answered a different set of questions")
    for key, spec in questions.items():
        answer = answers[key]
        if answer.type != spec.get("type", "noul"):
            raise ValueError(f"{key}: answer type differs from its question")
        if isinstance(answer, NoulAnswer):
            values = [answer.noul]
        else:
            options = spec["criteria"]
            expected = set(options) if isinstance(options, dict) else set(range(len(options)))
            if set(answer.probabilities) != expected:
                raise ValueError(f"{key}: answer options differ from its question")
            values = [*answer.probabilities.values(), answer.confidence]
            if not math.isclose(sum(answer.probabilities.values()), 1, abs_tol=0.001):
                raise ValueError(f"{key}: choice probabilities must sum to one")
            if isinstance(answer, ChoiceAnswer) and (
                answer.choice not in expected
                or answer.probabilities[answer.choice] != max(answer.probabilities.values())
            ):
                raise ValueError(f"{key}: selected choice must have the largest probability")
            if isinstance(answer, ScoreAnswer) and not math.isfinite(answer.score):
                raise ValueError(f"{key}: score must be finite")
        if any(not math.isfinite(value) or not 0 <= value <= 1 for value in values):
            raise ValueError(f"{key}: probabilities must lie in [0, 1]")


class InvalidJudgeOutput(ValueError):
    def __init__(self, message: str, response: SystemOneResponse):
        super().__init__(message)
        self.response = response


class SystemOneClient(TypeSafeClient):
    def __init__(
        self, api_key: str | None = None, timeout: float = 60.0,
        *, http_client: httpx2.Client | None = None,
    ):
        key = api_key or os.environ.get(API_KEY_ENV)
        if not key:
            raise ValueError(f"{API_KEY_ENV} is required for a paid scan")
        transport = http_client or httpx2.Client(timeout=timeout)

        def user_agent(request: httpx2.Request) -> None:
            request.headers["User-Agent"] = USER_AGENT

        transport.event_hooks["request"].append(user_agent)
        super().__init__(api_key=key, timeout=timeout, http_client=transport)

    def ask(self, *, model: str, state: Any, questions: dict[str, Any]) -> SystemOneResponse:
        cost_tracker.ensure_budget_available()
        request_cost(model, 0)
        response = self.system_one(model=model, state=state, questions=questions)
        cost_tracker.record(
            model, response.usage.input_tokens or 0, 0,
            actual_cost=request_cost(model, response.usage.input_tokens or 0),
        )
        try:
            validate_answers(response.answers, questions)
            if response.model != model:
                raise ValueError("returned judge differs from the requested model")
            if response.usage.input_tokens is None:
                raise ValueError("judge did not report input usage")
        except ValueError as exc:
            raise InvalidJudgeOutput(str(exc), response) from exc
        return response
