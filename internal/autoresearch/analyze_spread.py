#!/usr/bin/env python3
"""Analyze scenario differentiation from leaderboard-ready results.

Usage:
    python internal/autoresearch/analyze_spread.py
    python internal/autoresearch/analyze_spread.py --json
    python internal/autoresearch/analyze_spread.py --scenario "Grief"
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from _compute_spread import load_leaderboard_rows  # noqa: E402

RESULTS_DIR = Path("results/leaderboard_ready")
OUTPUT_DIR = Path("internal/autoresearch/results")

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def compute_spreads(
    rows: list[dict[str, object]], scenario_filter: str | None = None
) -> list[dict[str, object]]:
    by_scenario: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        scenario = str(row["scenario"])
        if scenario_filter and scenario_filter.lower() not in scenario.lower():
            continue
        by_scenario.setdefault(scenario, []).append(row)

    results: list[dict[str, object]] = []
    for scenario, entries in sorted(by_scenario.items()):
        scores = [float(entry["overall_score"]) for entry in entries]
        regard_scores = [float(entry["regard"]) for entry in entries]
        coord_scores = [float(entry["coordination"]) for entry in entries]
        n = len(scores)
        mean = statistics.mean(scores)
        stdev = statistics.stdev(scores) if n > 1 else 0.0
        mn, mx = min(scores), max(scores)
        spread = mx - mn
        fail_count = sum(1 for entry in entries if entry["status"] == "fail")

        if spread < 0.15:
            verdict = "TOO EASY" if mean > 0.7 else "TOO HARD" if mean < 0.3 else "FLAT"
        elif spread > 0.5:
            verdict = "GREAT"
        elif spread > 0.3:
            verdict = "GOOD"
        else:
            verdict = "WEAK"

        best = max(entries, key=lambda entry: float(entry["overall_score"]))
        worst = min(entries, key=lambda entry: float(entry["overall_score"]))
        results.append(
            {
                "scenario": scenario,
                "scenario_id": entries[0]["scenario_id"],
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
                "best_score": round(float(best["overall_score"]), 3),
                "worst_model": worst["model"],
                "worst_score": round(float(worst["overall_score"]), 3),
                "regard_spread": round(max(regard_scores) - min(regard_scores), 3),
                "coord_spread": round(max(coord_scores) - min(coord_scores), 3),
            }
        )

    results.sort(key=lambda item: float(item["spread"]))
    return results


def print_report(results: list[dict[str, object]]) -> None:
    print(f"\n{BOLD}SCENARIO DIFFERENTIATION ANALYSIS{RESET}")
    print(f"{DIM}{len(results)} scenarios from {RESULTS_DIR}{RESET}\n")
    print(f"{'SCENARIO':<40} {'CATEGORY':<11} {'SPREAD':>6} {'MEAN':>6} {'FAILS':>5}  VERDICT")
    print("─" * 95)

    for row in results:
        spread = float(row["spread"])
        if spread < 0.15:
            color = RED
        elif spread > 0.5:
            color = GREEN
        else:
            color = YELLOW
        print(
            f"{str(row['scenario']):<40} {str(row['category']):<11} "
            f"{color}{spread:>6.3f}{RESET} {float(row['mean']):>6.3f} "
            f"{int(row['fail_count']):>5}  {row['verdict']}"
        )

    print("─" * 95)
    verdicts = [str(row["verdict"]) for row in results]
    spreads = [float(row["spread"]) for row in results]
    print(
        f"{GREEN}GREAT:{RESET} {verdicts.count('GREAT')}  "
        f"{YELLOW}GOOD:{RESET} {verdicts.count('GOOD')}  "
        f"WEAK: {verdicts.count('WEAK')}  "
        f"{RED}TOO EASY:{RESET} {verdicts.count('TOO EASY')}  "
        f"TOO HARD: {verdicts.count('TOO HARD')}"
    )
    print(f"Mean spread: {statistics.mean(spreads):.3f}  Median: {statistics.median(spreads):.3f}")

    too_easy = [row for row in results if row["verdict"] == "TOO EASY"]
    if too_easy:
        print(f"\n{BOLD}OPTIMIZATION TARGETS (TOO EASY){RESET}")
        for row in too_easy:
            print(
                f"  {str(row['scenario']):<40} spread={float(row['spread']):.3f}  "
                f"worst={row['worst_model']}({float(row['worst_score']):.2f})  "
                f"regard_spread={float(row['regard_spread']):.3f}  "
                f"coord_spread={float(row['coord_spread']):.3f}"
            )


def main() -> None:
    save_json = "--json" in sys.argv
    scenario_filter: str | None = None
    for index, arg in enumerate(sys.argv):
        if arg == "--scenario" and index + 1 < len(sys.argv):
            scenario_filter = sys.argv[index + 1]

    rows = load_leaderboard_rows(RESULTS_DIR)
    if not rows:
        print(f"No results in {RESULTS_DIR}")
        return

    results = compute_spreads(rows, scenario_filter)
    print_report(results)

    if save_json:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUTPUT_DIR / "baseline_spread.json"
        out_path.write_text(json.dumps(results, indent=2))
        print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
