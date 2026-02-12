#!/usr/bin/env python3
"""
Verify minimum scenario coverage per v2 dimension for the consolidated core set.

Rule checked (Task 2.7):
- Each v2 dimension must have >= 2 scenarios with weight >= 2.

Current scenario files still use legacy scoring dimension keys; this script maps
legacy keys to v2 dimensions. `false_refusal` is inferred from scenario path
until scenario-level scoring dimensions are fully migrated in Task 3.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFESTS = [
    REPO_ROOT / "benchmark/scenarios/manifests/t1_core.txt",
    REPO_ROOT / "benchmark/scenarios/manifests/t2_core.txt",
    REPO_ROOT / "benchmark/scenarios/manifests/t3_core.txt",
]

V2_DIMENSIONS = (
    "safety",
    "compliance",
    "attunement",
    "belonging",
    "false_refusal",
    "memory",
    "consistency",
)

LEGACY_KEY_MAP = {
    "safety": "crisis_safety",
    "compliance": "regulatory_fitness",
    "attunement": "trauma_informed_flow",
    "belonging": "belonging_cultural_fitness",
    "memory": "memory_hygiene",
    "consistency": "longitudinal_consistency",
}


def load_core_scenarios() -> list[Path]:
    scenarios: list[Path] = []
    for manifest in MANIFESTS:
        for line in manifest.read_text(encoding="utf-8").splitlines():
            rel = line.strip()
            if not rel:
                continue
            scenarios.append(REPO_ROOT / rel)
    return scenarios


def main() -> int:
    scenario_paths = load_core_scenarios()
    coverage: dict[str, list[str]] = {dim: [] for dim in V2_DIMENSIONS}

    for scenario_path in scenario_paths:
        data = json.loads(scenario_path.read_text(encoding="utf-8"))
        scoring = data.get("scoring_dimensions", {})
        rel_path = str(scenario_path.relative_to(REPO_ROOT))

        for dim, legacy_key in LEGACY_KEY_MAP.items():
            if scoring.get(legacy_key, 0) >= 2:
                coverage[dim].append(rel_path)

        if "/safety/false_refusal/" in rel_path:
            coverage["false_refusal"].append(rel_path)

    print("Dimension coverage check (threshold: >=2 scenarios with weight >=2)")
    print(f"Core scenarios scanned: {len(scenario_paths)}")
    print("")

    failures: list[str] = []
    for dim in V2_DIMENSIONS:
        count = len(coverage[dim])
        status = "PASS" if count >= 2 else "FAIL"
        print(f"- {dim}: {count} [{status}]")
        for scenario in coverage[dim]:
            print(f"  - {scenario}")
        if count < 2:
            failures.append(dim)
        print("")

    if failures:
        print(f"FAILED dimensions: {', '.join(failures)}")
        return 1

    print("All dimensions satisfy minimum coverage.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
