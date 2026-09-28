"""OpenRouter API client."""

import asyncio
import json
import math
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

from invisiblebench.models._types import ChatMessage

_project_root = Path(__file__).parent.parent.parent.parent
_env_file = _project_root / ".env"
if _env_file.exists():
    load_dotenv(_env_file)
else:
    load_dotenv()

# Known generation-model pricing per million tokens (input, output)
_MODEL_PRICING: dict[str, tuple[float, float]] = {
    "google/gemini-2.5-flash-lite": (0.10, 0.40),
    "google/gemini-2.5-flash": (0.30, 2.50),
    "gpt-5-mini-2025-08-07": (0.25, 2.00),
    "openai/gpt-5-mini": (0.25, 2.00),
}

# A conservative token estimate for pre-dispatch reservations: real payloads
# run above four characters per billed token, so dividing by a smaller
# divisor keeps the reservation an upper bound, not a guess that undershoots.
_CHARS_PER_TOKEN_RESERVE_ESTIMATE = 3


def register_model_pricing(model: str, cost_per_m_input: float, cost_per_m_output: float) -> None:
    """Register per-token pricing for a model outside the built-in catalog.

    Lets callers with their own price list (e.g. the judge client, priced
    only on input tokens) share the one cost tracker's reserve/settle path
    instead of reimplementing it.
    """
    _MODEL_PRICING[model] = (cost_per_m_input, cost_per_m_output)


def _lookup_model_pricing(model: str) -> tuple[float, float] | None:
    pricing = _MODEL_PRICING.get(model)
    if pricing is not None:
        return pricing
    try:
        from invisiblebench.models.config import MODELS_FULL

        for m in MODELS_FULL:
            _MODEL_PRICING[m.id] = (m.cost_per_m_input, m.cost_per_m_output)
    except ImportError:
        return None
    return _MODEL_PRICING.get(model)


def estimate_request_reservation(model: str, messages: list[Any], max_tokens: int) -> float | None:
    """An upper-bound dollar estimate for a not-yet-dispatched chat request.

    Returns ``None`` when the model has no known pricing — the caller decides
    whether an unknown-cost dispatch is acceptable.
    """
    pricing = _lookup_model_pricing(model)
    if pricing is None:
        return None
    prompt_chars = sum(len(str(m.get("content", ""))) for m in messages)
    prompt_tokens_estimate = math.ceil(prompt_chars / _CHARS_PER_TOKEN_RESERVE_ESTIMATE)
    return (prompt_tokens_estimate / 1_000_000) * pricing[0] + (
        max_tokens / 1_000_000
    ) * pricing[1]


class CostTracker:

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._total: float = 0.0
        self._reported_total: float = 0.0
        self._estimated_total: float = 0.0
        self._calls: int = 0
        self._unknown_calls: int = 0
        self._by_model: dict[str, float] = {}
        self._max_cost_usd: float | None = None
        self._reserved: float = 0.0
        self._next_token: int = 0
        self._reservations: dict[int, float] = {}

    def reserve(self, amount: float | None, *, allow_unknown: bool = False) -> int:
        """Reserve an upper-bound dollar amount before dispatching a request.

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
                reserved_amount = max(float(amount), 0.0)
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

    def _apply(self, model: str, cost: float | None, kind: str) -> float:
        with self._lock:
            self._calls += 1
            if kind == "unknown":
                self._unknown_calls += 1
                return 0.0
            assert cost is not None
            self._total += cost
            self._by_model[model] = self._by_model.get(model, 0.0) + cost
            if kind == "reported":
                self._reported_total += cost
            else:
                self._estimated_total += cost
            return cost

    def record(
        self,
        model: str,
        prompt_tokens: int | None,
        completion_tokens: int,
        *,
        actual_cost: float | None = None,
    ) -> float:
        """Record one completed call. Always counts, even with unknown cost."""

        if actual_cost is not None:
            try:
                reported_cost = float(actual_cost)
            except (TypeError, ValueError):
                reported_cost = None
            if reported_cost is not None and (
                not math.isfinite(reported_cost) or reported_cost < 0
            ):
                reported_cost = None
        else:
            reported_cost = None

        if reported_cost is not None:
            return self._apply(model, reported_cost, "reported")

        pricing = _lookup_model_pricing(model)
        if pricing is None or prompt_tokens is None:
            return self._apply(model, None, "unknown")

        cost = (prompt_tokens / 1_000_000) * pricing[0] + (
            completion_tokens / 1_000_000
        ) * pricing[1]
        return self._apply(model, cost, "estimated")

    def settle(
        self,
        token: int,
        model: str,
        prompt_tokens: int | None,
        completion_tokens: int,
        *,
        actual_cost: float | None = None,
    ) -> float:
        """Release a reservation and record the call's actual cost in one step."""
        self.release(token)
        return self.record(model, prompt_tokens, completion_tokens, actual_cost=actual_cost)

    @property
    def total(self) -> float:
        with self._lock:
            return self._total

    @property
    def calls(self) -> int:
        with self._lock:
            return self._calls

    @property
    def unknown_calls(self) -> int:
        with self._lock:
            return self._unknown_calls

    def snapshot(self) -> dict[str, Any]:

        with self._lock:
            return {
                "total": self._total,
                "calls": self._calls,
                "by_model": dict(self._by_model),
                "max_cost_usd": self._max_cost_usd,
                "reported_total": self._reported_total,
                "estimated_total": self._estimated_total,
                "unknown_calls": self._unknown_calls,
            }

    def reset(self, *, max_cost_usd: float | None = None) -> None:
        with self._lock:
            self._total = 0.0
            self._reported_total = 0.0
            self._estimated_total = 0.0
            self._calls = 0
            self._unknown_calls = 0
            self._by_model.clear()
            self._max_cost_usd = max_cost_usd
            self._reserved = 0.0
            self._reservations.clear()

    def ensure_budget_available(self) -> None:
        with self._lock:
            if self._max_cost_usd is not None and self._total >= self._max_cost_usd:
                raise CostBudgetExceededError(
                    f"Runtime cost ceiling ${self._max_cost_usd:.4f} reached "
                    f"(recorded ${self._total:.4f})"
                )


cost_tracker = CostTracker()


class InsufficientCreditsError(RuntimeError):
    """HTTP 402: insufficient credits."""


class CostBudgetExceededError(RuntimeError):
    """The process-level API cost ceiling has been reached."""


class UnpricedModelCostError(CostBudgetExceededError):
    """A call with unknown cost was refused under an active runtime ceiling."""


MAX_COST_CEILING_MULTIPLIER = 1.5
MIN_COST_CEILING_HEADROOM_USD = 1.0


def maximum_reasonable_cost_ceiling(planned_cost_usd: float) -> float:
    """Bound live approval so a nominal ceiling remains a meaningful guardrail."""
    if planned_cost_usd < 0:
        raise ValueError("planned cost must be non-negative")
    return max(
        planned_cost_usd * MAX_COST_CEILING_MULTIPLIER,
        planned_cost_usd + MIN_COST_CEILING_HEADROOM_USD,
    )


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_HEADERS = {
    "HTTP-Referer": "https://github.com/givecare/invisiblebench",
    "X-Title": "InvisibleBench",
}


OPENAI_BASE_URL = "https://api.openai.com/v1"


@dataclass
class APIConfig:
    """Configuration for API clients."""

    openrouter_api_key: str | None = None
    timeout: int = 120
    max_retries: int = 3
    retry_delay: float = 2.0

    @classmethod
    def from_env(cls) -> "APIConfig":
        """Load configuration from environment variables."""
        return cls(
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
            timeout=_env_number("INVISIBLEBENCH_API_TIMEOUT_SECONDS", 120, minimum=0),
            max_retries=int(_env_number("INVISIBLEBENCH_API_MAX_RETRIES", 3, minimum=1)),
            retry_delay=_env_number("INVISIBLEBENCH_API_RETRY_DELAY_SECONDS", 2.0, minimum=0),
        )


def _env_number(name: str, default: float, *, minimum: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    if value < minimum:
        return default
    return value


def _resolve_api_backend() -> tuple[str | None, str | None, dict[str, str]]:
    """Resolve API key and base URL from available env vars.

    Priority: INVISIBLEBENCH_API_BACKEND (explicit) > OPENROUTER_API_KEY > OPENAI_API_KEY.
    Set INVISIBLEBENCH_API_BACKEND=openai to force OpenAI even when OpenRouter key exists.
    Returns (api_key, base_url, extra_headers).
    """
    forced = os.getenv("INVISIBLEBENCH_API_BACKEND", "").strip().lower()

    if forced == "openai":
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key and not openai_key.startswith("your_"):
            return openai_key, OPENAI_BASE_URL, {}

    if forced != "openai":
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        if openrouter_key and not openrouter_key.startswith("your_"):
            return openrouter_key, OPENROUTER_BASE_URL, OPENROUTER_HEADERS

    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key and not openai_key.startswith("your_"):
        return openai_key, OPENAI_BASE_URL, {}

    return None, None, {}


class ModelAPIClient:
    """Client for calling AI models via OpenRouter or OpenAI-compatible APIs."""

    def __init__(self, config: APIConfig | None = None):
        disable_llm = os.getenv("INVISIBLEBENCH_DISABLE_LLM", "").strip().lower()
        if disable_llm in {"1", "true", "yes"}:
            raise ValueError("LLM calls disabled via INVISIBLEBENCH_DISABLE_LLM")

        self.config = config or APIConfig.from_env()

        api_key, base_url, extra_headers = _resolve_api_backend()
        if not api_key:
            raise ValueError("No API key found. Set OPENROUTER_API_KEY or OPENAI_API_KEY.")

        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            **extra_headers,
        }

    @staticmethod
    def _format_request_error(exc: Exception) -> str:
        detail = str(exc)
        response = getattr(exc, "response", None)
        if response is not None:
            try:
                text = getattr(response, "text", None)
                if text is None and hasattr(response, "read"):
                    text = response.read()
                    if isinstance(text, bytes):
                        text = text.decode("utf-8", errors="ignore")
                if text:
                    detail += f" | Response: {text[:500]}"
            except (OSError, UnicodeDecodeError, AttributeError):
                pass
        return detail

    @staticmethod
    def _build_payload(
        model: str,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int,
        stream: bool = False,
        **kwargs,
    ) -> dict[str, Any]:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        payload.update(kwargs)
        if stream:
            payload["stream"] = True
        return payload

    @staticmethod
    def _parse_response(
        data: dict[str, Any],
        model: str,
        start_time: float,
        reservation: int | None = None,
    ) -> dict[str, Any]:
        if "choices" not in data or not data["choices"]:
            raise ValueError(f"No choices in response: {data}")

        response_text = data["choices"][0]["message"]["content"]
        finish_reason = data["choices"][0].get("finish_reason")
        usage = data.get("usage") or {}
        tokens_used = usage.get("total_tokens", 0)
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        latency_ms = (time.time() - start_time) * 1000

        if reservation is None:
            cost = cost_tracker.record(
                model,
                prompt_tokens,
                completion_tokens,
                actual_cost=usage.get("cost"),
            )
        else:
            cost = cost_tracker.settle(
                reservation,
                model,
                prompt_tokens,
                completion_tokens,
                actual_cost=usage.get("cost"),
            )

        return {
            "response": response_text,
            "finish_reason": finish_reason,
            "tokens": tokens_used,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "latency_ms": latency_ms,
            "model": model,
            "raw": data,
            "cost": cost,
        }

    async def call_model_async(
        self,
        model: str,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        *,
        allow_unknown_cost: bool = False,
        **kwargs,
    ) -> dict[str, Any]:
        """Async variant of call_model. Requires httpx.

        Reserves an upper-bound cost estimate before dispatch so concurrent
        callers cannot collectively overshoot an active budget ceiling, then
        settles the reservation to the actual (or estimated/unknown) cost
        once a response arrives. ``allow_unknown_cost`` opts an unpriced
        model into dispatch under a ceiling instead of being refused.
        """

        start_time = time.time()
        payload = self._build_payload(model, messages, temperature, max_tokens, **kwargs)
        reservation_amount = estimate_request_reservation(model, messages, max_tokens)
        reservation = cost_tracker.reserve(reservation_amount, allow_unknown=allow_unknown_cost)

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.timeout),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            ) as client:
                last_error: Exception | None = None
                for attempt in range(self.config.max_retries):
                    try:
                        response = await client.post(
                            f"{self.base_url}/chat/completions",
                            json=payload,
                            headers=self.headers,
                        )
                        response.raise_for_status()

                        data = response.json()
                        result = self._parse_response(data, model, start_time, reservation)
                        return result

                    except (
                        httpx.HTTPStatusError,
                        httpx.RequestError,
                        json.JSONDecodeError,
                    ) as e:
                        last_error = e
                        error_detail = self._format_request_error(e)
                        status_code = getattr(getattr(e, "response", None), "status_code", None)
                        if status_code == 402:
                            raise InsufficientCreditsError(
                                "OpenRouter account has insufficient credits. "
                                "Add credits at https://openrouter.ai/settings/credits"
                            ) from e
                        if attempt < self.config.max_retries - 1:
                            await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                            continue
                        raise RuntimeError(
                            f"Failed to call model {model} after {self.config.max_retries} "
                            f"attempts: {error_detail}"
                        ) from e

                raise RuntimeError(f"Failed to call model {model}") from last_error
        except BaseException:
            cost_tracker.release(reservation)
            raise
