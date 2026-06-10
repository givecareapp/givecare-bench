#!/usr/bin/env python3
"""InvisibleBench CLI runner."""
from __future__ import annotations

import argparse
import json
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
    emit_json,
)
from invisiblebench.cli._console import make_console
from invisiblebench.cli.agent_commands import (
    _run_doctor,
    _run_get,
    _run_leaderboard_mutation_json,
    _run_leaderboard_status_json,
)
from invisiblebench.cli.diff import (
    _infer_run_dir_for_output,
    diff_command,
)
from invisiblebench.cli.diff import (
    aggregate_results_by_model as aggregate_results_by_model,  # re-exported: tests import from this module
)
from invisiblebench.cli.diff import (
    compute_run_diff as compute_run_diff,  # re-exported: tests import from this module
)
from invisiblebench.cli.diff import (
    load_run_results as load_run_results,  # re-exported: tests import from this module
)
from invisiblebench.cli.result_helpers import (
    _compute_success as _compute_success,  # re-exported: tests import from this module
)
from invisiblebench.cli.transcript import (
    write_detailed_outputs as write_detailed_outputs,  # re-exported: tests import from this module
)
from invisiblebench.harnesses import adapter_name, is_mode_implemented, resolve_harness_mode
from invisiblebench.models.config import MODELS_FULL as CONFIG_MODELS_FULL
from invisiblebench.results_io import write_json
from invisiblebench.run_artifacts import (
    detect_transcripts_dir,
    load_result_rows,
    write_aggregate_results,
)
from invisiblebench.run_audit import audit_results_source, render_audit_markdown

try:
    from rich.table import Table  # noqa: F401

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

logger = logging.getLogger(__name__)

# Shared NO_COLOR/isatty-honoring Console factory (returns None without rich).
Console = make_console

load_dotenv()

# Token estimates per category for cost calculation
# Calibrated from actual benchmark runs (Jan 2026) - includes system prompt,
# conversation history growth, and scorer LLM calls
TOKEN_ESTIMATES = {
    1: {"input": 5500, "output": 1400},  # 3-5 turns
    2: {"input": 14000, "output": 3300},  # 8-12 turns
    3: {"input": 27000, "output": 6000},  # 20+ turns, multi-session
}

# Scorer LLM costs (per scenario) — not included in model-under-test tokens
# Scorer calls: safety (1 ref + 3 sampled), compliance (3), regard (LLM/cache-aware),
# coordination (mostly deterministic, adds false_refusal signal), plus memory (deterministic).
# Avg estimate: ~4-6 LLM calls/scenario
SCORER_MODEL_COSTS = {
    "flash_lite": {"cost_per_m_input": 0.10, "cost_per_m_output": 0.40},  # gemini-2.5-flash-lite
    "flash": {"cost_per_m_input": 0.30, "cost_per_m_output": 2.50},       # gemini-2.5-flash (safety ref)
}
# Per-scenario scorer token estimates (all scorers combined)
SCORER_CALLS_PER_SCENARIO = 8       # avg uncached LLM calls (flash-lite)
SCORER_REF_CALLS_PER_SCENARIO = 1   # safety reference call (flash)
SCORER_TOKENS_PER_CALL = {"input": 4000, "output": 800}

# SYSTEM_PROMPT is imported from invisiblebench.cli.transcript

MODELS_FULL = [model.model_dump() for model in CONFIG_MODELS_FULL]


from invisiblebench.cli.result_helpers import (  # noqa: E402,F401
    _make_error_result as _make_error_result,  # re-exported: tests import from this module
)
from invisiblebench.cli.run_command import (  # noqa: E402,F401
    ModeEngineScoringAdapter as ModeEngineScoringAdapter,  # re-exported: tests import from this module
)
from invisiblebench.cli.run_command import (  # noqa: E402,F401
    _aggregate_multi_run_results as _aggregate_multi_run_results,
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


def report_command(args) -> int:
    """Generate HTML report from any supported results source."""
    console = Console() if RICH_AVAILABLE else None

    results_path = Path(args.results)
    if not results_path.exists():
        msg = f"Results file not found: {results_path}"
        if console:
            console.print(f"[red]{msg}[/red]")
        else:
            print(msg)
        return 1

    try:
        results = load_result_rows(results_path)
    except (OSError, json.JSONDecodeError, ValueError) as e:
        msg = f"Could not load results: {e}"
        if console:
            console.print(f"[red]{msg}[/red]")
        else:
            print(msg)
        return 1

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = _infer_run_dir_for_output(results_path) / "report.html"

    try:
        from invisiblebench.export.reports import ReportGenerator

        reporter = ReportGenerator()
        reporter.generate_batch_report(
            results,
            str(output_path),
            metadata={"source": str(results_path)},
        )
        if console:
            console.print(f"[green]✓[/green] Report generated: {output_path}")
        else:
            print(f"Report generated: {output_path}")
        return 0
    except (ImportError, OSError) as e:
        msg = f"Failed to generate report: {e}"
        if console:
            console.print(f"[red]{msg}[/red]")
        else:
            print(msg)
        return 1


def diagnose_command(args) -> int:
    """Generate diagnostic report from results JSON."""
    console = Console() if RICH_AVAILABLE else None

    results_path = Path(args.results)
    if not results_path.exists():
        msg = f"Results file not found: {results_path}"
        if console:
            console.print(f"[red]{msg}[/red]")
        else:
            print(msg)
        return 1

    # Determine transcripts directory
    transcripts_dir = Path(args.transcripts) if args.transcripts else detect_transcripts_dir(results_path)

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = (results_path if results_path.is_dir() else results_path.parent) / "diagnostic_report.md"

    try:
        from invisiblebench.export.diagnostic import generate_diagnostic_report

        if results_path.is_file():
            diagnostic_input = results_path
        elif (results_path / "all_results.json").exists():
            diagnostic_input = results_path / "all_results.json"
        else:
            diagnostic_input = write_aggregate_results(results_path)

        report = generate_diagnostic_report(
            results_path=str(diagnostic_input),
            transcripts_dir=str(transcripts_dir) if transcripts_dir else None,
            previous_results_path=args.previous,
            output_path=str(output_path),
        )

        if console:
            console.print(f"[green]✓[/green] Diagnostic report generated: {output_path}")
        else:
            print(f"Diagnostic report generated: {output_path}")

        # Print summary
        lines = report.split("\n")
        summary_start = None
        for i, line in enumerate(lines):
            if line.startswith("## Summary"):
                summary_start = i
                break

        if summary_start and console:
            console.print("\n[bold]Summary:[/bold]")
            for line in lines[summary_start + 2 : summary_start + 10]:
                if line.strip():
                    console.print(f"  {line}")

        return 0
    except (ImportError, OSError, json.JSONDecodeError) as e:
        msg = f"Failed to generate diagnostic report: {e}"
        if console:
            console.print(f"[red]{msg}[/red]")
        else:
            print(msg)
        import traceback

        traceback.print_exc()
        return 1


def audit_command(args) -> int:
    """Generate run audit artifacts from a run/results source."""
    console = Console() if RICH_AVAILABLE else None

    results_path = Path(args.results)
    if not results_path.exists():
        msg = f"Results source not found: {results_path}"
        if console:
            console.print(f"[red]{msg}[/red]")
        else:
            print(msg)
        return 1

    try:
        audit = audit_results_source(
            results_path,
            expected_scenario_count=args.expected_scenarios,
            harness=args.harness,
            mode=args.mode,
            previous_source=args.previous,
        )
    except (OSError, json.JSONDecodeError, ValueError) as e:
        msg = f"Failed to audit results: {e}"
        if console:
            console.print(f"[red]{msg}[/red]")
        else:
            print(msg)
        return 1

    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = _infer_run_dir_for_output(results_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "run_audit.json", audit)
    (output_dir / "run_audit.md").write_text(render_audit_markdown(audit))

    _print_audit_summary(audit, console)
    if console:
        console.print(f"[green]✓[/green] Audit written: {output_dir / 'run_audit.json'}")
    else:
        print(f"Audit written: {output_dir / 'run_audit.json'}")
    return 0 if audit.get("run_valid") else 1


# _infer_run_dir_for_output, resolve_run_reference, load_run_results, aggregate_results_by_model,
# compute_run_diff, _format_score/_delta/_status_counts, _print_diff_table, diff_command
# moved to invisiblebench.cli.diff


# resolve_run_reference, load_run_results, aggregate_results_by_model, compute_run_diff,
# _format_score/_delta/_status_counts, _print_diff_table, diff_command: all moved to invisiblebench.cli.diff



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
  uv run bench --full -y                    All {len(CONFIG_MODELS_FULL)} models (run --dry-run for current estimate)
  uv run bench -m deepseek -y               Single model by name
  uv run bench -m gpt-5.2,claude -y         Multiple models by name
  uv run bench -m 1-4 -y                    Models 1-4 (by index)
  uv run bench -m 7 -y                      Model 7 = DeepSeek V3.2
  uv run bench -c safety,empathy -y         Safety + empathy categories only
  uv run bench --harness llm --mode raw -m deepseek -y

  # Eval Harness (GiveCare/Mira product)
  uv run bench --harness givecare --mode v2 -y                Full V2 runtime path
  uv run bench --provider givecare -y                         Alias for givecare/v2
  INVISIBLEBENCH_PRIVATE_CONFIDENTIAL_SCENARIOS_DIR=/path/to/private/confidential uv run bench --harness givecare --mode v2 -y --confidential
  uv run bench --harness givecare --mode v2 -c safety -y

  # Diagnostics
  uv run bench --provider givecare -y --diagnose  Run with diagnostic report
  uv run bench diagnose results.json              Generate diagnostic from results

  # Leaderboard
  uv run bench leaderboard add results/run_*/all_results.json  Add model to leaderboard
  uv run bench leaderboard rebuild    Rebuild from canonical files
  uv run bench leaderboard status     Health check (alias for 'bench health')

  # Statistics & Reliability
  uv run bench stats results/run_*/all_results.json       Score distributions + bootstrap CIs
  uv run bench stats results/leaderboard_ready/ -o s.md   With markdown output
  uv run bench reliability results/run_20260211/           Scorer inter-rater reliability
  uv run bench annotate export results/run_20260211/       Export annotation kit
  uv run bench annotate import results/annotations/scores.csv  Compute agreement

  # Utilities
  uv run bench report results.json    Regenerate HTML report
  uv run bench health                 Check leaderboard for issues
  uv run bench runs                   List all benchmark runs
  uv run bench diff <base> <new>      Compare two benchmark runs
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
        help="Emit agent-friendly JSON envelope (runs/stats/leaderboard[add|rebuild|status]/get)",
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

    # Report subcommand
    report_parser = subparsers.add_parser("report", help="Generate HTML report from results JSON")
    report_parser.add_argument("results", type=str, help="Path to all_results.json")
    report_parser.add_argument("--output", "-o", type=str, default=None, help="Output HTML path")

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

    # Clean subcommand (alias for archive)
    clean_parser = subparsers.add_parser("clean", help="Clean up old runs (alias for archive)")
    clean_parser.add_argument("--before", type=str, help="Archive runs before date (YYYYMMDD)")
    clean_parser.add_argument("--keep", type=int, help="Keep N most recent runs")
    clean_parser.add_argument(
        "--list", action="store_true", dest="list_runs", help="List runs (dry run)"
    )
    clean_parser.add_argument("--dry-run", action="store_true", help="Show what would be archived")

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

    # Diff subcommand
    diff_parser = subparsers.add_parser("diff", help="Compare two benchmark runs")
    diff_parser.add_argument("base_run", type=str, help="Base run reference")
    diff_parser.add_argument("new_run", type=str, help="New run reference")

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
        help="Scan per_run.jsonl to read (default: leaderboard metadata.source_artifact)",
    )
    explain_parser.add_argument(
        "--leaderboard", type=str, default=None,
        help="Leaderboard JSON used to resolve the default scan artifact",
    )

    # Rescore subcommand
    rescore_parser = subparsers.add_parser(
        "rescore", help="Rescore existing transcripts without re-running models"
    )
    rescore_parser.add_argument("run_dir", type=str, help="Path to run directory with transcripts/")
    rescore_parser.add_argument(
        "--update-leaderboard", action="store_true", help="Update leaderboard after rescoring"
    )

    # Diagnose subcommand
    diagnose_parser = subparsers.add_parser(
        "diagnose", help="Generate diagnostic report from results"
    )
    diagnose_parser.add_argument("results", type=str, help="Path to results JSON")
    diagnose_parser.add_argument("--transcripts", "-t", type=str, help="Transcripts directory")
    diagnose_parser.add_argument(
        "--previous", "-p", type=str, help="Previous results for comparison"
    )
    diagnose_parser.add_argument("--output", "-o", type=str, help="Output markdown path")

    audit_parser = subparsers.add_parser(
        "audit", help="Audit a run/results source and classify benchmark failure modes"
    )
    audit_parser.add_argument("results", type=str, help="Path to run dir, results JSON, or model_results/")
    audit_parser.add_argument("--previous", "-p", type=str, help="Previous run/results source for comparability checks")
    audit_parser.add_argument("--expected-scenarios", type=int, default=None, help="Expected scenario count per model/provider")
    audit_parser.add_argument("--harness", type=str, choices=["llm", "givecare"], default=None)
    audit_parser.add_argument("--mode", type=str, default=None)
    audit_parser.add_argument("--output-dir", type=str, default=None, help="Directory for run_audit.json and run_audit.md")

    # Leaderboard subcommand
    lb_parser = subparsers.add_parser(
        "leaderboard", help="Manage leaderboard (add, rebuild, status)"
    )
    lb_parser.add_argument(
        "action",
        choices=["add", "rebuild", "status"],
        help="add: add results to leaderboard, rebuild: regenerate from canonical files, status: health check",
    )
    lb_parser.add_argument(
        "results", nargs="?", default=None, help="Path to all_results.json (for 'add')"
    )
    lb_parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed info")
    lb_parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="For --json status: write full leaderboard to PATH; stdout gets summary envelope",
    )

    # Stats subcommand
    stats_parser = subparsers.add_parser(
        "stats", help="Statistical analysis: distributions, bootstrap CIs, pairwise comparisons"
    )
    stats_parser.add_argument(
        "results", type=str, help="Path to all_results.json or leaderboard_ready/ directory"
    )
    stats_parser.add_argument(
        "--output", "-o", type=str, default=None, help="Output markdown path"
    )
    stats_parser.add_argument(
        "--bootstrap", type=int, default=10000, help="Number of bootstrap samples (default: 10000)"
    )

    # Reliability subcommand
    rel_parser = subparsers.add_parser(
        "reliability", help="Scorer inter-rater reliability (runs LLM scorers N times)"
    )
    rel_parser.add_argument(
        "results", type=str, help="Path to results directory with transcripts"
    )
    rel_parser.add_argument(
        "--runs", "-n", type=int, default=5, help="Number of scoring runs (default: 5)"
    )
    rel_parser.add_argument(
        "--sample", type=int, default=10, help="Number of transcripts to sample (default: 10)"
    )
    rel_parser.add_argument(
        "--output", "-o", type=str, default=None, help="Output directory for raw data"
    )

    # Annotate subcommand
    annotate_parser = subparsers.add_parser(
        "annotate", help="Human annotation kit for human-LLM agreement"
    )
    annotate_parser.add_argument(
        "action",
        choices=["export", "import"],
        help="export: create scoring forms, import: compute agreement",
    )
    annotate_parser.add_argument(
        "path", type=str, help="Results path (export) or annotations CSV path (import)"
    )
    annotate_parser.add_argument(
        "--output", "-o", type=str, default=None, help="Output directory (export) or unused (import)"
    )
    annotate_parser.add_argument(
        "--sample", type=int, default=20, help="Number of transcripts to sample (default: 20)"
    )
    annotate_parser.add_argument(
        "--llm-scores", type=str, default=None, help="Path to _llm_scores.json (for import)"
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
    parser.add_argument("--dry-run", action="store_true", help="Estimate costs only")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-confirm")
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Write per-scenario JSON/HTML reports with turn flags",
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
        "--models",
        "-m",
        type=str,
        default=None,
        metavar="SPEC",
        help="Select models by name or number: 'deepseek', 'gpt-5.2,claude', '1-4', '7', '1,deepseek'",
    )
    parser.add_argument(
        "--update-leaderboard",
        action="store_true",
        help="Update public leaderboard after run completes (llm/raw only)",
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
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="Generate diagnostic report after run (actionable fix suggestions)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        metavar="N",
        help="Run each scenario N times and take median score (default: 1)",
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

    if args.command == "report":
        return report_command(args)

    if args.command == "explain":
        from invisiblebench.cli.explain import explain_command

        return explain_command(args)

    if args.command == "audit":
        return audit_command(args)

    if args.command == "health":
        from invisiblebench.cli.health import run_health

        return run_health(verbose=args.verbose)

    if args.command in ("archive", "clean"):
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

    if args.command == "diff":
        return diff_command(args)

    if args.command == "rescore":
        print("ERROR: V2 rescore has been archived. Use V3 ModeEngine scoring:")
        print("  uv run python scripts/run_scan.py <run_dir>")
        return 1

    if args.command == "diagnose":
        return diagnose_command(args)

    if args.command == "leaderboard":
        if args.action in ("add", "rebuild"):
            confirm_or_abort(
                f"leaderboard {args.action}"
                + (f" {args.results}" if args.results else ""),
                yes=bool(getattr(args, "yes", False)),
            )
        if json_output:
            if args.action == "status":
                return _run_leaderboard_status_json(out_path=getattr(args, "out", None))
            if args.action in ("add", "rebuild"):
                return _run_leaderboard_mutation_json(args.action, args.results)
        from invisiblebench.cli.leaderboard import run_leaderboard

        return run_leaderboard(
            action=args.action,
            results_path=args.results,
            verbose=args.verbose,
        )

    if args.command == "stats":
        from invisiblebench.stats.analysis import (
            compute_stats,
            format_stats_markdown,
            format_stats_report,
        )

        stats = compute_stats(args.results, n_bootstrap=args.bootstrap)
        if "error" in stats:
            if json_output:
                emit_json(status="error", command="stats", error=stats["error"])
            else:
                print(f"Error: {stats['error']}")
            return 1
        if json_output:
            emit_json(command="stats", data=stats)
        else:
            print(format_stats_report(stats))
        if args.output:
            Path(args.output).write_text(format_stats_markdown(stats))
            if not json_output:
                print(f"\nMarkdown report written to {args.output}")
            else:
                print(f"wrote: {args.output}", file=sys.stderr)
        return 0

    if args.command == "reliability":
        print("ERROR: V2 reliability analysis has been archived.")
        print("V3 uses per-mode K-repetition voting for reliability.")
        print("Run: uv run python scripts/run_scan.py --enable-llm <run_dir>")
        return 1

    if args.command == "annotate":
        if args.action == "export":
            from invisiblebench.stats.annotation import export_annotation_kit

            out_dir = args.output or "results/annotations"
            result = export_annotation_kit(
                args.path, out_dir, sample_size=args.sample
            )
            if "error" in result:
                print(f"Error: {result['error']}")
                return 1
            print(f"Exported {result['exported']} transcripts to {result['output_dir']}/")
            print(f"  Forms: {len(result['files']['forms'])} markdown files")
            print(f"  CSV template: {result['files']['csv_template']}")
            print(f"  Instructions: {result['files']['instructions']}")
            return 0
        else:  # import
            from invisiblebench.stats.annotation import (
                format_agreement_report,
                import_annotations,
            )

            result = import_annotations(args.path, llm_scores_path=args.llm_scores)
            if "error" in result:
                print(f"Error: {result['error']}")
                return 1
            print(format_agreement_report(result))
            return 0

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
            generate_diagnostic=args.diagnose,
            output_dir=args.output,
            adapter_name=adapter_name(harness_name, harness_mode),
            harness_mode=harness_mode,
            update_leaderboard=args.update_leaderboard,
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
            c.print("\n[dim]Examples:  bench --full -y  |  bench -m deepseek -y  |  bench -m 1-4 -y[/dim]")
        else:
            print("No model selected. Use --full or -m SPEC.\n")
            print("Available models:")
            for i, m in enumerate(all_models):
                print(f"  {i+1:>2}. {m['name']:<24} {m['id']}")
            print("\nExamples:  bench --full -y  |  bench -m deepseek -y  |  bench -m 1-4 -y")
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
        detailed_output=args.detailed,
        update_leaderboard=args.update_leaderboard,
        generate_diagnostic=args.diagnose,
        runs=getattr(args, "runs", 1),
        include_confidential=args.confidential,
    )


if __name__ == "__main__":
    sys.exit(main())
