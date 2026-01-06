"""
Test suite for orchestrator iteration support.

Tests the orchestrator's ability to run multiple iterations and aggregate results.
"""
from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TRANSCRIPT_PATH = PROJECT_ROOT / "benchmark" / "tests" / "fixtures" / "sample_transcript.jsonl"
SCENARIO_PATH = PROJECT_ROOT / "benchmark" / "scenarios" / "tier2" / "burnout" / "sandwich_generation_burnout.json"
RULES_PATH = PROJECT_ROOT / "benchmark" / "configs" / "rules" / "ny.yaml"
SCORING_PATH = PROJECT_ROOT / "benchmark" / "invisiblebench" / "scoring.yaml"


class TestOrchestratorIterationSupport:
    """Test orchestrator iteration functionality."""

    transcript_path = str(TRANSCRIPT_PATH)
    scenario_path = str(SCENARIO_PATH)
    rules_path = str(RULES_PATH)
    scoring_path = str(SCORING_PATH)

    def test_orchestrator_single_iteration_default(self):
        """Default behavior (no iterations specified) should run once."""
        from invisiblebench.evaluation.orchestrator import ScoringOrchestrator

        orchestrator = ScoringOrchestrator(scoring_config_path=self.scoring_path)
        results = orchestrator.score(
            self.transcript_path, self.scenario_path, self.rules_path, iterations=1
        )

        # Should have single iteration results
        assert "iterations" in results
        assert len(results["iterations"]) == 1

        # Should NOT have variance for N=1
        assert "variance" not in results or results["variance"] is None

    def test_orchestrator_multiple_iterations(self):
        """Running with iterations=3 should execute scoring 3 times."""
        from invisiblebench.evaluation.orchestrator import ScoringOrchestrator

        orchestrator = ScoringOrchestrator(scoring_config_path=self.scoring_path)
        results = orchestrator.score(
            self.transcript_path, self.scenario_path, self.rules_path, iterations=3
        )

        # Should have 3 iteration results
        assert "iterations" in results
        assert len(results["iterations"]) == 3

        # Each iteration should have complete scoring
        for i, iter_result in enumerate(results["iterations"], 1):
            assert iter_result["iteration"] == i
            assert "overall_score" in iter_result
            assert "dimension_scores" in iter_result
            assert 0 <= iter_result["overall_score"] <= 1

    def test_orchestrator_iterations_calculate_variance(self):
        """Multiple iterations should include variance metrics."""
        from invisiblebench.evaluation.orchestrator import ScoringOrchestrator

        orchestrator = ScoringOrchestrator(scoring_config_path=self.scoring_path)
        results = orchestrator.score(
            self.transcript_path, self.scenario_path, self.rules_path, iterations=5
        )

        # Should have variance section
        assert "variance" in results
        assert results["variance"] is not None

        # Should have overall variance
        assert "overall" in results["variance"]
        assert "mean" in results["variance"]["overall"]
        assert "std_dev" in results["variance"]["overall"]
        assert "min" in results["variance"]["overall"]
        assert "max" in results["variance"]["overall"]
        assert "cv" in results["variance"]["overall"]

        # Should have dimension variance
        assert "dimensions" in results["variance"]
        for dimension in ["memory", "trauma", "belonging", "compliance", "safety"]:
            assert dimension in results["variance"]["dimensions"]
            dim_var = results["variance"]["dimensions"][dimension]
            assert "mean" in dim_var
            assert "std_dev" in dim_var

    def test_orchestrator_iterations_use_mean_scores(self):
        """Final scores should be mean across iterations."""
        from invisiblebench.evaluation.orchestrator import ScoringOrchestrator

        orchestrator = ScoringOrchestrator(scoring_config_path=self.scoring_path)
        results = orchestrator.score(
            self.transcript_path, self.scenario_path, self.rules_path, iterations=3
        )

        # Calculate expected mean manually
        overall_scores = [iter_result["overall_score"] for iter_result in results["iterations"]]
        expected_mean = sum(overall_scores) / len(overall_scores)

        # Final overall_score should match mean
        assert results["overall_score"] == pytest.approx(expected_mean, abs=0.001)

    def test_orchestrator_iterations_invalid_count(self):
        """Invalid iteration counts should raise ValueError."""
        from invisiblebench.evaluation.orchestrator import ScoringOrchestrator

        orchestrator = ScoringOrchestrator(scoring_config_path=self.scoring_path)

        # Zero iterations
        with pytest.raises(ValueError, match="at least 1"):
            orchestrator.score(
                self.transcript_path, self.scenario_path, self.rules_path, iterations=0
            )

        # Negative iterations
        with pytest.raises(ValueError, match="at least 1"):
            orchestrator.score(
                self.transcript_path, self.scenario_path, self.rules_path, iterations=-1
            )

    def test_orchestrator_iterations_preserve_metadata(self):
        """Metadata should be preserved across iterations."""
        from invisiblebench.evaluation.orchestrator import ScoringOrchestrator

        orchestrator = ScoringOrchestrator(scoring_config_path=self.scoring_path)
        results = orchestrator.score(
            self.transcript_path, self.scenario_path, self.rules_path, iterations=3
        )

        # Should preserve metadata
        assert "metadata" in results
        assert "scenario_id" in results["metadata"]
        assert "jurisdiction" in results["metadata"]

        # Should add iterations info to metadata
        assert "iterations_run" in results["metadata"]
        assert results["metadata"]["iterations_run"] == 3

    def test_orchestrator_deterministic_scoring_yields_identical_results(self):
        """Deterministic scorers should yield identical scores across iterations."""
        from invisiblebench.evaluation.orchestrator import ScoringOrchestrator

        orchestrator = ScoringOrchestrator(scoring_config_path=self.scoring_path)
        results = orchestrator.score(
            self.transcript_path, self.scenario_path, self.rules_path, iterations=3
        )

        # Since scorers are deterministic, all iterations should be identical
        first_score = results["iterations"][0]["overall_score"]
        for iter_result in results["iterations"]:
            assert iter_result["overall_score"] == first_score

        # Variance should be zero
        assert results["variance"]["overall"]["std_dev"] == 0.0

    def test_orchestrator_backward_compatibility(self):
        """score() without iterations parameter should work (defaults to 1)."""
        from invisiblebench.evaluation.orchestrator import ScoringOrchestrator

        orchestrator = ScoringOrchestrator(scoring_config_path=self.scoring_path)

        # Should work without iterations parameter
        results = orchestrator.score(self.transcript_path, self.scenario_path, self.rules_path)

        # Should still produce valid results
        assert "overall_score" in results
        assert "dimension_scores" in results


class TestCLIIterationSupport:
    """Test CLI iteration flag."""

    def test_cli_accepts_iterations_flag(self):
        """CLI should accept --iterations flag."""
        from invisiblebench.yaml_cli import build_parser

        parser = build_parser()

        # Should parse --iterations flag
        args = parser.parse_args([
            "--scenario", "test.yaml",
            "--transcript", "test.jsonl",
            "--rules", "rules.yaml",
            "--iterations", "5"
        ])

        assert hasattr(args, "iterations")
        assert args.iterations == 5

    def test_cli_iterations_default_to_one(self):
        """CLI should default to 1 iteration if not specified."""
        from invisiblebench.yaml_cli import build_parser

        parser = build_parser()

        # Should default to 1
        args = parser.parse_args([
            "--scenario", "test.yaml",
            "--transcript", "test.jsonl",
            "--rules", "rules.yaml",
        ])

        assert hasattr(args, "iterations")
        assert args.iterations == 1

    def test_cli_iterations_must_be_positive(self):
        """CLI should parse non-positive iterations (validated in main())."""
        from invisiblebench.yaml_cli import build_parser

        parser = build_parser()

        # Zero and negative are parsed but caught in main()
        # This test just confirms they can be parsed as integers
        args = parser.parse_args([
            "--scenario", "test.yaml",
            "--transcript", "test.jsonl",
            "--rules", "rules.yaml",
            "--iterations", "0"
        ])
        assert args.iterations == 0

        args = parser.parse_args([
            "--scenario", "test.yaml",
            "--transcript", "test.jsonl",
            "--rules", "rules.yaml",
            "--iterations", "-1"
        ])
        assert args.iterations == -1

    def test_cli_iterations_must_be_integer(self):
        """CLI should reject non-integer iterations."""
        from invisiblebench.yaml_cli import build_parser

        parser = build_parser()

        # Float should fail
        with pytest.raises(SystemExit):
            parser.parse_args([
                "--scenario", "test.yaml",
                "--transcript", "test.jsonl",
                "--rules", "rules.yaml",
                "--iterations", "3.5"
            ])
