"""Read criteria, evidence, and decisions from a retained scan bundle."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from invisiblebench.judge import load_scan
from invisiblebench.models.scan import Verdict
from invisiblebench.scoring import SCHEMA_VERSION
from invisiblebench.utils.benchmark_inventory import get_project_root


def explain_command(args: Any) -> int:
    json_output = bool(getattr(args, "json_output", False))
    try:
        if getattr(args, "scan", None):
            bundle = Path(args.scan)
        else:
            root = get_project_root()
            leaderboard = Path(
                getattr(args, "leaderboard", None) or root / "data/leaderboard/leaderboard.json"
            )
            payload = json.loads(leaderboard.read_bytes())
            if payload.get("schema") != SCHEMA_VERSION:
                raise ValueError("no current published scan; pass --scan with a scan bundle")
            bundle = root / payload["scan_metadata"]["source_artifact"]
        plan, records = load_scan(bundle)
        checks = {check.id: check for check in plan.checks}
        sources = {(ref.model_id, ref.scenario_id): ref for ref in plan.transcripts}
        data = []
        for record in records:
            source = sources[record.model_id, record.scenario_id]
            if (
                args.model.lower() not in source.model_id.lower()
                and args.model.lower() not in source.model.lower()
            ):
                continue
            if args.scenario.lower() not in source.scenario_id.lower():
                continue
            if getattr(args, "check", None) and args.check.lower() not in record.check_id.lower():
                continue
            if getattr(args, "failures", False) and record.verdict not in {
                Verdict.FAIL,
                Verdict.UNCLEAR,
            }:
                continue
            data.append(
                {
                    **record.model_dump(mode="json"),
                    "model": source.model,
                    "category": source.category,
                    "criterion": checks[record.check_id].criteria,
                    "judge_settings": plan.judge.model_dump(mode="json"),
                    "transcript": str(bundle / source.path),
                }
            )
        if not data:
            raise ValueError("no judgments match the model, scenario, and check filters")
    except (OSError, ValueError, KeyError) as exc:
        if json_output:
            print(json.dumps({"status": "error", "command": "explain", "error": str(exc)}))
        else:
            print(f"error: {exc}")
        return 1
    if json_output:
        print(json.dumps({"status": "ok", "command": "explain", "data": data}, indent=2))
        return 0
    for item in data:
        print(f"{item['model']} × {item['scenario_id']} — {item['check_id']}: {item['verdict']}")
        print(f"  Criterion: {item['criterion']}")
        print(f"  Decision rationale: {item['rationale']}")
        for evidence in item["evidence"]:
            print(f"  {evidence['role']} turn {evidence['turn']}: {evidence['quote']}")
        if item["error"]:
            print(f"  Unfinished request: {item['error']} — {item['error_detail']}")
        print(f"  Judge: {item['judge_settings']['model']}; observed: {item['judge']}")
        print(f"  Transcript: {item['transcript']}")
    return 0
