#!/usr/bin/env python3
"""
Tier-0 Smoke Test Runner

Ultra-fast deployment gate that runs 5 critical safety scenarios.
ANY autofail = BLOCK deployment immediately.

Usage:
    python run_tier0_smoke_tests.py --model anthropic/claude-sonnet-4.5
    python run_tier0_smoke_tests.py --model openai/gpt-4o --seed 42

Exit codes:
    0: PASS (zero autofails)
    1: FAIL (one or more autofails)
    2: ERROR (runner failure)
"""

import sys
import argparse
import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass

# Add benchmark package to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from invisiblebench.api.client import ModelAPIClient, APIConfig
from invisiblebench.evaluation.evaluator import TriJudgeEvaluator
from invisiblebench.loaders.scenario_loader import ScenarioLoader
from invisiblebench.models import Scenario, TurnEvaluation

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Tier0Result:
    """Result from a single Tier-0 smoke test."""
    scenario_id: str
    scenario_title: str
    passed: bool
    autofail_detected: bool
    autofail_reason: str | None
    turns_evaluated: int
    elapsed_seconds: float


class Tier0SmokeTestRunner:
    """Fail-closed smoke test runner for deployment gating."""

    TIER0_SCENARIOS = [
        "tier0_diagnosis_trap",
        "tier0_dosing_trap",
        "tier0_explicit_si",
        "tier0_masked_si",
        "tier0_attachment_engineering"
    ]

    def __init__(self, model: str, seed: int | None = 42, api_client: ModelAPIClient | None = None):
        """
        Initialize smoke test runner.

        Args:
            model: Model identifier (e.g., "anthropic/claude-sonnet-4.5")
            seed: Random seed for reproducibility (default: 42)
            api_client: Optional API client (creates new if None)
        """
        self.model = model
        self.seed = seed
        self.api_client = api_client or ModelAPIClient()
        self.evaluator = TriJudgeEvaluator(self.api_client)
        self.loader = ScenarioLoader()
        self.results: List[Tier0Result] = []

    def load_tier0_scenarios(self) -> List[Scenario]:
        """Load all Tier-0 smoke test scenarios."""
        scenarios = []
        tier0_dir = Path(__file__).parent.parent.parent / "scenarios" / "tier0"

        if not tier0_dir.exists():
            logger.error(f"Tier-0 directory not found: {tier0_dir}")
            raise FileNotFoundError(f"Tier-0 scenarios directory missing: {tier0_dir}")

        for scenario_file in tier0_dir.glob("*.json"):
            try:
                scenario = self.loader.load_scenario(str(scenario_file))
                scenarios.append(scenario)
                logger.info(f"Loaded: {scenario.scenario_id}")
            except Exception as e:
                logger.error(f"Failed to load {scenario_file}: {e}")
                raise

        if len(scenarios) != 5:
            logger.warning(f"Expected 5 Tier-0 scenarios, found {len(scenarios)}")

        return scenarios

    def run_scenario(self, scenario: Scenario) -> Tier0Result:
        """
        Run a single Tier-0 scenario with fail-fast logic.

        Args:
            scenario: Tier-0 scenario to evaluate

        Returns:
            Tier0Result with pass/fail status
        """
        import time
        start_time = time.time()

        logger.info(f"\n{'='*60}")
        logger.info(f"RUNNING: {scenario.title}")
        logger.info(f"{'='*60}")

        autofail_detected = False
        autofail_reason = None
        turns_evaluated = 0

        try:
            # Run each turn
            context = []
            for turn in scenario.turns:
                turns_evaluated += 1
                logger.info(f"  Turn {turn.turn_number}/{len(scenario.turns)}: {turn.user_message[:60]}...")

                # Build conversation context
                context.append({"role": "user", "content": turn.user_message})

                # Get model response
                model_response_data = self.api_client.call_model(
                    model=self.model,
                    messages=context,
                    temperature=0.7,
                    seed=self.seed if self.seed is not None else None
                )

                model_response_text = model_response_data.get("response", "")
                context.append({"role": "assistant", "content": model_response_text})

                # Evaluate turn
                from invisiblebench.models import ModelResponse
                model_response = ModelResponse(
                    turn_number=turn.turn_number,
                    content=model_response_text,
                    model=self.model
                )

                turn_eval = self.evaluator.evaluate_turn(
                    scenario=scenario,
                    turn=turn,
                    model_response=model_response
                )

                # FAIL-FAST: Check for autofail
                if turn_eval.autofail_detected:
                    autofail_detected = True
                    autofail_reason = turn_eval.autofail_reason
                    logger.error(f"  ❌ AUTOFAIL DETECTED: {autofail_reason}")
                    break  # Stop immediately on autofail

                logger.info(f"  ✓ Turn {turn.turn_number} passed")

        except Exception as e:
            logger.error(f"  ERROR during evaluation: {e}")
            raise

        elapsed = time.time() - start_time
        passed = not autofail_detected

        result = Tier0Result(
            scenario_id=scenario.scenario_id,
            scenario_title=scenario.title,
            passed=passed,
            autofail_detected=autofail_detected,
            autofail_reason=autofail_reason,
            turns_evaluated=turns_evaluated,
            elapsed_seconds=elapsed
        )

        # Log result
        if passed:
            logger.info(f"✅ PASSED: {scenario.title} ({elapsed:.1f}s)")
        else:
            logger.error(f"❌ FAILED: {scenario.title}")
            logger.error(f"   Reason: {autofail_reason}")

        return result

    def run_all(self) -> bool:
        """
        Run all Tier-0 smoke tests.

        Returns:
            True if ALL tests pass (zero autofails), False otherwise
        """
        logger.info(f"\n{'#'*60}")
        logger.info(f"# TIER-0 SMOKE TESTS")
        logger.info(f"# Model: {self.model}")
        logger.info(f"# Seed: {self.seed}")
        logger.info(f"# Gate: FAIL-CLOSED (any autofail = BLOCK)")
        logger.info(f"{'#'*60}\n")

        scenarios = self.load_tier0_scenarios()

        for scenario in scenarios:
            result = self.run_scenario(scenario)
            self.results.append(result)

            # FAIL-FAST: Stop on first autofail
            if not result.passed:
                logger.error(f"\n🚫 DEPLOYMENT BLOCKED")
                logger.error(f"   First autofail in: {scenario.title}")
                logger.error(f"   Reason: {result.autofail_reason}")
                return False

        # All tests passed
        logger.info(f"\n{'#'*60}")
        logger.info(f"# ✅ ALL TIER-0 SMOKE TESTS PASSED")
        logger.info(f"# {len(self.results)}/{len(self.results)} scenarios passed")
        logger.info(f"# Model: {self.model} - DEPLOYMENT APPROVED")
        logger.info(f"{'#'*60}\n")

        return True

    def generate_report(self, output_path: str | None = None):
        """Generate JSON report of smoke test results."""
        report = {
            "model": self.model,
            "seed": self.seed,
            "gate_type": "fail_closed",
            "total_scenarios": len(self.results),
            "passed_scenarios": sum(1 for r in self.results if r.passed),
            "failed_scenarios": sum(1 for r in self.results if not r.passed),
            "deployment_approved": all(r.passed for r in self.results),
            "results": [
                {
                    "scenario_id": r.scenario_id,
                    "scenario_title": r.scenario_title,
                    "passed": r.passed,
                    "autofail_detected": r.autofail_detected,
                    "autofail_reason": r.autofail_reason,
                    "turns_evaluated": r.turns_evaluated,
                    "elapsed_seconds": r.elapsed_seconds
                }
                for r in self.results
            ]
        }

        if output_path:
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"Report saved to: {output_path}")

        return report


def main():
    parser = argparse.ArgumentParser(
        description="Run Tier-0 smoke tests for deployment gating"
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Model to test (e.g., anthropic/claude-sonnet-4.5)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)"
    )
    parser.add_argument(
        "--output",
        help="Path to save JSON report"
    )

    args = parser.parse_args()

    try:
        runner = Tier0SmokeTestRunner(
            model=args.model,
            seed=args.seed
        )

        all_passed = runner.run_all()

        if args.output:
            runner.generate_report(args.output)

        # Exit with appropriate code
        sys.exit(0 if all_passed else 1)

    except Exception as e:
        logger.error(f"SMOKE TEST RUNNER ERROR: {e}", exc_info=True)
        sys.exit(2)


if __name__ == "__main__":
    main()
