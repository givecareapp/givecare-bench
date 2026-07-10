#!/usr/bin/env python3
"""InvisibleBench CLI runner."""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

from dotenv import load_dotenv

from invisiblebench._agent_cli import (
    confirm_or_abort,
)
from invisiblebench.cli._console import make_console
from invisiblebench.cli.agent_commands import (
    _run_doctor,
    _run_get,
    _run_leaderboard_status_json,
)
from invisiblebench.cli.result_helpers import (
    _compute_success as _compute_success,  # re-exported: tests import from this module
)
from invisiblebench.harnesses import adapter_name, is_mode_implemented, resolve_harness_mode
from invisiblebench.models.config import MODELS_FULL as CONFIG_MODELS_FULL

try:
    from rich.table import Table  # noqa: F401

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

logger = logging.getLogger(__name__)

# Shared NO_COLOR/isatty-honoring Console factory (returns None without rich).
Console = make_console

load_dotenv()

# Cost-estimate constants (TOKEN_ESTIMATES, SCORER_*) live in
# invisiblebench.cli.run_command, which owns estimate_cost().

MODELS_FULL = [model.model_dump() for model in CONFIG_MODELS_FULL]


from invisiblebench.cli.result_helpers import (  # noqa: E402,F401
    _make_error_result as _make_error_result,  # re-exported: tests import from this module
)
from invisiblebench.cli.run_command import (  # noqa: E402,F401
    _print_audit_summary as _print_audit_summary,
)
from invisiblebench.cli.run_command import (  # noqa: E402,F401
    _scenario_matches_filter as _scenario_matches_filter,  # re-exported: tests use this module
)
from invisiblebench.cli.run_command import (  # noqa: E402,F401
    _write_run_audit as _write_run_audit,
)
from invisiblebench.cli.run_command import (  # noqa: E402,F401
    estimate_cost as estimate_cost,
)
from invisiblebench.cli.run_command import (  # noqa: E402,F401
    get_scenarios as get_scenarios,
)
from invisiblebench.cli.run_command import (  # noqa: E402,F401
    resolve_models as resolve_models,
)
from invisiblebench.cli.run_command import (  # noqa: E402,F401
    run_benchmark as run_benchmark,
)
from invisiblebench.cli.run_command import (  # noqa: E402,F401
    run_givecare_eval as run_givecare_eval,
)

# ---------- agent-friendly helpers ----------
# Note: _collect_runs and _run_runs stay in this module (tests monkeypatch them here)


def _collect_runs() -> list[dict[str, Any]]:
    """Return run records sorted newest first, with narrow fields."""
    from invisiblebench.cli.agent_commands import _runs_dir
    from invisiblebench.cli.archive import list_runs

    results_dir = _runs_dir()
    if not results_dir.exists():
        return []
    runs = list_runs(results_dir)
    runs.sort(key=lambda r: r.get("date") or datetime.min, reverse=True)
    records: list[dict[str, Any]] = []
    for r in runs:
        records.append(
            {
                "id": r["name"],
                "date": r["date"].strftime("%Y-%m-%d") if r.get("date") else None,
                "models": r.get("models", []),
                "scenarios": r.get("scenarios", 0),
                "size_mb": round(r.get("size_mb", 0.0), 2),
                "has_results": r.get("has_results", False),
                "artifact_state": r.get("artifact_state", "unknown"),
            }
        )
    return records


def _run_runs(
    *,
    limit: int,
    offset: int,
    json_output: bool,
    out_path: str | None = None,
) -> int:
    """Handle `bench runs` with optional --limit/--offset/--json/--out."""
    from invisiblebench.cli.agent_commands import _emit_or_write_json

    records = _collect_runs()
    total = len(records)
    if offset < 0:
        offset = 0
    if limit is None or limit < 0:
        limit = 25
    sliced = records[offset : offset + limit]

    if json_output or out_path:
        payload = {
            "total": total,
            "limit": limit,
            "offset": offset,
            "runs": sliced,
        }
        return _emit_or_write_json(
            command="runs",
            data=payload,
            record_count=len(sliced),
            out_path=out_path,
        )

    if not sliced:
        print("No runs found.")
        return 0

    if RICH_AVAILABLE:
        console = Console()
        table = Table(title=f"Benchmark Runs ({offset + 1}-{offset + len(sliced)} of {total})")
        table.add_column("Date", style="cyan")
        table.add_column("Run ID")
        table.add_column("Models")
        table.add_column("Scenarios", justify="right")
        table.add_column("Size", justify="right")
        table.add_column("State")
        table.add_column("Results")
        for r in sliced:
            models = ", ".join(r["models"][:2])
            if len(r["models"]) > 2:
                models += f" +{len(r['models']) - 2}"
            table.add_row(
                r["date"] or "unknown",
                r["id"],
                models or "-",
                str(r["scenarios"]) if r["scenarios"] else "-",
                f"{r['size_mb']:.1f}MB",
                r.get("artifact_state", "unknown"),
                "yes" if r["has_results"] else "no",
            )
        console.print(table)
    else:
        for r in sliced:
            print(f"{r['date'] or 'unknown'} | {r['id']} | {r['size_mb']:.1f}MB")

    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="InvisibleBench - AI Safety Benchmark Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  # Model Evaluation (raw LLM capability)
  uv run bench --full --dry-run             Plan all {len(CONFIG_MODELS_FULL)} models
  uv run bench -m deepseek --dry-run        Plan a single model by name
  uv run bench -m deepseek -y --max-cost-usd 1
                                             Run with an explicit ceiling
  uv run bench -m 1-4 --dry-run             Models 1-4 (by index)
  uv run bench -m 7 --dry-run               Model 7 = DeepSeek V4 Pro
  uv run bench -c safety,empathy --dry-run  Safety + empathy categories only

  # Eval Harness (GiveCare/Mira product)
  uv run bench --harness givecare --mode v2 -y                Full V2 runtime path
  uv run bench --provider givecare -y                         Alias for givecare/v2
  INVISIBLEBENCH_PRIVATE_CONFIDENTIAL_SCENARIOS_DIR=/path/to/private/confidential uv run bench --harness givecare --mode v2 -y --confidential
  uv run bench --harness givecare --mode v2 -c safety -y

  # Judge transcripts (JUDGE scan) and publish
  uv run python scripts/run_scan.py <run-dir> --profile publish --dry-run --enable-llm
  uv run python scripts/run_scan.py <run-dir> --profile publish --enable-llm --max-cost-usd <budget>
  uv run python -m invisiblebench.publish <scan>/per_run.jsonl <web-target>
                                      Fail-closed publish path
  uv run bench leaderboard status     Health check (alias for 'bench health')

  # Utilities
  uv run bench explain <model> <scenario> --failures   Trace scan evidence
  uv run bench health                 Check leaderboard for issues
  uv run bench runs                   List all benchmark runs
  uv run bench archive --keep 5       Keep 5 most recent runs
        """,
    )

    parser.add_argument(
        "--json",
        "--format",
        dest="json_output",
        action="store_const",
        const="json",
        default=None,
        help="Emit agent-friendly JSON envelope (runs/stats/leaderboard[status]/get)",
    )

    subparsers = parser.add_subparsers(dest="command")

    # Doctor subcommand
    subparsers.add_parser("doctor", help="Validate env vars and runs dir")

    # Get subcommand (read single run by id)
    get_parser = subparsers.add_parser("get", help="Read a single run's metadata by id")
    get_parser.add_argument("run_id", type=str, help="Run directory name or prefix")
    get_parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Write full JSON payload to PATH; stdout gets {path,byte_count,record_count} summary",
    )

    # Health subcommand
    health_parser = subparsers.add_parser("health", help="Check leaderboard health and flag issues")
    health_parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed info")

    # Archive subcommand
    archive_parser = subparsers.add_parser("archive", help="Archive old benchmark runs")
    archive_parser.add_argument("--before", type=str, help="Archive runs before date (YYYYMMDD)")
    archive_parser.add_argument("--keep", type=int, help="Keep N most recent runs")
    archive_parser.add_argument(
        "--list", action="store_true", dest="list_runs", help="List runs (dry run)"
    )
    archive_parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be archived"
    )

    # Runs subcommand (list runs)
    runs_parser = subparsers.add_parser("runs", help="List all benchmark runs")
    runs_parser.add_argument("--limit", type=int, default=25, help="Max rows (default 25)")
    runs_parser.add_argument("--offset", type=int, default=0, help="Skip N rows (default 0)")
    runs_parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Write full JSON payload to PATH; stdout gets {path,byte_count,record_count} summary",
    )

    # Explain subcommand
    explain_parser = subparsers.add_parser(
        "explain", help="Trace a leaderboard cell to its verdicts and transcript evidence"
    )
    explain_parser.add_argument("model", type=str, help="Model name or id (substring match)")
    explain_parser.add_argument("scenario", type=str, help="Scenario id (substring match)")
    explain_parser.add_argument(
        "--check", type=str, default=None, help="Filter to checks whose id contains this"
    )
    explain_parser.add_argument(
        "--failures", action="store_true", help="Show only FAIL/UNCLEAR checks"
    )
    explain_parser.add_argument(
        "--scan", type=str, default=None,
        help="Scan per_run.jsonl to read (default: leaderboard scan_metadata.source_artifact)",
    )
    explain_parser.add_argument(
        "--leaderboard", type=str, default=None,
        help="Leaderboard JSON used to resolve the default scan artifact",
    )

    # Leaderboard subcommand
    lb_parser = subparsers.add_parser(
        "leaderboard", help="Show leaderboard health status"
    )
    lb_parser.add_argument(
        "action",
        choices=["status"],
        help="status: leaderboard health check (alias for 'bench health')",
    )
    lb_parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed info")
    lb_parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="For --json status: write full leaderboard to PATH; stdout gets summary envelope",
    )

    # Main run arguments (default command)
    parser.add_argument("--full", action="store_true", help=f"All {len(CONFIG_MODELS_FULL)} models × all scenarios")

    parser.add_argument("--output", type=Path, default=None, help="Output directory")
    parser.add_argument(
        "--harness",
        type=str,
        choices=["llm", "givecare"],
        default=None,
        help="Evaluation surface to run: 'llm' (benchmark core) or 'givecare' (system harnesses)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default=None,
        help="Harness mode. LLM: raw. GiveCare: v2",
    )
    parser.add_argument("--dry-run", action="store_true", help="Plan conservative costs only")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-confirm")
    parser.add_argument(
        "--max-cost-usd",
        type=float,
        default=None,
        metavar="USD",
        help=(
            "Required ceiling for live LLM transcript generation; run "
            "--dry-run first to plan a conservative budget"
        ),
    )
    parser.add_argument(
        "--category",
        "-c",
        type=str,
        default=None,
        help="Filter to specific categories (e.g., 'safety' or 'safety,empathy')",
    )
    parser.add_argument(
        "--scenario",
        "-s",
        type=str,
        default=None,
        help="Filter to specific scenarios by ID or name (comma-separated)",
    )
    parser.add_argument(
        "--parallel",
        "-p",
        type=int,
        default=None,
        metavar="N",
        help="Run N models in parallel (default: sequential)",
    )
    parser.add_argument(
        "--scenario-parallel",
        type=int,
        default=1,
        metavar="N",
        help="Run up to N scenarios concurrently per model for the llm/raw harness (default: 1)",
    )
    parser.add_argument(
        "--transcripts-only",
        action="store_true",
        help="Generate target model transcripts only; judge later with scripts/run_scan.py (default)",
    )
    parser.add_argument(
        "--models",
        "-m",
        type=str,
        default=None,
        metavar="SPEC",
        help="Select models by name or number: 'deepseek', 'gpt-5.6,claude', '1-4', '7', '1,deepseek'",
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=["openrouter", "givecare"],
        default="openrouter",
        help="Select the eval harness target (openrouter=LLM, givecare=V2 system)",
    )
    parser.add_argument(
        "--confidential",
        action="store_true",
        help=(
            "Include private confidential scenarios via "
            "INVISIBLEBENCH_PRIVATE_CONFIDENTIAL_SCENARIOS_DIR"
        ),
    )
    args = parser.parse_args(argv)

    json_output = bool(getattr(args, "json_output", None))

    if args.command == "doctor":
        return _run_doctor()

    if args.command == "get":
        return _run_get(
            args.run_id,
            json_output=json_output,
            out_path=getattr(args, "out", None),
        )

    if args.command == "explain":
        from invisiblebench.cli.explain import explain_command

        return explain_command(args)

    if args.command == "health":
        from invisiblebench.cli.health import run_health

        return run_health(verbose=args.verbose)

    if args.command == "archive":
        from invisiblebench.cli.archive import run_archive, run_list

        if args.list_runs:
            return run_list()
        if args.before is None and args.keep is None:
            print(
                f"{args.command}: pass --before YYYYMMDD or --keep N",
                file=sys.stderr,
            )
            return 2
        if not args.dry_run:
            if args.before and args.keep is not None:
                prompt = f"archive runs older than {args.before}, keeping {args.keep} most recent"
            elif args.before:
                prompt = f"archive runs older than {args.before}"
            else:
                prompt = f"archive runs keeping {args.keep} most recent"
            confirm_or_abort(prompt, yes=bool(getattr(args, "yes", False)))
        return run_archive(before=args.before, keep=args.keep, dry_run=args.dry_run)

    if args.command == "runs":
        return _run_runs(
            limit=getattr(args, "limit", 25),
            offset=getattr(args, "offset", 0),
            json_output=json_output,
            out_path=getattr(args, "out", None),
        )

    if args.command == "leaderboard":
        if json_output:
            return _run_leaderboard_status_json(out_path=getattr(args, "out", None))
        from invisiblebench.cli.leaderboard import run_leaderboard

        return run_leaderboard(action=args.action, verbose=args.verbose)

    category_filter = None
    if args.category:
        category_filter = [c.strip().lower() for c in args.category.split(",")]

    scenario_filter = None
    if args.scenario:
        scenario_filter = [s.strip().lower() for s in args.scenario.split(",")]

    try:
        harness_name, harness_mode = resolve_harness_mode(
            harness=args.harness,
            provider=args.provider,
            mode=args.mode,
        )
    except ValueError as e:
        print(str(e))
        return 1

    if not is_mode_implemented(harness_name, harness_mode):
        print(
            f"Harness mode not implemented yet: {harness_name}/{harness_mode}. "
            f"Use '{harness_name}/{'v2' if harness_name == 'givecare' else 'raw'}' for now."
        )
        return 1

    if harness_name == "givecare":
        return run_givecare_eval(
            category_filter=category_filter,
            scenario_filter=scenario_filter,
            include_confidential=args.confidential,
            verbose=True,
            dry_run=args.dry_run,
            auto_confirm=args.yes,
            output_dir=args.output,
            adapter_name=adapter_name(harness_name, harness_mode),
            harness_mode=harness_mode,
        )

    # Default: raw LLM benchmark via llm/raw harness
    all_models = MODELS_FULL

    # Resolve which models to run
    if args.full:
        models = all_models
    elif args.models:
        try:
            indices = resolve_models(args.models, all_models)
            if not indices:
                msg = f"No models match '{args.models}' (have {len(all_models)} models)"
                print(msg)
                return 1
            models = [all_models[i] for i in indices]
            selected = [m["name"] for m in models]
            if RICH_AVAILABLE:
                Console().print(f"[cyan]Models: {', '.join(selected)}[/cyan]")
            else:
                print(f"Models: {', '.join(selected)}")
        except ValueError as e:
            if RICH_AVAILABLE:
                Console().print(f"[red]{e}[/red]")
            else:
                print(str(e))
            return 1
    else:
        # No --full and no -m: show catalog and exit
        if RICH_AVAILABLE:
            c = Console()
            c.print("[bold]No model selected.[/bold] Use [cyan]--full[/cyan] or [cyan]-m SPEC[/cyan].\n")
            c.print("[bold]Available models:[/bold]")
            for i, m in enumerate(all_models):
                c.print(f"  [dim]{i+1:>2}.[/dim] {m['name']:<24} [dim]{m['id']}[/dim]")
            c.print(
                "\n[dim]Examples:  bench --full --dry-run  |  "
                "bench -m deepseek -y --max-cost-usd 1[/dim]"
            )
        else:
            print("No model selected. Use --full or -m SPEC.\n")
            print("Available models:")
            for i, m in enumerate(all_models):
                print(f"  {i+1:>2}. {m['name']:<24} {m['id']}")
            print(
                "\nExamples:  bench --full --dry-run  |  "
                "bench -m deepseek -y --max-cost-usd 1"
            )
        return 1

    if args.output:
        output_dir = args.output
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(f"results/run_{timestamp}")

    return run_benchmark(
        models=models,
        output_dir=output_dir,
        dry_run=args.dry_run,
        auto_confirm=args.yes,
        category_filter=category_filter,
        scenario_filter=scenario_filter,
        parallel=args.parallel,
        scenario_parallel=args.scenario_parallel,
        include_confidential=args.confidential,
        max_cost_usd=args.max_cost_usd,
    )


if __name__ == "__main__":
    sys.exit(main())
