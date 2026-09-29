#!/usr/bin/env python3
"""Freeze constructed validation cases and print a native scan plan. No model calls."""

import argparse
import json
from pathlib import Path

from invisiblebench.validation_controls import plan_controls


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New UTC run directory")
    args = parser.parse_args()
    plan = plan_controls(args.output)
    print(
        json.dumps(
            {
                "plan": str(args.output / "scan_plan.json"),
                "judge": plan.judge.model,
                "conversations": len(plan.transcripts),
                "checks": len(plan.checks),
                "requests": plan.planned_requests,
                "judgments": plan.planned_judgments,
                "estimated_cost_usd": plan.estimated_cost_usd,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
