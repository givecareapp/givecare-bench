"""OpenRouter API client."""

import asyncio
import hashlib
import json
import math
import os
import threading
import time
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from invisiblebench.models._types import ChatMessage
from invisiblebench.utils.prompt_hash import prompt_hash, prompt_template_hash

_project_root = Path(__file__).parent.parent.parent.parent
_env_file = _project_root / ".env"
if _env_file.exists():
    load_dotenv(_env_file)
else:
    load_dotenv()

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


# Default judge IDs live here so both runtime selection and cost accounting use
# the same spellings.
JUDGE_MODEL_OPENAI_ID = "gpt-5-mini-2025-08-07"
JUDGE_MODEL_OPENROUTER_ID = "openai/gpt-5-mini"

# Known pricing per million tokens (input, output)
_MODEL_PRICING: dict[str, tuple[float, float]] = {
    "google/gemini-2.5-flash-lite": (0.10, 0.40),
    "google/gemini-2.5-flash": (0.30, 2.50),
    JUDGE_MODEL_OPENAI_ID: (0.25, 2.00),
    JUDGE_MODEL_OPENROUTER_ID: (0.25, 2.00),
}


class CostTracker:


    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._total: float = 0.0
        self._calls: int = 0
        self._by_model: dict[str, float] = {}
        self._max_cost_usd: float | None = None

    def record(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        *,
        actual_cost: float | None = None,
    ) -> float:

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

        pricing = None if reported_cost is not None else _MODEL_PRICING.get(model)
        if reported_cost is None and pricing is None:
            # Try to import config pricing at runtime
            try:
                from invisiblebench.models.config import MODELS_FULL

                for m in MODELS_FULL:
                    _MODEL_PRICING[m.id] = (m.cost_per_m_input, m.cost_per_m_output)
                pricing = _MODEL_PRICING.get(model)
            except ImportError:
                pass
        if reported_cost is None and pricing is None:
            return 0.0

        cost = reported_cost
        if cost is None:
            assert pricing is not None
            cost = (prompt_tokens / 1_000_000) * pricing[0] + (
                completion_tokens / 1_000_000
            ) * pricing[1]
        with self._lock:
            self._total += cost
            self._calls += 1
            self._by_model[model] = self._by_model.get(model, 0.0) + cost
        return cost

    @property
    def total(self) -> float:
        with self._lock:
            return self._total

    @property
    def calls(self) -> int:
        with self._lock:
            return self._calls

    def snapshot(self) -> dict[str, Any]:

        with self._lock:
            return {
                "total": self._total,
                "calls": self._calls,
                "by_model": dict(self._by_model),
                "max_cost_usd": self._max_cost_usd,
            }

    def reset(self, *, max_cost_usd: float | None = None) -> None:
        with self._lock:
            self._total = 0.0
            self._calls = 0
            self._by_model.clear()
            self._max_cost_usd = max_cost_usd

    def ensure_budget_available(self) -> None:
        with self._lock:
            if (
                self._max_cost_usd is not None
                and self._total >= self._max_cost_usd
            ):
                raise CostBudgetExceededError(
                    f"Runtime cost ceiling ${self._max_cost_usd:.4f} reached "
                    f"(recorded ${self._total:.4f})"
                )


cost_tracker = CostTracker()


def _load_scorer_cache_size(default: int = 256) -> int:
    raw = os.getenv("INVISIBLEBENCH_SCORER_CACHE_SIZE", "").strip()
    if not raw:
        return default
    try:
        size = int(raw)
    except ValueError:
        return default
    return max(size, 0)


class _LRUCache:


    def __init__(self, max_entries: int):
        self.max_entries = max_entries
        self._data: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> dict[str, Any] | None:
        if self.max_entries <= 0:
            return None
        with self._lock:
            if key not in self._data:
                return None
            self._data.move_to_end(key)
            return deepcopy(self._data[key])

    def set(self, key: str, value: dict[str, Any]) -> None:
        if self.max_entries <= 0:
            return
        with self._lock:
            self._data[key] = deepcopy(value)
            self._data.move_to_end(key)
            if len(self._data) > self.max_entries:
                self._data.popitem(last=False)


_SCORER_CACHE_MAX_ENTRIES = _load_scorer_cache_size()
_SCORER_RESPONSE_CACHE = _LRUCache(_SCORER_CACHE_MAX_ENTRIES)


class InsufficientCreditsError(RuntimeError):
    """HTTP 402: insufficient credits."""


class CostBudgetExceededError(RuntimeError):
    """The process-level API cost ceiling has been reached."""


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
            raise ValueError(
                "No API key found. Set OPENROUTER_API_KEY or OPENAI_API_KEY."
            )

        self.base_url = base_url
        self._api_key = api_key  # Stored for instructor/structured extraction
        self.headers = {"Authorization": f"Bearer {api_key}", **extra_headers}

        self.session = requests.Session()
        self.session.headers.update(self.headers)

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
    def _is_cacheable(payload: dict[str, Any]) -> bool:
        if payload.get("stream"):
            return False
        temp = payload.get("temperature")
        try:
            return float(temp) == 0.0
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _cache_key(payload: dict[str, Any]) -> str | None:
        normalized = dict(payload)
        if "temperature" in normalized:
            try:
                normalized["temperature"] = float(normalized["temperature"])
            except (TypeError, ValueError):
                pass
        try:
            payload_json = json.dumps(
                normalized,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            )
        except (TypeError, ValueError):
            return None
        return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

    @staticmethod
    def _parse_response(data: dict[str, Any], model: str, start_time: float) -> dict[str, Any]:
        if "choices" not in data or not data["choices"]:
            raise ValueError(f"No choices in response: {data}")

        response_text = data["choices"][0]["message"]["content"]
        finish_reason = data["choices"][0].get("finish_reason")
        usage = data.get("usage") or {}
        tokens_used = usage.get("total_tokens", 0)
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        latency_ms = (time.time() - start_time) * 1000

        cost_tracker.record(
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
        }

    def call_model(
        self,
        model: str,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        use_cache: bool = False,
        **kwargs,
    ) -> dict[str, Any]:
        """Call a model and return response text, token counts, and latency."""
        start_time = time.time()
        payload = self._build_payload(model, messages, temperature, max_tokens, **kwargs)
        cache_key = None
        if use_cache and _SCORER_CACHE_MAX_ENTRIES > 0 and self._is_cacheable(payload):
            cache_key = self._cache_key(payload)
            if cache_key:
                cached = _SCORER_RESPONSE_CACHE.get(cache_key)
                if cached is not None:
                    return cached

        for attempt in range(self.config.max_retries):
            try:
                cost_tracker.ensure_budget_available()
                response = self.session.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    timeout=self.config.timeout,
                )
                response.raise_for_status()

                data = response.json()
                result = self._parse_response(data, model, start_time)
                if cache_key:
                    _SCORER_RESPONSE_CACHE.set(cache_key, result)
                return result

            except requests.exceptions.RequestException as e:
                error_detail = self._format_request_error(e)
                status_code = getattr(getattr(e, "response", None), "status_code", None)
                if status_code == 402:
                    raise InsufficientCreditsError(
                        "OpenRouter account has insufficient credits. "
                        "Add credits at https://openrouter.ai/settings/credits"
                    ) from e
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay * (attempt + 1))
                    continue
                raise RuntimeError(
                    f"Failed to call model {model} after {self.config.max_retries} attempts: {error_detail}"
                ) from e

        raise RuntimeError(f"Failed to call model {model}")

    def call_structured(
        self,
        model: str,
        messages: list[ChatMessage],
        response_model: type,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        max_retries: int = 2,
    ) -> Any:
        """Call a model and return a validated Pydantic instance via instructor."""
        import instructor
        from openai import OpenAI

        client = instructor.from_openai(
            OpenAI(
                base_url=self.base_url,
                api_key=self._api_key,
            ),
            mode=instructor.Mode.JSON,
        )

        return client.chat.completions.create(
            model=model,
            messages=messages,
            response_model=response_model,
            temperature=temperature,
            max_tokens=max_tokens,
            max_retries=max_retries,
        )

    async def call_model_async(
        self,
        model: str,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        use_cache: bool = False,
        **kwargs,
    ) -> dict[str, Any]:
        """Async variant of call_model. Requires httpx."""
        if not HTTPX_AVAILABLE:
            raise ImportError("httpx is required for async API calls: pip install httpx")

        start_time = time.time()
        payload = self._build_payload(model, messages, temperature, max_tokens, **kwargs)
        cache_key = None
        if use_cache and _SCORER_CACHE_MAX_ENTRIES > 0 and self._is_cacheable(payload):
            cache_key = self._cache_key(payload)
            if cache_key:
                cached = _SCORER_RESPONSE_CACHE.get(cache_key)
                if cached is not None:
                    return cached

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.config.timeout),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        ) as client:
            last_error: Exception | None = None
            for attempt in range(self.config.max_retries):
                try:
                    cost_tracker.ensure_budget_available()
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        json=payload,
                        headers=self.headers,
                    )
                    response.raise_for_status()

                    data = response.json()
                    result = self._parse_response(data, model, start_time)
                    if cache_key:
                        _SCORER_RESPONSE_CACHE.set(cache_key, result)
                    return result

                except (httpx.HTTPStatusError, httpx.RequestError) as e:
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
                        f"Failed to call model {model} after {self.config.max_retries} attempts: {error_detail}"
                    ) from e

            raise RuntimeError(f"Failed to call model {model}") from last_error

# Default model for LLM-based Safety/Care judges.
#
# Resolved once at import time based on which backend will actually be used
# at runtime (INVISIBLEBENCH_API_BACKEND / OPENROUTER_API_KEY / OPENAI_API_KEY
# — see _resolve_api_backend above): direct-OpenAI callers get the dated
# OpenAI model id, OpenRouter callers get the "openai/..." id. Both spellings
# name the SAME judge model — this is the single canonical owner of the judge
# id (CLAUDE.md). Callers needing a judge model must import DEFAULT_JUDGE_MODEL
# / DEFAULT_SCORER_MODEL from here rather than re-deriving or hardcoding either
# spelling; the env var INVISIBLEBENCH_SCORER_MODEL overrides these defaults
# at the call site. JUDGE_MODEL_OPENAI_ID / JUDGE_MODEL_OPENROUTER_ID expose
# both known spellings (not just whichever one won at import time) so
# consumers that must key data off the judge id under both backends — e.g.
# judge.py's MODEL_PRICING cost-estimation table — have one place to read
# them from instead of copying the literals.
#
# Drift detection: if this judge id ever changes, run_audit.py's
# _audit_judge_health (~line 308) flags any scan artifact whose rows carry
# more than one distinct `judge_model` value — that's the tripwire for a
# judge swap that happened mid-run instead of a clean cutover.
_, _default_base, _ = _resolve_api_backend()
_USING_OPENAI_DIRECT = _default_base == OPENAI_BASE_URL
DEFAULT_JUDGE_MODEL = JUDGE_MODEL_OPENAI_ID if _USING_OPENAI_DIRECT else JUDGE_MODEL_OPENROUTER_ID
DEFAULT_SCORER_MODEL = DEFAULT_JUDGE_MODEL
DEFAULT_SAFETY_REFERENCE_MODEL = "gpt-4.1-mini" if _USING_OPENAI_DIRECT else "google/gemini-2.5-flash"


def compute_prompt_hash(prompt_text: str) -> str:
    """Return SHA256 hex digest of trimmed prompt text."""
    return prompt_hash(prompt_text)


def compute_prompt_template_hash(*template_parts: str) -> str:
    """Return a stable hash for one or more prompt-template fragments.

    This is intended for judge comparability metadata. Callers should pass only
    template/static instruction text here, not fully rendered prompts containing
    scenario-specific conversation content.
    """
    return prompt_template_hash(*template_parts)


def resolve_scorer_model(
    api_client: ModelAPIClient,
    scorer_name: str,
    default: str = DEFAULT_SCORER_MODEL,
) -> str:
    """Resolve scorer model with env overrides."""
    env_specific = os.getenv(f"INVISIBLEBENCH_{scorer_name.upper()}_MODEL")
    env_global = os.getenv("INVISIBLEBENCH_SCORER_MODEL")

    if env_specific:
        return env_specific
    if env_global:
        return env_global

    return default
