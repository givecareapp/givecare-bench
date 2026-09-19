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
        from typesafe_sdk import TypeSafeClient

        key = api_key or os.environ.get(API_KEY_ENV)
        if not key:
            raise ValueError(f"{API_KEY_ENV} is required for a paid scan")
        self._client = TypeSafeClient(api_key=key, timeout=timeout)

    def ask(self, *, model: str, state: Any, questions: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """Return {"model", "nouls", "input_tokens"}; raises on transport failure.

        `nouls` is the ledger's probability map. A noul question contributes its
        own key; a choice question contributes one key per option,
        `<question>=<option>`, holding that option's probability.
        """
        from typesafe_sdk import Choice, Noul, NoulCriteria

        cost_tracker.ensure_budget_available()
        built: dict[str, Any] = {}
        for key, spec in questions.items():
            if spec.get("type") == "choice":
                built[key] = Choice(instructions=spec["instructions"], criteria=spec["criteria"])
                continue
            criteria = spec.get("criteria")
            built[key] = Noul(
                instructions=spec["instructions"],
                criteria=NoulCriteria(**criteria) if criteria else None,
            )
        response = self._client.system_one(model=model, state=state, questions=built)
        input_tokens = int(response.usage.input_tokens)
        # Bill before reading the answers: a malformed response still cost money.
        cost_tracker.record(model, input_tokens, 0, actual_cost=request_cost(model, input_tokens))
        nouls: dict[str, float] = {}
        for key, spec in questions.items():
            if spec.get("type") == "choice":
                probabilities = dict(response.choices[key].probabilities)
                for option in spec["criteria"]:
                    nouls[f"{key}={option}"] = float(probabilities[option])
                continue
            nouls[key] = float(response.nouls[key].noul)
        return {"model": response.model, "nouls": nouls, "input_tokens": input_tokens}

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
        from typesafe_sdk import Choice, Noul, NoulCriteria, Score

        cost_tracker.ensure_budget_available()
        built: dict[str, Any] = {}
        for key, spec in questions.items():
            kind = spec["type"]
            if kind == "noul":
                criteria = spec.get("criteria")
                built[key] = Noul(
                    instructions=spec.get("instructions"),
                    criteria=NoulCriteria(**criteria) if criteria else None,
                )
            elif kind == "choice":
                built[key] = Choice(
                    instructions=spec.get("instructions"), criteria=spec["criteria"]
                )
            elif kind == "score":
                built[key] = Score(
                    instructions=spec.get("instructions"), criteria=spec["criteria"]
                )
            else:
                raise ValueError(f"unknown question type: {kind!r}")

        response = self._client.system_one(model=model, state=state, questions=built)
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
