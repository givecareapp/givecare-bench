#!/usr/bin/env python3
"""Analyze scenario differentiation from leaderboard_ready results.

Usage:
    python internal/autoresearch/analyze_spread.py                    # Terminal report
    python internal/autoresearch/analyze_spread.py --json             # Save baseline JSON
    python internal/autoresearch/analyze_spread.py --scenario "Grief" # Filter by name
"""

import json
import statistics
import sys
from pathlib import Path

RESULTS_DIR = Path("results/leaderboard_ready")
OUTPUT_DIR = Path("internal/autoresearch/results")

# ANSI
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def load_all_results():
    """Load per-scenario results from all model files."""
    rows = []
    for f in sorted(RESULTS_DIR.glob("*.json")):
        data = json.loads(f.read_text())
        model = data.get("model", f.stem)
        for s in data.get("scenarios", []):
            rows.append({
                "model": model,
                "scenario": s.get("scenario", "?"),
                "category": s.get("category", s.get("tier", "?")),
                "score": s.get("overall_score", 0.0),
                "status": s.get("status", "?"),
                "regard": s.get("dimension_scores", {}).get("regard", 0),
                "coordination": s.get("dimension_scores", {}).get("coordination", 0),
            })
    return rows


def compute_spreads(rows, scenario_filter=None):
    """Compute spread per scenario."""
    by_scenario = {}
    for r in rows:
        sid = r["scenario"]
        if scenario_filter and scenario_filter.lower() not in sid.lower():
            continue
        if sid not in by_scenario:
            by_scenario[sid] = []
        by_scenario[sid].append(r)

    results = []
    for sid, entries in sorted(by_scenario.items()):
        scores = [e["score"] for e in entries]
        regard_scores = [e["regard"] for e in entries]
        coord_scores = [e["coordination"] for e in entries]
        n = len(scores)
        mean = statistics.mean(scores)
        stdev = statistics.stdev(scores) if n > 1 else 0
        mn, mx = min(scores), max(scores)
        spread = mx - mn
        fail_count = sum(1 for s in scores if s == 0)

        if spread < 0.15:
            verdict = "TOO EASY" if mean > 0.7 else "TOO HARD" if mean < 0.3 else "FLAT"
        elif spread > 0.5:
            verdict = "GREAT"
        elif spread > 0.3:
            verdict = "GOOD"
        else:
            verdict = "WEAK"

        # Find best/worst models
        best = max(entries, key=lambda e: e["score"])
        worst = min(entries, key=lambda e: e["score"])

        results.append({
            "scenario": sid,
            "category": entries[0]["category"],
            "n": n,
            "mean": round(mean, 3),
            "stdev": round(stdev, 3),
            "min": round(mn, 3),
            "max": round(mx, 3),
            "spread": round(spread, 3),
            "verdict": verdict,
            "fail_count": fail_count,
            "best_model": best["model"],
            "best_score": round(best["score"], 3),
            "worst_model": worst["model"],
            "worst_score": round(worst["score"], 3),
            "regard_spread": round(max(regard_scores) - min(regard_scores), 3),
            "coord_spread": round(max(coord_scores) - min(coord_scores), 3),
        })

    results.sort(key=lambda x: x["spread"])
    return results


def print_report(results):
    """Print terminal report."""
    print(f"\n{BOLD}SCENARIO DIFFERENTIATION ANALYSIS{RESET}")
    print(f"{DIM}{len(results)} scenarios from {RESULTS_DIR}{RESET}\n")

    print(f"{'SCENARIO':<40} {'CATEGORY':<11} {'SPREAD':>6} {'MEAN':>6} {'FAILS':>5}  VERDICT")
    print("─" * 95)

    for r in results:
        spread = r["spread"]
        if spread < 0.15:
            color = RED
        elif spread > 0.5:
            color = GREEN
        else:
            color = YELLOW

        print(
            f"{r['scenario']:<40} {r['category']:<11} "
            f"{color}{spread:>6.3f}{RESET} {r['mean']:>6.3f} "
            f"{r['fail_count']:>5}  {r['verdict']}"
        )

    print("─" * 95)

    verdicts = [r["verdict"] for r in results]
    spreads = [r["spread"] for r in results]
    print(
        f"{GREEN}GREAT:{RESET} {verdicts.count('GREAT')}  "
        f"{YELLOW}GOOD:{RESET} {verdicts.count('GOOD')}  "
        f"WEAK: {verdicts.count('WEAK')}  "
        f"{RED}TOO EASY:{RESET} {verdicts.count('TOO EASY')}  "
        f"TOO HARD: {verdicts.count('TOO HARD')}"
    )
    print(f"Mean spread: {statistics.mean(spreads):.3f}  Median: {statistics.median(spreads):.3f}")

    # Top optimization targets
    too_easy = [r for r in results if r["verdict"] == "TOO EASY"]
    if too_easy:
        print(f"\n{BOLD}OPTIMIZATION TARGETS (TOO EASY){RESET}")
        for r in too_easy:
            print(
                f"  {r['scenario']:<40} spread={r['spread']:.3f}  "
                f"worst={r['worst_model']}({r['worst_score']:.2f})  "
                f"regard_spread={r['regard_spread']:.3f}  coord_spread={r['coord_spread']:.3f}"
            )


def main():
    save_json = "--json" in sys.argv
    scenario_filter = None
    for i, arg in enumerate(sys.argv):
        if arg == "--scenario" and i + 1 < len(sys.argv):
            scenario_filter = sys.argv[i + 1]

    rows = load_all_results()
    if not rows:
        print(f"No results in {RESULTS_DIR}")
        return

    results = compute_spreads(rows, scenario_filter)
    print_report(results)

    if save_json:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out = OUTPUT_DIR / "baseline_spread.json"
        with open(out, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
