"""Artifact readers preserve the active format and do not expose host paths."""

import pytest

from invisiblebench.utils.io import artifact_reference, leaderboard_rows


def test_artifact_reference_hides_external_host_paths(tmp_path):
    root = tmp_path / "repo"
    inside = root / "results/scan/judgments.jsonl"
    outside = tmp_path / "private/judgments.jsonl"
    assert artifact_reference(inside, root) == "results/scan/judgments.jsonl"
    assert artifact_reference(outside, root) == "judgments.jsonl"


@pytest.mark.parametrize("include_retired", [False, True])
def test_leaderboard_reads_current_rows(include_retired):
    rows = [{"model": "a"}, {"model": "b"}]
    payload = {"models": rows}
    if include_retired:
        payload["overall_leaderboard"] = [{"model": "retired"}]
    assert leaderboard_rows(payload) == rows


@pytest.mark.parametrize("payload", [{"overall_leaderboard": []}, {"foo": 1}, [1, 2, 3]])
def test_leaderboard_rejects_missing_current_rows(payload):
    with pytest.raises(ValueError):
        leaderboard_rows(payload)


def test_installed_code_cannot_adopt_another_projects_checkout(tmp_path, monkeypatch):
    from invisiblebench.utils import benchmark_inventory

    other = tmp_path / "other-project"
    installed = other / ".venv/site-packages/invisiblebench/module.py"
    installed.parent.mkdir(parents=True)
    (other / "pyproject.toml").write_text('[project]\nname = "other"\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(benchmark_inventory, "__file__", str(installed))
    with pytest.raises(FileNotFoundError, match="checkout"):
        benchmark_inventory.get_project_root()

    checkout = tmp_path / "gc-bench"
    (checkout / "checks").mkdir(parents=True)
    (checkout / "benchmark").mkdir()
    (checkout / "benchmark/benchmark_inventory.json").write_text("{}")
    monkeypatch.chdir(checkout / "benchmark")
    assert benchmark_inventory.get_project_root() == checkout
