"""Public projection is a plain script; it works without a private workspace driver."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from benchmark.tests.fixtures.current_scan import write_current_qa_fixture
from invisiblebench import projection

ROOT = Path(__file__).resolve().parents[3]


def sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def test_public_contract_declares_only_projection() -> None:
    declaration = json.loads((ROOT / ".givecare/module.json").read_text())
    assert [module["id"] for module in declaration["modules"]] == ["bench.publish"]
    (capability,) = declaration["modules"][0]["capabilities"]
    assert capability["name"] == "benchmark.web-release.project"
    assert capability["adapter"] == {
        "kind": "evidence-operation",
        "ref": ".givecare/projection-driver.json#corpus.project",
    }
    manifest = json.loads((ROOT / ".givecare/projection-driver.json").read_text())
    assert manifest["capabilities"] == {"corpus.project": {"effect": "write", "gate": "none"}}
    assert manifest["write_scopes"] == [
        "data/leaderboard/leaderboard.json",
        "data/releases/web-bench-release.tar.gz",
    ]
    assert "scripts/evidence_driver.py" not in json.dumps(manifest)
    assert "hound" not in json.dumps(manifest).lower()


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
    payload = {
        "schema_version": "gc-bench.web-benchmark-release.input/v3",
        "bundle_path": paths["scan"].relative_to(tmp_path).as_posix(),
        "plan_sha256": sha(paths["plan"].read_bytes()),
        "judgments_sha256": sha(paths["ledger"].read_bytes()),
        "leaderboard_path": paths["leaderboard"].relative_to(tmp_path).as_posix(),
        "leaderboard_sha256": sha(paths["leaderboard"].read_bytes()),
    }
    dry = projection.project_web_release(payload, root=tmp_path, dry_run=True)
    assert dry["outcome"] == "dry-run"
    assert dry["written"] == []
    assert not (tmp_path / "data/leaderboard/leaderboard.json").exists()

    first = projection.project_web_release(payload, root=tmp_path)
    assert first["outcome"] == "completed"
    second = projection.project_web_release(payload, root=tmp_path)
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
    assert projection.project_web_release(payload, root=tmp_path)["expected_effects"] == []

    from invisiblebench.judge import load_scan

    plan = load_scan(paths["scan"])[0]
    source_manifest = paths["scan"] / plan.sources[0].manifest.path
    source_manifest.write_bytes(source_manifest.read_bytes() + b"\n")
    with pytest.raises(projection.DriverError, match="Publication QA failed"):
        projection.project_web_release(payload, root=tmp_path)


def test_bound_input_computes_matching_digests_and_schema(tmp_path) -> None:
    from invisiblebench.judge import LEDGER_FILE, PLAN_FILE

    bundle = tmp_path / "results" / "run-1"
    bundle.mkdir(parents=True)
    (bundle / PLAN_FILE).write_bytes(b'{"plan":true}\n')
    (bundle / LEDGER_FILE).write_bytes(b'{"judgment":true}\n')
    leaderboard = bundle / "leaderboard.candidate.json"
    leaderboard.write_bytes(b'{"leaderboard":true}\n')

    payload = projection._bound_input(
        bundle=bundle, leaderboard=leaderboard, root=tmp_path, learning_lineage=None
    )
    assert payload["schema_version"] == "gc-bench.web-benchmark-release.input/v3"
    assert payload["bundle_path"] == "results/run-1"
    assert payload["leaderboard_path"] == "results/run-1/leaderboard.candidate.json"
    assert payload["plan_sha256"] == sha((bundle / PLAN_FILE).read_bytes())
    assert payload["judgments_sha256"] == sha((bundle / LEDGER_FILE).read_bytes())
    assert payload["leaderboard_sha256"] == sha(leaderboard.read_bytes())
    assert "learning_lineage" not in payload


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
    with pytest.raises(projection.DriverError, match="symlink"):
        projection._write_outputs({target: b"new"}, effects, root=tmp_path)
    target.unlink()
    target.write_bytes(b"changed")
    with pytest.raises(projection.DriverError, match="before digest changed"):
        projection._write_outputs({target: b"new"}, effects, root=tmp_path)
    assert source.read_bytes() == b"old"


def test_bound_inputs_reject_digest_drift_and_symlinks(tmp_path):
    source = tmp_path / "source.json"
    source.write_bytes(b"{}\n")
    with pytest.raises(projection.DriverError, match="does not match"):
        projection._read_bound_file("source.json", "0" * 64, field="source", root=tmp_path)
    (tmp_path / "link.json").symlink_to(source)
    with pytest.raises(projection.DriverError, match="symbolic link"):
        projection._read_bound_file(
            "link.json", sha(source.read_bytes()), field="source", root=tmp_path
        )


def test_learning_lineage_remains_exact():
    lineage = {
        "demand_sha256": "c" * 64,
        "trace_refs": [{"loop_id": "loop", "intent_sha256": "d" * 64}],
        "module_refs": [],
    }
    assert projection._learning_lineage(lineage) is lineage
    with pytest.raises(projection.DriverError, match="loop_id and intent_sha256"):
        projection._learning_lineage(
            {"demand_sha256": "c" * 64, "trace_refs": [{"loop_id": "loop"}], "module_refs": []}
        )
