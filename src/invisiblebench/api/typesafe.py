"""The judge model client: one request of yes/no questions over one turn."""

from __future__ import annotations

import os
from typing import Any

from invisiblebench.api.client import cost_tracker

DEFAULT_JUDGE_MODEL = "jev-1.13.0"
JUDGE_PRICE_PER_MTOK_INPUT = 0.042
JUDGE_PRICING: dict[str, float] = {DEFAULT_JUDGE_MODEL: JUDGE_PRICE_PER_MTOK_INPUT}
# Observed on saved scans: about 4.3 UTF-8 bytes per billed token. Three keeps the estimate above cost.
ESTIMATED_BYTES_PER_TOKEN = 3
API_KEY_ENV = "TYPESAFE_API_KEY"


def estimated_cost(model: str, request_bytes: int) -> float | None:
    """A conservative dry-run estimate from the request payload size."""
    price = JUDGE_PRICING.get(model)
    if price is None:
        return None
    return request_bytes / ESTIMATED_BYTES_PER_TOKEN / 1_000_000 * price


def request_cost(model: str, input_tokens: int) -> float:
    return input_tokens / 1_000_000 * JUDGE_PRICING[model]


class SystemOneClient:
    """Thin wrapper over the TypeSafe SDK. Output tokens are free; only input is billed."""

    def __init__(self, api_key: str | None = None, timeout: float = 60.0):
        import httpx2
        from typesafe_sdk import TypeSafeClient

        key = api_key or os.environ.get(API_KEY_ENV)
        if not key:
            raise ValueError(f"{API_KEY_ENV} is required for a paid scan")
        def set_user_agent(request: httpx2.Request) -> None:
            # The SDK overwrites constructor headers when it builds each request.
            request.headers["User-Agent"] = "OpenAI File Downloader, XaiImageApiFetch/1.0"

        self._client = TypeSafeClient(
            api_key=key,
            timeout=timeout,
            http_client=httpx2.Client(
                timeout=timeout, event_hooks={"request": [set_user_agent]}
            ),
        )

    def ask(self, *, model: str, state: Any, questions: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """Return {"model", "nouls", "input_tokens"}; raises on transport failure.

        `nouls` is the ledger's probability map. A noul question contributes its
        own key; a choice question contributes one key per option,
        `<question>=<option>`, holding that option's probability.
        """
        if any(spec.get("type", "noul") not in {"noul", "choice"} for spec in questions.values()):
            raise ValueError("ledger questions must use noul or choice")
        response = self.ask_typed(
            model=model, state=state,
            questions={key: {"type": "noul", **spec} for key, spec in questions.items()},
        )
        nouls: dict[str, float] = {}
        for key, spec in questions.items():
            answer = response["answers"][key]
            if spec.get("type") == "choice":
                for option in spec["criteria"]:
                    nouls[f"{key}={option}"] = float(answer["probabilities"][option])
                continue
            nouls[key] = answer["noul"]
        return {"model": response["model"], "nouls": nouls, "input_tokens": response["input_tokens"]}

    def ask_typed(
        self, *, model: str, state: Any, questions: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        """One request mixing noul, choice, and score questions.

        Each `questions[key]` is `{"type": "noul" | "choice" | "score",
        "instructions": ..., "criteria": ...}`. A noul's criteria is an
        optional `{"true": ..., "false": ...}` map, unlike `ask`'s bare
        instructions. A choice's criteria maps each option to its
        description; a score's criteria is an ordered list of level
        descriptions, one per level from zero.

        Returns `{"model", "answers", "input_tokens"}`. Each `answers[key]`
        keeps its question's `"type"` plus that type's fields: noul answers
        carry `"noul"`; choice answers carry `"choice"`, `"probabilities"`,
        `"confidence"`; score answers carry `"score"`, `"probabilities"`,
        `"confidence"`. Raises on transport failure or an unknown type.
        """
        cost_tracker.ensure_budget_available()
        for spec in questions.values():
            kind = spec["type"]
            if kind not in {"noul", "choice", "score"}:
                raise ValueError(f"unknown question type: {kind!r}")
        response = self._client.system_one(model=model, state=state, questions=questions)
        input_tokens = int(response.usage.input_tokens)
        # Bill before reading the answers: a malformed response still cost money.
        cost_tracker.record(model, input_tokens, 0, actual_cost=request_cost(model, input_tokens))

        answers: dict[str, Any] = {}
        for key, spec in questions.items():
            kind = spec["type"]
            if kind == "noul":
                answers[key] = {"type": "noul", "noul": float(response.nouls[key].noul)}
            elif kind == "choice":
                choice = response.choices[key]
                answers[key] = {
                    "type": "choice",
                    "choice": choice.choice,
                    "probabilities": dict(choice.probabilities),
                    "confidence": float(choice.confidence),
                }
            else:
                score = response.scores[key]
                answers[key] = {
                    "type": "score",
                    "score": float(score.score),
                    "probabilities": dict(score.probabilities),
                    "confidence": float(score.confidence),
                }
        return {"model": response.model, "answers": answers, "input_tokens": input_tokens}
