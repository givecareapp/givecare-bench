"""Tests for invisiblebench.utils.io helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from invisiblebench.utils.io import artifact_reference, leaderboard_rows


def test_artifact_reference_is_repo_relative_or_basename(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    inside = repo_root / "results" / "scan" / "judgments.jsonl"
    inside.parent.mkdir(parents=True)
    inside.touch()
    outside = tmp_path / "private" / "judgments.jsonl"
    outside.parent.mkdir()
    outside.touch()

    assert artifact_reference(inside, repo_root) == "results/scan/judgments.jsonl"
    assert artifact_reference(outside, repo_root) == "judgments.jsonl"


def test_leaderboard_rows_current_models_key() -> None:
    assert leaderboard_rows({"models": [{"model": "a"}, {"model": "b"}]}) == [
        {"model": "a"},
        {"model": "b"},
    ]


def test_leaderboard_rows_rejects_retired_overall_leaderboard_by_default() -> None:
    with pytest.raises(ValueError, match="models"):
        leaderboard_rows({"overall_leaderboard": [{"model": "a"}]})


def test_leaderboard_rows_has_no_retired_shape_opt_in() -> None:
    with pytest.raises(TypeError):
        leaderboard_rows(  # type: ignore[call-arg]
            {"overall_leaderboard": [{"model": "a"}]},
            allow_legacy=True,
        )


def test_leaderboard_rows_prefers_current_over_retired_shape() -> None:
    # If both keys are present, the current safety-care/v1 key wins.
    data = {"overall_leaderboard": [{"model": "canonical"}], "models": [{"model": "proj"}]}
    assert leaderboard_rows(data) == [{"model": "proj"}]


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


def test_the_project_root_is_the_checkout_that_holds_the_benchmark(
    tmp_path: Path, monkeypatch
) -> None:
    """An installed wheel carries only code; it must not adopt another project's root."""
    from invisiblebench.utils import benchmark_inventory
    from invisiblebench.utils.benchmark_inventory import get_project_root

    other = tmp_path / "other-project"
    (other / ".venv" / "site-packages" / "invisiblebench").mkdir(parents=True)
    (other / "pyproject.toml").write_text('[project]\nname = "other"\n')
    installed = other / ".venv" / "site-packages" / "invisiblebench" / "module.py"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(benchmark_inventory, "__file__", str(installed))
    with pytest.raises(FileNotFoundError, match="checkout"):
        get_project_root()

    checkout = tmp_path / "gc-bench"
    (checkout / "checks").mkdir(parents=True)
    (checkout / "benchmark").mkdir()
    (checkout / "benchmark" / "benchmark_inventory.json").write_text("{}")
    monkeypatch.chdir(checkout / "benchmark")
    assert get_project_root() == checkout
