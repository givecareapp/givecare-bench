"""
Quick start example for InvisibleBench.

This script demonstrates how to:
1. Load scenarios
2. Run a single evaluation
3. Export results
"""
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from invisiblebench.cli import BenchmarkRunner


def main():
    """Run quick start example."""
    print("InvisibleBench Quick Start")
    print("=" * 60)

    # Check for API key
    if not os.getenv("OPENROUTER_API_KEY"):
        print("\nError: OPENROUTER_API_KEY environment variable not set")
        print("Please set it with: export OPENROUTER_API_KEY='your_key_here'")
        return

    # Initialize runner
    print("\n1. Initializing benchmark runner...")
    runner = BenchmarkRunner(
        session_approach="hybrid_summary",
        output_dir="./results"
    )

    # Load scenarios
    print("\n2. Loading scenarios...")
    scenarios = runner.load_scenarios("./scenarios")
    print(f"   Loaded {len(scenarios)} scenarios")

    for scenario in scenarios:
        print(f"   - {scenario.scenario_id} ({scenario.tier.value})")

    # Test with single scenario
    if scenarios:
        scenario = scenarios[0]
        model = "anthropic/claude-3.7-sonnet"

        print("\n3. Running evaluation...")
        print(f"   Scenario: {scenario.scenario_id}")
        print(f"   Model: {model}")

        try:
            result = runner.run_single_scenario(model, scenario)

            print("\n4. Results:")
            print(f"   Overall Score: {result.total_score:.1f}/100")
            print(f"   Autofails: {result.autofail_count}")
            print(f"   Passed: {'✓' if result.passed else '✗'}")

            print("\n   Dimension Breakdown (normalized scores):")
            for dim, score in result.final_scores.items():
                percentage = score * 100
                print(f"   - {dim.value}: {percentage:.1f}%")

            # Export result
            output_file = f"./results/quickstart_{scenario.scenario_id}_{model.replace('/', '_')}.json"
            runner.exporter.export_scenario_result(result, output_file)

            print(f"\n5. Full results exported to: {output_file}")

        except Exception as e:
            print(f"\n   Error during evaluation: {e}")
            print("   This might be due to API access or rate limits.")

    print("\n" + "=" * 60)
    print("Quick start complete!")
    print("\nNext steps:")
    print("- Review OPERATIONS.md for full benchmark runs")
    print("- Check scenarios/ directory for example scenarios")
    print("- See README.md for complete documentation")


if __name__ == "__main__":
    main()
