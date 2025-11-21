#!/usr/bin/env python3
"""Generate leaderboard.json with revised compliance scores."""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

def load_original_results(model_prefix: str) -> List[Dict[str, Any]]:
    """Load original result files for a model."""
    results_dir = Path("results/full_validation")
    result_files = sorted(results_dir.glob(f"{model_prefix}_*.json"))

    results = []
    for f in result_files:
        with open(f) as file:
            results.append(json.load(file))

    return results

def load_rescored_compliance() -> Dict[str, Dict[str, Any]]:
    """Load rescored compliance scores."""
    with open("results/all_models_rescore_comparison.json") as f:
        data = json.load(f)

    # Build lookup: model -> scenario_id -> revised compliance
    compliance_lookup = {}

    for model_name, model_data in data.items():
        compliance_lookup[model_name] = {}
        for comparison in model_data["comparisons"]:
            scenario_id = comparison["scenario_id"]
            compliance_lookup[model_name][scenario_id] = comparison["revised"]["compliance"]

    return compliance_lookup

def generate_model_entry(model_name: str, model_prefix: str, compliance_scores: Dict[str, float]) -> Dict[str, Any]:
    """Generate leaderboard entry for a model."""
    original_results = load_original_results(model_prefix)

    if not original_results:
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

    for result in original_results:
        scenario_id = result["scenario_id"]

        # Get revised compliance score
        revised_compliance = compliance_scores.get(scenario_id, result["dimensions"]["compliance"])

        # Collect dimension scores
        all_scores["memory"].append(result["dimensions"]["memory"])
        all_scores["trauma"].append(result["dimensions"]["trauma"])
        all_scores["belonging"].append(result["dimensions"]["belonging"])
        all_scores["compliance"].append(revised_compliance)
        all_scores["safety"].append(result["dimensions"]["safety"])

        total_cost += result.get("total_cost", 0.0)

        # Build scenario entry
        scenarios.append({
            "scenario": result["scenario"],
            "tier": result["tier"],
            "overall_score": result["overall_score"],  # Note: This uses original overall, not recalculated
            "dimension_scores": {
                "memory": result["dimensions"]["memory"],
                "trauma": result["dimensions"]["trauma"],
                "belonging": result["dimensions"]["belonging"],
                "compliance": revised_compliance,
                "safety": result["dimensions"]["safety"]
            },
            "status": "completed"
        })

    # Calculate average dimension scores
    avg_scores = {
        dim: sum(scores) / len(scores) if scores else 0.0
        for dim, scores in all_scores.items()
    }

    # Calculate overall score (average of all dimensions)
    overall_score = sum(avg_scores.values()) / len(avg_scores) if avg_scores else 0.0

    return {
        "model": model_name,
        "model_name": model_name,
        "scenarios": scenarios,
        "dimension_scores": avg_scores,
        "total_cost": total_cost,
        "benchmark_version": "v1.1.0-revised",
        "timestamp": datetime.utcnow().isoformat(),
        "overall_score": overall_score
    }

def main():
    """Generate leaderboard data."""
    print("Generating leaderboard with revised compliance scores...")

    # Load rescored compliance data
    compliance_lookup = load_rescored_compliance()

    # Model definitions
    models = [
        ("GPT-4o Mini", "openai_gpt-4o-mini", "openai_gpt-4o-mini"),
        ("DeepSeek Chat v3", "deepseek_deepseek-chat-v3-0324", "deepseek_deepseek-chat-v3-0324"),
        ("Claude Sonnet 4.5", "anthropic_claude-sonnet-4.5", "anthropic_claude-sonnet-4.5"),
        ("Gemini 2.5 Flash", "google_gemini-2.5-flash", "google_gemini-2.5-flash")
    ]

    leaderboard = []

    for model_name, model_prefix, lookup_key in models:
        print(f"Processing {model_name}...")

        compliance_scores = compliance_lookup.get(lookup_key, {})
        entry = generate_model_entry(model_name, model_prefix, compliance_scores)

        if entry:
            leaderboard.append(entry)
            print(f"  Overall: {entry['overall_score']:.3f}")
            print(f"  Compliance: {entry['dimension_scores']['compliance']:.3f}")

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
            "benchmark_version": "v1.1.0-revised",
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "total_models": len(leaderboard),
            "total_scenarios": len(leaderboard[0]["scenarios"]) if leaderboard else 0,
            "note": "Compliance scores updated with Tier 0 Crisis Override framework (2025-11-21)"
        },
        "overall_leaderboard": leaderboard,
        "dimension_leaderboards": {
            "crisis_safety": [],
            "regulatory_fitness": [],
            "trauma_informed_flow": [],
            "belonging_cultural_fitness": [],
            "relational_quality": [],
            "actionable_support": [],
            "longitudinal_consistency": [],
            "memory_hygiene": []
        },
        "cost_efficiency": cost_efficiency,
        "autofail_tracking": [],
        "variance_report": []
    }

    # Save to website data directory
    output_path = Path("benchmark/website/data/leaderboard.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ Leaderboard saved to: {output_path}")
    print(f"\nFinal Rankings:")
    for entry in leaderboard:
        print(f"  #{entry['rank']} {entry['model']}: {entry['overall_score']:.3f} (Compliance: {entry['dimension_scores']['compliance']:.3f})")

if __name__ == "__main__":
    main()
