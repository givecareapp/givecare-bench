#!/usr/bin/env python3
"""Replay saved judge responses through the current engine without API calls.

This checks request drift, decision parsing, evidence validation, and aggregation.
It does not measure model accuracy or repeat the model's inference.
A frozen scan must use the current contract and retain every raw judge response.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from invisiblebench.evaluation.mode_engine import ModeEngine  # noqa: E402
from invisiblebench.utils.io import load_jsonl  # noqa: E402
from invisiblebench.utils.prompt_hash import prompt_template_hash  # noqa: E402
from invisiblebench.version import SCANNED_ROW_CONTRACT_VERSION  # noqa: E402


class ReplayClient:
    def __init__(self, row: dict[str, Any]):
        self.results = {result["prompt_hash"]: result for result in row["mode_results"]}

    def call_model(self, **kwargs: Any) -> dict[str, Any]:
        key = prompt_template_hash(kwargs["messages"][0]["content"])
        saved = self.results[key]
        input_hash = hashlib.sha256(
            json.dumps(kwargs["messages"], ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest()
        if input_hash != saved["extra"]["input_sha256"]:
            raise ValueError("judge input changed")
        judge = saved["judge"]
        for field in ("model", "temperature", "max_tokens"):
            if kwargs[field] != judge[field]:
                raise ValueError(f"judge {field} changed")
        return {"response": saved["extra"]["raw_response"],
                "raw": {"model": judge["resolved_model"], "provider": judge["provider"]}}


def compare_row(stored: dict[str, Any], rescored: list[dict[str, Any]]) -> list[str]:
    old = {result["mode_id"]: result for result in stored["mode_results"]}
    new = {result["mode_id"]: result for result in rescored}
    return [check for check in sorted(old.keys() | new.keys()) if old.get(check) != new.get(check)]


def replay_row(row: dict[str, Any]) -> list[str]:
    if row.get("contract_version") != SCANNED_ROW_CONTRACT_VERSION:
        raise ValueError("Frozen scan uses a retired contract. Create a current-contract freeze.")
    models = {result["judge"]["model"] for result in row["mode_results"]}
    if len(models) != 1:
        raise ValueError("Frozen scan must use one judge model")
    engine = ModeEngine(llm_api_client=ReplayClient(row), llm_model=models.pop())
    output = engine.evaluate(load_jsonl(Path(row["transcript_path"])), {})
    diffs = compare_row(row, output.mode_results)
    for key, value in output.to_dict().items():
        if key != "mode_results" and row.get(key) != value:
            diffs.append(key)
    return diffs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen", required=True, type=Path)
    args = parser.parse_args()
    try:
        rows = load_jsonl(args.frozen)
        if not rows:
            raise ValueError("Frozen scan is empty")
        diffs = {f"{row['model_id']}/{row['scenario_id']}": replay_row(row) for row in rows}
    except (OSError, ValueError, KeyError) as exc:
        print(f"Cannot replay: {exc}", file=sys.stderr)
        return 2
    changed = {key: value for key, value in diffs.items() if value}
    if changed:
        print(json.dumps(changed, indent=2))
        return 1
    print(f"CLEAN: {len(rows)} rows replayed from saved responses; no API calls.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
