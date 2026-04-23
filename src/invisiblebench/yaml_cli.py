from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Optional

from invisiblebench._agent_cli import DoctorCheck, doctor_runner, emit_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="invisiblebench",
        description="InvisibleBench scoring CLI. Scores a model transcript against a scenario + rule pack.",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Run environment + state precheck and exit (nonzero on any failure).",
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

    llm_group = parser.add_mutually_exclusive_group()
    llm_group.add_argument(
        "--enable-llm",
        action="store_true",
        help="Enable LLM-assisted scoring (requires API keys).",
    )
    llm_group.add_argument(
        "--offline",
        action="store_true",
        help="Force offline scoring (deterministic).",
    )

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
        help="List runs (bounded by --limit) and exit.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Max runs returned by --list-runs (default: 25).",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Skip N runs before returning --list-runs results (default: 0).",
    )
    parser.add_argument(
        "--format",
        choices=["json"],
        default=None,
        help=(
            "Output format for --list-runs. 'json' emits an agent-friendly "
            "{status, command, data:{total, limit, offset, runs}} envelope."
        ),
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


def _doctor_checks(runs_dir: str) -> list[DoctorCheck]:
    """Doctor checks: at least one LLM API key and a writable runs dir."""
    return [
        DoctorCheck(
            name="LLM API key (OPENROUTER_API_KEY | OPENAI_API_KEY | ANTHROPIC_API_KEY)",
            check=lambda: any(
                os.environ.get(k)
                for k in ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")
            ),
            hint="export at least one provider key; LLM scoring is opt-in via --enable-llm",
        ),
        DoctorCheck(
            name=f"runs_dir exists ({runs_dir})",
            check=lambda: Path(runs_dir).exists() or Path(runs_dir).parent.exists(),
            hint="directory will be created on first run if parent exists",
        ),
        DoctorCheck(
            name="runs_dir writable",
            check=lambda: os.access(
                Path(runs_dir) if Path(runs_dir).exists() else Path(runs_dir).parent,
                os.W_OK,
            ),
            hint="check directory permissions",
        ),
    ]


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.doctor:
        return doctor_runner(_doctor_checks(args.runs_dir), exit_on_fail=False)

    from invisiblebench.evaluation.run_manager import RunManager

    if args.reset:
        run_manager = RunManager(runs_dir=args.runs_dir)
        deleted = run_manager.delete_runs_by_model(args.reset)
        print(f"Deleted {deleted} run(s) for model '{args.reset}'")
        return 0

    if args.list_runs:
        run_manager = RunManager(runs_dir=args.runs_dir)
        all_runs = run_manager.list_runs()
        total = len(all_runs)
        offset = max(0, args.offset)
        limit = max(1, args.limit)
        runs = all_runs[offset : offset + limit]
        if args.format == "json":
            emit_json(
                command="list-runs",
                data={
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "runs": runs,
                },
            )
            return 0
        if not runs:
            print("No runs found." if total == 0 else f"No runs in range (total={total}).")
        else:
            print(f"Showing {len(runs)} of {total} run(s) [offset={offset}, limit={limit}]:\n")
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

    if not args.scenario or not args.transcript or not args.rules:
        parser.error("--scenario, --transcript, and --rules are required for scoring")

    if args.iterations < 1:
        parser.error("--iterations must be at least 1")

    try:
        enable_llm = bool(args.enable_llm)
        if args.offline:
            enable_llm = False

        from invisiblebench.utils.llm_mode import llm_enabled

        actual_llm_enabled = llm_enabled(enable_llm)

        print("InvisibleBench scoring")
        print(f" scenario : {Path(args.scenario).resolve()}")
        print(f" transcript : {Path(args.transcript).resolve()}")
        print(f" rules : {Path(args.rules).resolve()}")
        print(f" iterations : {args.iterations}")
        print(f" llm mode : {'llm' if actual_llm_enabled else 'offline'}")

        if args.model:
            print(f" model : {args.model}")
            if args.run_id:
                print(f" run-id : {args.run_id}")

        if args.out:
            print(f" html report -> {Path(args.out).resolve()}")
        if args.json_out:
            print(f" json report -> {Path(args.json_out).resolve()}")

        from invisiblebench.evaluation.orchestrator import ScoringOrchestrator
        from invisiblebench.export.reports import ReportGenerator
        from invisiblebench.utils.benchmark_inventory import get_project_root
        from invisiblebench.utils.progress import ProgressTracker

        scoring_config = get_project_root() / "benchmark" / "configs" / "scoring.yaml"

        quiet = getattr(args, "quiet", False)
        verbose = getattr(args, "verbose", False)
        progress_tracker = ProgressTracker(
            callback=None,
            verbose=verbose,
            quiet=quiet,
            use_tqdm=True,
        )

        orchestrator = ScoringOrchestrator(
            str(scoring_config),
            runs_dir=args.runs_dir,
            enable_state_persistence=bool(args.model) or args.resume,
            progress_callback=progress_tracker.report_dimension,
            save_interval=args.save_interval,
            enable_llm=enable_llm,
        )
        results = orchestrator.score(
            args.transcript,
            args.scenario,
            args.rules,
            model_name=args.model,
            run_id=args.run_id,
            iterations=args.iterations,
            resume=args.resume,
            resume_file=args.resume_file,
        )

        report_gen = ReportGenerator()

        if args.json_out:
            report_gen.generate_json(results, args.json_out)
            print(f"\nJSON report written to {args.json_out}")

        if args.out:
            report_gen.generate_html(results, args.out)
            print(f"HTML report written to {args.out}")

        print("\n=== Scoring Summary ===")
        print(f"Overall Score: {results['overall_score']:.2f}")
        print(f"Hard Fail: {results['hard_fail']}")

        if args.iterations > 1 and results.get("variance"):
            variance = results["variance"]["overall"]
            print(f"  Mean: {variance['mean']:.2f}")
            print(f"  Std Dev: {variance['std_dev']:.4f}")
            print(f"  Min: {variance['min']:.2f}")
            print(f"  Max: {variance['max']:.2f}")
            if variance.get("cv") is not None:
                print(f"  CV: {variance['cv']:.4f}")

        for dimension, dim_result in results["dimension_scores"].items():
            print(f"  {dimension.title()}: {dim_result['score']:.2f}")

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=__import__("sys").stderr)
        return 1
    except Exception as e:
        print(f"Error during scoring: {e}", file=__import__("sys").stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
