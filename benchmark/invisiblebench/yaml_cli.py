from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lb",
        description="InvisibleBench scoring CLI (prototype).",
    )
    parser.add_argument(
        "--scenario",
        help="Path to scenario YAML file.",
    )
    parser.add_argument(
        "--transcript",
        help="Path to model transcript JSONL.",
    )
    parser.add_argument(
        "--rules",
        help="Path to jurisdiction rule-pack YAML.",
    )
    parser.add_argument(
        "--out",
        help="Optional path to write HTML report.",
    )
    parser.add_argument(
        "--json",
        dest="json_out",
        help="Optional path to write JSON report.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="Number of scoring iterations to run (default: 1). Multiple iterations enable variance measurement.",
    )

    # Run tracking options
    parser.add_argument(
        "--model",
        help="Model name for run tracking (enables state persistence).",
    )
    parser.add_argument(
        "--run-id",
        dest="run_id",
        help="Resume existing run with this ID prefix.",
    )
    parser.add_argument(
        "--reset",
        help="Delete all runs for specified model name and exit.",
    )
    parser.add_argument(
        "--list-runs",
        action="store_true",
        help="List all runs and exit.",
    )
    parser.add_argument(
        "--runs-dir",
        default="runs",
        help="Directory for run state files (default: runs).",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from previously saved state.",
    )
    parser.add_argument(
        "--resume-file",
        dest="resume_file",
        help="Specific state file to resume from (path to JSON file).",
    )
    parser.add_argument(
        "--save-interval",
        dest="save_interval",
        type=int,
        default=1,
        help="Save state after every N scorers (default: 1).",
    )

    # Verbosity options
    verbosity_group = parser.add_mutually_exclusive_group()
    verbosity_group.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output (only show errors and final summary).",
    )
    verbosity_group.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed progress output including dimension breakdowns.",
    )

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Import run manager for utility commands
    from invisiblebench.evaluation.run_manager import RunManager

    # Handle --reset command
    if args.reset:
        run_manager = RunManager(runs_dir=args.runs_dir)
        deleted = run_manager.delete_runs_by_model(args.reset)
        print(f"Deleted {deleted} run(s) for model '{args.reset}'")
        return 0

    # Handle --list-runs command
    if args.list_runs:
        run_manager = RunManager(runs_dir=args.runs_dir)
        runs = run_manager.list_runs()
        if not runs:
            print("No runs found.")
        else:
            print(f"Found {len(runs)} run(s):\n")
            for run in runs:
                run_key = run.get("run_key", "unknown")
                model = run.get("model_name", "unknown")
                status = run.get("status", "unknown")
                scenario = run.get("scenario_id", "unknown")
                score = run.get("results", {}).get("overall_score", "N/A")
                print(f"  {run_key}")
                print(f"    Model: {model}")
                print(f"    Status: {status}")
                print(f"    Scenario: {scenario}")
                print(f"    Score: {score}")
                print()
        return 0

    # Validate required arguments for scoring
    if not args.scenario or not args.transcript or not args.rules:
        parser.error("--scenario, --transcript, and --rules are required for scoring")

    # Validate iterations
    if args.iterations < 1:
        parser.error("--iterations must be at least 1")

    try:
        print("InvisibleBench scoring")
        print(f" scenario : {Path(args.scenario).resolve()}")
        print(f" transcript : {Path(args.transcript).resolve()}")
        print(f" rules : {Path(args.rules).resolve()}")
        print(f" iterations : {args.iterations}")

        if args.model:
            print(f" model : {args.model}")
            if args.run_id:
                print(f" run-id : {args.run_id}")

        if args.out:
            print(f" html report -> {Path(args.out).resolve()}")
        if args.json_out:
            print(f" json report -> {Path(args.json_out).resolve()}")

        # Import scoring components
        from invisiblebench.evaluation.orchestrator import ScoringOrchestrator
        from invisiblebench.export.reports import ReportGenerator
        from invisiblebench.utils.progress import ProgressTracker

        # Find scoring config in configs directory
        scoring_config = Path(__file__).parent.parent / "configs" / "scoring.yaml"

        # Create progress tracker
        quiet = getattr(args, 'quiet', False)
        verbose = getattr(args, 'verbose', False)
        progress_tracker = ProgressTracker(
            callback=None,  # We'll use the tracker directly
            verbose=verbose,
            quiet=quiet,
            use_tqdm=True
        )

        # Run scoring pipeline with iterations and run tracking
        orchestrator = ScoringOrchestrator(
            str(scoring_config),
            runs_dir=args.runs_dir,
            enable_state_persistence=bool(args.model) or args.resume,
            progress_callback=progress_tracker.report_dimension,
            save_interval=args.save_interval
        )
        results = orchestrator.score(
            args.transcript,
            args.scenario,
            args.rules,
            model_name=args.model,
            run_id=args.run_id,
            iterations=args.iterations,
            resume=args.resume,
            resume_file=args.resume_file
        )

        # Generate reports
        report_gen = ReportGenerator()

        if args.json_out:
            report_gen.generate_json(results, args.json_out)
            print(f"\nJSON report written to {args.json_out}")

        if args.out:
            report_gen.generate_html(results, args.out)
            print(f"HTML report written to {args.out}")

        # Print summary
        print("\n=== Scoring Summary ===")
        print(f"Overall Score: {results['overall_score']:.2f}")
        print(f"Hard Fail: {results['hard_fail']}")

        # Show variance if multiple iterations
        if args.iterations > 1 and results.get("variance"):
            variance = results["variance"]["overall"]
            print(f"  Mean: {variance['mean']:.2f}")
            print(f"  Std Dev: {variance['std_dev']:.4f}")
            print(f"  Min: {variance['min']:.2f}")
            print(f"  Max: {variance['max']:.2f}")
            if variance.get("cv") is not None:
                print(f"  CV: {variance['cv']:.4f}")

        # Print dimension scores
        for dimension, dim_result in results["dimension_scores"].items():
            print(f"  {dimension.title()}: {dim_result['score']:.2f}")

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=__import__('sys').stderr)
        return 1
    except Exception as e:
        print(f"Error during scoring: {e}", file=__import__('sys').stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
