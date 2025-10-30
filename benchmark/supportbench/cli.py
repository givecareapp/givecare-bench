"""
Main benchmark runner for SupportBench.
"""
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Optional
import uuid

from supportbench.models import Scenario, BenchmarkRun
from supportbench.api import ModelAPIClient, APIConfig
from supportbench.api.client import DEFAULT_TEST_MODELS
from supportbench.session import SessionManager
from supportbench.evaluation import ScenarioEvaluator as ScenarioEvaluator
from supportbench.export import ResultsExporter
from supportbench.export.results_exporter import LeaderboardHTMLGenerator
from supportbench.loaders.scenario_loader import ScenarioLoader


class BenchmarkRunner:
    """Main orchestrator for running SupportBench evaluations."""

    def __init__(
        self,
        api_config: Optional[APIConfig] = None,
        session_approach: str = "hybrid_summary",
        output_dir: str = "./results"
    ):
        """
        Initialize benchmark runner.

        Args:
            api_config: API configuration (defaults to env vars)
            session_approach: Stateful session approach for Tier 3
            output_dir: Directory for results output
        """
        self.api_config = api_config or APIConfig.from_env()
        self.api_client = ModelAPIClient(self.api_config)
        self.session_manager = SessionManager(
            self.api_client,
            approach=session_approach
        )
        self.evaluator = ScenarioEvaluator(
            self.api_client,
            self.session_manager
        )
        self.exporter = ResultsExporter(output_dir)

    def load_scenarios(self, scenario_dir: str) -> List[Scenario]:
        """
        Load all scenario JSON files from directory (recursively).

        Args:
            scenario_dir: Path to scenarios directory

        Returns:
            List of Scenario objects
        """
        loader = ScenarioLoader(scenario_dir)
        scenarios = loader.load_all()

        for scenario in scenarios:
            print(f"Loaded scenario: {scenario.scenario_id} ({scenario.tier.value})")

        return scenarios

    def run_benchmark(
        self,
        models: List[str],
        scenarios: List[Scenario],
        run_id: Optional[str] = None
    ) -> BenchmarkRun:
        """
        Run full benchmark across models and scenarios.

        Args:
            models: List of model identifiers to test
            scenarios: List of scenarios to evaluate
            run_id: Optional run ID (generated if not provided)

        Returns:
            BenchmarkRun with all results
        """
        run_id = run_id or f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
        timestamp = datetime.now().isoformat()

        print(f"\n{'='*60}")
        print(f"SupportBench Evaluation")
        print(f"Run ID: {run_id}")
        print(f"Models: {len(models)}")
        print(f"Scenarios: {len(scenarios)}")
        print(f"{'='*60}\n")

        benchmark_run = BenchmarkRun(
            run_id=run_id,
            timestamp=timestamp,
            models_tested=models,
            scenarios=[s.scenario_id for s in scenarios]
        )

        total_evaluations = len(models) * len(scenarios)
        current_eval = 0

        for model in models:
            print(f"\n--- Evaluating model: {model} ---")

            for scenario in scenarios:
                current_eval += 1
                print(f"\n[{current_eval}/{total_evaluations}] Scenario: {scenario.scenario_id}")

                try:
                    result = self.evaluator.evaluate_scenario(scenario, model)
                    benchmark_run.results.append(result)

                    print(f"  ✓ Score: {result.total_score:.1f}/{result.max_possible_score:.1f}")
                    print(f"  ✓ Autofails: {result.autofail_count}")
                    print(f"  ✓ Time: {result.execution_time_seconds:.1f}s")

                except Exception as e:
                    print(f"  ✗ Error: {e}")
                    continue

        return benchmark_run

    def run_single_scenario(
        self,
        model: str,
        scenario: Scenario
    ):
        """
        Run a single scenario evaluation (useful for testing).

        Args:
            model: Model to test
            scenario: Scenario to evaluate

        Returns:
            ScenarioResult
        """
        print(f"\nEvaluating {model} on {scenario.scenario_id}...")
        result = self.evaluator.evaluate_scenario(scenario, model)

        print(f"\nResults:")
        print(f"  Total Score: {result.total_score:.1f}/{result.max_possible_score:.1f}")
        print(f"  Autofails: {result.autofail_count}")
        print(f"  Passed: {result.passed}")

        print(f"\n  Dimension Scores:")
        for dim, score in result.final_scores.items():
            print(f"    {dim.value}: {score:.1f}")

        return result


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="SupportBench - Benchmark for AI safety in long-term care relationships"
    )
    parser.add_argument(
        "--scenarios",
        type=str,
        default="./scenarios",
        help="Path to scenarios directory"
    )
    parser.add_argument(
        "--models",
        type=str,
        nargs="+",
        help="Models to test (defaults to top 10)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="./results",
        help="Output directory for results"
    )
    parser.add_argument(
        "--session-approach",
        type=str,
        choices=["memory_injection", "full_history", "hybrid_summary"],
        default="hybrid_summary",
        help="Stateful session approach for Tier 3 scenarios"
    )
    parser.add_argument(
        "--single-scenario",
        type=str,
        help="Run single scenario by ID (for testing)"
    )
    parser.add_argument(
        "--single-model",
        type=str,
        help="Test single model (for testing)"
    )
    parser.add_argument(
        "--export-html",
        action="store_true",
        help="Export HTML leaderboard"
    )

    args = parser.parse_args()

    # Initialize runner
    runner = BenchmarkRunner(
        session_approach=args.session_approach,
        output_dir=args.output
    )

    # Load scenarios
    scenarios = runner.load_scenarios(args.scenarios)

    if not scenarios:
        print("No scenarios found. Exiting.")
        return

    # Determine models to test
    models = args.models or DEFAULT_TEST_MODELS

    # Single scenario test mode
    if args.single_scenario:
        scenario = next((s for s in scenarios if s.scenario_id == args.single_scenario), None)
        if not scenario:
            print(f"Scenario {args.single_scenario} not found.")
            return

        model = args.single_model or models[0]
        result = runner.run_single_scenario(model, scenario)

        # Export single result
        output_file = f"{args.output}/single_test_{scenario.scenario_id}_{model.replace('/', '_')}.json"
        runner.exporter.export_scenario_result(result, output_file)
        return

    # Full benchmark run
    benchmark_run = runner.run_benchmark(models, scenarios)

    # Export results
    output_dir = runner.exporter.export_benchmark_run(benchmark_run)

    # Generate HTML leaderboard if requested
    if args.export_html:
        leaderboard = benchmark_run.get_leaderboard()
        heatmap_data = runner.exporter._generate_heatmap_data(benchmark_run)
        html_file = f"{output_dir}/leaderboard.html"

        LeaderboardHTMLGenerator.generate_html(
            leaderboard,
            heatmap_data,
            html_file
        )

    print(f"\n{'='*60}")
    print(f"Benchmark complete!")
    print(f"Results: {output_dir}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
