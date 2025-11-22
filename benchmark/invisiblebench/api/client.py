"""
API client for calling models via OpenRouter and direct provider APIs.
"""
import os
import time
from typing import List, Dict, Optional, Any
import requests
from dataclasses import dataclass


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
        self.config = config or APIConfig.from_env()

        # Try OpenRouter first, fall back to direct provider APIs
        # Skip placeholder values
        has_openrouter = (self.config.openrouter_api_key and
                         not self.config.openrouter_api_key.startswith("your_"))
        has_openai = (self.config.openai_api_key and
                     not self.config.openai_api_key.startswith("your_"))
        has_anthropic = (self.config.anthropic_api_key and
                        not self.config.anthropic_api_key.startswith("your_"))

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

        if not self.available_providers:
            raise ValueError("At least one API key must be set (OPENROUTER, OPENAI, or ANTHROPIC)")

        # Default to first available provider (will be overridden per call)
        self.provider = list(self.available_providers.keys())[0]
        self.use_openrouter = (self.provider == "openrouter")  # Track if using OpenRouter
        provider_config = self.available_providers[self.provider]
        self.base_url = provider_config["base_url"]
        api_key = provider_config["api_key"]
        extra_headers = provider_config["extra_headers"]

        self.session = requests.Session()
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
                else:
                    # OpenAI-compatible format (OpenRouter, OpenAI)
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
                    except:
                        pass

                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay * (attempt + 1))
                    continue
                raise RuntimeError(f"Failed to call model {model} after {self.config.max_retries} attempts: {error_detail}")

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

        # Check model name patterns
        if "claude" in model.lower() and "anthropic" in self.available_providers:
            return "anthropic"
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


class JudgeClient:
    """Specialized client for judge models with pre-configured prompts.

    Note: Judge 2 uses google/gemini-2.5-pro which requires OpenRouter.
    Direct Google provider is not implemented. Ensure OPENROUTER_API_KEY
    is set or modify JUDGE_MODELS to use only Anthropic/OpenAI models.
    """

    # Judge model assignments - heterogeneous judges for diverse perspectives.
    # Judge 2 uses a Gemini model that currently requires OpenRouter routing.
    JUDGE_MODELS = {
        "judge_1": "anthropic/claude-3.7-sonnet",  # Safety & Regulatory (instruction-following)
        "judge_2": "google/gemini-2.5-pro",        # Cultural & Relational (nuanced understanding) - REQUIRES OPENROUTER
        "judge_3": "anthropic/claude-opus-4"       # Trajectory & Actionable (advanced reasoning)
    }

    def __init__(self, api_client: ModelAPIClient):
        """Initialize with base API client.

        Warns if using Gemini models without OpenRouter configured.
        """
        self.api_client = api_client
        self.judge_models = dict(self.JUDGE_MODELS)

        # Warn or replace judges if Gemini models are configured without OpenRouter
        import logging
        available_providers = set(api_client.available_providers.keys())
        has_openrouter = "openrouter" in available_providers

        if not has_openrouter:
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
        prompt = judge_prompt_template.format(
            scenario_context=scenario_context,
            turn_number=turn_number,
            user_message=user_message,
            model_response=model_response,
            expected_behaviors="\n".join(f"- {b}" for b in expected_behaviors),
            autofail_triggers="\n".join(f"- {t}" for t in autofail_triggers)
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
DEFAULT_TEST_MODELS = [
    "anthropic/claude-sonnet-4.5",
    "anthropic/claude-haiku-4.5",
    "openai/gpt-5.1",
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "openai/gpt-oss-safeguard-20b",
    "google/gemini-2.5-pro",
    "google/gemini-2.5-flash",
    "x-ai/grok-4.1-fast",
    "deepseek/deepseek-chat-v3-0324",
    "qwen/qwen3-235b-a22b-2507",
    "qwen/qwen3-vl-8b-thinking",
]
