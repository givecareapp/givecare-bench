#!/usr/bin/env python3
"""
Convert validation results to leaderboard format.

Takes all_results.json from validation and splits it into per-model files
that the leaderboard generator expects.

Usage:
    python benchmark/scripts/validation/prepare_for_leaderboard.py \
      --input results/minimal_validation/all_results.json \
      --output results/minimal_validation/leaderboard_ready/
"""

import argparse
import json
from pathlib import Path

from invisiblebench.results_io import aggregate_model_results


def main():
    parser = argparse.ArgumentParser(description="Prepare validation results for leaderboard")
    parser.add_argument("--input", required=True, help="Path to all_results.json from validation")
    parser.add_argument("--output", required=True, help="Output directory for per-model JSON files")

    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output)

    # Load validation results
    print(f"Loading results from: {input_path}")
    with open(input_path) as f:
        results = json.load(f)

    print(f"Found {len(results)} evaluation results")

    # Aggregate by model
    models = aggregate_model_results(results)
    print(f"Aggregated into {len(models)} models")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write per-model files
    for model_id, model_data in models.items():
        # Create safe filename
        safe_name = model_id.replace("/", "_").replace(" ", "_")
        output_file = output_dir / f"{safe_name}.json"

        with open(output_file, "w") as f:
            json.dump(model_data, f, indent=2)

        print(f"✓ {model_data['model_name']}: {output_file}")

    print("\nReady for leaderboard generation!")
    print("Run: python benchmark/scripts/leaderboard/generate_leaderboard.py \\")
    print(f"       --input {output_dir} \\")
    print("       --output data/v2/")


if __name__ == "__main__":
    main()
