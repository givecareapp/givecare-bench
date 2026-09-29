"""Durable generation attempts replace in-memory-only transcript ownership."""

from __future__ import annotations

import fcntl
import json
import math
import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel

from invisiblebench.api.client import CostBudgetExceededError


class GenerationJournal:
    """One scenario's frozen inputs and ordered attempts. Never retry ambiguous calls."""

    def __init__(self, path: Path, contract: dict[str, Any]):
        self.path, self.contract = path, contract

    @staticmethod
    def inspect(path: Path) -> dict:
        content = path.read_bytes()
        if not content or not content.endswith(b"\n"):
            raise ValueError(f"incomplete generation journal: {path}")
        rows = [json.loads(line) for line in content.splitlines()]
        if set(rows[0]) != {"contract"}:
            raise ValueError(f"missing generation contract: {path}")
        completed, pending, cost = {}, None, 0.0
        for row in rows[1:]:
            if row.get("event") == "attempt":
                if pending is not None or row["key"] in completed:
                    raise ValueError(f"invalid generation attempt order: {path}")
                pending = row
            elif row.get("event") in {"response", "refused"}:
                if pending is None or row["key"] != pending["key"]:
                    raise ValueError(f"unbound generation response: {path}")
                if row["event"] == "response":
                    value = row["value"]
                    if value.get("cost_known") is False:
                        raise ValueError(f"unknown provider cost in {path}; no automatic resume")
                    amount = value.get("cost", 0.0)
                    if (
                        not isinstance(amount, (int, float))
                        or not math.isfinite(amount)
                        or amount < 0
                    ):
                        raise ValueError(f"invalid saved generation cost: {path}")
                    cost += amount
                    completed[row["key"]] = (pending["request"], value)
                pending = None
            elif row.get("event") == "error" and pending and row["key"] == pending["key"]:
                raise ValueError(
                    f"ambiguous generation attempt {row['key']}: {row['error']} in {path}; no automatic retry"
                )
            else:
                raise ValueError(f"unknown generation event: {path}")
        if pending is not None:
            raise ValueError(
                f"ambiguous generation attempt {pending['key']} in {path}; "
                "no saved response does not prove no provider charge. No automatic retry."
            )
        return {"contract": rows[0]["contract"], "completed": completed, "cost": cost}

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open("a+b")
        try:
            fcntl.flock(self.stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if self.stream.tell() == 0:
                self._append({"contract": self.contract})
            state = self.inspect(self.path)
            if state["contract"] != self.contract:
                raise ValueError(f"generation contract changed: {self.path}")
            self.completed: dict[str, tuple[dict[str, Any], dict[str, Any]]] = state["completed"]
            return self
        except BaseException:
            self.stream.close()
            raise

    def __exit__(self, *_):
        self.stream.close()

    def _append(self, value):
        self.stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False).encode() + b"\n")
        self.stream.flush()
        os.fsync(self.stream.fileno())

    async def call(
        self,
        key: str,
        request: dict[str, Any],
        operation: Callable[[], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        if key in self.completed:
            saved_request, value = self.completed[key]
            if saved_request != request:
                raise ValueError(f"generation request changed: {key}")
            return value
        self._append({"event": "attempt", "key": key, "request": request})
        try:
            value = await operation()
        except CostBudgetExceededError:
            # The transport reserves before dispatch. This exception proves no call was sent.
            self._append({"event": "refused", "key": key})
            raise
        except BaseException as exc:
            response = getattr(exc, "response", None)
            self._append(
                {
                    "event": "error",
                    "key": key,
                    "error": type(exc).__name__,
                    "detail": str(exc),
                    "response": (
                        response.model_dump(mode="json")
                        if isinstance(response, BaseModel)
                        else (
                            response.text
                            if isinstance(response, httpx.Response)
                            else getattr(exc, "doc", None)
                        )
                    ),
                }
            )
            raise
        self._append({"event": "response", "key": key, "value": value})
        self.completed[key] = (request, value)
        if value.get("cost_known") is False:
            raise ValueError("Provider response saved, but its cost is unknown; generation stopped")
        return value
