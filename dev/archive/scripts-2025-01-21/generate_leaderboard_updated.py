#!/usr/bin/env python3
"""Generate leaderboard.json from updated Belonging/Trauma scores."""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

def load_model_results(model_prefix: str) -> List[Dict[str, Any]]:
    """Load all result files for a model."""
    results_dir = Path("results/full_validation")
    result_files = sorted(results_dir.glob(f"{model_prefix}_*.json"))

    results = []
    for f in result_files:
        # Skip files that don't have tier info
        if f.name.startswith("all_"):
            continue

        with open(f) as file:
            data = json.load(file)
            # Extract scenario info from filename
            # Format: provider_model_tier_scenario.json
            parts = f.stem.split("_")
            tier_idx = None
            for i, part in enumerate(parts):
                if part.startswith("tier") or part.startswith("conf"):
                    tier_idx = i
                    break

            if tier_idx:
                tier = parts[tier_idx]
                scenario = "_".join(parts[tier_idx:])
            else:
                tier = "unknown"
                scenario = f.stem

            data["tier"] = tier
            data["scenario"] = scenario
            data["scenario_id"] = f.stem

            results.append(data)

    return results

def generate_model_entry(model_name: str, model_prefix: str) -> Dict[str, Any]:
    """Generate leaderboard entry for a model."""
    results = load_model_results(model_prefix)

    if not results:
        return None

    # Calculate aggregate scores
    all_scores = {
        "memory": [],
        "trauma": [],
        "belonging": [],
        "compliance": [],
        "safety": []
    }

    total_cost = 0.0
    scenarios = []

    for result in results:
        # Get dimension scores (handle both "dimensions" and "dimension_scores" keys)
        dims = result.get("dimensions", result.get("dimension_scores", {}))

        # Collect dimension scores
        all_scores["memory"].append(dims.get("memory", 0.0))
        all_scores["trauma"].append(dims.get("trauma", 0.0))
        all_scores["belonging"].append(dims.get("belonging", 0.0))
        all_scores["compliance"].append(dims.get("compliance", 0.0))
        all_scores["safety"].append(dims.get("safety", 0.0))

        total_cost += result.get("total_cost", 0.0)

        # Build scenario entry
        scenarios.append({
            "scenario": result["scenario"],
            "tier": result["tier"],
            "overall_score": result.get("overall_score", 0.0),
            "dimension_scores": {
                "memory": dims.get("memory", 0.0),
                "trauma": dims.get("trauma", 0.0),
                "belonging": dims.get("belonging", 0.0),
                "compliance": dims.get("compliance", 0.0),
                "safety": dims.get("safety", 0.0)
            },
            "status": "completed"
        })

    # Calculate average dimension scores
    avg_scores = {
        dim: sum(scores) / len(scores) if scores else 0.0
        for dim, scores in all_scores.items()
    }

    # Calculate overall score (weighted average)
    weights = {
        "memory": 0.25,
        "trauma": 0.25,
        "belonging": 0.20,
        "compliance": 0.20,
        "safety": 0.10
    }

    overall_score = sum(avg_scores[dim] * weight for dim, weight in weights.items())

    return {
        "model": model_name,
        "model_name": model_name,
        "scenarios": scenarios,
        "dimension_scores": avg_scores,
        "total_cost": total_cost,
        "benchmark_version": "v1.1.0",
        "timestamp": datetime.utcnow().isoformat(),
        "overall_score": overall_score
    }

def main():
    """Generate leaderboard data."""
    print("Generating leaderboard with updated Belonging/Trauma scores...")

    # Model definitions
    models = [
        ("Claude Sonnet 4.5", "anthropic_claude-sonnet-4.5"),
        ("DeepSeek Chat v3", "deepseek_deepseek-chat-v3-0324"),
        ("Gemini 2.5 Flash", "google_gemini-2.5-flash"),
        ("GPT-4o Mini", "openai_gpt-4o-mini")
    ]

    leaderboard = []

    for model_name, model_prefix in models:
        print(f"\nProcessing {model_name}...")

        entry = generate_model_entry(model_name, model_prefix)

        if entry:
            leaderboard.append(entry)
            print(f"  Overall: {entry['overall_score']:.3f}")
            print(f"  Memory: {entry['dimension_scores']['memory']:.3f}")
            print(f"  Trauma: {entry['dimension_scores']['trauma']:.3f}")
            print(f"  Belonging: {entry['dimension_scores']['belonging']:.3f}")
            print(f"  Compliance: {entry['dimension_scores']['compliance']:.3f}")
            print(f"  Safety: {entry['dimension_scores']['safety']:.3f}")
            print(f"  Scenarios: {len(entry['scenarios'])}")

    # Sort by overall score (descending)
    leaderboard.sort(key=lambda x: x["overall_score"], reverse=True)

    # Add ranks
    for i, entry in enumerate(leaderboard, 1):
        entry["rank"] = i

    # Build cost efficiency
    cost_efficiency = [
        {
            "model": entry["model"],
            "score": entry["overall_score"],
            "cost": entry["total_cost"],
            "cost_per_point": entry["total_cost"] / entry["overall_score"] if entry["overall_score"] > 0 else 0
        }
        for entry in leaderboard
    ]
    cost_efficiency.sort(key=lambda x: x["cost_per_point"])

    # Generate final JSON
    output = {
        "metadata": {
            "benchmark_version": "v1.1.0",
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "total_models": len(leaderboard),
            "total_scenarios": len(leaderboard[0]["scenarios"]) if leaderboard else 0,
            "note": "Updated with revised Belonging (4 penalty categories) and Trauma-Informed Design (7 principles) scorers (2025-11-21)"
        },
        "overall_leaderboard": leaderboard,
        "dimension_leaderboards": {},
        "cost_efficiency": cost_efficiency,
        "autofail_tracking": [],
        "variance_report": []
    }

    # Save to website data directory
    output_path = Path("benchmark/website/data/leaderboard.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n{'='*80}")
    print(f"✅ Leaderboard saved to: {output_path}")
    print(f"{'='*80}")
    print(f"\nFinal Rankings:")
    for entry in leaderboard:
        print(f"  #{entry['rank']} {entry['model']}: {entry['overall_score']:.3f}")
        print(f"       Memory: {entry['dimension_scores']['memory']:.3f} | "
              f"Trauma: {entry['dimension_scores']['trauma']:.3f} | "
              f"Belonging: {entry['dimension_scores']['belonging']:.3f} | "
              f"Compliance: {entry['dimension_scores']['compliance']:.3f} | "
              f"Safety: {entry['dimension_scores']['safety']:.3f}")

if __name__ == "__main__":
    main()
