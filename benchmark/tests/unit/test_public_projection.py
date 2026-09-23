"""Public projection works without the private workspace driver."""

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


def test_module_entrypoint_refuses_private_intake() -> None:
    for request, accepted in [
        ({"mode": "check"}, True),
        ({"mode": "plan", "operation": "corpus.apply"}, False),
    ]:
        result = subprocess.run(
            [sys.executable, "-B", "-m", "invisiblebench.projection"],
            input=json.dumps(request),
            capture_output=True,
            text=True,
            check=True,
        )
        assert json.loads(result.stdout)["ok"] is accepted


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
    request = {"operation": "corpus.project", "input": payload, "mode": "plan"}
    first = projection.handle(request)
    assert projection.handle(request) == first
    with pytest.raises(projection.DriverError, match="approved deterministic plan"):
        projection.handle({**request, "mode": "execute", "driver_plan": {}})
    result = projection.handle({**request, "mode": "execute", "driver_plan": first["data"]})
    assert result["ok"] and result["outcome"] == "completed"
    release = tmp_path / "data/releases/web-bench-release.tar.gz"
    assert sha(release.read_bytes()) == first["artifacts"][0]["sha256"]
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
    assert projection.handle(request)["data"]["expected_effects"] == []
    from invisiblebench.judge import load_scan

    plan = load_scan(paths["scan"])[0]
    source_manifest = paths["scan"] / plan.sources[0].manifest.path
    source_manifest.write_bytes(source_manifest.read_bytes() + b"\n")
    with pytest.raises(projection.DriverError, match="Publication QA failed"):
        projection.handle(request)


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
