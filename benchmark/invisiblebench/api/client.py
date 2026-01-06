"""
API client for calling models via OpenRouter and direct provider APIs.
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
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    timeout: int = 120
    max_retries: int = 3
    retry_delay: float = 2.0

    @classmethod
    def from_env(cls) -> 'APIConfig':
        """Load configuration from environment variables."""
        return cls(
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )


class ModelAPIClient:
    """Client for calling various AI models via OpenRouter."""

    def __init__(self, config: Optional[APIConfig] = None):
        """Initialize API client with configuration."""
        disable_llm = os.getenv("INVISIBLEBENCH_DISABLE_LLM", "").strip().lower()
        if disable_llm in {"1", "true", "yes"}:
            raise ValueError("LLM calls disabled via INVISIBLEBENCH_DISABLE_LLM")

        self.config = config or APIConfig.from_env()

        # Try OpenRouter first, fall back to direct provider APIs
        # Skip placeholder values
        has_openrouter = (self.config.openrouter_api_key and
                         not self.config.openrouter_api_key.startswith("your_"))
        has_openai = (self.config.openai_api_key and
                     not self.config.openai_api_key.startswith("your_"))
        has_anthropic = (self.config.anthropic_api_key and
                        not self.config.anthropic_api_key.startswith("your_"))
        has_google = (self.config.google_api_key and
                      not self.config.google_api_key.startswith("your_"))

        # Priority: OpenRouter > specific providers
        # Store all available providers for dynamic routing
        self.available_providers = {}

        if has_openrouter:
            self.available_providers["openrouter"] = {
                "base_url": "https://openrouter.ai/api/v1",
                "api_key": self.config.openrouter_api_key,
                "extra_headers": {
                    "HTTP-Referer": "https://github.com/givecare/invisiblebench",
                    "X-Title": "InvisibleBench"
                }
            }
        if has_openai:
            self.available_providers["openai"] = {
                "base_url": "https://api.openai.com/v1",
                "api_key": self.config.openai_api_key,
                "extra_headers": {}
            }
        if has_anthropic:
            self.available_providers["anthropic"] = {
                "base_url": "https://api.anthropic.com/v1",
                "api_key": self.config.anthropic_api_key,
                "extra_headers": {
                    "anthropic-version": "2023-06-01"
                }
            }
        if has_google:
            self.available_providers["google"] = {
                "base_url": "https://generativelanguage.googleapis.com/v1beta",
                "api_key": self.config.google_api_key,
                "extra_headers": {}
            }

        if not self.available_providers:
            raise ValueError(
                "At least one API key must be set (OPENROUTER, OPENAI, ANTHROPIC, or GOOGLE)"
            )

        # Default to first available provider (will be overridden per call)
        self.provider = list(self.available_providers.keys())[0]
        self.use_openrouter = (self.provider == "openrouter")  # Track if using OpenRouter
        provider_config = self.available_providers[self.provider]
        self.base_url = provider_config["base_url"]
        api_key = provider_config["api_key"]
        extra_headers = provider_config["extra_headers"]

        self.session = requests.Session()
        if self.provider == "google":
            self.session.headers.update({
                "Content-Type": "application/json",
                **extra_headers
            })
        else:
            self.session.headers.update({
                "Authorization": f"Bearer {api_key}",
                **extra_headers
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
                # Determine provider based on model prefix
                active_provider = self._select_provider(model)
                provider_config = self.available_providers[active_provider]

                # Convert model format for direct provider APIs
                api_model = model
                if active_provider != "openrouter" and "/" in model:
                    # Convert "openai/gpt-4o-mini" to "gpt-4o-mini" for direct API
                    api_model = model.split("/")[-1]

                # Anthropic uses different API format
                if active_provider == "anthropic":
                    # Anthropic requires system messages to be in a separate parameter
                    system_content = None
                    filtered_messages = []

                    for msg in messages:
                        if msg.get("role") == "system":
                            system_content = msg.get("content")
                        else:
                            filtered_messages.append(msg)

                    anthropic_payload = {
                        "model": api_model,
                        "max_tokens": max_tokens,
                        "messages": filtered_messages,
                        "temperature": temperature,
                        **kwargs
                    }

                    if system_content:
                        anthropic_payload["system"] = system_content

                    # Create session with Anthropic-specific headers
                    # Anthropic uses x-api-key, not Authorization header!
                    session = requests.Session()
                    session.headers.update({
                        "x-api-key": provider_config['api_key'],
                        **provider_config['extra_headers'],
                        "Content-Type": "application/json"
                    })

                    response = session.post(
                        f"{provider_config['base_url']}/messages",
                        json=anthropic_payload,
                        timeout=self.config.timeout
                    )
                elif active_provider == "google":
                    system_content = None
                    contents = []

                    for msg in messages:
                        role = msg.get("role")
                        if role == "system":
                            if system_content:
                                system_content += f"\n{msg.get('content', '')}"
                            else:
                                system_content = msg.get("content", "")
                            continue

                        google_role = "user" if role == "user" else "model"
                        contents.append({
                            "role": google_role,
                            "parts": [{"text": msg.get("content", "")}]
                        })

                    api_model = model.split("/")[-1] if "/" in model else model
                    google_payload = {
                        "contents": contents,
                        "generationConfig": {
                            "temperature": temperature,
                            "maxOutputTokens": max_tokens,
                        },
                    }
                    if system_content:
                        google_payload["system_instruction"] = {
                            "parts": [{"text": system_content}]
                        }

                    session = requests.Session()
                    session.headers.update({
                        "Content-Type": "application/json",
                        **provider_config["extra_headers"],
                    })

                    response = session.post(
                        f"{provider_config['base_url']}/models/{api_model}:generateContent",
                        params={"key": provider_config["api_key"]},
                        json=google_payload,
                        timeout=self.config.timeout
                    )
                else:
                    # OpenAI-compatible format (OpenRouter, OpenAI)
                    # Reuse existing session for connection pooling
                    session = self.session
                    # Update headers for this specific provider if different from default
                    if active_provider != self.provider:
                        session = requests.Session()
                        session.headers.update({
                            "Authorization": f"Bearer {provider_config['api_key']}",
                            **provider_config['extra_headers']
                        })

                    # OpenAI GPT-5 models use max_completion_tokens instead of max_tokens
                    # and only support temperature=1
                    api_payload = {**payload, "model": api_model}
                    if active_provider == "openai" and "gpt-5" in api_model.lower():
                        api_payload["max_completion_tokens"] = api_payload.pop("max_tokens")
                        api_payload["temperature"] = 1  # GPT-5 models only support temperature=1

                    response = session.post(
                        f"{provider_config['base_url']}/chat/completions",
                        json=api_payload,
                        timeout=self.config.timeout
                    )
                response.raise_for_status()

                data = response.json()
                latency_ms = (time.time() - start_time) * 1000

                # Extract response based on provider format
                if active_provider == "anthropic":
                    if "content" not in data or len(data["content"]) == 0:
                        raise ValueError(f"No content in response: {data}")
                    response_text = data["content"][0]["text"]
                    tokens_used = data.get("usage", {}).get("input_tokens", 0) + data.get("usage", {}).get("output_tokens", 0)
                elif active_provider == "google":
                    candidates = data.get("candidates", [])
                    if not candidates:
                        raise ValueError(f"No candidates in response: {data}")
                    parts = candidates[0].get("content", {}).get("parts", [])
                    response_text = "".join(part.get("text", "") for part in parts)
                    usage = data.get("usageMetadata", {})
                    tokens_used = usage.get("totalTokenCount")
                    if tokens_used is None:
                        tokens_used = usage.get("promptTokenCount", 0) + usage.get("candidatesTokenCount", 0)
                else:
                    # OpenAI-compatible format
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

    def _select_provider(self, model: str) -> str:
        """Select appropriate provider based on model identifier."""
        # ALWAYS use OpenRouter if available (supports all models)
        # This is the correct approach for multi-model benchmarking
        if "openrouter" in self.available_providers:
            return "openrouter"

        # Fallback: route based on model prefix (only if OpenRouter not available)
        if "/" in model:
            provider_prefix = model.split("/")[0]
            if provider_prefix == "anthropic" and "anthropic" in self.available_providers:
                return "anthropic"
            elif provider_prefix == "openai" and "openai" in self.available_providers:
                return "openai"
            elif provider_prefix == "google" and "google" in self.available_providers:
                return "google"

        # Check model name patterns
        if "claude" in model.lower() and "anthropic" in self.available_providers:
            return "anthropic"
        elif "gemini" in model.lower() and "google" in self.available_providers:
            return "google"
        elif ("gpt" in model.lower() or "o1" in model.lower()) and "openai" in self.available_providers:
            return "openai"

        # Default to first available
        return list(self.available_providers.keys())[0]

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
        # Convert model format for direct OpenAI API
        api_model = model
        if not self.use_openrouter and "/" in model:
            api_model = model.split("/")[-1]

        payload = {
            "model": api_model,
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
    """Resolve scorer model with env overrides and provider-aware fallback."""
    env_specific = os.getenv(f"INVISIBLEBENCH_{scorer_name.upper()}_MODEL")
    env_global = os.getenv("INVISIBLEBENCH_SCORER_MODEL")

    if env_specific:
        return env_specific
    if env_global:
        return env_global

    # OpenRouter can serve any model string, so keep defaults.
    if "openrouter" in api_client.available_providers:
        return default

    prefix = default.split("/")[0] if "/" in default else ""
    if prefix and prefix in api_client.available_providers:
        return default

    if "google" in api_client.available_providers:
        return "google/gemini-2.5-flash-lite"
    if "openai" in api_client.available_providers:
        return "openai/gpt-4o-mini"
    if "anthropic" in api_client.available_providers:
        return "anthropic/claude-3.7-sonnet"

    return default


class JudgeClient:
    """Specialized client for judge models with pre-configured prompts.

    Env overrides:
      - INVISIBLEBENCH_JUDGE_MODEL (sets all judges)
      - INVISIBLEBENCH_JUDGE_MODEL_1/2/3 (per-judge override)
    """

    # Judge model assignments - heterogeneous judges for diverse perspectives.
    # Using 3 different providers ensures no single-model bias.
    # Can be overridden via constructor or environment variables.
    DEFAULT_JUDGE_MODELS = {
        "judge_1": "openai/gpt-4o",                      # Fast, good accuracy
        "judge_2": "google/gemini-2.0-flash-001",        # Google Flash, fast
        "judge_3": "anthropic/claude-sonnet-4"           # Strong reasoning, diversity
    }

    def __init__(self, api_client: ModelAPIClient, judge_models: dict = None):
        """Initialize with base API client.

        Args:
            api_client: ModelAPIClient instance
            judge_models: Optional dict to override default judge models.
                          Keys: "judge_1", "judge_2", "judge_3"
                          Values: model identifiers (e.g., "openai/gpt-4o")

        Warns if using Gemini models without OpenRouter configured.
        """
        self.api_client = api_client
        self.judge_models = dict(judge_models or self.DEFAULT_JUDGE_MODELS)

        global_override = os.getenv("INVISIBLEBENCH_JUDGE_MODEL")
        if global_override:
            for judge_id in self.judge_models:
                self.judge_models[judge_id] = global_override
        else:
            for idx in range(1, 4):
                env_model = os.getenv(f"INVISIBLEBENCH_JUDGE_MODEL_{idx}")
                if env_model:
                    self.judge_models[f"judge_{idx}"] = env_model

        # Warn or replace judges if Gemini models are configured without OpenRouter
        import logging
        available_providers = set(api_client.available_providers.keys())
        supports_google = "openrouter" in available_providers or "google" in available_providers

        if not supports_google:
            has_google_judge = any("google/" in model for model in self.judge_models.values())
            if has_google_judge:
                # Pick a fallback judge model from available providers
                fallback_model = None
                if "anthropic" in available_providers:
                    fallback_model = "anthropic/claude-3.7-sonnet"
                elif "openai" in available_providers:
                    fallback_model = "openai/gpt-4o"

                if fallback_model:
                    for judge_id, model in list(self.judge_models.items()):
                        if "google/" in model:
                            self.judge_models[judge_id] = fallback_model
                    logging.warning(
                        "OpenRouter not configured; replaced Google judge models with %s",
                        fallback_model,
                    )
                else:
                    raise ValueError(
                        "Judge configuration includes Google Gemini models but OPENROUTER_API_KEY "
                        "is not set and no Anthropic/OpenAI provider fallback is available."
                    )

    def evaluate_turn(
        self,
        judge_id: str,
        scenario_context: str,
        turn_number: int,
        user_message: str,
        model_response: str,
        expected_behaviors: List[str],
        autofail_triggers: List[str],
        judge_prompt_template: str
    ) -> Dict[str, Any]:
        """
        Evaluate a single turn with a specific judge.

        Args:
            judge_id: Judge identifier ("judge_1", "judge_2", "judge_3")
            scenario_context: Background context for the scenario
            turn_number: Turn number in conversation
            user_message: User's message
            model_response: Model's response to evaluate
            expected_behaviors: List of expected behaviors
            autofail_triggers: List of autofail conditions
            judge_prompt_template: Template for judge prompt

        Returns:
            Dictionary with scores, reasoning, and autofail status
        """
        if judge_id not in self.judge_models:
            raise ValueError(f"Unknown judge_id: {judge_id}")

        model = self.judge_models[judge_id]

        # Format the judge prompt
        # SECURITY: Escape braces in user content to prevent format string injection
        def escape_braces(s: str) -> str:
            return s.replace("{", "{{").replace("}", "}}")

        prompt = judge_prompt_template.format(
            scenario_context=escape_braces(scenario_context),
            turn_number=turn_number,
            user_message=escape_braces(user_message),
            model_response=escape_braces(model_response),
            expected_behaviors="\n".join(f"- {escape_braces(b)}" for b in expected_behaviors),
            autofail_triggers="\n".join(f"- {escape_braces(t)}" for t in autofail_triggers)
        )

        messages = [
            {"role": "user", "content": prompt}
        ]

        # Call judge model with temperature 0 for consistency
        result = self.api_client.call_model(
            model=model,
            messages=messages,
            temperature=0.0,
            max_tokens=2000
        )

        return {
            "judge_id": judge_id,
            "model": model,
            "raw_response": result["response"],
            "tokens": result["tokens"],
            "latency_ms": result["latency_ms"]
        }


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
