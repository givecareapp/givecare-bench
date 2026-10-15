"""The bench command: export Inspect logs, scans, evidence reads, and run storage."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from datetime import UTC, datetime
from pathlib import Path

from invisiblebench.api.typesafe import DEFAULT_JUDGE_MODEL
from invisiblebench.cli import agent_commands, scan
from invisiblebench.cli.agent_commands import emit_json
from invisiblebench.utils.manifest import RUN_DIRECTORY_TIME_FORMAT


def _run_runs(*, limit, offset, json_output):
    records = sorted(
        agent_commands.list_runs(agent_commands._runs_dir()),
        key=lambda r: r["date"] or "",
        reverse=True,
    )
    offset, limit = max(offset, 0), 25 if limit is None or limit < 0 else limit
    selected = [
        {key: value for key, value in r.items() if key != "manifests"}
        for r in records[offset : offset + limit]
    ]
    if json_output:
        emit_json("runs", {"total": len(records), "limit": limit, "offset": offset, "runs": selected})
        return 0
    if not selected:
        print("No runs found.")
    for r in selected:
        names = ", ".join(r["models"][:2]) + (f" +{len(r['models']) - 2}" if len(r["models"]) > 2 else "")
        print(
            "  ".join(
                [
                    r["date"] or "unknown",
                    r["id"],
                    names or "-",
                    f"{r['scenarios']} scenarios",
                    r["artifact_state"],
                    "results" if r["has_results"] else "no results",
                ]
            )
        )
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", dest="json_output", action="store_true")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser(
        "doctor",
        help="Check credentials and run storage; creates runs dir if missing and writes a temporary probe",
    )
    get = sub.add_parser("get", help="Read one run")
    get.add_argument("run_id")
    jury = sub.add_parser("jury", help="Regenerate a Jury Card from saved evidence")
    jury.add_argument("run_id")
    runs = sub.add_parser("runs", help="List runs")
    runs.add_argument("--limit", type=int, default=25)
    runs.add_argument("--offset", type=int, default=0)
    explain = sub.add_parser("explain", help="Read a verdict and its exact evidence")
    explain.add_argument("model")
    explain.add_argument("scenario")
    explain.add_argument("--check")
    explain.add_argument("--failures", action="store_true")
    explain.add_argument("--scan")
    explain.add_argument("--leaderboard")
    questions = sub.add_parser(
        "questions", help="Inspect probabilities and verdict-relevant uncertainty"
    )
    questions.add_argument("run_id")
    questions.add_argument("--limit", type=int)
    compare = sub.add_parser("compare", help="Compare two current-format saved scans")
    compare.add_argument("--old", required=True)
    compare.add_argument("--new", required=True)
    compare.add_argument(
        "--expectations",
        type=Path,
        help="Frozen research expectations JSONL; read-only agreement report",
    )
    leaderboard = sub.add_parser("leaderboard", help="Leaderboard status, candidate generation, QA")
    leaderboard.add_argument("action", choices=["status", "generate", "qa"])
    leaderboard.add_argument("--scan", type=Path, help="Scan bundle directory (generate, qa)")
    leaderboard.add_argument("--candidate", type=Path, help="Candidate path (qa required; generate output)")
    scan.configure(sub.add_parser("scan", help="Plan, execute, or rejudge a frozen scan"))
    export = sub.add_parser(
        "export",
        help="Write a judge-ready run directory from Inspect logs (see invisiblebench.inspect_task)",
    )
    export.add_argument("logs", nargs="+", type=Path)
    export.add_argument("--output", type=Path)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    json_output = args.json_output
    if args.command == "scan":
        return scan.scan_command(args)
    if args.command == "doctor":
        return agent_commands._run_doctor(json_output=json_output)
    if args.command == "get":
        return agent_commands._run_get(args.run_id, json_output=json_output)
    if args.command == "runs":
        return _run_runs(limit=args.limit, offset=args.offset, json_output=json_output)
    if args.command == "jury":
        from invisiblebench.jury_card import write_jury_card

        try:
            run = agent_commands._load_run_metadata(args.run_id)
            if run is None:
                raise ValueError(f"run not found: {args.run_id}")
            card = write_jury_card(Path(run["path"]))
        except (OSError, ValueError, KeyError) as exc:
            if json_output:
                emit_json("jury", error=str(exc))
            else:
                print(str(exc), file=sys.stderr)
            return 1
        if json_output:
            emit_json("jury", {"path": str(card)})
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
    if args.command == "leaderboard":
        if args.action in {"generate", "qa"}:
            from invisiblebench.scoring import generate_leaderboard, validate_leaderboard

            if args.scan is None or (args.action == "qa" and args.candidate is None):
                print("leaderboard generate|qa needs --scan (qa also --candidate)", file=sys.stderr)
                return 2
            if args.action == "generate":
                try:
                    print(generate_leaderboard(args.scan, args.candidate))
                except (OSError, ValueError) as exc:
                    print(str(exc), file=sys.stderr)
                    return 1
                return 0
            errors = validate_leaderboard(args.scan, args.candidate)
            for error in errors:
                print(error, file=sys.stderr)
            if not errors:
                print("QA passed")
            return int(bool(errors))
        from invisiblebench.cli.health import run_health

        return run_health(json_output=json_output)
    if args.command == "export":
        from invisiblebench.inspect_export import export_run

        output = args.output or Path("results") / datetime.now(UTC).strftime(
            RUN_DIRECTORY_TIME_FORMAT
        )
        try:
            export_run(args.logs, output)
        except (OSError, ValueError, KeyError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        summary = json.loads((output / "transcript_run.json").read_bytes())
        print(f"{summary['status']}: {summary['transcript_count']}/{summary['expected_transcripts']}"
              f" transcripts, {summary['error_count']} errors, {summary['missing_count']} missing")
        print("Next: " + shlex.join(["uv", "run", "bench", "scan", "plan", str(output),
                                      "--llm-model", DEFAULT_JUDGE_MODEL]))
        return 0 if summary["status"] == "complete" else 1
    build_parser().print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
