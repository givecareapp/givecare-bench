"""
API client for calling models via OpenRouter.
"""

import asyncio
import hashlib
import json
import os
import threading
import time
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
import requests

# Always try to load .env from project root (handles various entry points)
_project_root = Path(__file__).parent.parent.parent.parent
_env_file = _project_root / ".env"
if _env_file.exists():
    load_dotenv(_env_file)
else:
    # Fallback to CWD
    load_dotenv()

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


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
    """Simple thread-safe LRU cache for scorer responses."""

    def __init__(self, max_entries: int):
        self.max_entries = max_entries
        self._data: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        if self.max_entries <= 0:
            return None
        with self._lock:
            if key not in self._data:
                return None
            self._data.move_to_end(key)
            return deepcopy(self._data[key])

    def set(self, key: str, value: Dict[str, Any]) -> None:
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
    """Raised when the OpenRouter account has insufficient credits (HTTP 402)."""

    pass


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_HEADERS = {
    "HTTP-Referer": "https://github.com/givecare/invisiblebench",
    "X-Title": "InvisibleBench",
}


@dataclass
class APIConfig:
    """Configuration for API clients."""

    openrouter_api_key: Optional[str] = None
    timeout: int = 120
    max_retries: int = 3
    retry_delay: float = 2.0

    @classmethod
    def from_env(cls) -> "APIConfig":
        """Load configuration from environment variables."""
        return cls(openrouter_api_key=os.getenv("OPENROUTER_API_KEY"))


class ModelAPIClient:
    """Client for calling various AI models via OpenRouter."""

    def __init__(self, config: Optional[APIConfig] = None):
        """Initialize API client with configuration."""
        disable_llm = os.getenv("INVISIBLEBENCH_DISABLE_LLM", "").strip().lower()
        if disable_llm in {"1", "true", "yes"}:
            raise ValueError("LLM calls disabled via INVISIBLEBENCH_DISABLE_LLM")

        self.config = config or APIConfig.from_env()

        api_key = self.config.openrouter_api_key
        if not api_key or api_key.startswith("your_"):
            raise ValueError("OPENROUTER_API_KEY must be set for model access")

        self.base_url = OPENROUTER_BASE_URL
        self.headers = {"Authorization": f"Bearer {api_key}", **OPENROUTER_HEADERS}

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
            except Exception:
                pass
        return detail

    @staticmethod
    def _build_payload(
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        stream: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
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
    def _is_cacheable(payload: Dict[str, Any]) -> bool:
        if payload.get("stream"):
            return False
        temp = payload.get("temperature")
        try:
            return float(temp) == 0.0
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _cache_key(payload: Dict[str, Any]) -> Optional[str]:
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
    def _parse_response(data: Dict[str, Any], model: str, start_time: float) -> Dict[str, Any]:
        if "choices" not in data or not data["choices"]:
            raise ValueError(f"No choices in response: {data}")

        response_text = data["choices"][0]["message"]["content"]
        tokens_used = data.get("usage", {}).get("total_tokens", 0)
        latency_ms = (time.time() - start_time) * 1000

        return {
            "response": response_text,
            "tokens": tokens_used,
            "latency_ms": latency_ms,
            "model": model,
            "raw": data,
        }

    def call_model(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Call a model via OpenRouter.

        Args:
            model: Model identifier (e.g., "anthropic/claude-3.7-sonnet")
            messages: List of message dicts with "role" and "content"
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional model parameters

        Returns:
            Dictionary with response text, tokens used, and latency
        """
        start_time = time.time()
        payload = self._build_payload(model, messages, temperature, max_tokens, **kwargs)
        cache_key = None
        if _SCORER_CACHE_MAX_ENTRIES > 0 and self._is_cacheable(payload):
            cache_key = self._cache_key(payload)
            if cache_key:
                cached = _SCORER_RESPONSE_CACHE.get(cache_key)
                if cached is not None:
                    return cached

        for attempt in range(self.config.max_retries):
            try:
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
                        f"OpenRouter account has insufficient credits. "
                        f"Add credits at https://openrouter.ai/settings/credits"
                    ) from e
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay * (attempt + 1))
                    continue
                raise RuntimeError(
                    f"Failed to call model {model} after {self.config.max_retries} attempts: {error_detail}"
                ) from e

        raise RuntimeError(f"Failed to call model {model}")

    async def call_model_async(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Call a model via OpenRouter asynchronously.

        Requires httpx to be installed: pip install httpx

        Args:
            model: Model identifier (e.g., "anthropic/claude-3.7-sonnet")
            messages: List of message dicts with "role" and "content"
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional model parameters

        Returns:
            Dictionary with response text, tokens used, and latency
        """
        if not HTTPX_AVAILABLE:
            raise ImportError("httpx is required for async API calls: pip install httpx")

        start_time = time.time()
        payload = self._build_payload(model, messages, temperature, max_tokens, **kwargs)
        cache_key = None
        if _SCORER_CACHE_MAX_ENTRIES > 0 and self._is_cacheable(payload):
            cache_key = self._cache_key(payload)
            if cache_key:
                cached = _SCORER_RESPONSE_CACHE.get(cache_key)
                if cached is not None:
                    return cached

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.config.timeout),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        ) as client:
            last_error: Optional[Exception] = None
            for attempt in range(self.config.max_retries):
                try:
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
                            f"OpenRouter account has insufficient credits. "
                            f"Add credits at https://openrouter.ai/settings/credits"
                        ) from e
                    if attempt < self.config.max_retries - 1:
                        await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                        continue
                    raise RuntimeError(
                        f"Failed to call model {model} after {self.config.max_retries} attempts: {error_detail}"
                    ) from e

            raise RuntimeError(f"Failed to call model {model}") from last_error

    def call_model_streaming(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs,
    ):
        """
        Call a model with streaming response (for future implementation).

        Args:
            model: Model identifier
            messages: List of message dicts
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional model parameters

        Yields:
            Response chunks as they arrive
        """
        payload = self._build_payload(
            model, messages, temperature, max_tokens, stream=True, **kwargs
        )

        response = self.session.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            timeout=self.config.timeout,
            stream=True,
        )
        response.raise_for_status()

        for line in response.iter_lines():
            if line:
                yield line.decode("utf-8")


# Default model for LLM-based scorers (safety, belonging, trauma, compliance)
# Can be overridden by passing api_client with different model in scorer calls
DEFAULT_SCORER_MODEL = "google/gemini-2.5-flash-lite"
DEFAULT_SAFETY_REFERENCE_MODEL = "anthropic/claude-3.7-sonnet"


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


# Default reference models used in the public scripts/results
# Top 10 models for benchmarking (via OpenRouter)
DEFAULT_TEST_MODELS = [
    "openai/gpt-5",  # Latest OpenAI
    "openai/gpt-4o",  # OpenAI flagship
    "anthropic/claude-sonnet-4.5",  # Top Anthropic
    "anthropic/claude-sonnet-4",  # Strong reasoning
    "google/gemini-2.5-pro",  # Top Google
    "google/gemini-2.5-flash",  # Fast Google
    "deepseek/deepseek-chat",  # Top open-source
    "meta-llama/llama-3.1-70b-instruct",  # Best Llama
    "qwen/qwen-2.5-72b-instruct",  # Top Chinese model
    "x-ai/grok-4",  # xAI flagship
]
