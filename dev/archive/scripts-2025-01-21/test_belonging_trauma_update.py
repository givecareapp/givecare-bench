#!/usr/bin/env python3
"""
Test script for updated Belonging and Trauma scorers.

Re-scores existing Claude Sonnet 4.5 transcripts to validate:
1. Belonging scores drop from 85-97% to 60-85% (stricter criteria)
2. Trauma scores reflect 7 new trauma-informed principles
"""

import json
import sys
from pathlib import Path

# Add benchmark to path
sys.path.insert(0, str(Path(__file__).parent / "benchmark"))

from invisiblebench.evaluation.orchestrator import ScoringOrchestrator
from invisiblebench.api.client import ModelAPIClient


def load_existing_result(result_path: Path) -> dict:
    """Load existing result JSON to get old scores."""
    with open(result_path, 'r') as f:
        return json.load(f)


def rescore_scenario(
    result_path: Path,
    transcript_path: Path,
    scenario_path: Path,
    orchestrator: ScoringOrchestrator
) -> dict:
    """Re-score a single scenario with updated scorers."""
    # Load original result for comparison
    original = load_existing_result(result_path)

    # Re-score with updated scorers
    print(f"\nRe-scoring: {result_path.name}")
    print(f"  Transcript: {transcript_path.name}")
    print(f"  Scenario: {scenario_path.name}")

    new_results = orchestrator.score(
        transcript_path=str(transcript_path),
        scenario_path=str(scenario_path),
        rules_path="benchmark/configs/rules/base.yaml",
        model_name="Claude Sonnet 4.5"
    )

    # Extract dimension scores
    old_belonging = original.get("dimension_scores", {}).get("belonging", {}).get("score", 0.0)
    new_belonging = new_results.get("dimension_scores", {}).get("belonging", {}).get("score", 0.0)

    old_trauma = original.get("dimension_scores", {}).get("trauma", {}).get("score", 0.0)
    new_trauma = new_results.get("dimension_scores", {}).get("trauma", {}).get("score", 0.0)

    # Print comparison
    belonging_change = new_belonging - old_belonging
    trauma_change = new_trauma - old_trauma

    print(f"\n  📊 BELONGING:")
    print(f"     Old: {old_belonging:.3f} → New: {new_belonging:.3f} ({belonging_change:+.3f})")
    if new_belonging < old_belonging:
        print(f"     ✅ Score decreased as expected (stricter criteria)")
    elif new_belonging > old_belonging:
        print(f"     ⚠️  Score increased (unexpected)")
    else:
        print(f"     ➡️  No change")

    # Show belonging breakdown if available
    belonging_breakdown = new_results.get("dimension_scores", {}).get("belonging", {}).get("breakdown", {})
    if belonging_breakdown:
        print(f"\n  📋 Belonging breakdown:")
        print(f"     Recognition: {belonging_breakdown.get('recognition', 0.0):.2f}")
        print(f"     Agency: {belonging_breakdown.get('agency', 0.0):.2f}")
        print(f"     Connection: {belonging_breakdown.get('connection', 0.0):.2f}")
        print(f"     Explicit Othering Penalty: {belonging_breakdown.get('explicit_othering_penalty', 0.0):.2f}")
        print(f"     Implicit Stereotyping Penalty: {belonging_breakdown.get('implicit_stereotyping_penalty', 0.0):.2f}")
        print(f"     Power-Over Penalty: {belonging_breakdown.get('power_over_penalty', 0.0):.2f}")
        print(f"     Individual Blame Penalty: {belonging_breakdown.get('individual_blame_penalty', 0.0):.2f}")

    print(f"\n  🧠 TRAUMA:")
    print(f"     Old: {old_trauma:.3f} → New: {new_trauma:.3f} ({trauma_change:+.3f})")

    # Show trauma breakdown if available
    trauma_breakdown = new_results.get("dimension_scores", {}).get("trauma", {}).get("breakdown", {})
    if trauma_breakdown:
        print(f"\n  📋 Trauma breakdown:")
        print(f"     Skill Correctness: {trauma_breakdown.get('skill_correctness', 0.0):.2f}")
        print(f"     Grounding Before Advice: {trauma_breakdown.get('grounding_before_advice', 0.0):.2f}")
        print(f"     Boundary Integrity: {trauma_breakdown.get('boundary_integrity', 0.0):.2f}")
        print(f"     Safety & Predictability: {trauma_breakdown.get('safety_predictability', 0.0):.2f}")
        print(f"     Trust & Transparency: {trauma_breakdown.get('trust_transparency', 0.0):.2f}")
        print(f"     Choice & Control: {trauma_breakdown.get('choice_control', 0.0):.2f}")
        print(f"     Empowerment & Agency: {trauma_breakdown.get('empowerment_agency', 0.0):.2f}")
        print(f"     Collaboration & Community: {trauma_breakdown.get('collaboration_community', 0.0):.2f}")
        print(f"     Cultural Sensitivity: {trauma_breakdown.get('cultural_sensitivity', 0.0):.2f}")
        print(f"     Flexibility & Adaptability: {trauma_breakdown.get('flexibility_adaptability', 0.0):.2f}")

    return {
        "scenario": result_path.stem,
        "old_belonging": old_belonging,
        "new_belonging": new_belonging,
        "belonging_change": belonging_change,
        "old_trauma": old_trauma,
        "new_trauma": new_trauma,
        "trauma_change": trauma_change,
        "belonging_breakdown": belonging_breakdown,
        "trauma_breakdown": trauma_breakdown
    }


def main():
    print("="*80)
    print("TESTING UPDATED BELONGING AND TRAUMA SCORERS")
    print("="*80)

    # Initialize orchestrator with updated scorers
    print("\nInitializing orchestrator...")
    orchestrator = ScoringOrchestrator(
        scoring_config_path="benchmark/configs/scoring.yaml",
        enable_state_persistence=False
    )

    # Find all Claude Sonnet 4.5 results
    results_dir = Path("results/full_validation")
    if not results_dir.exists():
        print(f"ERROR: Results directory not found: {results_dir}")
        return 1

    # Test on 3 scenarios (one per tier)
    test_scenarios = [
        {
            "result": "anthropic_claude-sonnet-4.5_tier1_crisis_001.json",
            "transcript": "transcripts/anthropic_claude-sonnet-4.5_tier1_crisis_001.jsonl",
            "scenario": "temp_scenario_tier1_crisis_001.yaml"
        },
        {
            "result": "anthropic_claude-sonnet-4.5_tier2_sandwich_001.json",
            "transcript": "transcripts/anthropic_claude-sonnet-4.5_tier2_sandwich_001.jsonl",
            "scenario": "temp_scenario_tier2_sandwich_001.yaml"
        },
        {
            "result": "anthropic_claude-sonnet-4.5_tier3_longitudinal_001.json",
            "transcript": "transcripts/anthropic_claude-sonnet-4.5_tier3_longitudinal_001.jsonl",
            "scenario": "temp_scenario_tier3_longitudinal_001.yaml"
        }
    ]

    all_results = []

    for i, scenario_config in enumerate(test_scenarios, 1):
        print(f"\n{'='*80}")
        print(f"Test {i}/3")
        print(f"{'='*80}")

        result_path = results_dir / scenario_config["result"]
        transcript_path = results_dir / scenario_config["transcript"]
        scenario_path = results_dir / scenario_config["scenario"]

        if not result_path.exists():
            print(f"⚠️  Skipping (result not found): {result_path}")
            continue

        if not transcript_path.exists():
            print(f"⚠️  Skipping (transcript not found): {transcript_path}")
            continue

        if not scenario_path.exists():
            print(f"⚠️  Skipping (scenario not found): {scenario_path}")
            continue

        try:
            result = rescore_scenario(
                result_path=result_path,
                transcript_path=transcript_path,
                scenario_path=scenario_path,
                orchestrator=orchestrator
            )
            all_results.append(result)
        except Exception as e:
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            continue

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    if not all_results:
        print("No successful re-scores")
        return 1

    avg_belonging_change = sum(r["belonging_change"] for r in all_results) / len(all_results)
    avg_trauma_change = sum(r["trauma_change"] for r in all_results) / len(all_results)

    print(f"\nAverage changes across {len(all_results)} scenarios:")
    print(f"  Belonging: {avg_belonging_change:+.3f} (expected: negative)")
    print(f"  Trauma: {avg_trauma_change:+.3f}")

    if avg_belonging_change < 0:
        print("\n✅ Belonging scores decreased as expected (stricter criteria working)")
    else:
        print("\n⚠️  Belonging scores did not decrease (may need rubric adjustment)")

    # Save detailed results
    output_file = Path("test_belonging_trauma_results.json")
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f"\nDetailed results saved to: {output_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
