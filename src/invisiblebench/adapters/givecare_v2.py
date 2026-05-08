#!/usr/bin/env python3
"""GiveCare V2 system harness for InvisibleBench.

Runs benchmark scenarios against the active gc-sms Convex HTTP contract:

- `/api/admin` action `harnessHealth`
- `/api/admin` action `runBenchmarkTurn`

No local gc-sms package paths, bridge bundles, or legacy CLI layout are used.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import jsonlines
import requests
from dotenv import load_dotenv

from invisiblebench.utils.benchmark_inventory import (
    collect_scenario_paths,
    get_private_confidential_dir,
    get_project_root,
    scenario_category_for_path,
)

PROJECT_ROOT = get_project_root()
load_dotenv(PROJECT_ROOT / ".env")

PROVIDER_NAME = "givecare"
PROVIDER_VERSION = "2.0.0"
MODEL_NAME = "GiveCare V2 (Mira)"
MODEL_ID = "givecare/mira-v2"


class GiveCareV2Provider:
    """HTTP adapter for the active gc-sms V2 benchmark contract."""

    def __init__(
        self,
        site_url: str | None = None,
        admin_key: str | None = None,
        timeout_s: float = 120.0,
    ):
        self.site_url = (site_url or os.environ.get("GIVECARE_CONVEX_SITE_URL") or os.environ.get("CONVEX_SITE_URL") or "").rstrip("/")
        self.admin_key = admin_key or os.environ.get("GIVECARE_BENCH_KEY") or os.environ.get("ORG_ADMIN_KEY") or ""
        self.timeout_s = timeout_s
        if not self.site_url:
            raise RuntimeError("GIVECARE_CONVEX_SITE_URL or CONVEX_SITE_URL is required")
        if not self.admin_key:
            raise RuntimeError("GIVECARE_BENCH_KEY or ORG_ADMIN_KEY is required")

    def close(self) -> None:
        pass

    def healthcheck(self) -> dict[str, Any]:
        response = self._admin("harnessHealth")
        result = response.get("result")
        return result if isinstance(result, dict) else response

    def run_turn(
        self,
        *,
        scenario_id: str,
        user_message: str,
        previous_messages: list[dict[str, str]],
    ) -> str:
        response = self._admin(
            "runBenchmarkTurn",
            scenarioId=scenario_id,
            userMessage=user_message,
            previousMessages=previous_messages,
        )
        result = response.get("result")
        if not isinstance(result, dict) or not isinstance(result.get("replyText"), str):
            raise RuntimeError(f"Invalid runBenchmarkTurn response: {response!r}")
        return result["replyText"]

    def _admin(self, action: str, **params: Any) -> dict[str, Any]:
        resp = requests.post(
            f"{self.site_url}/api/admin",
            json={"action": action, **params},
            headers={"Authorization": f"Bearer {self.admin_key}"},
            timeout=self.timeout_s,
        )
        try:
            body = resp.json()
        except ValueError:
            body = {"raw": resp.text}
        if resp.status_code >= 400:
            raise RuntimeError(f"{action} failed with HTTP {resp.status_code}: {body}")
        if isinstance(body, dict):
            return body
        raise RuntimeError(f"{action} returned non-object JSON: {body!r}")


def load_scenario(scenario_path: str) -> dict[str, Any]:
    with open(scenario_path) as f:
        return json.load(f)


def get_category_from_path(scenario_path: Path) -> str:
    return scenario_category_for_path(
        scenario_path,
        get_private_confidential_dir(get_project_root()),
    )


def get_scenario_title(scenario: dict[str, Any], scenario_path: Path) -> str:
    if isinstance(scenario.get("title"), str):
        return scenario["title"]
    scenario_id = str(scenario.get("scenario_id") or scenario_path.stem)
    return scenario_id.replace("_", " ").title()


def get_turns_from_scenario(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    if "sessions" in scenario:
        turns: list[dict[str, Any]] = []
        for session in scenario["sessions"]:
            turns.extend(session.get("turns", []))
        return turns
    return scenario.get("turns", [])


def run_scenario(
    provider: GiveCareV2Provider,
    scenario_path: str,
    output_dir: Path,
    verbose: bool = False,
) -> tuple[Path, dict[str, Any]]:
    scenario = load_scenario(scenario_path)
    scenario_id = str(scenario.get("scenario_id") or Path(scenario_path).stem)
    turns = get_turns_from_scenario(scenario)

    if verbose:
        print(f"\n=== {get_scenario_title(scenario, Path(scenario_path))} ===")

    transcript: list[dict[str, Any]] = []
    history: list[dict[str, str]] = []

    from invisiblebench.evaluation.branching import resolve_branch

    prev_assistant_msg: str | None = None
    for turn in turns:
        turn_num = turn["turn_number"]
        user_msg, branch_id = resolve_branch(turn, prev_assistant_msg)
        user_entry: dict[str, Any] = {"turn": turn_num, "role": "user", "content": user_msg}
        if branch_id is not None:
            user_entry["branch_id"] = branch_id
        transcript.append(user_entry)

        if verbose:
            branch_label = f" [branch:{branch_id}]" if branch_id else ""
            print(f"[{turn_num}] User{branch_label}: {user_msg}")

        reply = provider.run_turn(
            scenario_id=scenario_id,
            user_message=user_msg,
            previous_messages=history,
        )
        transcript.append({"turn": turn_num, "role": "assistant", "content": reply})
        history.extend([
            {"role": "user", "text": user_msg},
            {"role": "assistant", "text": reply},
        ])
        prev_assistant_msg = reply

        if verbose:
            print(f"    Mira: {reply[:100]}{'...' if len(reply) > 100 else ''}")

    output_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = output_dir / f"givecare_v2_{scenario_id}.jsonl"
    with jsonlines.open(transcript_path, "w") as writer:
        writer.write_all(transcript)

    return transcript_path, scenario


def get_scenarios(
    scenarios_dir: Path,
    category_filter: list[str] | None = None,
    include_confidential: bool = False,
) -> list[Path]:
    del scenarios_dir
    return collect_scenario_paths(
        get_project_root(),
        category_filter=category_filter,
        include_confidential=include_confidential,
    )
