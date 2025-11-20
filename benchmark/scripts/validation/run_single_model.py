#!/usr/bin/env python3
"""Run benchmark with ONLY ONE model to test scoring variance."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from supportbench.evaluation.run_manager import RunManager
from supportbench.api.client import ModelAPIClient

def main():
    # Single model, single scenario test
    model = "anthropic/claude-sonnet-4.5"
    scenario = "benchmark/scenarios/tier1/crisis/crisis_detection.json"

    print("=" * 60)
    print("SINGLE MODEL TEST")
    print("=" * 60)
    print(f"Model: {model}")
    print(f"Scenario: {scenario}")
    print("=" * 60)

    client = ModelAPIClient()
    manager = RunManager(client=client, output_dir="results/single_model_test")

    # Run the evaluation
    result = manager.run_single_evaluation(
        model_id=model,
        scenario_path=scenario,
        output_dir="results/single_model_test"
    )

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Overall Score: {result['overall_score']:.3f}")
    print(f"\nDimension Scores:")
    for dim, score in result['dimensions'].items():
        print(f"  {dim}: {score:.3f}")
    print(f"\nHard Fail: {result['hard_fail']}")
    print(f"Cost: ${result['cost']:.4f}")
    print("=" * 60)

if __name__ == "__main__":
    main()
