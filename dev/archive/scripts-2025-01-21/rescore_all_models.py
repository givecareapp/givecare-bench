#!/usr/bin/env python3
"""Re-score all model transcripts with revised compliance rubric (Tier 0 Crisis Override)."""
import json
import sys
from pathlib import Path
from typing import Dict, Any, List
import yaml

# Add benchmark to path
sys.path.insert(0, str(Path(__file__).parent / "benchmark"))

from invisiblebench.evaluation.scorers import compliance_revised
from invisiblebench.api import ModelAPIClient


def load_transcript(result_file: Path) -> List[Dict[str, Any]]:
    """Load transcript from result file."""
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
    # Get model filter from command line (optional)
    model_filter = sys.argv[1] if len(sys.argv) > 1 else None

    print("=" * 80)
    print("RE-SCORING ALL MODELS WITH TIER 0 CRISIS OVERRIDE")
    print("=" * 80)
    print()

    # Initialize API client
    print("Initializing API client...")
    api_client = ModelAPIClient()

    # Find all result files
    results_dir = Path("results/full_validation")
    all_files = sorted(results_dir.glob("*.json"))

    if model_filter:
        all_files = [f for f in all_files if model_filter in f.name]
        print(f"Filtering to model: {model_filter}")

    print(f"Found {len(all_files)} result files")
    print()

    # Group by model
    models = {}
    for f in all_files:
        model_name = "_".join(f.stem.split("_")[:2])
        if model_name not in models:
            models[model_name] = []
        models[model_name].append(f)

    # Re-score each model
    all_comparisons = {}

    for model_name, files in sorted(models.items()):
        print(f"\n{'=' * 80}")
        print(f"MODEL: {model_name}")
        print(f"{'=' * 80}\n")

        comparisons = []

        for i, result_file in enumerate(files, 1):
            print(f"[{i}/{len(files)}] Re-scoring {result_file.name}...")

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

        # Generate model summary
        if comparisons:
            total = len(comparisons)
            originally_failed = sum(1 for c in comparisons if c["original"]["hard_fail"])
            now_failed = sum(1 for c in comparisons if c["revised"]["hard_fail"])

            avg_old = sum(c["original"]["compliance"] for c in comparisons) / total
            avg_new = sum(c["revised"]["compliance"] for c in comparisons) / total

            print(f"\n{model_name} SUMMARY:")
            print(f"  Hard Fails: {originally_failed}/{total} → {now_failed}/{total} ({now_failed - originally_failed:+d})")
            print(f"  Avg Compliance: {avg_old:.3f} → {avg_new:.3f} ({avg_new - avg_old:+.3f})")
            print()

            all_comparisons[model_name] = {
                "summary": {
                    "total": total,
                    "originally_failed": originally_failed,
                    "now_failed": now_failed,
                    "avg_old_compliance": avg_old,
                    "avg_new_compliance": avg_new
                },
                "comparisons": comparisons
            }

    # Save all results
    output_file = Path("results/all_models_rescore_comparison.json")
    with open(output_file, "w") as f:
        json.dump(all_comparisons, f, indent=2)

    print(f"\n{'=' * 80}")
    print(f"All results saved to: {output_file}")
    print(f"{'=' * 80}\n")

    # Print cross-model comparison
    print("\n" + "=" * 80)
    print("CROSS-MODEL COMPARISON")
    print("=" * 80)
    print()
    print(f"{'Model':<30} {'Original':<15} {'Revised':<15} {'Improvement':<15}")
    print("-" * 80)

    for model_name, data in sorted(all_comparisons.items()):
        s = data["summary"]
        orig = f"{s['avg_old_compliance']:.3f}"
        rev = f"{s['avg_new_compliance']:.3f}"
        imp = f"{s['avg_new_compliance'] - s['avg_old_compliance']:+.3f}"
        print(f"{model_name:<30} {orig:<15} {rev:<15} {imp:<15}")

    print()


if __name__ == "__main__":
    main()
