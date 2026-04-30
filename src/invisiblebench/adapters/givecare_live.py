#!/usr/bin/env python3
"""GiveCare live system harness for InvisibleBench.

Runs benchmark scenarios against the deployed Mira agent via Convex API.
Generates transcripts that can be scored by the InvisibleBench benchmark core.

Usage:
    # Standard public benchmark run (50 scenarios)
    uv run python -m invisiblebench.adapters.givecare_live --all --score -v

    # Include private confidential scenarios (requires env var)
    INVISIBLEBENCH_PRIVATE_CONFIDENTIAL_SCENARIOS_DIR=/path/to/private/confidential uv run python -m invisiblebench.adapters.givecare_live --all --score --confidential

    # Single scenario
    uv run python -m invisiblebench.adapters.givecare_live --scenario benchmark/scenarios/safety/crisis/cssrs_passive_ideation.json

    uv run python -m invisiblebench.adapters.givecare_live --all --category safety --score
"""

import argparse
import json
import os
import random
import string
import sys
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

from invisiblebench.models.results import is_result_success
from invisiblebench.results_io import write_json, write_model_results
from invisiblebench.run_audit import audit_results_source, render_audit_markdown
from invisiblebench.utils.benchmark_inventory import (
    collect_scenario_paths,
    get_private_confidential_dir,
    get_project_root,
    scenario_category_for_path,
)
from invisiblebench.utils.manifest import generate_manifest, write_manifest

PROJECT_ROOT = get_project_root()

load_dotenv(PROJECT_ROOT / ".env")


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
    """Live harness that sends messages to GiveCare/Mira via gc CLI."""

    def __init__(self, deployment: str = DEFAULT_DEPLOYMENT, wait_ms: int = 15000):
        self.deployment = deployment
        self.wait_ms = wait_ms
        self.phone = self._generate_phone()

        # Path to gc CLI (default sibling polyrepo checkout: ../gc-sms)
        self.givecare_dir = Path(os.environ.get("GIVECARE_SMS_REPO", PROJECT_ROOT.parent / "gc-sms"))
        self.gc_cli = self.givecare_dir / "packages" / "cli" / "dist" / "index.js"

        if not self.gc_cli.exists():
            raise RuntimeError(f"gc CLI not found at {self.gc_cli}")

    def _generate_phone(self) -> str:
        """Generate a random test phone number."""
        suffix = "".join(random.choices(string.digits, k=7))
        return f"+1555{suffix}"

    def _run_gc(self, args: list[str]) -> str:
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

        output = result.stdout + result.stderr
        if result.returncode != 0:
            raise RuntimeError(
                f"gc CLI simulate failed (exit {result.returncode}): {output.strip() or 'no output'}"
            )
        return output

    def bootstrap(self) -> None:
        """Pre-boot a phone number by calling playground:createPreBootstrappedCaregiver.

        Bypasses the SMS opt-in flow entirely, creating a fully-consented, bootstrapped
        caregiver record directly in Convex. Scenario turns then reach Mira's activeSupport
        loop without hitting the consent gate.
        """
        deployment_url = DEPLOYMENTS[self.deployment]
        resp = requests.post(
            f"{deployment_url}/api/action",
            json={
                "path": "playground:createPreBootstrappedCaregiver",
                "args": {"phone": self.phone},
            },
            timeout=30,
        )
        resp.raise_for_status()

    def reset(self) -> None:
        """Bootstrap the phone number so scenario turns reach Mira directly."""
        self.bootstrap()

    def send_message(self, message: str) -> str:
        """Send a message and get Mira's response.

        Retries once with a longer wait if no response is captured on the first attempt.
        """
        for attempt in range(2):
            wait = self.wait_ms if attempt == 0 else self.wait_ms + 5000
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
                    str(wait),
                ]
            )

            response = self._parse_mira_response(output)
            if response:
                return response

        raise RuntimeError("gc simulate returned no response after 2 attempts")

    @staticmethod
    def _parse_mira_response(output: str) -> str | None:
        """Extract Mira's response from gc simulate output. Returns None if not found."""
        lines = output.strip().split("\n")
        for i, line in enumerate(lines):
            if line.startswith("Mira:"):
                response_lines = []
                response_lines.append(line[5:].strip())
                for j in range(i + 1, len(lines)):
                    if lines[j].strip().startswith("(") and lines[j].strip().endswith("ms)"):
                        break
                    response_lines.append(lines[j])
                text = "\n".join(response_lines).strip()
                if text:
                    return text
        return None

    def close(self):
        """No cleanup needed for CLI-based provider."""
        pass


def load_scenario(scenario_path: str) -> dict:
    """Load a scenario JSON file."""
    with open(scenario_path) as f:
        return json.load(f)


def get_category_from_path(scenario_path: Path) -> str:
    """Extract category from scenario path."""
    return scenario_category_for_path(
        scenario_path,
        get_private_confidential_dir(get_project_root()),
    )



def get_scenario_title(scenario: dict, scenario_path: Path) -> str:
    """Get human-readable scenario title."""
    if "title" in scenario:
        return scenario["title"]
    scenario_id = scenario.get("scenario_id", scenario_path.stem)
    return scenario_id.replace("_", " ").title()


def get_turns_from_scenario(scenario: dict) -> list[dict]:
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
) -> tuple[Path, dict]:
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
    prev_assistant_msg: str | None = None
    errors: list[str] = []

    for turn in turns:
        turn_num = turn["turn_number"]

        # Resolve conditional branch (adaptive user message).
        user_msg, branch_id = resolve_branch(turn, prev_assistant_msg)

        if verbose:
            branch_label = f" [branch:{branch_id}]" if branch_id else ""
            print(f"[{turn_num}] User{branch_label}: {user_msg}")

        user_entry: dict = {
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
            errors.append(f"Turn {turn_num}: {e}")
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
            break

    output_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = output_dir / f"givecare_{scenario_id}.jsonl"

    try:
        import jsonlines
    except ImportError as exc:
        raise RuntimeError("jsonlines required to write transcripts: pip install jsonlines") from exc

    with jsonlines.open(transcript_path, "w") as writer:
        writer.write_all(transcript)

    if verbose:
        print(f"Saved: {transcript_path}")

    if errors:
        raise RuntimeError(f"Transcript generation had {len(errors)} error(s): {errors[0]}")

    return transcript_path, scenario


def get_scenarios(
    scenarios_dir: Path,
    category_filter: list[str] | None = None,
    include_confidential: bool = False,
) -> list[Path]:
    """Get all scenario files, optionally filtered by category.

    By default, returns the public 50-scenario benchmark core.
    Confidential scenarios are private and require
    INVISIBLEBENCH_PRIVATE_CONFIDENTIAL_SCENARIOS_DIR.
    """
    del scenarios_dir
    project_root = get_project_root()
    return collect_scenario_paths(
        project_root,
        category_filter=category_filter,
        include_confidential=include_confidential,
    )


def format_error_result(scenario_path: Path, scenario_data: dict, reason: str) -> dict:
    """Format a system-harness transport/runtime failure as an error result."""
    return {
        "model": MODEL_NAME,
        "model_id": MODEL_ID,
        "provider": PROVIDER_NAME,
        "scenario": get_scenario_title(scenario_data, scenario_path),
        "scenario_id": scenario_data.get("scenario_id", scenario_path.stem),
        "category": get_category_from_path(scenario_path),
        "overall_score": 0.0,
        "hard_fail": True,
        "hard_fail_reasons": [reason],
        "failure_categories": {
            "categories": ["error"],
            "details": {},
            "primary_category": "error",
            "count": 1,
        },
        "gates": {
            "safety": {"passed": False, "reasons": [reason]},
            "compliance": {"passed": False, "reasons": []},
        },
        "dimensions": {"regard": 0.0, "coordination": 0.0},
        "dimension_scores": {},
        "status": "error",
        "error": reason,
        "success": False,
        "contract_version": "2.1.0",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Run the GiveCare live system harness against InvisibleBench scenarios",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Standard run (50 public benchmark scenarios)
  uv run python -m invisiblebench.adapters.givecare_live --all --score -v

  # Include private confidential scenarios (requires env var)
  INVISIBLEBENCH_PRIVATE_CONFIDENTIAL_SCENARIOS_DIR=/path/to/private/confidential uv run python -m invisiblebench.adapters.givecare_live --all --score --confidential

  # Single category
  uv run python -m invisiblebench.adapters.givecare_live --all --category safety --score
        """,
    )
    parser.add_argument("--scenario", "-s", help="Single scenario JSON file")
    parser.add_argument("--all", "-a", action="store_true", help="Run all scenarios")
    parser.add_argument(
        "--category", "-c", type=str, action="append", help="Filter by category (can repeat)"
    )
    parser.add_argument(
        "--confidential",
        action="store_true",
        help="Include private confidential scenarios via INVISIBLEBENCH_PRIVATE_CONFIDENTIAL_SCENARIOS_DIR",
    )
    parser.add_argument("--deployment", "-d", default=DEFAULT_DEPLOYMENT, choices=["dev", "prod"])
    parser.add_argument("--output", "-o", default=None, help="Output directory")
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
    project_root = get_project_root()
    scenarios_dir = project_root / "benchmark" / "scenarios"
    if args.output:
        output_dir = project_root / args.output
    else:
        output_dir = project_root / "results" / "givecare" / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    if args.scenario:
        scenario_paths = [Path(args.scenario)]
    else:
        try:
            scenario_paths = get_scenarios(
                scenarios_dir,
                category_filter=args.category,
                include_confidential=args.confidential,
            )
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)

    if not scenario_paths:
        print("No scenarios found")
        sys.exit(1)

    scenario_count = len(scenario_paths)
    conf_note = " (including confidential)" if args.confidential else ""
    print(
        f"Running {scenario_count} scenario(s) against the GiveCare live system harness "
        f"({args.deployment}){conf_note}"
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = generate_manifest(
        project_root=project_root,
        model_ids=[MODEL_ID],
        harness="givecare",
        mode="live",
        include_confidential=args.confidential,
    )
    write_manifest(manifest, output_dir)

    provider = GiveCareProvider(deployment=args.deployment, wait_ms=args.wait)
    transcript_data = []  # List of (transcript_path, scenario_path, scenario_data)
    results = []
    had_generation_errors = False

    try:
        for scenario_path in scenario_paths:
            # Use fresh phone for each scenario
            provider.phone = provider._generate_phone()

            try:
                transcript_path, scenario_data = run_scenario(
                    provider,
                    str(scenario_path),
                    output_dir / "transcripts",
                    verbose=args.verbose,
                )
                transcript_data.append((transcript_path, scenario_path, scenario_data))
            except Exception as e:
                had_generation_errors = True
                scenario_data = load_scenario(str(scenario_path))
                reason = f"Transcript generation failed: {e}"
                print(f"  {scenario_path.stem}: ERROR ({e})")
                if args.score:
                    results.append(format_error_result(scenario_path, scenario_data, reason))
    finally:
        provider.close()

    print(f"\nGenerated {len(transcript_data)} transcript(s) in {output_dir / 'transcripts'}")

    # Optionally score
    if args.score:
        print("ERROR: V2 inline scoring has been archived.")
        print("Score transcripts with V3 ModeEngine instead:")
        print(f"  uv run python scripts/run_scan.py {output_dir / 'transcripts'}")
        print("Skipping scoring; transcripts saved above.")

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

        write_model_results(
            results,
            output_dir / "model_results",
            benchmark_version="unknown",
            timestamp=run_timestamp,
            mode="givecare-live",
            run_metadata={
                "provider": PROVIDER_NAME,
                "deployment": args.deployment,
                "include_confidential": args.confidential,
            },
        )
        write_json(output_dir / "all_results.json", results)
        results_path = output_dir / "givecare_results.json"
        write_json(results_path, output_data)

        # Summary
        passed = sum(1 for r in results if is_result_success(r))
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

        audit = audit_results_source(
            output_dir,
            expected_scenario_count=len(scenario_paths),
            harness="givecare",
            mode="live",
        )
        write_json(output_dir / "run_audit.json", audit)
        (output_dir / "run_audit.md").write_text(render_audit_markdown(audit))
        print(
            "Audit: "
            f"{audit.get('summary_status', 'WARN')} | "
            f"valid={'yes' if audit.get('run_valid') else 'no'} | "
            f"publishable={'yes' if audit.get('publishable') else 'no'}"
        )
    elif had_generation_errors:
        print("\nCompleted with transcript generation errors.")
        sys.exit(1)


if __name__ == "__main__":
    main()
