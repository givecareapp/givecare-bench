"""Run identity comes from evidence; repeated models remain separate runs."""

import json

import pytest

from benchmark.tests.fixtures.current_scan import FixtureJudge, write_source_run
from invisiblebench.cli import agent_commands, archive, runner
from invisiblebench.judge import plan_scan, run_scan
from invisiblebench.utils.manifest import write_manifest


def test_same_model_runs_are_distinct_and_ambiguous_prefix_is_rejected(tmp_path, monkeypatch, capsys):
    results = tmp_path / "results"
    source = write_source_run(tmp_path, roster=[("case", "context")])
    bundles = [results / "2026-09-09_00-33-18Z", results / "2026-09-09_02-00-00Z"]
    for bundle in bundles:
        plan = plan_scan([source], bundle)
        run_scan(bundle, max_cost_usd=plan.estimated_cost_usd, client=FixtureJudge())
    monkeypatch.setattr(agent_commands, "_runs_dir", lambda: results)
    assert [item["name"] for item in archive.list_runs(results)] == [p.name for p in bundles]
    assert all(item["artifact_state"] == "judged" for item in archive.list_runs(results))
    with pytest.raises(ValueError, match="multiple runs"):
        agent_commands._load_run_metadata("2026-09-09")
    assert runner.main(["--json", "jury", bundles[0].name]) == 0
    card = json.loads(capsys.readouterr().out)["data"]["path"]
    assert card.endswith("2026-09-09_00-33-18Z/jury-card.md")
    metadata = agent_commands._load_run_metadata(bundles[0].name)
    assert metadata["models"] == ["fixture/model"]
    assert metadata["manifests"][0]["run_id"] == "synthetic-fixture"
    assert metadata["jury_card"] == card
    assert metadata["date"].endswith("Z")
    assert runner._collect_runs()[0]["id"] == bundles[1].name


def test_manifest_cannot_overwrite_a_previous_run(tmp_path):
    path = write_manifest({"run_id": "first"}, tmp_path)
    saved = path.read_bytes()
    with pytest.raises(FileExistsError):
        write_manifest({"run_id": "second"}, tmp_path)
    assert path.read_bytes() == saved


def test_archive_keeps_run_name_and_refuses_collisions(tmp_path, monkeypatch):
    results = tmp_path / "results"
    run = results / "2026-09-09_00-33-18Z"
    run.mkdir(parents=True)
    write_manifest({"run_id": "one", "run_date": "2026-09-09T00:33:18+00:00"}, run)
    monkeypatch.setattr(archive, "get_project_root", lambda: tmp_path)
    collision = results / "archive" / run.name
    collision.mkdir(parents=True)
    with pytest.raises(FileExistsError, match="already exists"):
        archive.archive_runs(keep_recent=0)
    assert run.exists()
    collision.rmdir()
    moved, kept = archive.archive_runs(keep_recent=0)
    assert moved == [collision] and kept == []
    assert not archive.list_runs(results)
