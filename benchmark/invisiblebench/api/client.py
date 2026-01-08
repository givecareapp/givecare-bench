"""
API client for calling models via OpenRouter.
"""
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests


@dataclass
class APIConfig:
    """Configuration for API clients."""
    openrouter_api_key: Optional[str] = None
    timeout: int = 120
    max_retries: int = 3
    retry_delay: float = 2.0

    @classmethod
    def from_env(cls) -> 'APIConfig':
        """Load configuration from environment variables."""
        return cls(
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY")
        )


class ModelAPIClient:
    """Client for calling various AI models via OpenRouter."""

    def __init__(self, config: Optional[APIConfig] = None):
        """Initialize API client with configuration."""
        disable_llm = os.getenv("INVISIBLEBENCH_DISABLE_LLM", "").strip().lower()
        if disable_llm in {"1", "true", "yes"}:
            raise ValueError("LLM calls disabled via INVISIBLEBENCH_DISABLE_LLM")

        self.config = config or APIConfig.from_env()

        # OpenRouter only (single provider)
        api_key = self.config.openrouter_api_key
        if not api_key or api_key.startswith("your_"):
            raise ValueError("OPENROUTER_API_KEY must be set for model access")

        self.available_providers = {
            "openrouter": {
                "base_url": "https://openrouter.ai/api/v1",
                "api_key": api_key,
                "extra_headers": {
                    "HTTP-Referer": "https://github.com/givecare/invisiblebench",
                    "X-Title": "InvisibleBench"
                }
            }
        }

        self.provider = "openrouter"
        self.use_openrouter = True
        provider_config = self.available_providers[self.provider]
        self.base_url = provider_config["base_url"]

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            **provider_config["extra_headers"]
        })

    def call_model(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
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

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }

        for attempt in range(self.config.max_retries):
            try:
                response = self.session.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    timeout=self.config.timeout
                )
                response.raise_for_status()

                data = response.json()
                latency_ms = (time.time() - start_time) * 1000

                if "choices" not in data or len(data["choices"]) == 0:
                    raise ValueError(f"No choices in response: {data}")

                response_text = data["choices"][0]["message"]["content"]
                tokens_used = data.get("usage", {}).get("total_tokens", 0)

                return {
                    "response": response_text,
                    "tokens": tokens_used,
                    "latency_ms": latency_ms,
                    "model": model,
                    "raw": data
                }

            except requests.exceptions.RequestException as e:
                # Log error details for debugging
                error_detail = str(e)
                if hasattr(e, 'response') and e.response is not None:
                    try:
                        error_detail += f" | Response: {e.response.text[:500]}"
                    except Exception:
                        pass

                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay * (attempt + 1))
                    continue
                raise RuntimeError(
                    f"Failed to call model {model} after {self.config.max_retries} attempts: {error_detail}"
                ) from e

        raise RuntimeError(f"Failed to call model {model}")

    def call_model_streaming(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
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
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            **kwargs
        }

        response = self.session.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            timeout=self.config.timeout,
            stream=True
        )
        response.raise_for_status()

        for line in response.iter_lines():
            if line:
                yield line.decode('utf-8')


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
    "openai/gpt-5",                          # Latest OpenAI
    "openai/gpt-4o",                         # OpenAI flagship
    "anthropic/claude-sonnet-4.5",           # Top Anthropic
    "anthropic/claude-sonnet-4",             # Strong reasoning
    "google/gemini-2.5-pro",                 # Top Google
    "google/gemini-2.5-flash",               # Fast Google
    "deepseek/deepseek-chat",                # Top open-source
    "meta-llama/llama-3.1-70b-instruct",     # Best Llama
    "qwen/qwen-2.5-72b-instruct",            # Top Chinese model
    "x-ai/grok-4",                           # xAI flagship
]
