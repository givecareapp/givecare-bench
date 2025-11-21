#!/usr/bin/env python3
"""Re-score Claude Sonnet 4.5 transcripts with revised compliance rubric.

This script:
1. Loads existing Claude evaluation results
2. Re-scores them using the revised three-tier compliance framework
3. Compares old vs. new scores
4. Generates a summary report
"""
import json
import sys
from pathlib import Path
from typing import Dict, Any, List
import yaml

# Add benchmark to path
sys.path.insert(0, str(Path(__file__).parent / "benchmark"))

from supportbench.evaluation.scorers import compliance_revised
from supportbench.api import ModelAPIClient


def load_transcript(result_file: Path) -> List[Dict[str, Any]]:
    """Load transcript from result file."""
    # Get transcript file path
    transcript_file = result_file.parent / "transcripts" / f"{result_file.stem}.jsonl"

    if not transcript_file.exists():
        raise FileNotFoundError(f"Transcript not found: {transcript_file}")

    transcript = []
    with open(transcript_file) as f:
        for line in f:
            if line.strip():
                transcript.append(json.loads(line))

    return transcript


def load_scenario(scenario_id: str) -> Dict[str, Any]:
    """Load scenario definition."""
    # Search for scenario file
    scenarios_dir = Path("benchmark/scenarios")

    for scenario_file in scenarios_dir.rglob("*.json"):
        try:
            with open(scenario_file) as f:
                scenario = json.load(f)
                if scenario.get("scenario_id") == scenario_id:
                    return scenario
        except Exception:
            continue

    # Return minimal scenario if not found
    return {"scenario_id": scenario_id, "risk_triggers": []}


def load_rules() -> Dict[str, Any]:
    """Load compliance rules."""
    rules_file = Path("benchmark/configs/rules/base.yaml")
    with open(rules_file) as f:
        return yaml.safe_load(f)


def rescore_result(result_file: Path, api_client: ModelAPIClient) -> Dict[str, Any]:
    """Re-score a single result file."""
    # Load original result
    with open(result_file) as f:
        original = json.load(f)

    # Load transcript
    transcript = load_transcript(result_file)

    # Load scenario
    scenario = load_scenario(original["scenario_id"])

    # Load rules
    rules = load_rules()

    # Re-score compliance with revised scorer
    new_compliance = compliance_revised.score(
        transcript=transcript,
        scenario=scenario,
        rules=rules,
        api_client=api_client
    )

    return {
        "file": result_file.name,
        "scenario_id": original["scenario_id"],
        "scenario": original["scenario"],
        "tier": original["tier"],
        "original": {
            "compliance": original["dimensions"]["compliance"],
            "overall": original["overall_score"],
            "hard_fail": original["hard_fail"]
        },
        "revised": {
            "compliance": new_compliance["score"],
            "hard_fail": len(new_compliance["hard_fails"]) > 0,
            "soft_violations": len(new_compliance["violations"]),
            "breakdown": new_compliance["breakdown"]
        },
        "evidence": new_compliance["evidence"]
    }


def main():
    """Main re-scoring function."""
    print("=" * 80)
    print("CLAUDE SONNET 4.5 RE-SCORING WITH REVISED COMPLIANCE RUBRIC")
    print("=" * 80)
    print()

    # Initialize API client
    print("Initializing API client...")
    api_client = ModelAPIClient()

    # Find all Claude result files
    results_dir = Path("results/full_validation")
    claude_files = sorted(results_dir.glob("anthropic_claude-sonnet-4.5_*.json"))

    print(f"Found {len(claude_files)} Claude evaluation results")
    print()

    # Re-score each file
    comparisons = []

    for i, result_file in enumerate(claude_files, 1):
        print(f"[{i}/{len(claude_files)}] Re-scoring {result_file.name}...")

        try:
            comparison = rescore_result(result_file, api_client)
            comparisons.append(comparison)

            # Print quick summary
            old_score = comparison["original"]["compliance"]
            new_score = comparison["revised"]["compliance"]
            change = "🔼" if new_score > old_score else ("🔽" if new_score < old_score else "➡️")

            print(f"  {change} Compliance: {old_score:.2f} → {new_score:.2f}")
            if comparison["revised"]["soft_violations"] > 0:
                print(f"     (Soft violations: {comparison['revised']['soft_violations']})")
            print()

        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            print()
            continue

    # Generate summary report
    print("=" * 80)
    print("SUMMARY REPORT")
    print("=" * 80)
    print()

    # Calculate statistics
    total = len(comparisons)
    originally_failed = sum(1 for c in comparisons if c["original"]["hard_fail"])
    now_failed = sum(1 for c in comparisons if c["revised"]["hard_fail"])

    avg_old_compliance = sum(c["original"]["compliance"] for c in comparisons) / total if total > 0 else 0
    avg_new_compliance = sum(c["revised"]["compliance"] for c in comparisons) / total if total > 0 else 0

    improved = sum(1 for c in comparisons if c["revised"]["compliance"] > c["original"]["compliance"])
    unchanged = sum(1 for c in comparisons if c["revised"]["compliance"] == c["original"]["compliance"])
    degraded = sum(1 for c in comparisons if c["revised"]["compliance"] < c["original"]["compliance"])

    print(f"Total Evaluations: {total}")
    print()
    print(f"Hard Fails:")
    print(f"  Original: {originally_failed}/{total} ({originally_failed/total*100:.1f}%)")
    print(f"  Revised:  {now_failed}/{total} ({now_failed/total*100:.1f}%)")
    print(f"  Change:   {now_failed - originally_failed:+d} ({(now_failed - originally_failed)/total*100:+.1f}%)")
    print()
    print(f"Average Compliance Score:")
    print(f"  Original: {avg_old_compliance:.3f}")
    print(f"  Revised:  {avg_new_compliance:.3f}")
    print(f"  Change:   {avg_new_compliance - avg_old_compliance:+.3f} ({(avg_new_compliance - avg_old_compliance)/avg_old_compliance*100:+.1f}%)")
    print()
    print(f"Score Changes:")
    print(f"  Improved:  {improved}/{total} ({improved/total*100:.1f}%)")
    print(f"  Unchanged: {unchanged}/{total} ({unchanged/total*100:.1f}%)")
    print(f"  Degraded:  {degraded}/{total} ({degraded/total*100:.1f}%)")
    print()

    # Show detailed results by tier
    print("Breakdown by Tier:")
    print()
    for tier in [1, 2, 3]:
        tier_results = [c for c in comparisons if c["tier"] == tier]
        if tier_results:
            tier_old = sum(c["original"]["compliance"] for c in tier_results) / len(tier_results)
            tier_new = sum(c["revised"]["compliance"] for c in tier_results) / len(tier_results)
            tier_fails_old = sum(1 for c in tier_results if c["original"]["hard_fail"])
            tier_fails_new = sum(1 for c in tier_results if c["revised"]["hard_fail"])

            print(f"  Tier {tier} ({len(tier_results)} scenarios):")
            print(f"    Compliance: {tier_old:.3f} → {tier_new:.3f} ({tier_new - tier_old:+.3f})")
            print(f"    Hard Fails: {tier_fails_old} → {tier_fails_new} ({tier_fails_new - tier_fails_old:+d})")
            print()

    # Show examples of navigation support that was previously flagged
    print("=" * 80)
    print("EXAMPLES OF NAVIGATION SUPPORT NOW ALLOWED")
    print("=" * 80)
    print()

    for comparison in comparisons:
        if comparison["original"]["hard_fail"] and not comparison["revised"]["hard_fail"]:
            print(f"✅ {comparison['scenario']} ({comparison['scenario_id']})")
            print(f"   Was: Hard Fail → Now: {comparison['revised']['compliance']:.2f}")

            # Show some evidence
            for evidence in comparison["evidence"][:3]:
                if "TIER 3" in evidence or "Allowed" in evidence:
                    print(f"   {evidence}")
            print()

    # Save detailed results
    output_file = Path("results/claude_rescore_comparison.json")
    with open(output_file, "w") as f:
        json.dump({
            "summary": {
                "total": total,
                "originally_failed": originally_failed,
                "now_failed": now_failed,
                "avg_old_compliance": avg_old_compliance,
                "avg_new_compliance": avg_new_compliance,
                "improved": improved,
                "unchanged": unchanged,
                "degraded": degraded
            },
            "comparisons": comparisons
        }, f, indent=2)

    print(f"Detailed results saved to: {output_file}")
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
