"""One place for corpus inventory, version, and canary consistency."""

import json
import re
import tomllib
from collections import Counter

import invisiblebench
from invisiblebench.utils.benchmark_inventory import (
    get_project_root,
    load_inventory,
    regenerate_inventory,
)
from invisiblebench.version import BENCHMARK_VERSION

ROOT = get_project_root()


def test_inventory_matches_its_sources(published_checks):
    inventory = load_inventory()
    assert inventory == regenerate_inventory()
    paths = list((ROOT / "benchmark/scenarios").rglob("*.json"))
    categories = Counter(p.relative_to(ROOT / "benchmark/scenarios").parts[0] for p in paths)
    assert inventory["categories"] == categories
    assert inventory["standard_total"] == len(paths)


def test_versions_agree():
    card = json.loads((ROOT / "benchmark/benchmark_card.json").read_text())
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert (
        invisiblebench.__version__
        == BENCHMARK_VERSION
        == project["project"]["version"]
        == load_inventory()["benchmark_version"]
        == card["benchmark_details"]["version"]
    )


def test_every_public_scenario_embeds_the_canary():
    scenarios = ROOT / "benchmark/scenarios"
    match = re.search(r"canary GUID (\S+)", (scenarios / "CANARY.txt").read_text())
    assert match, "CANARY.txt has no canary GUID"
    missing = [
        str(p.relative_to(scenarios))
        for p in scenarios.rglob("*.json")
        if match.group(1) not in p.read_text()
    ]
    assert missing == [], f"scenarios missing canary GUID: {missing}"
