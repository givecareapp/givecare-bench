"""TypeSafe transport and the request/answer contract shared by every judge caller."""

from __future__ import annotations

import json
import math
import threading
from pathlib import Path
from typing import Any

import httpx2
from dotenv import load_dotenv
from typesafe_sdk import (
    Answer,
    BoxAnswer,
    ChoiceAnswer,
    NoulAnswer,
    RetryPolicy,
    ScoreAnswer,
    SystemOneResponse,
    TypeSafeClient,
)

_env_file = Path(__file__).parent.parent.parent.parent / ".env"
if _env_file.exists():
    load_dotenv(_env_file)
else:
    load_dotenv()

DEFAULT_JUDGE_MODEL = "jev-1.14.0"
JUDGE_PRICE_PER_MTOK_INPUT = 0.042
# Saved runs keep the judge that answered them, so every pinned Jev stays priced.
JUDGE_PRICING: dict[str, float] = {
    "jev-1.13.0": JUDGE_PRICE_PER_MTOK_INPUT,
    "jev-1.14.0": JUDGE_PRICE_PER_MTOK_INPUT,
}
ESTIMATED_BYTES_PER_TOKEN = 3
# Jev's context: 64k tokens per request, and 32k for state plus the longest
# question (docs.typesafe.ai/models). Serialized bytes / ESTIMATED_BYTES_PER_TOKEN
# is a preflight estimate, not a tokenizer-backed guarantee that a request fits.
MAX_REQUEST_TOKENS = 64_000
MAX_STATE_AND_QUESTION_TOKENS = 32_000
# Both pinned Jev models have a 64 Ki-token input ceiling; output is free.
JEV_MAX_INPUT_TOKENS = 65_536
# The native attempt journal owns recovery. An HTTP error may have been billed;
# one recorded attempt must never conceal multiple physical requests.
RETRY = RetryPolicy(max_retries=0)


def _nonnegative_cost(value: float, name: str) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return value


class CostBudgetExceededError(RuntimeError):
    """The process-level API cost ceiling has been reached."""


class UnpricedModelCostError(CostBudgetExceededError):
    """A call with unknown cost was refused under an active runtime ceiling."""


MAX_COST_CEILING_MULTIPLIER = 1.5
MIN_COST_CEILING_HEADROOM_USD = 1.0


def maximum_reasonable_cost_ceiling(planned_cost_usd: float) -> float:
    """Bound live approval so a nominal ceiling remains a meaningful guardrail."""
    planned_cost_usd = _nonnegative_cost(planned_cost_usd, "planned cost")
    return max(
        planned_cost_usd * MAX_COST_CEILING_MULTIPLIER,
        planned_cost_usd + MIN_COST_CEILING_HEADROOM_USD,
    )


def _call_cost(
    model: str,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    actual_cost: float | None,
) -> float | None:
    """Cost of one call, or None when it cannot be known (never a fake zero)."""
    if actual_cost is not None:
        try:
            return _nonnegative_cost(actual_cost, "reported cost")
        except (TypeError, ValueError):
            pass
    price = JUDGE_PRICING.get(model)
    if price is None or prompt_tokens is None or completion_tokens is None:
        return None
    if any(
        not isinstance(n, int) or isinstance(n, bool) or n < 0
        for n in (prompt_tokens, completion_tokens)
    ):
        return None
    return prompt_tokens * price / 1_000_000


class CostTracker:
    """Process-wide judge spend with a reserve-then-settle ceiling."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._total: float = 0.0
        self._max_cost_usd: float | None = None
        self._reserved: float = 0.0
        self._next_token: int = 0
        self._reservations: dict[int, float] = {}

    def reserve(self, amount: float | None, *, allow_unknown: bool = False) -> int:
        """Reserve an estimated dollar amount before dispatching a request.

        ``amount`` is ``None`` when the request's cost cannot be estimated in
        advance (no known pricing). Under an active ceiling, an unknown
        amount is refused unless the caller opts in with ``allow_unknown``.
        Returns a token to pass to :meth:`settle` or :meth:`release`.
        """
        with self._lock:
            if amount is None:
                if self._max_cost_usd is not None and not allow_unknown:
                    raise UnpricedModelCostError(
                        f"refusing to dispatch a call with unknown cost under the active "
                        f"${self._max_cost_usd:.4f} runtime cost ceiling "
                        "(pass allow_unknown=True to opt in)"
                    )
                reserved_amount = 0.0
            else:
                reserved_amount = _nonnegative_cost(amount, "reservation")
            if self._max_cost_usd is not None:
                projected = self._total + self._reserved + reserved_amount
                if projected > self._max_cost_usd:
                    raise CostBudgetExceededError(
                        f"Runtime cost ceiling ${self._max_cost_usd:.4f} would be exceeded "
                        f"(spent ${self._total:.4f}, reserved ${self._reserved:.4f}, "
                        f"this request up to ${reserved_amount:.4f})"
                    )
            self._next_token += 1
            token = self._next_token
            self._reservations[token] = reserved_amount
            self._reserved += reserved_amount
            return token

    def release(self, token: int) -> None:
        """Cancel a reservation without recording a call (e.g. after an error)."""
        with self._lock:
            amount = self._reservations.pop(token, None)
            if amount is not None:
                self._reserved -= amount

    def record(
        self,
        model: str,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        *,
        actual_cost: float | None = None,
    ) -> float:
        """Record one completed call. An unknown cost adds nothing."""
        cost = _call_cost(model, prompt_tokens, completion_tokens, actual_cost)
        if cost is None:
            return 0.0
        with self._lock:
            self._total += cost
        return cost

    def settle(
        self,
        token: int,
        model: str,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        *,
        actual_cost: float | None = None,
    ) -> float:
        """Release a reservation and record the call's actual cost in one step."""
        with self._lock:
            if token not in self._reservations:
                raise ValueError("reservation is unknown or already settled")
            cost = self.record(model, prompt_tokens, completion_tokens, actual_cost=actual_cost)
            self.release(token)
            return cost

    @property
    def total(self) -> float:
        with self._lock:
            return self._total

    def reset(self, *, max_cost_usd: float | None = None) -> None:
        if max_cost_usd is not None:
            max_cost_usd = _nonnegative_cost(max_cost_usd, "cost ceiling")
        with self._lock:
            self._total = 0.0
            self._max_cost_usd = max_cost_usd
            self._reserved = 0.0
            self._reservations.clear()


cost_tracker = CostTracker()


def _bytes(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, default=str).encode())


# `{"state": ` + state + `, "questions": ` + questions + `}`
_REQUEST_FRAME_BYTES = len('{"state": ') + len(', "questions": ') + len("}")


def _check_sizes(state: int, longest: int, items: int, count: int) -> None:
    """Apply both limits to serialized byte sizes.

    `items` is the summed size of every `"key": value` pair; the whole request
    adds braces and `", "` separators, which is exactly what json.dumps writes.
    """
    if state / ESTIMATED_BYTES_PER_TOKEN + longest / ESTIMATED_BYTES_PER_TOKEN > (
        MAX_STATE_AND_QUESTION_TOKENS
    ):
        raise ValueError(
            f"state plus the longest question may exceed {MAX_STATE_AND_QUESTION_TOKENS} tokens"
        )
    whole = _REQUEST_FRAME_BYTES + state + 2 + items + 2 * max(count - 1, 0)
    if whole / ESTIMATED_BYTES_PER_TOKEN > MAX_REQUEST_TOKENS:
        raise ValueError(f"the whole request may exceed {MAX_REQUEST_TOKENS} tokens")


def check_context(state: Any, questions: dict[str, Any]) -> None:
    """Reject estimated oversize requests without truncating evidence.

    A passing estimate can still exceed the provider's tokenizer limit. The
    native error remains a technical failure, never a fabricated judgment.
    """
    sizes = [(_bytes({key: question}) - 2, _bytes(question)) for key, question in questions.items()]
    _check_sizes(
        _bytes(state),
        max((value for _, value in sizes), default=0),
        sum(item for item, _ in sizes),
        len(sizes),
    )


class ContextFit:
    """Grow one request question by question; each size is serialized once.

    Decisions equal `check_context` on the same state and questions.
    """

    def __init__(self, state: Any):
        self._state = _bytes(state)
        self.reset()

    def reset(self) -> None:
        self._longest = 0
        self._items = 0
        self._count = 0

    @staticmethod
    def size(key: str, question: Any) -> tuple[int, int]:
        """Serialized bytes of the `"key": value` pair and of the value alone."""
        return _bytes({key: question}) - 2, _bytes(question)

    def check_alone(self, size: tuple[int, int]) -> None:
        _check_sizes(self._state, size[1], size[0], 1)

    def accepts(self, size: tuple[int, int]) -> bool:
        try:
            _check_sizes(
                self._state,
                max(self._longest, size[1]),
                self._items + size[0],
                self._count + 1,
            )
        except ValueError:
            return False
        return True

    def add(self, size: tuple[int, int]) -> None:
        self._longest = max(self._longest, size[1])
        self._items += size[0]
        self._count += 1


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
        if isinstance(answer, BoxAnswer):
            raise ValueError(f"{key}: box answers are not part of the judge contract")
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


class UnknownJudgeCost(RuntimeError):
    """The judge answered without valid input usage, so its cost is unknown."""

    def __init__(self, response: SystemOneResponse):
        super().__init__("judge did not report valid non-negative input usage")
        self.response = response


def validate_response(response: SystemOneResponse, model: str, questions: dict[str, Any]) -> None:
    if response.usage.input_tokens is None or response.usage.input_tokens < 0:
        raise UnknownJudgeCost(response)
    validate_answers(response.answers, questions)
    if response.model != model:
        raise ValueError("returned judge differs from the requested model")


class InvalidJudgeOutput(ValueError):
    def __init__(self, message: str, response: SystemOneResponse):
        super().__init__(message)
        self.response = response


def _user_agent(request: httpx2.Request) -> None:
    # The SDK overwrites header options. Apply policy at HTTPX's request hook.
    request.headers["User-Agent"] = "OpenAI File Downloader, XaiImageApiFetch/1.0"


class SystemOneClient(TypeSafeClient):
    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 60.0,
        *,
        http_client: httpx2.Client | None = None,
    ):
        http_client = http_client or httpx2.Client(timeout=timeout)
        http_client.event_hooks["request"].append(_user_agent)
        try:
            super().__init__(
                api_key=api_key,
                timeout=timeout,
                retry=RETRY,
                http_client=http_client,
            )
        except BaseException:
            http_client.close()
            raise

    def ask(self, *, model: str, state: Any, questions: dict[str, Any]) -> SystemOneResponse:
        # Unconditional: the judge has one price owner (JUDGE_PRICING) and a
        # paid scan must never dispatch against a model this process cannot
        # price, ceiling or no ceiling.
        maximum_cost = request_cost(model, JEV_MAX_INPUT_TOKENS)
        check_context(state, questions)

        # Size estimates plan the scan; only the provider's ceiling authorizes spend.
        reservation = cost_tracker.reserve(maximum_cost)
        try:
            response = self.system_one(model=model, state=state, questions=questions)
        except BaseException:
            # No documented contract says a failed request is unbilled.
            cost_tracker.settle(reservation, model, None, 0)
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
