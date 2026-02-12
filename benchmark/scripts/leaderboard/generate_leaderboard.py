#!/usr/bin/env python3
"""
Generate leaderboard data from canonical benchmark results.

Usage:
    python benchmark/scripts/leaderboard/generate_leaderboard.py --input results/leaderboard_ready/ --output benchmark/website/data/
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set


def load_confidential_ids(base_dir: Path) -> Set[str]:
    """Load confidential scenario IDs from the repo."""
    confidential_dir = base_dir / "benchmark" / "scenarios" / "confidential"
    if not confidential_dir.exists():
        return set()

    ids: Set[str] = set()
    for scenario_file in confidential_dir.glob("*.json"):
        with open(scenario_file) as f:
            data = json.load(f)
        scenario_id = data.get("scenario_id")
        if scenario_id:
            ids.add(scenario_id)
    return ids


def has_confidential_scenarios(result: Dict, confidential_ids: Set[str]) -> bool:
    """Return True if result includes any confidential scenarios."""
    for scenario in result.get("scenarios", []):
        if scenario.get("confidential") is True:
            return True
        scenario_id = scenario.get("scenario_id")
        if scenario_id and scenario_id in confidential_ids:
            return True
    return False


def load_canonical_results(
    results_dir: Path,
    include_confidential: bool,
    confidential_ids: Set[str],
) -> List[Dict]:
    """Load all verified canonical results"""
    results = []
    for result_file in results_dir.glob("*.json"):
        if result_file.name.startswith("."):
            continue

        with open(result_file) as f:
            data = json.load(f)

        if not include_confidential and has_confidential_scenarios(data, confidential_ids):
            print(f"Skipping {result_file.name} (confidential scenarios present)")
            continue

        # Verify integrity (basic check - expand with signature verification)
        if verify_result_integrity(data):
            results.append(data)
        else:
            print(f"⚠️  Skipping {result_file.name} - integrity check failed")

    return results


def verify_result_integrity(result: Dict) -> bool:
    """Basic integrity checks (add signature verification later)"""
    required_fields = ["model", "benchmark_version", "scenarios", "overall_score", "timestamp"]
    return all(field in result for field in required_fields)


def compute_rankings(results: List[Dict]) -> List[Dict]:
    """Compute overall rankings with tie-breaking"""
    # Sort by overall score (descending), then by cost (ascending)
    sorted_results = sorted(
        results, key=lambda r: (-r["overall_score"], r.get("total_cost", float("inf")))
    )

    # Add rank
    for i, result in enumerate(sorted_results, 1):
        result["rank"] = i

    return sorted_results


def compute_dimension_leaderboards(results: List[Dict]) -> Dict[str, List[Dict]]:
    """Create dimension-specific leaderboards"""
    dimensions = [
        "crisis_safety",
        "regulatory_fitness",
        "trauma_informed_flow",
        "belonging_cultural_fitness",
        "relational_quality",
        "actionable_support",
        "longitudinal_consistency",
        "memory_hygiene",
    ]

    dimension_boards = {}
    for dim in dimensions:
        # Extract dimension scores
        dim_results = []
        for result in results:
            dim_score = result.get("dimension_scores", {}).get(dim)
            if dim_score is not None:
                dim_results.append(
                    {
                        "model": result["model"],
                        "score": dim_score,
                        "max_score": result.get("dimension_max_scores", {}).get(dim, 3.0),
                    }
                )

        # Sort by score
        dim_results.sort(key=lambda x: -x["score"])
        dimension_boards[dim] = dim_results

    return dimension_boards


def compute_cost_efficiency(results: List[Dict]) -> List[Dict]:
    """Compute cost-performance frontier"""
    efficiency = []
    for result in results:
        if "total_cost" in result and result["total_cost"] > 0:
            efficiency.append(
                {
                    "model": result["model"],
                    "score": result["overall_score"],
                    "cost": result["total_cost"],
                    "cost_per_point": result["total_cost"] / result["overall_score"],
                }
            )

    # Sort by cost_per_point (lower is better)
    efficiency.sort(key=lambda x: x["cost_per_point"])
    return efficiency


def compute_autofail_tracking(results: List[Dict]) -> List[Dict]:
    """Track models with autofail incidents"""
    autofail_report = []
    for result in results:
        autofails = []
        for scenario in result.get("scenarios", []):
            if scenario.get("autofail_triggered"):
                autofails.append(
                    {
                        "scenario_id": scenario["scenario_id"],
                        "dimension": scenario.get("autofail_dimension"),
                        "reason": scenario.get("autofail_reason"),
                    }
                )

        if autofails:
            autofail_report.append(
                {"model": result["model"], "autofail_count": len(autofails), "incidents": autofails}
            )

    # Sort by autofail_count (descending - worst offenders first)
    autofail_report.sort(key=lambda x: -x["autofail_count"])
    return autofail_report


def _get_code_version() -> str:
    """Read code version from pyproject.toml."""
    import re

    pyproject_path = Path(__file__).resolve().parents[3] / "pyproject.toml"
    if pyproject_path.exists():
        match = re.search(
            r'^version\s*=\s*"([^"]+)"',
            pyproject_path.read_text(),
            re.MULTILINE,
        )
        if match:
            return match.group(1)
    return "unknown"


def compute_safety_report_card(results: List[Dict]) -> Dict:
    """Build safety report card from model results (gate pass/fail per model)."""
    model_reports = []
    scenario_matrix: Dict[str, Dict[str, str]] = {}

    for result in results:
        model = result["model"]
        scenarios = result.get("scenarios", [])
        safety_passed = 0
        safety_failed = 0
        compliance_passed = 0
        compliance_failed = 0
        failures = []

        for s in scenarios:
            sid = s.get("scenario_id", "")
            gates = s.get("gates", {})
            sg = gates.get("safety", {})
            cg = gates.get("compliance", {})
            s_pass = sg.get("passed", True)
            c_pass = cg.get("passed", True)

            if s_pass:
                safety_passed += 1
            else:
                safety_failed += 1
                failures.append({"scenario_id": sid, "gate": "safety", "reasons": sg.get("reasons", [])})

            if c_pass:
                compliance_passed += 1
            else:
                compliance_failed += 1
                failures.append({"scenario_id": sid, "gate": "compliance", "reasons": cg.get("reasons", [])})

            scenario_matrix.setdefault(sid, {})[model] = "PASS" if (s_pass and c_pass) else "FAIL"

        total = len(scenarios)
        model_reports.append({
            "model": model,
            "safety_gate": {
                "passed": safety_passed, "failed": safety_failed,
                "total": total, "pass_rate": safety_passed / total if total else 0.0,
            },
            "compliance_gate": {
                "passed": compliance_passed, "failed": compliance_failed,
                "total": total, "pass_rate": compliance_passed / total if total else 0.0,
            },
            "overall_gate_pass": safety_failed == 0 and compliance_failed == 0,
            "failures": failures,
        })

    return {"models": model_reports, "scenario_matrix": scenario_matrix}


def compute_quality_leaderboard(results: List[Dict]) -> List[Dict]:
    """Rank models by regard + coordination scores (only those passing all gates)."""
    quality_results = []
    for result in results:
        scenarios = result.get("scenarios", [])
        # Check if all gates pass
        all_gates_pass = True
        for s in scenarios:
            gates = s.get("gates", {})
            if not gates.get("safety", {}).get("passed", True):
                all_gates_pass = False
                break
            if not gates.get("compliance", {}).get("passed", True):
                all_gates_pass = False
                break

        # Compute average regard and coordination
        regard_scores = []
        coord_scores = []
        for s in scenarios:
            dims = s.get("dimensions", {})
            if isinstance(dims, dict):
                r = dims.get("regard")
                c = dims.get("coordination")
                if isinstance(r, (int, float)):
                    regard_scores.append(r)
                if isinstance(c, (int, float)):
                    coord_scores.append(c)

        avg_regard = sum(regard_scores) / len(regard_scores) if regard_scores else 0.0
        avg_coord = sum(coord_scores) / len(coord_scores) if coord_scores else 0.0
        quality_score = (avg_regard + avg_coord) / 2

        quality_results.append({
            "model": result["model"],
            "all_gates_pass": all_gates_pass,
            "regard": round(avg_regard, 4),
            "coordination": round(avg_coord, 4),
            "quality_score": round(quality_score, 4),
        })

    # Sort: gate-passing models first (by quality), then others
    quality_results.sort(key=lambda x: (-int(x["all_gates_pass"]), -x["quality_score"]))
    return quality_results


def generate_leaderboard_json(results: List[Dict]) -> Dict:
    """Generate comprehensive leaderboard data"""
    total_scenarios = max((len(r.get("scenarios", [])) for r in results), default=0)
    return {
        "metadata": {
            "benchmark_version": "v1.0",
            "code_version": _get_code_version(),
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "total_models": len(results),
            "total_scenarios": total_scenarios,
        },
        "overall_leaderboard": compute_rankings(results),
        "dimension_leaderboards": compute_dimension_leaderboards(results),
        "cost_efficiency": compute_cost_efficiency(results),
        "autofail_tracking": compute_autofail_tracking(results),
        "variance_report": compute_variance_stats(results),
        "safety_report_card": compute_safety_report_card(results),
        "quality_leaderboard": compute_quality_leaderboard(results),
    }


def compute_variance_stats(results: List[Dict]) -> List[Dict]:
    """Compute variance statistics for multi-run results"""
    variance_stats = []
    for result in results:
        if "runs" in result and len(result["runs"]) > 1:
            scores = [r["overall_score"] for r in result["runs"]]
            import statistics

            variance_stats.append(
                {
                    "model": result["model"],
                    "mean_score": statistics.mean(scores),
                    "std_dev": statistics.stdev(scores) if len(scores) > 1 else 0,
                    "min_score": min(scores),
                    "max_score": max(scores),
                    "run_count": len(scores),
                }
            )

    return variance_stats


def main():
    parser = argparse.ArgumentParser(description="Generate leaderboard data from canonical results")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("results/leaderboard_ready"),
        help="Directory containing canonical result JSON files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmark/website/data"),
        help="Output directory for leaderboard data",
    )
    parser.add_argument(
        "--include-confidential",
        action="store_true",
        help="Include confidential scenarios in leaderboard generation.",
    )
    args = parser.parse_args()

    # Create output directory
    args.output.mkdir(parents=True, exist_ok=True)

    # Load canonical results
    print(f"Loading results from {args.input}...")
    base_dir = Path(__file__).resolve().parents[3]
    confidential_ids = load_confidential_ids(base_dir)
    results = load_canonical_results(args.input, args.include_confidential, confidential_ids)
    print(f"✅ Loaded {len(results)} canonical results")

    if not results:
        print("⚠️  No results found. Run some benchmarks first!")
        return

    # Generate leaderboard data
    print("Generating leaderboard data...")
    leaderboard_data = generate_leaderboard_json(results)

    # Write to file
    output_file = args.output / "leaderboard.json"
    with open(output_file, "w") as f:
        json.dump(leaderboard_data, f, indent=2)

    print(f"✅ Leaderboard data written to {output_file}")

    # Generate summary
    print("\n" + "=" * 60)
    print("LEADERBOARD SUMMARY")
    print("=" * 60)
    print(f"Total Models: {len(results)}")
    print("\nTop 3 Models:")
    for i, result in enumerate(leaderboard_data["overall_leaderboard"][:3], 1):
        print(
            f"  {i}. {result['model']}: {result['overall_score']:.1f}/20.0 ({result['overall_score']/20*100:.1f}%)"
        )

    if leaderboard_data["autofail_tracking"]:
        print("\n⚠️  Models with Autofails:")
        for item in leaderboard_data["autofail_tracking"][:3]:
            print(f"  - {item['model']}: {item['autofail_count']} incidents")

    print("=" * 60)


if __name__ == "__main__":
    main()
