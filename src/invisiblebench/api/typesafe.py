"""TypeSafe transport and the request/answer contract shared by every judge caller."""

from __future__ import annotations

import json
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

from invisiblebench.api.client import cost_tracker, register_model_pricing

DEFAULT_JUDGE_MODEL = "jev-1.13.0"
JUDGE_PRICE_PER_MTOK_INPUT = 0.042
JUDGE_PRICING: dict[str, float] = {DEFAULT_JUDGE_MODEL: JUDGE_PRICE_PER_MTOK_INPUT}
ESTIMATED_BYTES_PER_TOKEN = 3
# Jev's context: 64k tokens per request, and 32k for state plus the longest
# question (docs.typesafe.ai/models). Serialized bytes / ESTIMATED_BYTES_PER_TOKEN
# is a preflight estimate, not a tokenizer-backed guarantee that a request fits.
MAX_REQUEST_TOKENS = 64_000
MAX_STATE_AND_QUESTION_TOKENS = 32_000
API_KEY_ENV = "TYPESAFE_API_KEY"

# The judge is billed only on input tokens. Registering it with the shared
# cost tracker's pricing catalog lets `ask()` reserve and settle through the
# same reserve/settle path every other dispatch uses, instead of a separate
# implementation.
for _model, _price in JUDGE_PRICING.items():
    register_model_pricing(_model, _price, 0.0)


def _tokens(value: Any) -> float:
    return len(json.dumps(value, ensure_ascii=False, default=str).encode()) / ESTIMATED_BYTES_PER_TOKEN


def check_context(state: Any, questions: dict[str, Any]) -> None:
    """Reject estimated oversize requests without truncating evidence.

    A passing estimate can still exceed the provider's tokenizer limit. The
    native error remains a technical failure, never a fabricated judgment.
    """
    state_tokens = _tokens(state)
    longest = max((_tokens(question) for question in questions.values()), default=0.0)
    if state_tokens + longest > MAX_STATE_AND_QUESTION_TOKENS:
        raise ValueError(
            f"state plus the longest question may exceed {MAX_STATE_AND_QUESTION_TOKENS} tokens"
        )
    if _tokens({"state": state, "questions": questions}) > MAX_REQUEST_TOKENS:
        raise ValueError(f"the whole request may exceed {MAX_REQUEST_TOKENS} tokens")


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
            # The SDK documents an approximate distribution; retained responses
            # include totals of 0.99 after rounding. Preserve those values, do not renormalize.
            if not 0.99 <= sum(answer.probabilities.values()) <= 1.01:
                raise ValueError(f"{key}: choice probabilities must sum to approximately one")
            if isinstance(answer, ChoiceAnswer) and (
                answer.choice not in expected
                or answer.probabilities[answer.choice] != max(answer.probabilities.values())
            ):
                raise ValueError(f"{key}: selected choice must have the largest probability")
            if isinstance(answer, ScoreAnswer) and not math.isfinite(answer.score):
                raise ValueError(f"{key}: score must be finite")
        if any(not math.isfinite(value) or not 0 <= value <= 1 for value in values):
            raise ValueError(f"{key}: probabilities must lie in [0, 1]")


def validate_response(response: SystemOneResponse, model: str, questions: dict[str, Any]) -> None:
    validate_answers(response.answers, questions)
    if response.model != model:
        raise ValueError("returned judge differs from the requested model")
    if response.usage.input_tokens is None or response.usage.input_tokens < 0:
        raise ValueError("judge did not report valid non-negative input usage")


class InvalidJudgeOutput(ValueError):
    def __init__(self, message: str, response: SystemOneResponse):
        super().__init__(message)
        self.response = response


class SystemOneClient(TypeSafeClient):
    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 60.0,
        *,
        http_client: httpx2.Client | None = None,
    ):
        key = api_key or os.environ.get(API_KEY_ENV)
        if not key:
            raise ValueError(f"{API_KEY_ENV} is required for a paid scan")
        super().__init__(
            api_key=key,
            timeout=timeout,
            headers={"User-Agent": "OpenAI File Downloader, XaiImageApiFetch/1.0"},
            http_client=http_client or httpx2.Client(timeout=timeout),
        )

    def ask(self, *, model: str, state: Any, questions: dict[str, Any]) -> SystemOneResponse:
        # Unconditional: the judge has one price owner (JUDGE_PRICING) and a
        # paid scan must never dispatch against a model this process cannot
        # price, ceiling or no ceiling.
        request_cost(model, 0)
        check_context(state, questions)

        request_bytes = len(json.dumps({"state": state, "questions": questions}, default=str))
        reservation = cost_tracker.reserve(estimated_cost(model, request_bytes))
        try:
            response = self.system_one(model=model, state=state, questions=questions)
        except Exception:
            cost_tracker.release(reservation)
            raise

        tokens = response.usage.input_tokens
        cost_tracker.settle(
            reservation, model, tokens if tokens is not None and tokens >= 0 else None, 0
        )
        try:
            validate_response(response, model, questions)
        except ValueError as exc:
            raise InvalidJudgeOutput(str(exc), response) from exc
        return response
