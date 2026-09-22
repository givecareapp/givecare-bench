"""Plan, execute, and rejudge scans through the installed bench command."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from invisiblebench.api.client import CostBudgetExceededError
from invisiblebench.api.typesafe import DEFAULT_JUDGE_MODEL
from invisiblebench.judge import PLAN_FILE, load_scan, plan_rejudge, plan_scan, run_scan
from invisiblebench.jury_card import write_jury_card


def configure(parser):
    commands = parser.add_subparsers(dest="scan_action", required=True)
    plan = commands.add_parser("plan", help="Freeze transcript sources; no model calls")
    plan.add_argument("run_dirs", nargs="+", type=Path)
    plan.add_argument("--output", type=Path)
    plan.add_argument("--llm-model", default=DEFAULT_JUDGE_MODEL)
    plan.add_argument("--limit", type=int)
    plan.add_argument("--filter")
    rejudge = commands.add_parser("rejudge", help="Plan a new run over exact frozen evidence")
    rejudge.add_argument("frozen", type=Path)
    rejudge.add_argument("--output", type=Path, required=True)
    rejudge.add_argument("--llm-model", default=DEFAULT_JUDGE_MODEL)
    run = commands.add_parser("run", help="Resume a frozen plan with an explicit ceiling")
    run.add_argument("--plan", required=True, type=Path)
    run.add_argument("--max-cost-usd", required=True, type=float)


def scan_command(args):
    try:
        if args.scan_action == "run":
            if args.plan.name != PLAN_FILE:
                raise ValueError(f"--plan must name the saved {PLAN_FILE}")
            judgments = run_scan(args.plan.parent, max_cost_usd=args.max_cost_usd)
            answers = load_scan(args.plan.parent, complete=True)[1]
            print(
                f"Complete: {len(judgments)} judgments from {len(answers)} requests; "
                f"cost: ${sum(a.cost_usd for a in answers):.6f}"
            )
            print(f"Jury Card: {write_jury_card(args.plan.parent)}")
        else:
            if args.scan_action == "rejudge":
                result = plan_rejudge(args.frozen, args.output, model=args.llm_model)
            else:
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
                f"Transcripts: {len(result.transcripts)}; checks: {len(result.checks)}; "
                f"requests: {result.planned_requests}; judgments: {result.planned_judgments}"
            )
            print(f"Estimated cost envelope: {result.estimated_cost_usd} USD")
    except KeyboardInterrupt:
        print("Interrupted. Saved answers are retained; resume the same plan.", file=sys.stderr)
        return 130
    except CostBudgetExceededError as exc:
        print(str(exc), file=sys.stderr)
        return 4
    except (OSError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    configure(parser)
    return scan_command(parser.parse_args(argv))
