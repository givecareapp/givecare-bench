#!/usr/bin/env python3
"""Compute spread from a benchmark run on a single scenario.

Called by run_scenario.sh — reads per-model result JSONs from a run directory.
"""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, help="Benchmark run directory")
    parser.add_argument("--scenario", required=True, help="Scenario name filter")
    parser.add_argument("--output", required=True, help="Output JSON path")
    parser.add_argument("--label", required=True, help="Experiment label")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    scenario_filter = args.scenario.lower()

    # Read all_results.json or individual result files
    all_results_path = run_dir / "all_results.json"
    if all_results_path.exists():
        results = json.loads(all_results_path.read_text())
        if isinstance(results, dict):
            results = [results]
    else:
        results = []
        for f in run_dir.glob("*.json"):
            if f.name == "all_results.json":
                continue
            try:
                data = json.loads(f.read_text())
                results.append(data)
            except (json.JSONDecodeError, OSError):
                continue

    # Filter to matching scenario
    matched = []
    for r in results:
        name = r.get("scenario", "").lower()
        sid = r.get("scenario_id", "").lower()
        if scenario_filter in name or scenario_filter in sid:
            matched.append(r)

    if not matched:
        print(f"WARNING: No results matching '{args.scenario}' in {run_dir}")
        output = {
            "label": args.label,
            "scenario": args.scenario,
            "error": "No matching results",
            "spread": 0.0,
            "models": [],
        }
    else:
        scores = []
        models = []
        for r in matched:
            model = r.get("model", r.get("model_id", "?"))
            score = r.get("overall_score", 0.0)
            scores.append(score)
            models.append({
                "model": model,
                "overall_score": score,
                "hard_fail": r.get("hard_fail", False),
                "regard": r.get("dimensions", {}).get("regard", 0),
                "coordination": r.get("dimensions", {}).get("coordination", 0),
                "status": r.get("status", "?"),
            })

        spread = max(scores) - min(scores)
        mean = sum(scores) / len(scores)

        output = {
            "label": args.label,
            "scenario": args.scenario,
            "n_models": len(matched),
            "spread": round(spread, 3),
            "mean": round(mean, 3),
            "min": round(min(scores), 3),
            "max": round(max(scores), 3),
            "models": models,
        }

        print(f"Scenario: {args.scenario}")
        print(f"Models:   {len(matched)}")
        print(f"Spread:   {spread:.3f}")
        print(f"Mean:     {mean:.3f}")
        print(f"Range:    {min(scores):.3f} - {max(scores):.3f}")
        print()
        for m in sorted(models, key=lambda x: -x["overall_score"]):
            fail = " FAIL" if m["hard_fail"] else ""
            print(f"  {m['model']:<30} {m['overall_score']:.3f}{fail}")

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nSaved: {args.output}")


if __name__ == "__main__":
    main()
