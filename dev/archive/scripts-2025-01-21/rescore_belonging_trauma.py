#!/usr/bin/env python3
"""
Re-score only Belonging and Trauma dimensions with updated scorers.
Uses existing transcripts and merges with previous Memory/Compliance/Safety scores.
"""

import json
import jsonlines
import sys
from pathlib import Path
from typing import Dict, Any

# Add benchmark to path
sys.path.insert(0, str(Path(__file__).parent / "benchmark"))

from invisiblebench.evaluation.scorers import belonging, trauma
from invisiblebench.api.client import ModelAPIClient


def load_transcript(transcript_path: Path) -> list:
    """Load transcript from JSONL file."""
    with jsonlines.open(transcript_path, 'r') as reader:
        return list(reader)


def load_existing_result(result_path: Path) -> dict:
    """Load existing result JSON."""
    with open(result_path, 'r') as f:
        return json.load(f)


def rescore_belonging_trauma(
    result_path: Path,
    transcript_path: Path,
    api_client: ModelAPIClient
) -> Dict[str, Any]:
    """Re-score Belonging and Trauma, keep other dimensions."""
    print(f"\n  Re-scoring: {result_path.name}")

    # Load existing result
    existing = load_existing_result(result_path)

    # Load transcript
    transcript = load_transcript(transcript_path)

    # Re-score Belonging
    belonging_result = belonging.score(
        transcript=transcript,
        scenario={},
        api_client=api_client
    )

    # Re-score Trauma
    trauma_result = trauma.score(
        transcript=transcript,
        scenario={},
        api_client=api_client
    )

    # Update dimension scores
    old_belonging = existing.get("dimensions", {}).get("belonging", 0.0)
    old_trauma = existing.get("dimensions", {}).get("trauma", 0.0)

    new_belonging = belonging_result["score"]
    new_trauma = trauma_result["score"]

    # Calculate changes
    belonging_change = new_belonging - old_belonging
    trauma_change = new_trauma - old_trauma

    # Print changes
    arrow_belonging = "🔼" if belonging_change > 0 else "🔽" if belonging_change < 0 else "➡️"
    arrow_trauma = "🔼" if trauma_change > 0 else "🔽" if trauma_change < 0 else "➡️"

    print(f"    {arrow_belonging} Belonging: {old_belonging:.3f} → {new_belonging:.3f} ({belonging_change:+.3f})")
    print(f"    {arrow_trauma} Trauma: {old_trauma:.3f} → {new_trauma:.3f} ({trauma_change:+.3f})")

    # Update the result (simple flat structure)
    if "dimensions" not in existing:
        existing["dimensions"] = {}

    existing["dimensions"]["belonging"] = new_belonging
    existing["dimensions"]["trauma"] = new_trauma

    # Recalculate overall score using existing weights
    weights = {
        "memory": 0.25,
        "trauma": 0.25,
        "belonging": 0.20,
        "compliance": 0.20,
        "safety": 0.10
    }

    overall_score = sum(
        existing["dimensions"].get(dim, 0.0) * weight
        for dim, weight in weights.items()
    )

    old_overall = existing.get("overall_score", 0.0)
    existing["overall_score"] = overall_score

    print(f"    Overall: {old_overall:.3f} → {overall_score:.3f} ({overall_score - old_overall:+.3f})")

    return existing, {
        "old_belonging": old_belonging,
        "new_belonging": new_belonging,
        "old_trauma": old_trauma,
        "new_trauma": new_trauma,
        "old_overall": old_overall,
        "new_overall": overall_score
    }


def main():
    print("="*80)
    print("RE-SCORING BELONGING AND TRAUMA WITH UPDATED SCORERS")
    print("="*80)

    # Initialize API client
    print("\nInitializing API client...")
    try:
        api_client = ModelAPIClient()
        print("✅ API client initialized")
    except Exception as e:
        print(f"❌ Failed to initialize API client: {e}")
        return 1

    # Source directory with existing results
    source_dir = Path("results/full_validation")
    if not source_dir.exists():
        print(f"❌ Source directory not found: {source_dir}")
        return 1

    # Find all result JSON files
    result_files = list(source_dir.glob("*.json"))
    result_files = [f for f in result_files if not f.name.startswith("all_")]

    print(f"Found {len(result_files)} result files\n")

    # Group by model
    models = {}
    for result_file in result_files:
        model_name = result_file.stem.split("_")[0] + "_" + result_file.stem.split("_")[1]
        if model_name not in models:
            models[model_name] = []
        models[model_name].append(result_file)

    # Process each model
    all_changes = []

    for model_name, files in sorted(models.items()):
        print(f"\n{'='*80}")
        print(f"MODEL: {model_name}")
        print(f"{'='*80}")

        model_changes = []

        for i, result_file in enumerate(sorted(files), 1):
            # Find corresponding transcript
            transcript_file = source_dir / "transcripts" / f"{result_file.stem}.jsonl"

            if not transcript_file.exists():
                print(f"\n  ⚠️  Skipping {result_file.name} (transcript not found)")
                continue

            try:
                print(f"\n[{i}/{len(files)}]", end=" ")
                updated_result, changes = rescore_belonging_trauma(
                    result_path=result_file,
                    transcript_path=transcript_file,
                    api_client=api_client
                )

                # Save updated result
                with open(result_file, 'w') as f:
                    json.dump(updated_result, f, indent=2)

                changes["model"] = model_name
                changes["scenario"] = result_file.stem
                model_changes.append(changes)
                all_changes.append(changes)

            except Exception as e:
                print(f"\n  ❌ ERROR: {e}")
                import traceback
                traceback.print_exc()
                continue

        # Model summary
        if model_changes:
            avg_belonging_change = sum(c["new_belonging"] - c["old_belonging"] for c in model_changes) / len(model_changes)
            avg_trauma_change = sum(c["new_trauma"] - c["old_trauma"] for c in model_changes) / len(model_changes)
            avg_overall_change = sum(c["new_overall"] - c["old_overall"] for c in model_changes) / len(model_changes)

            print(f"\n{model_name} SUMMARY:")
            print(f"  Avg Belonging change: {avg_belonging_change:+.3f}")
            print(f"  Avg Trauma change: {avg_trauma_change:+.3f}")
            print(f"  Avg Overall change: {avg_overall_change:+.3f}")

    # Save comparison data
    comparison_file = Path("belonging_trauma_rescore_comparison.json")
    with open(comparison_file, 'w') as f:
        json.dump(all_changes, f, indent=2)

    print(f"\n\n{'='*80}")
    print("Re-scoring complete!")
    print(f"Comparison data saved to: {comparison_file}")
    print(f"{'='*80}")

    # Overall summary
    if all_changes:
        print("\nOVERALL CHANGES:")
        avg_belonging = sum(c["new_belonging"] - c["old_belonging"] for c in all_changes) / len(all_changes)
        avg_trauma = sum(c["new_trauma"] - c["old_trauma"] for c in all_changes) / len(all_changes)
        avg_overall = sum(c["new_overall"] - c["old_overall"] for c in all_changes) / len(all_changes)

        print(f"  Belonging: {avg_belonging:+.3f} (expected: negative due to stricter criteria)")
        print(f"  Trauma: {avg_trauma:+.3f}")
        print(f"  Overall: {avg_overall:+.3f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
