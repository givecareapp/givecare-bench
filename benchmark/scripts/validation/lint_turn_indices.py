"""Lint scenario turn index fields for mixed usage."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

from invisiblebench.utils.turn_index import lint_turn_indices


def _collect_warnings(path: Path) -> List[str]:
    with open(path) as f:
        scenario = json.load(f)
    warnings = lint_turn_indices(scenario)
    scenario_id = scenario.get("scenario_id", path.name)
    return [f"{scenario_id}: {warning}" for warning in warnings]


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint turn index fields in scenarios.")
    parser.add_argument(
        "--scenario-dir",
        default="benchmark/scenarios",
        help="Scenario directory to scan (default: benchmark/scenarios)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if warnings are found.",
    )
    args = parser.parse_args()

    scenario_dir = Path(args.scenario_dir)
    if not scenario_dir.exists():
        raise SystemExit(f"Scenario directory not found: {scenario_dir}")

    all_warnings: List[str] = []
    for json_file in sorted(scenario_dir.rglob("*.json")):
        all_warnings.extend(_collect_warnings(json_file))

    if all_warnings:
        print("Turn index lint warnings:")
        for warning in all_warnings:
            print(f"  - {warning}")
        return 1 if args.strict else 0

    print("No turn index lint warnings found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
