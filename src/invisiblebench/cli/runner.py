"""The bench command: generation, scans, evidence reads, and run storage."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from rich.table import Table

from invisiblebench._agent_cli import confirm_or_abort, emit_json
from invisiblebench.cli import agent_commands, run_command, scan
from invisiblebench.cli._console import make_console
from invisiblebench.models.config import MODELS_FULL
from invisiblebench.utils.manifest import RUN_DIRECTORY_TIME_FORMAT


def _collect_runs():
    from invisiblebench.cli.archive import list_runs

    runs = sorted(
        list_runs(agent_commands._runs_dir()), key=lambda r: r["date"] or datetime.min, reverse=True
    )
    return [
        {
            "id": r["name"],
            "date": r["date"].isoformat(timespec="seconds") + "Z" if r["date"] else None,
            "models": r["models"],
            "scenarios": r["scenarios"],
            "size_mb": round(r["size_mb"], 2),
            "has_results": r["has_results"],
            "artifact_state": r["artifact_state"],
            "jury_card": r["jury_card"],
        }
        for r in runs
    ]


def _run_runs(*, limit, offset, json_output, out_path=None):
    records = _collect_runs()
    offset, limit = max(offset, 0), 25 if limit is None or limit < 0 else limit
    selected = records[offset : offset + limit]
    if json_output or out_path:
        return agent_commands._emit_or_write_json(
            command="runs",
            data={"total": len(records), "limit": limit, "offset": offset, "runs": selected},
            record_count=len(selected),
            out_path=out_path,
        )
    if not selected:
        print("No runs found.")
        return 0
    table = Table(title="Benchmark Runs")
    for column in ("Date", "Run ID", "Models", "Scenarios", "Size", "State", "Results"):
        table.add_column(column)
    for r in selected:
        names = ", ".join(r["models"][:2])
        if len(r["models"]) > 2:
            names += f" +{len(r['models']) - 2}"
        table.add_row(
            r["date"] or "unknown",
            r["id"],
            names or "-",
            str(r["scenarios"] or "-"),
            f"{r['size_mb']:.1f}MB",
            r["artifact_state"],
            "yes" if r["has_results"] else "no",
        )
    make_console().print(table)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json", "--format", dest="json_output", action="store_const", const="json"
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser(
        "doctor",
        help="Check credentials and run storage; creates runs dir if missing and writes a temporary probe",
    )
    get = sub.add_parser("get", help="Read one run")
    get.add_argument("run_id")
    get.add_argument("--out")
    jury = sub.add_parser("jury", help="Regenerate a Jury Card from saved evidence")
    jury.add_argument("run_id")
    health = sub.add_parser("health", help="Check the owner leaderboard")
    health.add_argument("--verbose", "-v", action="store_true")
    archive = sub.add_parser("archive", help="Move explicitly selected old runs to the archive")
    archive.add_argument("--before")
    archive.add_argument("--keep", type=int)
    archive.add_argument("--list", action="store_true", dest="list_runs")
    archive.add_argument("--dry-run", action="store_true")
    archive.add_argument("--yes", action="store_true", dest="archive_yes")
    runs = sub.add_parser("runs", help="List runs")
    runs.add_argument("--limit", type=int, default=25)
    runs.add_argument("--offset", type=int, default=0)
    runs.add_argument("--out")
    explain = sub.add_parser("explain", help="Read a verdict and its exact evidence")
    explain.add_argument("model")
    explain.add_argument("scenario")
    explain.add_argument("--check")
    explain.add_argument("--failures", action="store_true")
    explain.add_argument("--scan")
    explain.add_argument("--leaderboard")
    questions = sub.add_parser("questions", help="Inspect unresolved question probabilities")
    questions.add_argument("run_id")
    questions.add_argument("--limit", type=int)
    compare = sub.add_parser("compare", help="Compare two current-format saved scans")
    compare.add_argument("--old", required=True)
    compare.add_argument("--new", required=True)
    leaderboard = sub.add_parser("leaderboard", help="Read leaderboard status")
    leaderboard.add_argument("action", choices=["status"])
    leaderboard.add_argument("--verbose", "-v", action="store_true")
    leaderboard.add_argument("--out")
    scan.configure(sub.add_parser("scan", help="Plan, execute, or rejudge a frozen scan"))
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", "-y", action="store_true")
    parser.add_argument("--max-cost-usd", type=float)
    parser.add_argument("--category", "-c")
    parser.add_argument("--scenario", "-s")
    parser.add_argument("--parallel", "-p", type=int)
    parser.add_argument("--scenario-parallel", type=int, default=1)
    parser.add_argument("--models", "-m")
    parser.add_argument("--confidential", action="store_true")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    json_output = bool(args.json_output)
    if args.command == "scan":
        return scan.scan_command(args)
    if args.command == "doctor":
        return agent_commands._run_doctor(json_output=json_output)
    if args.command == "get":
        return agent_commands._run_get(args.run_id, json_output=json_output, out_path=args.out)
    if args.command == "runs":
        return _run_runs(
            limit=args.limit, offset=args.offset, json_output=json_output, out_path=args.out
        )
    if args.command == "jury":
        from invisiblebench.jury_card import write_jury_card

        try:
            run = agent_commands._load_run_metadata(args.run_id)
            if run is None:
                raise ValueError(f"run not found: {args.run_id}")
            card = write_jury_card(Path(run["path"]))
        except (OSError, ValueError, KeyError) as exc:
            if json_output:
                emit_json(status="error", command="jury", error=str(exc))
            else:
                print(str(exc), file=sys.stderr)
            return 1
        if json_output:
            emit_json(command="jury", data={"path": str(card)})
        else:
            print(card)
        return 0
    if args.command == "explain":
        from invisiblebench.cli.explain import explain_command

        return explain_command(args)
    if args.command == "questions":
        from invisiblebench.cli.questions import questions_command

        return questions_command(args)
    if args.command == "compare":
        from invisiblebench.cli.compare import compare_command

        return compare_command(args)
    if args.command == "health":
        from invisiblebench.cli.health import run_health

        return run_health(verbose=args.verbose, json_output=json_output)
    if args.command == "leaderboard":
        if json_output or args.out:
            return agent_commands._run_leaderboard_status_json(out_path=args.out)
        from invisiblebench.cli.leaderboard import run_leaderboard

        return run_leaderboard(action=args.action, verbose=args.verbose)
    if args.command == "archive":
        from invisiblebench.cli.archive import run_archive

        if args.list_runs:
            return _run_runs(limit=sys.maxsize, offset=0, json_output=json_output)
        if (args.before is None) == (args.keep is None):
            print("archive: pass one of --before YYYYMMDD or --keep N", file=sys.stderr)
            return 2
        if not args.dry_run:
            prompt = (
                f"archive runs older than {args.before}"
                if args.before
                else f"archive runs keeping {args.keep} most recent"
            )
            confirm_or_abort(prompt, yes=args.yes or args.archive_yes)
        return run_archive(before=args.before, keep=args.keep, dry_run=args.dry_run)

    models = [m.model_dump() for m in MODELS_FULL]
    if args.full and args.models:
        print("--full runs the whole roster; drop it to run only -m SPEC.", file=sys.stderr)
        return 1
    if not args.full:
        if not args.models:
            print("No model selected. Use --full or -m SPEC.\n")
            for i, model in enumerate(models, 1):
                print(f"{i:>2}. {model['name']:<24} {model['id']}")
            return 1
        try:
            indices = run_command.resolve_models(args.models, models)
            if not indices:
                raise ValueError(f"No models match '{args.models}'")
            models = [models[i] for i in indices]
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        make_console().print(f"Models: {', '.join(m['name'] for m in models)}")
    return run_command.run_benchmark(
        models=models,
        output_dir=args.output
        or Path("results") / datetime.now(UTC).strftime(RUN_DIRECTORY_TIME_FORMAT),
        dry_run=args.dry_run,
        auto_confirm=args.yes,
        category_filter=(
            [c.strip().lower() for c in args.category.split(",")] if args.category else None
        ),
        scenario_filter=(
            [s.strip().lower() for s in args.scenario.split(",")] if args.scenario else None
        ),
        parallel=args.parallel,
        scenario_parallel=args.scenario_parallel,
        include_confidential=args.confidential,
        max_cost_usd=args.max_cost_usd,
    )


if __name__ == "__main__":
    raise SystemExit(main())
