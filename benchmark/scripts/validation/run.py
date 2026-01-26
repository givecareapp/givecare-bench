#!/usr/bin/env python3
"""
InvisibleBench CLI Runner with rich terminal output.

A unified benchmark runner with live progress display, ETA estimation,
and continuous execution until completion.

Usage:
    python benchmark/scripts/validation/run.py              # Interactive mode
    python benchmark/scripts/validation/run.py --minimal    # Quick validation
    python benchmark/scripts/validation/run.py --full       # Full benchmark
    python benchmark/scripts/validation/run.py --dry-run    # Cost estimate only
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Rich imports for pretty terminal output
try:
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import (
        BarColumn,
        MofNCompleteColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
        TimeRemainingColumn,
    )
    from rich.table import Table
    from rich.text import Text

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = None

# Add parent to path for shared imports
sys.path.insert(0, str(Path(__file__).parent))

from shared import (
    MODELS_FULL,
    MODELS_MINIMAL,
    check_jsonlines,
    estimate_cost,
    generate_heatmap,
    generate_summary_table,
    generate_transcript,
    get_scenarios,
    load_scenario_json,
    run_evaluation,
)

load_dotenv()


def create_progress() -> Progress:
    """Create a rich progress bar with multiple columns."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=Console(stderr=True),
        expand=False,
    )


def create_status_table(
    current_model: str,
    current_scenario: str,
    completed: int,
    total: int,
    passed: int,
    failed: int,
    cost_so_far: float,
    elapsed_seconds: float,
) -> Table:
    """Create a live status table."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Label", style="dim")
    table.add_column("Value", style="bold")

    table.add_row("Current Model", f"[cyan]{current_model}[/cyan]")
    table.add_row("Current Scenario", f"[yellow]{current_scenario}[/yellow]")
    table.add_row("Progress", f"[green]{completed}[/green] / {total}")
    table.add_row("Passed", f"[green]{passed}[/green]")
    table.add_row("Failed", f"[red]{failed}[/red]")
    table.add_row("Cost", f"[magenta]${cost_so_far:.3f}[/magenta]")
    table.add_row("Elapsed", f"{elapsed_seconds/60:.1f} min")

    if completed > 0:
        eta_seconds = (elapsed_seconds / completed) * (total - completed)
        table.add_row("ETA", f"{eta_seconds/60:.1f} min remaining")

    return table


def print_banner(console: Console, mode: str, models: list, scenarios: list, total_cost: float):
    """Print startup banner with run configuration."""
    console.print()
    console.print(
        Panel(
            f"[bold cyan]InvisibleBench[/bold cyan] [dim]v1.1.0[/dim]\n"
            f"[dim]AI Safety Benchmark for Caregiving Relationships[/dim]",
            border_style="cyan",
        )
    )

    config_table = Table(show_header=False, box=None, padding=(0, 2))
    config_table.add_column("", style="dim")
    config_table.add_column("")

    config_table.add_row("Mode", f"[bold]{mode.upper()}[/bold]")
    config_table.add_row("Models", str(len(models)))
    config_table.add_row("Scenarios", str(len(scenarios)))
    config_table.add_row("Total Evaluations", str(len(models) * len(scenarios)))
    config_table.add_row("Estimated Cost", f"[magenta]${total_cost:.2f}[/magenta]")

    console.print(Panel(config_table, title="[bold]Configuration[/bold]", border_style="blue"))

    # List models
    console.print("\n[bold]Models:[/bold]")
    for m in models:
        console.print(f"  [cyan]•[/cyan] {m['name']}")

    # List scenarios by tier
    console.print("\n[bold]Scenarios:[/bold]")
    for tier in sorted(set(s["tier"] for s in scenarios)):
        tier_scenarios = [s for s in scenarios if s["tier"] == tier]
        console.print(f"  [yellow]Tier {tier}:[/yellow]")
        for s in tier_scenarios:
            console.print(f"    [dim]•[/dim] {s['name']}")

    console.print()


def print_results_summary(console: Console, results: list, elapsed_seconds: float):
    """Print final results summary."""
    total_cost = sum(r["cost"] for r in results)
    passed = len([r for r in results if r["status"] != "error" and not r.get("hard_fail")])
    failed = len(results) - passed

    # Summary panel
    summary = Table(show_header=False, box=None)
    summary.add_column("", style="dim")
    summary.add_column("")

    summary.add_row("Total Evaluations", str(len(results)))
    summary.add_row("Passed", f"[green]{passed}[/green]")
    summary.add_row("Failed", f"[red]{failed}[/red]")
    summary.add_row("Total Cost", f"[magenta]${total_cost:.3f}[/magenta]")
    summary.add_row("Total Time", f"{elapsed_seconds/60:.1f} minutes")

    console.print(
        Panel(summary, title="[bold green]Benchmark Complete[/bold green]", border_style="green")
    )

    # Results table
    results_table = Table(title="Results by Model", show_lines=True)
    results_table.add_column("Model", style="cyan")
    results_table.add_column("Scenario", style="yellow")
    results_table.add_column("Overall", justify="right")
    results_table.add_column("Status", justify="center")

    for r in sorted(results, key=lambda x: (x["model"], x["scenario"])):
        score = r["overall_score"]
        score_style = "green" if score >= 0.7 else "yellow" if score >= 0.5 else "red"
        status = "[green]✓[/green]" if r["status"] != "error" and not r.get("hard_fail") else "[red]✗[/red]"

        results_table.add_row(
            r["model"],
            r["scenario"],
            f"[{score_style}]{score:.2f}[/{score_style}]",
            status,
        )

    console.print(results_table)


def run_benchmark(
    mode: str,
    output_dir: Path,
    skip_transcripts: bool = False,
    dry_run: bool = False,
    auto_confirm: bool = False,
) -> int:
    """
    Run the benchmark with rich terminal output.

    Args:
        mode: "minimal" or "full"
        output_dir: Directory to save results
        skip_transcripts: Skip transcript generation
        dry_run: Only estimate costs
        auto_confirm: Skip confirmation prompt

    Returns:
        Exit code (0 for success, 1 for error)
    """
    console = Console() if RICH_AVAILABLE else None

    # Select models and scenarios
    if mode == "minimal":
        models = MODELS_MINIMAL
        scenarios = get_scenarios(include_confidential=False, minimal=True)
    else:
        models = MODELS_FULL
        scenarios = get_scenarios(include_confidential=False, minimal=False)

    total = len(models) * len(scenarios)
    total_cost = sum(estimate_cost(s["tier"], m) for m in models for s in scenarios)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Print banner
    if RICH_AVAILABLE:
        print_banner(console, mode, models, scenarios, total_cost)
    else:
        print(f"\n{'='*60}")
        print(f"InvisibleBench - {mode.upper()} MODE")
        print(f"{'='*60}")
        print(f"Models: {len(models)}")
        print(f"Scenarios: {len(scenarios)}")
        print(f"Total evaluations: {total}")
        print(f"Estimated cost: ${total_cost:.2f}")
        print(f"{'='*60}\n")

    if dry_run:
        if RICH_AVAILABLE:
            console.print("[yellow]DRY RUN[/yellow] - No evaluations will be run")
        else:
            print("DRY RUN - No evaluations will be run")
        return 0

    # Check API keys
    if not os.getenv("OPENROUTER_API_KEY"):
        msg = "ERROR: OPENROUTER_API_KEY not set"
        if RICH_AVAILABLE:
            console.print(f"[red]{msg}[/red]")
        else:
            print(msg)
        return 1

    check_jsonlines()

    # Confirm
    if not auto_confirm:
        if RICH_AVAILABLE:
            console.print("[bold]Proceed with evaluations?[/bold] [dim](y/n)[/dim]", end=" ")
        response = input()
        if response.lower() != "y":
            print("Cancelled")
            return 0
    else:
        if RICH_AVAILABLE:
            console.print("[dim]Auto-confirmed with --yes flag[/dim]")

    # Initialize API client
    if RICH_AVAILABLE:
        console.print("\n[dim]Initializing API client...[/dim]")
    try:
        from invisiblebench.api.client import ModelAPIClient

        api_client = ModelAPIClient()
    except Exception as e:
        if RICH_AVAILABLE:
            console.print(f"[red]ERROR: Failed to initialize API client: {e}[/red]")
        else:
            print(f"ERROR: Failed to initialize API client: {e}")
        return 1

    # Initialize orchestrator
    if RICH_AVAILABLE:
        console.print("[dim]Initializing scoring orchestrator...[/dim]")
    try:
        from invisiblebench.evaluation.orchestrator import ScoringOrchestrator

        scoring_config_path = Path("benchmark/configs/scoring.yaml")
        orchestrator = ScoringOrchestrator(
            scoring_config_path=str(scoring_config_path),
            enable_state_persistence=False,
            enable_llm=True,
        )
    except Exception as e:
        if RICH_AVAILABLE:
            console.print(f"[red]ERROR: Failed to initialize orchestrator: {e}[/red]")
        else:
            print(f"ERROR: Failed to initialize orchestrator: {e}")
        import traceback

        traceback.print_exc()
        return 1

    # Run evaluations with progress display
    results = []
    start_time = time.time()
    passed = 0
    failed = 0

    if RICH_AVAILABLE:
        # Use rich progress display
        with create_progress() as progress:
            task = progress.add_task("[cyan]Running benchmark...", total=total)

            for model_idx, model in enumerate(models):
                for scenario_idx, scenario_info in enumerate(scenarios):
                    eval_num = model_idx * len(scenarios) + scenario_idx + 1

                    # Update progress description
                    progress.update(
                        task,
                        description=f"[cyan]{model['name']}[/cyan] → [yellow]{scenario_info['name']}[/yellow]",
                    )

                    # Load scenario
                    scenario_path = Path(scenario_info["path"])
                    if not scenario_path.exists():
                        progress.console.print(
                            f"[red]ERROR: Scenario not found: {scenario_path}[/red]"
                        )
                        failed += 1
                        progress.advance(task)
                        continue

                    scenario = load_scenario_json(str(scenario_path))

                    # Generate or load transcript
                    transcript_filename = (
                        f"{model['id'].replace('/', '_')}_{scenario['scenario_id']}.jsonl"
                    )
                    transcript_path = output_dir / "transcripts" / transcript_filename

                    if not skip_transcripts or not transcript_path.exists():
                        try:
                            transcript_path = generate_transcript(
                                model_id=model["id"],
                                scenario=scenario,
                                api_client=api_client,
                                output_path=transcript_path,
                            )
                        except Exception as e:
                            progress.console.print(
                                f"[red]ERROR generating transcript: {e}[/red]"
                            )
                            failed += 1
                            progress.advance(task)
                            continue

                    # Run evaluation
                    try:
                        result = run_evaluation(
                            model=model,
                            scenario=scenario,
                            scenario_info=scenario_info,
                            transcript_path=transcript_path,
                            output_dir=output_dir,
                            orchestrator=orchestrator,
                        )
                        results.append(result)

                        if result["status"] != "error" and not result.get("hard_fail"):
                            passed += 1
                            progress.console.print(
                                f"  [green]✓[/green] {result['overall_score']:.2f}"
                            )
                        else:
                            failed += 1
                            progress.console.print(
                                f"  [red]✗[/red] {result.get('status', 'failed')}"
                            )

                    except Exception as e:
                        progress.console.print(f"[red]ERROR during evaluation: {e}[/red]")
                        failed += 1

                    progress.advance(task)

    else:
        # Fallback to basic output
        for model_idx, model in enumerate(models):
            for scenario_idx, scenario_info in enumerate(scenarios):
                eval_num = model_idx * len(scenarios) + scenario_idx + 1
                print(f"\n[{eval_num}/{total}] {model['name']} → {scenario_info['name']}")

                scenario_path = Path(scenario_info["path"])
                if not scenario_path.exists():
                    print(f"  ERROR: Scenario not found: {scenario_path}")
                    failed += 1
                    continue

                scenario = load_scenario_json(str(scenario_path))

                transcript_filename = (
                    f"{model['id'].replace('/', '_')}_{scenario['scenario_id']}.jsonl"
                )
                transcript_path = output_dir / "transcripts" / transcript_filename

                if not skip_transcripts or not transcript_path.exists():
                    try:
                        transcript_path = generate_transcript(
                            model_id=model["id"],
                            scenario=scenario,
                            api_client=api_client,
                            output_path=transcript_path,
                        )
                    except Exception as e:
                        print(f"  ERROR generating transcript: {e}")
                        failed += 1
                        continue

                try:
                    result = run_evaluation(
                        model=model,
                        scenario=scenario,
                        scenario_info=scenario_info,
                        transcript_path=transcript_path,
                        output_dir=output_dir,
                        orchestrator=orchestrator,
                    )
                    results.append(result)

                    if result["status"] != "error" and not result.get("hard_fail"):
                        passed += 1
                        print(f"  PASS: {result['overall_score']:.2f}")
                    else:
                        failed += 1
                        print(f"  FAIL: {result.get('status', 'failed')}")

                except Exception as e:
                    print(f"  ERROR during evaluation: {e}")
                    failed += 1

    elapsed_seconds = time.time() - start_time

    if not results:
        msg = "ERROR: No successful evaluations completed"
        if RICH_AVAILABLE:
            console.print(f"[red]{msg}[/red]")
        else:
            print(msg)
        return 1

    # Save results
    all_results_path = output_dir / "all_results.json"
    with open(all_results_path, "w") as f:
        json.dump(results, f, indent=2)

    # Generate outputs
    generate_summary_table(results, output_dir)
    generate_heatmap(results, output_dir)

    # Print summary
    if RICH_AVAILABLE:
        console.print()
        print_results_summary(console, results, elapsed_seconds)
        console.print(f"\n[dim]Results saved to: {output_dir}[/dim]")
    else:
        print(f"\n{'='*60}")
        print("BENCHMARK COMPLETE")
        print(f"{'='*60}")
        print(f"Total: {len(results)}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Cost: ${sum(r['cost'] for r in results):.3f}")
        print(f"Time: {elapsed_seconds/60:.1f} minutes")
        print(f"Results: {output_dir}")
        print(f"{'='*60}\n")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="InvisibleBench CLI - AI Safety Benchmark Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py --minimal -y        Quick validation (22 evals, ~$0.15)
  python run.py --full -y           Full benchmark (all tiers, ~$30-40)
  python run.py --dry-run           Estimate costs only
  python run.py --output results/   Custom output directory
        """,
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--minimal",
        action="store_true",
        help="Run minimal validation (1 model × 22 scenarios)",
    )
    mode_group.add_argument(
        "--full",
        action="store_true",
        help="Run full benchmark (10 models × all scenarios)",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output directory (default: results/run_YYYYMMDD_HHMMSS/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Estimate costs without running evaluations",
    )
    parser.add_argument(
        "--skip-transcripts",
        action="store_true",
        help="Skip transcript generation (use existing)",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Auto-confirm (skip interactive prompt)",
    )

    args = parser.parse_args()

    # Determine mode
    if args.minimal:
        mode = "minimal"
    elif args.full:
        mode = "full"
    else:
        # Default to minimal for safety
        mode = "minimal"

    # Set output directory
    if args.output:
        output_dir = args.output
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(f"results/run_{timestamp}")

    return run_benchmark(
        mode=mode,
        output_dir=output_dir,
        skip_transcripts=args.skip_transcripts,
        dry_run=args.dry_run,
        auto_confirm=args.yes,
    )


if __name__ == "__main__":
    sys.exit(main())
