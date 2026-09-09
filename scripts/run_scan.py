#!/usr/bin/env python3
"""Plan a portable scan bundle, or run its pending judgments."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from invisiblebench.api.client import DEFAULT_JUDGE_MODEL, CostBudgetExceededError  # noqa: E402
from invisiblebench.judge import PLAN_FILE, plan_scan, run_scan  # noqa: E402
from invisiblebench.jury_card import write_jury_card  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="Freeze inputs and estimate cost; no model calls.")
    plan.add_argument("run_dirs", nargs="+", type=Path)
    plan.add_argument("--output", type=Path, help="New scan directory. A single source is frozen in place by default.")
    plan.add_argument("--llm-model", default=DEFAULT_JUDGE_MODEL)
    plan.add_argument("--limit", type=int)
    plan.add_argument("--filter")
    run = commands.add_parser("run", help="Resume a saved plan; completed judgments are retained.")
    run.add_argument("--plan", required=True, type=Path)
    run.add_argument("--max-cost-usd", required=True, type=float)
    args = parser.parse_args()
    try:
        if args.command == "plan":
            if args.output is None:
                if len(args.run_dirs) != 1:
                    raise ValueError("multiple source runs require --output")
                args.output = args.run_dirs[0]
            result = plan_scan(
                args.run_dirs,
                args.output,
                judge_model=args.llm_model,
                limit=args.limit,
                filename_filter=args.filter,
            )
            print(f"Plan: {args.output / PLAN_FILE}")
            print(
                f"Transcripts: {len(result.transcripts)}; checks: {len(result.checks)}; calls: {result.planned_calls}"
            )
            print(f"Estimated cost envelope: {result.estimated_cost_usd} USD")
        else:
            if args.plan.name != PLAN_FILE:
                raise ValueError(f"--plan must name the saved {PLAN_FILE}")
            records = run_scan(args.plan.parent, max_cost_usd=args.max_cost_usd)
            print(
                f"Complete: {sum(record.error is None for record in records)} judgments; recorded cost: "
                f"{sum(record.cost_usd for record in records):.6f} USD"
            )
            print(f"Jury Card: {write_jury_card(args.plan.parent)}")
    except KeyboardInterrupt:
        print(
            "Interrupted. Completed judgments are saved. Run the same plan to resume.",
            file=sys.stderr,
        )
        return 130
    except CostBudgetExceededError as exc:
        print(str(exc), file=sys.stderr)
        return 4
    except (OSError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
