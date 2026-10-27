"""Public projection is a plain script; it works without a private workspace driver."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from benchmark.tests.fixtures.current_scan import FixtureJudge, write_current_qa_fixture
from invisiblebench import projection
from invisiblebench.jury_card import write_jury_card

ROOT = Path(__file__).resolve().parents[3]


def sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def test_contract_declares_the_web_release_projection() -> None:
    declaration = json.loads((ROOT / ".givecare/module.json").read_text())
    release = next(
        item for item in declaration["produces"]
        if item["id"] == "gc-bench.web-benchmark-release/v5"
    )
    assert release["path"] == "data/releases/web-bench-release.tar.gz"
    assert release["for"] == ["gc-web"]


def test_cli_rejects_a_bundle_that_is_not_bound_and_complete(tmp_path) -> None:
    bundle = tmp_path / "results" / "missing-run"
    result = subprocess.run(
        [sys.executable, "-B", "-m", "invisiblebench.projection", "--bundle", str(bundle)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "gc-bench projection:" in result.stderr


def test_current_scan_projects_with_real_qa_and_keeps_decisions_private(monkeypatch, tmp_path):
    paths = write_current_qa_fixture(tmp_path)
    monkeypatch.setattr(projection, "ROOT", tmp_path)
    bundle = paths["scan"]
    dry = projection.project_web_release(bundle, root=tmp_path, dry_run=True)
    assert dry["outcome"] == "dry-run"
    assert dry["written"] == []
    assert not (tmp_path / "data/leaderboard/leaderboard.json").exists()

    assert dry["source_plan_sha256"] == sha(paths["plan"].read_bytes())
    assert dry["source_judgments_sha256"] == sha(paths["ledger"].read_bytes())
    assert {e["path"] for e in dry["expected_effects"]} == {
        "data/leaderboard/leaderboard.json",
        "data/releases/web-bench-release.tar.gz",
    }
    assert all(len(e["after_sha256"]) == 64 for e in dry["expected_effects"])

    first = projection.project_web_release(bundle, root=tmp_path)
    assert first["outcome"] == "completed"
    second = projection.project_web_release(bundle, root=tmp_path)
    assert second["outcome"] == "no-change"
    assert second["written"] == []
    assert second["release"] == first["release"]

    release = tmp_path / "data/releases/web-bench-release.tar.gz"
    assert sha(release.read_bytes()) == first["release"]["sha256"]
    with tarfile.open(release, "r:gz") as archive:
        assert set(archive.getnames()) == {"leaderboard.json", "release-manifest.json"}
        public_bytes = archive.extractfile("leaderboard.json").read()
        assert public_bytes == (tmp_path / "data/leaderboard/leaderboard.json").read_bytes()
        for private_field in (b'"mode_results"', b'"evidence"', b'"rationale"', b'"answers"'):
            assert private_field not in public_bytes
        manifest = json.load(archive.extractfile("release-manifest.json"))
        assert manifest["members"] == [
            {
                "path": "leaderboard.json",
                "bytes": len(public_bytes),
                "sha256": sha(public_bytes),
            }
        ]
    assert projection.project_web_release(bundle, root=tmp_path)["expected_effects"] == []

    from invisiblebench.judge import load_scan

    plan = load_scan(paths["scan"])[0]
    source_manifest = paths["scan"] / plan.sources[0].manifest.path
    source_manifest.write_bytes(source_manifest.read_bytes() + b"\n")
    with pytest.raises(projection.ProjectionError, match="Publication QA failed"):
        projection.project_web_release(bundle, root=tmp_path)


def test_writer_preserves_before_bytes_on_failed_exchange(monkeypatch, tmp_path):
    targets = [tmp_path / name for name in ("a.json", "b.json")]
    for target in targets:
        target.write_bytes(b"old")
    effects = [projection._effect(p, b"new", root=tmp_path) for p in targets]
    replace = projection.os.replace
    failed = False

    def fail_second(source, destination):
        nonlocal failed
        if destination == targets[1] and not failed:
            failed = True
            raise OSError("exchange failed")
        replace(source, destination)

    monkeypatch.setattr(projection.os, "replace", fail_second)
    with pytest.raises(OSError, match="exchange failed"):
        projection._write_outputs(dict.fromkeys(targets, b"new"), effects, root=tmp_path)
    assert all(p.read_bytes() == b"old" for p in targets)


def test_writer_refuses_symlinks_and_changed_before_bytes(tmp_path):
    source = tmp_path / "source"
    source.write_bytes(b"old")
    target = tmp_path / "output"
    target.symlink_to(source)
    effects = [projection._effect(target, b"new", root=tmp_path)]
    with pytest.raises(projection.ProjectionError, match="symlink"):
        projection._write_outputs({target: b"new"}, effects, root=tmp_path)
    target.unlink()
    target.write_bytes(b"changed")
    with pytest.raises(projection.ProjectionError, match="before digest changed"):
        projection._write_outputs({target: b"new"}, effects, root=tmp_path)
    assert source.read_bytes() == b"old"


def test_incomplete_coverage_is_refused_and_writes_nothing(monkeypatch, tmp_path):
    from invisiblebench.judge import plan_scan, run_scan

    paths = write_current_qa_fixture(tmp_path)
    monkeypatch.setattr(projection, "ROOT", tmp_path)
    subset = tmp_path / "subset"
    plan = plan_scan([paths["source_run"]], subset, limit=1)
    run_scan(subset, max_cost_usd=plan.estimated_cost_usd, client=FixtureJudge())
    with pytest.raises(projection.ProjectionError, match="Publication QA failed"):
        projection.project_web_release(subset, root=tmp_path)
    assert not (tmp_path / "data").exists()


def test_synthetic_demo_bundle_is_refused_by_projection(monkeypatch, tmp_path):
    paths = write_current_qa_fixture(tmp_path, synthetic=True)
    monkeypatch.setattr(projection, "ROOT", tmp_path)
    with pytest.raises(projection.ProjectionError, match="synthetic fixture"):
        projection.project_web_release(paths["scan"], root=tmp_path, dry_run=True)
    assert "FIXTURE-JUDGED" in write_jury_card(paths["scan"]).read_text()


def test_projection_requires_a_settled_attempt_journal(monkeypatch, tmp_path):
    from invisiblebench.judge import replay_scan

    paths = write_current_qa_fixture(tmp_path)
    monkeypatch.setattr(projection, "ROOT", tmp_path)
    bundle = paths["scan"]
    journal = bundle / "attempts.jsonl"
    original = journal.read_bytes()

    assert projection.project_web_release(bundle, root=tmp_path, dry_run=True)["strict_qa"]

    key = json.loads(original.splitlines()[0])["key"]
    journal.write_bytes(original + json.dumps({"event": "attempt", "key": key}).encode() + b"\n")
    with pytest.raises(projection.ProjectionError, match="no saved outcome"):
        projection.project_web_release(bundle, root=tmp_path, dry_run=True)

    journal.unlink()
    with pytest.raises(projection.ProjectionError, match="attempts.jsonl"):
        projection.project_web_release(bundle, root=tmp_path, dry_run=True)
    assert replay_scan(bundle) == []
