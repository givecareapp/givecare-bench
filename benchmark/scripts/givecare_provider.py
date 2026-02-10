#!/usr/bin/env python3
"""
GiveCare Provider for InvisibleBench

Runs benchmark scenarios against the deployed Mira agent via Convex API.
Generates transcripts that can be scored by the InvisibleBench scorer.

Usage:
    # Standard run (29 scenarios, matches leaderboard)
    python benchmark/scripts/givecare_provider.py --all --score -v

    # Include confidential scenarios (32 total)
    python benchmark/scripts/givecare_provider.py --all --score --confidential

    # Single scenario
    python benchmark/scripts/givecare_provider.py --scenario benchmark/scenarios/tier1/crisis/crisis_detection.json

    # Filter by tier
    python benchmark/scripts/givecare_provider.py --all --tier 1 --score
"""

import argparse
import json
import random
import string
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Load .env for API keys
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

try:
    import jsonlines
except ImportError:
    print("jsonlines required: pip install jsonlines")
    sys.exit(1)


# Provider metadata
PROVIDER_NAME = "givecare"
PROVIDER_VERSION = "1.0.0"
MODEL_NAME = "GiveCare (Mira)"
MODEL_ID = "givecare/mira"

# Convex deployment URLs
DEPLOYMENTS = {
    "dev": "https://agreeable-lion-831.convex.cloud",
    "prod": "https://doting-tortoise-411.convex.cloud",
}

DEFAULT_DEPLOYMENT = "dev"


class GiveCareProvider:
    """Provider that sends messages to GiveCare/Mira via gc CLI."""

    def __init__(self, deployment: str = DEFAULT_DEPLOYMENT, wait_ms: int = 6000):
        self.deployment = deployment
        self.wait_ms = wait_ms
        self.phone = self._generate_phone()

        # Path to gc CLI (in givecare repo)
        self.gc_cli = (
            Path(__file__).parent.parent.parent.parent
            / "givecare"
            / "packages"
            / "cli"
            / "dist"
            / "index.js"
        )
        self.givecare_dir = Path(__file__).parent.parent.parent.parent / "givecare"

        if not self.gc_cli.exists():
            raise RuntimeError(f"gc CLI not found at {self.gc_cli}")

    def _generate_phone(self) -> str:
        """Generate a random test phone number."""
        suffix = "".join(random.choices(string.digits, k=7))
        return f"+1555{suffix}"

    def _run_gc(self, args: List[str]) -> str:
        """Run gc CLI command and return output."""
        import subprocess

        cmd = ["node", str(self.gc_cli)] + args
        result = subprocess.run(
            cmd,
            cwd=str(self.givecare_dir),
            capture_output=True,
            text=True,
            timeout=60,
        )

        return result.stdout + result.stderr

    def reset(self) -> None:
        """Reset the test user (handled by gc CLI per-run)."""
        pass  # gc CLI resets automatically

    def send_message(self, message: str) -> str:
        """Send a message and get Mira's response."""
        output = self._run_gc(
            [
                "simulate",
                "--message",
                message,
                "--phone",
                self.phone,
                "--deployment",
                self.deployment,
                "--wait",
                str(self.wait_ms),
            ]
        )

        # Parse response from output
        # Format: "User: ...\nMira: <response>\n(XXXms)"
        lines = output.strip().split("\n")
        for i, line in enumerate(lines):
            if line.startswith("Mira:"):
                # Get everything after "Mira: " until timing line
                response_lines = []
                response_lines.append(line[5:].strip())
                for j in range(i + 1, len(lines)):
                    if lines[j].strip().startswith("(") and lines[j].strip().endswith("ms)"):
                        break
                    response_lines.append(lines[j])
                return "\n".join(response_lines).strip()

        return "(no response)"

    def close(self):
        """No cleanup needed for CLI-based provider."""
        pass


def load_scenario(scenario_path: str) -> Dict:
    """Load a scenario JSON file."""
    with open(scenario_path) as f:
        return json.load(f)


def get_tier_from_path(scenario_path: Path) -> int:
    """Extract tier number from scenario path."""
    path_str = str(scenario_path)
    if "/tier0/" in path_str:
        return 0
    elif "/tier1/" in path_str:
        return 1
    elif "/tier2/" in path_str:
        return 2
    elif "/tier3/" in path_str:
        return 3
    elif "/confidential/" in path_str:
        return -1  # Confidential scenarios
    return -1


def get_scenario_title(scenario: Dict, scenario_path: Path) -> str:
    """Get human-readable scenario title."""
    if "title" in scenario:
        return scenario["title"]
    # Convert scenario_id to title case
    scenario_id = scenario.get("scenario_id", scenario_path.stem)
    return scenario_id.replace("_", " ").title()


def get_turns_from_scenario(scenario: Dict) -> List[Dict]:
    """Extract turns from a scenario (handles both single and multi-session)."""
    if "sessions" in scenario:
        all_turns = []
        for session in scenario["sessions"]:
            all_turns.extend(session.get("turns", []))
        return all_turns
    return scenario.get("turns", [])


def run_scenario(
    provider: GiveCareProvider,
    scenario_path: str,
    output_dir: Path,
    verbose: bool = False,
) -> tuple[Path, Dict]:
    """Run a single scenario and generate transcript. Returns (transcript_path, scenario_data)."""
    scenario = load_scenario(scenario_path)
    scenario_id = scenario.get("scenario_id", Path(scenario_path).stem)
    turns = get_turns_from_scenario(scenario)

    if verbose:
        print(f"\n=== {scenario.get('title', scenario_id)} ===")
        print(f"Phone: {provider.phone}")

    # Reset user before scenario
    provider.reset()

    from invisiblebench.evaluation.branching import resolve_branch

    transcript = []
    prev_assistant_msg: Optional[str] = None

    for turn in turns:
        turn_num = turn["turn_number"]

        # Resolve conditional branch (adaptive user message).
        user_msg, branch_id = resolve_branch(turn, prev_assistant_msg)

        if verbose:
            branch_label = f" [branch:{branch_id}]" if branch_id else ""
            print(f"[{turn_num}] User{branch_label}: {user_msg}")

        user_entry: Dict = {
            "turn": turn_num,
            "role": "user",
            "content": user_msg,
        }
        if branch_id is not None:
            user_entry["branch_id"] = branch_id
        transcript.append(user_entry)

        try:
            response = provider.send_message(user_msg)

            if verbose:
                print(f"    Mira: {response[:100]}{'...' if len(response) > 100 else ''}")

            transcript.append(
                {
                    "turn": turn_num,
                    "role": "assistant",
                    "content": response,
                }
            )
            prev_assistant_msg = response
        except Exception as e:
            error_msg = f"[ERROR: {e}]"
            if verbose:
                print(f"    ERROR: {e}")
            transcript.append(
                {
                    "turn": turn_num,
                    "role": "assistant",
                    "content": error_msg,
                    "error": True,
                }
            )
            prev_assistant_msg = None

    # Save transcript
    output_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = output_dir / f"givecare_{scenario_id}.jsonl"

    with jsonlines.open(transcript_path, "w") as writer:
        writer.write_all(transcript)

    if verbose:
        print(f"Saved: {transcript_path}")

    return transcript_path, scenario


def get_scenarios(
    scenarios_dir: Path,
    tier_filter: Optional[List[int]] = None,
    include_confidential: bool = False,
) -> List[Path]:
    """Get all scenario files, optionally filtered by tier.

    By default, excludes confidential scenarios to match leaderboard (29 scenarios).
    Use include_confidential=True for full set (32 scenarios).
    """
    scenarios = []

    for tier_dir in ["tier0", "tier1", "tier2", "tier3"]:
        tier_num = int(tier_dir[-1])
        if tier_filter and tier_num not in tier_filter:
            continue

        tier_path = scenarios_dir / tier_dir
        if not tier_path.exists():
            continue

        # Handle nested directories (tier1/crisis/, etc.)
        for item in tier_path.rglob("*.json"):
            scenarios.append(item)

    # Include confidential scenarios only if explicitly requested
    if include_confidential:
        conf_path = scenarios_dir / "confidential"
        if conf_path.exists():
            for item in conf_path.rglob("*.json"):
                scenarios.append(item)

    return sorted(scenarios)


def format_result(
    scenario_path: Path,
    scenario_data: Dict,
    score_result: Dict,
) -> Dict:
    """Format a single result to match InvisibleBench standard format."""
    scenario_id = scenario_data.get("scenario_id", scenario_path.stem)
    tier = get_tier_from_path(scenario_path)
    title = get_scenario_title(scenario_data, scenario_path)

    overall_score = score_result.get("overall_score", 0.0)
    hard_fail = score_result.get("hard_fail", False)
    hard_fail_reasons = score_result.get("hard_fail_reasons", [])

    # Extract dimension scores (flatten to just scores for consistency)
    dimension_scores = {}
    raw_dimensions = score_result.get("dimension_scores", {})
    for dim_name, dim_data in raw_dimensions.items():
        if isinstance(dim_data, dict):
            dimension_scores[dim_name] = dim_data.get("score", 0.0)
        else:
            dimension_scores[dim_name] = dim_data

    # Build failure categories
    failure_categories = {
        "categories": [],
        "details": {},
        "primary_category": None,
        "count": 0,
    }
    if hard_fail:
        # Determine failure category from hard_fail_reasons
        for reason in hard_fail_reasons:
            if "safety" in reason.lower() or "crisis" in reason.lower():
                failure_categories["categories"].append("safety")
            elif "compliance" in reason.lower():
                failure_categories["categories"].append("compliance")
        failure_categories["count"] = len(failure_categories["categories"])
        if failure_categories["categories"]:
            failure_categories["primary_category"] = failure_categories["categories"][0]

    return {
        "model": MODEL_NAME,
        "model_id": MODEL_ID,
        "provider": PROVIDER_NAME,
        "scenario": title,
        "scenario_id": scenario_id,
        "tier": tier,
        "overall_score": overall_score,
        "hard_fail": hard_fail,
        "hard_fail_reasons": hard_fail_reasons,
        "failure_categories": failure_categories,
        "dimensions": dimension_scores,
        "dimensions_detailed": raw_dimensions,  # Keep full details for debugging
        "status": "fail" if hard_fail else "pass",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Run GiveCare against InvisibleBench scenarios",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Standard run (29 scenarios, matches leaderboard)
  python givecare_provider.py --all --score -v

  # Include confidential scenarios (32 total)
  python givecare_provider.py --all --score --confidential

  # Single tier
  python givecare_provider.py --all --tier 1 --score
        """,
    )
    parser.add_argument("--scenario", "-s", help="Single scenario JSON file")
    parser.add_argument("--all", "-a", action="store_true", help="Run all scenarios")
    parser.add_argument(
        "--tier", "-t", type=int, action="append", help="Filter by tier (can repeat)"
    )
    parser.add_argument(
        "--confidential", action="store_true", help="Include confidential scenarios (32 vs 29)"
    )
    parser.add_argument("--deployment", "-d", default=DEFAULT_DEPLOYMENT, choices=["dev", "prod"])
    parser.add_argument("--output", "-o", default="results/givecare", help="Output directory")
    parser.add_argument(
        "--wait", "-w", type=int, default=6000, help="Wait time between send/receive (ms)"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--score", action="store_true", help="Score transcripts after generation")

    args = parser.parse_args()

    if not args.scenario and not args.all:
        parser.print_help()
        print("\nError: Must specify --scenario or --all")
        sys.exit(1)

    # Find project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    scenarios_dir = project_root / "benchmark" / "scenarios"
    output_dir = project_root / args.output

    # Get scenarios to run
    if args.scenario:
        scenario_paths = [Path(args.scenario)]
    else:
        scenario_paths = get_scenarios(
            scenarios_dir,
            args.tier,
            include_confidential=args.confidential,
        )

    if not scenario_paths:
        print("No scenarios found")
        sys.exit(1)

    scenario_count = len(scenario_paths)
    conf_note = " (including confidential)" if args.confidential else ""
    print(f"Running {scenario_count} scenario(s) against GiveCare ({args.deployment}){conf_note}")

    provider = GiveCareProvider(deployment=args.deployment, wait_ms=args.wait)
    transcript_data = []  # List of (transcript_path, scenario_path, scenario_data)

    try:
        for scenario_path in scenario_paths:
            # Use fresh phone for each scenario
            provider.phone = provider._generate_phone()

            transcript_path, scenario_data = run_scenario(
                provider,
                str(scenario_path),
                output_dir / "transcripts",
                verbose=args.verbose,
            )
            transcript_data.append((transcript_path, scenario_path, scenario_data))
    finally:
        provider.close()

    print(f"\nGenerated {len(transcript_data)} transcript(s) in {output_dir / 'transcripts'}")

    # Optionally score
    if args.score:
        print("\nScoring transcripts...")
        from invisiblebench.evaluation.orchestrator import ScoringOrchestrator

        scoring_config = project_root / "benchmark" / "configs" / "scoring.yaml"
        rules_path = project_root / "benchmark" / "configs" / "rules" / "base.yaml"

        orchestrator = ScoringOrchestrator(
            scoring_config_path=str(scoring_config),
            enable_state_persistence=False,
            enable_llm=True,
        )

        results = []
        for transcript_path, scenario_path, scenario_data in transcript_data:
            try:
                score_result = orchestrator.score(
                    transcript_path=str(transcript_path),
                    scenario_path=str(scenario_path),
                    rules_path=str(rules_path),
                    model_name=MODEL_NAME,
                )

                # Format to standard format
                formatted = format_result(scenario_path, scenario_data, score_result)
                results.append(formatted)

                score = formatted["overall_score"]
                status = "FAIL" if formatted["hard_fail"] else "PASS"
                print(f"  {formatted['scenario']}: {status} ({int(score * 100)}%)")

            except Exception as e:
                print(f"  {scenario_path.stem}: ERROR ({e})")
                # Create error result in standard format
                scenario_id = scenario_data.get("scenario_id", scenario_path.stem)
                results.append(
                    {
                        "model": MODEL_NAME,
                        "model_id": MODEL_ID,
                        "provider": PROVIDER_NAME,
                        "scenario": get_scenario_title(scenario_data, scenario_path),
                        "scenario_id": scenario_id,
                        "tier": get_tier_from_path(scenario_path),
                        "overall_score": 0.0,
                        "hard_fail": True,
                        "hard_fail_reasons": [str(e)],
                        "failure_categories": {
                            "categories": ["error"],
                            "details": {},
                            "primary_category": "error",
                            "count": 1,
                        },
                        "dimensions": {},
                        "status": "error",
                        "error": str(e),
                    }
                )

        # Save results with metadata
        run_timestamp = datetime.now().isoformat()
        output_data = {
            "metadata": {
                "provider": PROVIDER_NAME,
                "provider_version": PROVIDER_VERSION,
                "model": MODEL_NAME,
                "model_id": MODEL_ID,
                "deployment": args.deployment,
                "timestamp": run_timestamp,
                "scenario_count": len(results),
                "include_confidential": args.confidential,
            },
            "results": results,
        }

        results_path = output_dir / "givecare_results.json"
        with open(results_path, "w") as f:
            json.dump(output_data, f, indent=2)

        # Summary
        passed = sum(1 for r in results if not r.get("hard_fail"))
        failed = len(results) - passed
        avg_score = sum(r["overall_score"] for r in results) / len(results) * 100 if results else 0

        print(f"\n{'='*50}")
        print("GiveCare Eval Results")
        print(f"{'='*50}")
        print(f"Scenarios: {len(results)}")
        print(f"Passed:    {passed}")
        print(f"Failed:    {failed}")
        print(f"Average:   {avg_score:.1f}%")
        print(f"{'='*50}")
        print(f"Saved: {results_path}")


if __name__ == "__main__":
    main()
