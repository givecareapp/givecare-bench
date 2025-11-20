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

import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any


def aggregate_model_results(results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Group results by model and aggregate scores."""
    models = {}

    for result in results:
        model_id = result['model']

        if model_id not in models:
            models[model_id] = {
                'model': model_id,
                'model_name': result.get('model', result.get('model_id', model_id)),
                'scenarios': [],
                'dimension_scores': {},
                'overall_scores': [],
                'total_cost': 0.0,
                'benchmark_version': 'v1.0.0',
                'timestamp': result.get('timestamp', datetime.now().isoformat())
            }

        # Collect scenario results
        models[model_id]['scenarios'].append({
            'scenario': result['scenario'],
            'tier': result['tier'],
            'overall_score': result['overall_score'],
            'dimension_scores': result.get('dimensions', result.get('dimension_scores', {})),
            'status': result['status']
        })

        # Aggregate dimension scores
        for dim, score in result.get('dimensions', result.get('dimension_scores', {})).items():
            if dim not in models[model_id]['dimension_scores']:
                models[model_id]['dimension_scores'][dim] = []
            models[model_id]['dimension_scores'][dim].append(score)

        # Collect overall scores
        models[model_id]['overall_scores'].append(result['overall_score'])

        # Add cost
        models[model_id]['total_cost'] += result.get('cost', 0.0)

    # Compute averages
    for model_id, model_data in models.items():
        # Average dimension scores
        for dim in model_data['dimension_scores']:
            scores = model_data['dimension_scores'][dim]
            model_data['dimension_scores'][dim] = sum(scores) / len(scores)

        # Average overall score
        model_data['overall_score'] = sum(model_data['overall_scores']) / len(model_data['overall_scores'])

        # Remove temporary list
        del model_data['overall_scores']

    return models


def main():
    parser = argparse.ArgumentParser(description='Prepare validation results for leaderboard')
    parser.add_argument(
        '--input',
        required=True,
        help='Path to all_results.json from validation'
    )
    parser.add_argument(
        '--output',
        required=True,
        help='Output directory for per-model JSON files'
    )

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
        safe_name = model_id.replace('/', '_').replace(' ', '_')
        output_file = output_dir / f"{safe_name}.json"

        with open(output_file, 'w') as f:
            json.dump(model_data, f, indent=2)

        print(f"✓ {model_data['model_name']}: {output_file}")

    print(f"\nReady for leaderboard generation!")
    print(f"Run: python benchmark/scripts/community/generate_leaderboard.py \\")
    print(f"       --input {output_dir} \\")
    print(f"       --output benchmark/website/data/")


if __name__ == '__main__':
    main()
