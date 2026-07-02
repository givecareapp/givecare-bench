"""Inventory drift fails CI instead of living in prose.

benchmark/benchmark_inventory.json is the single owner of the public
scenario and check counts ("every meaning has one owner"). These tests pin
the inventory to the filesystem: `ls checks/` is the taxonomy and
`benchmark/scenarios/` is the public set, so any add/retire that forgets the
inventory — or any doc citing a stale count — is caught here, not at the
next publish.
"""

from __future__ import annotations

import json
import re

import pytest

from invisiblebench.evaluation.check_registry import registered_check_ids
from invisiblebench.utils.benchmark_inventory import (
    get_project_root,
    load_inventory,
)

ROOT = get_project_root()


def _scenario_files_by_category() -> dict[str, int]:
    scenarios_dir = ROOT / "benchmark" / "scenarios"
    counts: dict[str, int] = {}
    for path in scenarios_dir.rglob("*.json"):
        category = path.relative_to(scenarios_dir).parts[0]
        counts[category] = counts.get(category, 0) + 1
    return counts


def test_inventory_categories_match_disk() -> None:
    inventory = load_inventory()
    on_disk = _scenario_files_by_category()
    assert on_disk == inventory["categories"], (
        f"scenario files on disk {on_disk} != inventory {inventory['categories']}"
    )


def test_inventory_standard_total_is_consistent() -> None:
    inventory = load_inventory()
    assert inventory["standard_total"] == sum(inventory["categories"].values())
    assert inventory["standard_total"] == sum(_scenario_files_by_category().values())


def test_inventory_check_count_matches_taxonomy() -> None:
    inventory = load_inventory()
    assert inventory["check_count"] == len(registered_check_ids()), (
        "checks/ and benchmark_inventory.json disagree — update check_count "
        "in the same commit that adds or retires a check"
    )


def test_leaderboard_never_claims_more_scenarios_than_exist() -> None:
    leaderboard_path = ROOT / "data" / "leaderboard" / "leaderboard.json"
    data = json.loads(leaderboard_path.read_text())
    inventory = load_inventory()
    # Current safety-care/v1 format: total_scenarios lives in scan_metadata.
    # Retired V3 format: total_scenarios lives in metadata.
    scan_meta = data.get("scan_metadata") or data.get("metadata") or {}
    total = scan_meta.get("total_scenarios")
    assert total is not None, (
        "leaderboard.json must carry total_scenarios in scan_metadata "
        "(safety-care/v1) or metadata (retired V3)"
    )
    # Published count may lag the corpus (scenarios added after the last
    # scan join at the next publish) but can never exceed it.
    assert total <= inventory["standard_total"]


def test_every_public_scenario_embeds_the_canary() -> None:
    scenarios_dir = ROOT / "benchmark" / "scenarios"
    canary_text = (scenarios_dir / "CANARY.txt").read_text()
    match = re.search(r"canary GUID (\S+)", canary_text)
    assert match, "CANARY.txt has no 'canary GUID <guid>' line"
    guid = match.group(1)
    missing = [
        str(path.relative_to(scenarios_dir))
        for path in scenarios_dir.rglob("*.json")
        if guid not in path.read_text()
    ]
    assert missing == [], f"scenarios missing canary GUID: {missing}"


def test_claude_md_cites_current_counts() -> None:
    """The contract section's counts must match the inventory owner.

    CLAUDE.md is a gitignored local operating doc, so this guard only runs
    on checkouts that have it (dev machines, not CI).
    """
    claude_md = ROOT / "CLAUDE.md"
    if not claude_md.exists():
        pytest.skip("CLAUDE.md is local-only (gitignored); absent in CI checkouts")
    text = claude_md.read_text()
    inventory = load_inventory()
    assert f"checks: {inventory['check_count']} across" in text
    assert f"{inventory['standard_total']} on disk" in text
