"""Tests for invisiblebench.utils.io helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from invisiblebench.utils.io import leaderboard_rows


def test_leaderboard_rows_canonical_key() -> None:
    assert leaderboard_rows({"overall_leaderboard": [{"model": "a"}]}) == [{"model": "a"}]


def test_leaderboard_rows_projected_key() -> None:
    assert leaderboard_rows({"models": [{"model": "a"}, {"model": "b"}]}) == [
        {"model": "a"},
        {"model": "b"},
    ]


def test_leaderboard_rows_prefers_canonical_over_projected() -> None:
    # If both keys are present, the canonical source key wins.
    data = {"overall_leaderboard": [{"model": "canonical"}], "models": [{"model": "proj"}]}
    assert leaderboard_rows(data) == [{"model": "canonical"}]


def test_leaderboard_rows_missing_key_raises_valueerror() -> None:
    with pytest.raises(ValueError):
        leaderboard_rows({"foo": 1})


def test_leaderboard_rows_non_dict_raises_valueerror() -> None:
    with pytest.raises(ValueError):
        leaderboard_rows([1, 2, 3])  # type: ignore[arg-type]


def test_benchmark_version_single_source_of_truth() -> None:
    """The benchmark version is defined once and must agree everywhere.

    Guards against drift between the code constant
    (``invisiblebench.version.BENCHMARK_VERSION``), the runtime-read inventory
    (``benchmark/benchmark_inventory.json``), and the external model card
    (``benchmark/benchmark_card.json``). The inventory is the machine-readable
    runtime source; the card is documentation only. They must not diverge.
    """
    from invisiblebench.utils.benchmark_inventory import get_project_root
    from invisiblebench.version import BENCHMARK_VERSION

    root: Path = get_project_root()
    inventory = json.loads(
        (root / "benchmark" / "benchmark_inventory.json").read_text()
    )
    card = json.loads((root / "benchmark" / "benchmark_card.json").read_text())

    assert BENCHMARK_VERSION == inventory["benchmark_version"]
    assert BENCHMARK_VERSION == card["benchmark_details"]["version"]
