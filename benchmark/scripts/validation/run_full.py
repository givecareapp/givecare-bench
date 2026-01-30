#!/usr/bin/env python3
"""
Full benchmark script for InvisibleBench.

Runs 10 models x 22 scenarios = 220 evaluations (~$3-5 total cost)

Scenarios by tier:
  - Tier 0: 5 scenarios (smoke tests - crisis detection edge cases)
  - Tier 1: 5 scenarios (3-5 turns - boundaries, crisis, cultural)
  - Tier 2: 9 scenarios (8-12 turns - burnout, belonging, grief)
  - Tier 3: 3 scenarios (20+ turns - longitudinal memory)

Usage:
    python benchmark/scripts/validation/run_full.py --output results/full_benchmark/
    python benchmark/scripts/validation/run_full.py --dry-run  # estimate cost

Requirements:
    export OPENROUTER_API_KEY="your-key"
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# Add parent to path for shared imports
sys.path.insert(0, str(Path(__file__).parent))

from shared import (
    MODELS_FULL,
    check_jsonlines,
    generate_heatmap,
    generate_summary_table,
    generate_transcript,
    get_scenarios,
    load_scenario_json,
    print_plan,
    run_evaluation,
)

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Run full InvisibleBench benchmark")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/full_benchmark"),
        help="Output directory for results"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Estimate costs without running evaluations"
    )
    parser.add_argument(
        "--skip-transcripts",
        action="store_true",
        help="Skip transcript generation (use existing transcripts)"
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Auto-confirm (skip interactive prompt)"
    )
    parser.add_argument(
        "--include-confidential",
        action="store_true",
        help="Include confidential holdout scenarios (not for public leaderboard).",
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Write per-scenario JSON/HTML reports with turn flags",
    )

    args = parser.parse_args()

    # Get scenarios
    scenarios = get_scenarios(include_confidential=args.include_confidential, minimal=False)
    models = MODELS_FULL

    if args.include_confidential:
        print("WARNING: Including confidential scenarios. Do not submit these results to the leaderboard.")

    # Create output directory
    args.output.mkdir(parents=True, exist_ok=True)

    # Print plan and get cost estimate
    print_plan(models, scenarios, args.output, "FULL BENCHMARK")

    if args.dry_run:
        print("DRY RUN - No evaluations will be run")
        return 0

    # Check API keys
    if not os.getenv("OPENROUTER_API_KEY"):
        print("ERROR: No API keys found")
        print("Please set OPENROUTER_API_KEY")
        return 1

    # Check jsonlines
    check_jsonlines()

    # Confirm
    if not args.yes:
        response = input("Proceed with evaluations? (y/n): ")
        if response.lower() != 'y':
            print("Cancelled")
            return 0
    else:
        print("Auto-confirmed with --yes flag")

    # Initialize API client
    print("\nInitializing API client...")
    try:
        from invisiblebench.api.client import ModelAPIClient
        api_client = ModelAPIClient()
        print("API client ready")
    except Exception as e:
        print(f"ERROR: Failed to initialize API client: {e}")
        return 1

    # Initialize orchestrator
    print("Initializing scoring orchestrator...")
    try:
        from invisiblebench.evaluation.orchestrator import ScoringOrchestrator
        scoring_config_path = Path("benchmark/configs/scoring.yaml")
        if not scoring_config_path.exists():
            scoring_config_path = args.output / "temp_scoring_config.yaml"

        orchestrator = ScoringOrchestrator(
            scoring_config_path=str(scoring_config_path),
            enable_state_persistence=False,
            enable_llm=True,
        )
        print("Orchestrator ready")
    except Exception as e:
        print(f"ERROR: Failed to initialize orchestrator: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Run evaluations
    results = []
    total = len(models) * len(scenarios)
    start_time = time.time()

    try:
        from tqdm import tqdm
        pbar = tqdm(total=total, desc="Running evaluations")
        use_tqdm = True
    except ImportError:
        use_tqdm = False
        print("Note: Install tqdm for progress bars (pip install tqdm)")

    for model_idx, model in enumerate(models):
        for scenario_idx, scenario_info in enumerate(scenarios):
            eval_num = model_idx * len(scenarios) + scenario_idx + 1

            if not use_tqdm:
                print(f"\n[{eval_num}/{total}] Starting evaluation...")

            # Load scenario
            scenario_path = Path(scenario_info["path"])
            if not scenario_path.exists():
                print(f"  ERROR: Scenario not found: {scenario_path}")
                continue

            scenario = load_scenario_json(str(scenario_path))

            # Generate or load transcript
            transcript_filename = f"{model['id'].replace('/', '_')}_{scenario['scenario_id']}.jsonl"
            transcript_path = args.output / "transcripts" / transcript_filename

            if not args.skip_transcripts or not transcript_path.exists():
                try:
                    transcript_path = generate_transcript(
                        model_id=model["id"],
                        scenario=scenario,
                        api_client=api_client,
                        output_path=transcript_path
                    )
                except Exception as e:
                    print(f"  ERROR generating transcript: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            else:
                print(f"  Using existing transcript: {transcript_path}")

            # Run evaluation
            try:
                result = run_evaluation(
                    model=model,
                    scenario=scenario,
                    scenario_info=scenario_info,
                    transcript_path=transcript_path,
                    output_dir=args.output,
                    orchestrator=orchestrator,
                    detailed_output=args.detailed,
                )
                results.append(result)
            except Exception as e:
                print(f"  ERROR during evaluation: {e}")
                import traceback
                traceback.print_exc()
                continue

            if use_tqdm:
                pbar.update(1)

    if use_tqdm:
        pbar.close()

    end_time = time.time()
    elapsed_time = end_time - start_time

    if not results:
        print("\nERROR: No successful evaluations completed")
        return 1

    # Generate outputs
    print("\n\nGenerating summary outputs...")

    # Save all results
    all_results_path = args.output / "all_results.json"
    with open(all_results_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"All results saved to: {all_results_path}")

    # Generate summary table and heatmap
    generate_summary_table(results, args.output)
    generate_heatmap(results, args.output)

    # Final summary
    total_actual_cost = sum(r['cost'] for r in results)
    successful = len([r for r in results if r['status'] != 'error'])

    print(f"\n{'='*60}")
    print("FULL BENCHMARK COMPLETE")
    print(f"{'='*60}")
    print(f"Total evaluations: {len(results)}/{total}")
    print(f"Successful: {successful}")
    print(f"Failed: {len(results) - successful}")
    print(f"Actual cost: ${total_actual_cost:.2f}")
    print(f"Elapsed time: {elapsed_time/60:.1f} minutes")
    print(f"Results saved to: {args.output}")
    print(f"{'='*60}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
