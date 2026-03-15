#!/usr/bin/env python3
"""Live terminal dashboard for autoresearch scenario optimization.

Usage:
    python autoresearch/dashboard.py           # Terminal dashboard (auto-refresh)
    python autoresearch/dashboard.py --once    # Print once, no refresh
"""

import json
import statistics
import sys
import time
from pathlib import Path

LEADERBOARD_DIR = Path("results/leaderboard_ready")
RESULTS_DIR = Path(__file__).parent / "results"

# ANSI colors
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def load_spreads():
    """Compute current scenario spreads from leaderboard_ready."""
    rows = []
    for f in sorted(LEADERBOARD_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        model = data.get("model", f.stem)
        for s in data.get("scenarios", []):
            rows.append({
                "model": model,
                "scenario": s.get("scenario", "?"),
                "score": s.get("overall_score", 0.0),
            })

    by_scenario = {}
    for r in rows:
        sid = r["scenario"]
        if sid not in by_scenario:
            by_scenario[sid] = []
        by_scenario[sid].append(r["score"])

    results = []
    for sid, scores in sorted(by_scenario.items()):
        spread = max(scores) - min(scores)
        mean = statistics.mean(scores)
        if spread < 0.15:
            verdict = "TOO EASY" if mean > 0.7 else "TOO HARD" if mean < 0.3 else "FLAT"
        elif spread > 0.5:
            verdict = "GREAT"
        elif spread > 0.3:
            verdict = "GOOD"
        else:
            verdict = "WEAK"
        results.append({"scenario": sid, "spread": spread, "mean": mean, "verdict": verdict})

    results.sort(key=lambda x: x["spread"])
    return results


def load_experiments():
    """Load experiment results."""
    experiments = []
    for f in sorted(RESULTS_DIR.glob("experiment_*.json")):
        try:
            data = json.loads(f.read_text())
            experiments.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    return experiments


def spread_color(s):
    if s >= 0.50:
        return GREEN
    if s >= 0.30:
        return YELLOW
    return RED


def spread_bar(s, width=15):
    filled = int(min(s, 1.0) * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"{spread_color(s)}{bar}{RESET}"


def render(spreads, experiments):
    lines = []
    lines.append(f"\n{BOLD}{'═' * 70}{RESET}")
    lines.append(f"{BOLD}  AUTORESEARCH — Scenario Differentiation{RESET}")
    lines.append(f"{BOLD}{'═' * 70}{RESET}\n")

    if not spreads:
        lines.append(f"  {DIM}No leaderboard data in {LEADERBOARD_DIR}{RESET}")
        return "\n".join(lines)

    # Summary counts
    verdicts = [s["verdict"] for s in spreads]
    too_easy = verdicts.count("TOO EASY")
    weak = verdicts.count("WEAK")
    good = verdicts.count("GOOD")
    great = verdicts.count("GREAT")
    all_spreads = [s["spread"] for s in spreads]

    lines.append(
        f"  {RED}{BOLD}{too_easy}{RESET} TOO EASY  "
        f"{YELLOW}{weak}{RESET} WEAK  "
        f"{GREEN}{good}{RESET} GOOD  "
        f"{GREEN}{BOLD}{great}{RESET} GREAT  "
        f"{DIM}| mean spread: {statistics.mean(all_spreads):.3f}{RESET}"
    )
    lines.append(f"  {'─' * 66}")

    # Show all scenarios sorted by spread
    for s in spreads:
        spread = s["spread"]
        name = s["scenario"][:35]
        verdict = s["verdict"]

        v_color = RED if "EASY" in verdict or "HARD" in verdict else YELLOW if "WEAK" in verdict else GREEN
        lines.append(
            f"  {name:<36} {spread_bar(spread)} "
            f"{spread_color(spread)}{spread:.3f}{RESET}  "
            f"{v_color}{verdict}{RESET}"
        )

    lines.append(f"\n  {'─' * 66}")

    # Target: all scenarios ≥ 0.20 spread
    below_target = sum(1 for s in spreads if s["spread"] < 0.20)
    lines.append(
        f"  Target: all ≥ 0.20 spread  |  "
        f"{RED}{below_target}{RESET} scenarios below target"
    )

    # Experiments
    if experiments:
        lines.append(f"\n  {BOLD}EXPERIMENTS{RESET}")
        lines.append(f"  {'─' * 66}")
        lines.append(f"  {'#':<4} {'Scenario':<30} {'Spread':>7} {'Models':>7}")
        lines.append(f"  {'─' * 66}")

        for exp in experiments:
            label = exp.get("label", "?").replace("experiment_", "")
            scenario = exp.get("scenario", "?")[:28]
            spread = exp.get("spread", 0)
            n = exp.get("n_models", 0)
            err = exp.get("error", "")

            if err:
                lines.append(f"  {label:<4} {scenario:<30} {DIM}{err}{RESET}")
            else:
                lines.append(
                    f"  {label:<4} {scenario:<30} "
                    f"{spread_color(spread)}{spread:>7.3f}{RESET} {n:>7}"
                )

    lines.append(f"\n{BOLD}{'═' * 70}{RESET}\n")
    return "\n".join(lines)


def main():
    once = "--once" in sys.argv

    while True:
        spreads = load_spreads()
        experiments = load_experiments()
        output = render(spreads, experiments)
        print("\033[2J\033[H" + output, end="")
        if once:
            break
        try:
            time.sleep(5)
        except KeyboardInterrupt:
            break


if __name__ == "__main__":
    main()
