"""Helm Evidence boundaries for Evals intake and the complete web release."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]

DRIVER = ROOT / "scripts" / "evidence_driver.py"



def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()

def _json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True) + "\n").encode()

def _load_driver():
    spec = importlib.util.spec_from_file_location("gc_bench_hound_driver", DRIVER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def _source_file(root: Path, relative: str, content: bytes) -> tuple[str, str]:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return relative, _sha(content)

def test_manifest_limits_hound_writes_to_owner_outputs() -> None:
    manifest = json.loads((ROOT / "evidence-driver.json").read_text())
    assert manifest["exec"] == [".venv/bin/python", "-B", "scripts/evidence_driver.py"]
    assert manifest["write_scopes"] == ["benchmark/scenarios", "data/releases/web-bench-release.tar.gz", "data/leaderboard/leaderboard.json"]

def test_driver_check_emits_one_protocol_response() -> None:
    import subprocess
    import sys
    result = subprocess.run([sys.executable, "-B", str(DRIVER)], cwd=ROOT, input='{"mode":"check"}', capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)["data"] == {"protocol": "hound.protocol.v1"}

def test_module_declares_fixed_evals_sync_and_single_web_release() -> None:
    declaration = json.loads((ROOT / ".givecare/module.json").read_text())
    capabilities = {cap["name"]: cap for module in declaration["modules"] for cap in module["capabilities"]}
    assert capabilities["benchmark.evals.projection.sync"]["adapter"]["kind"] == "owner-projection-sync"
    assert capabilities["benchmark.scenarios.apply"]["accepts"] == ["gc-bench.candidate-intake.input/v2"]
    assert capabilities["benchmark.web-release.project"]["accepts"] == ["gc-bench.web-benchmark-release.input/v2"]

def test_candidate_intake_reads_local_materialization_and_preserves_run(monkeypatch, tmp_path: Path) -> None:
    driver = _load_driver()
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    (tmp_path / "benchmark" / "scenarios").mkdir(parents=True)
    source = {"schema_version": "givecare.artifact-ref/v1", "owner": "evals.dataset", "kind": "owner-projection", "artifact_id": "data/all.jsonl", "revision": "sha256:" + "a" * 64, "sha256": "a" * 64, "access": "public"}
    record = {"id": "case-1", "input": "Help", "category": "crisis"}
    monkeypatch.setattr(driver, "_materialized_evals_projection", lambda: ("b" * 64, source, _json(record)))
    request = {"mode": "plan", "operation": "corpus.apply", "input": {"schema_version": "gc-bench.candidate-intake.input/v2", "selected_ids": ["case-1"]}}
    plan = driver.handle(request)
    assert plan["data"]["source_run_id"] == "b" * 64
    executed = driver.handle({**request, "mode": "execute", "driver_plan": plan["data"]})
    written = tmp_path / executed["data"]["paths"][0]
    assert json.loads(written.read_text())["metadata"]["source_projection_run_id"] == "b" * 64

def test_candidate_intake_rejects_caller_supplied_source() -> None:
    driver = _load_driver()
    with pytest.raises(driver.DriverError, match="only schema_version and selected_ids"):
        driver._candidate_outputs({"schema_version": "gc-bench.candidate-intake.input/v2", "source_plan_id": "a" * 64, "selected_ids": ["case-1"]})

def test_candidate_intake_rejects_multiple_or_absent_ids(monkeypatch) -> None:
    driver = _load_driver()
    source = {"schema_version": "givecare.artifact-ref/v1", "owner": "evals.dataset", "kind": "owner-projection", "artifact_id": "data/all.jsonl", "revision": "sha256:" + "a" * 64, "sha256": "a" * 64, "access": "public"}
    records = _json({"id": "case-1", "input": "Help"})
    monkeypatch.setattr(driver, "_materialized_evals_projection", lambda: ("b" * 64, source, records))
    with pytest.raises(driver.DriverError, match="exactly one"):
        driver._candidate_outputs({"schema_version": "gc-bench.candidate-intake.input/v2", "selected_ids": ["case-1", "case-2"]})
    with pytest.raises(driver.DriverError, match="absent from the bound projection"):
        driver._candidate_outputs({"schema_version": "gc-bench.candidate-intake.input/v2", "selected_ids": ["missing"]})

def test_bound_file_rejects_digest_drift_and_symlink(monkeypatch, tmp_path: Path) -> None:
    driver = _load_driver()
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    path = tmp_path / "data" / "source.json"
    path.parent.mkdir()
    path.write_text("{}\n")
    with pytest.raises(driver.DriverError, match="does not match"):
        driver._read_bound_file("data/source.json", "0" * 64, field="source")
    link = tmp_path / "data" / "link.json"
    link.symlink_to(path)
    with pytest.raises(driver.DriverError, match="symbolic link"):
        driver._read_bound_file("data/link.json", "0" * 64, field="source")

def test_web_release_ref_and_hound_artifact_are_exact(monkeypatch) -> None:
    driver = _load_driver()
    artifact = driver._web_release_ref("a" * 64)
    assert artifact["artifact_id"] == "data/releases/web-bench-release.tar.gz"
    monkeypatch.setattr(driver, "_operation_outputs", lambda _request: ({}, {"release": artifact}, "gc-bench.web-benchmark-release/v2"))
    response = driver.handle({"mode": "plan", "operation": "corpus.project"})
    assert response["artifacts"] == [artifact]

def test_learning_lineage_stays_exact() -> None:
    driver = _load_driver()
    lineage = {"demand_sha256": "c" * 64, "trace_refs": [{"loop_id": "loop", "intent_sha256": "d" * 64}], "module_refs": []}
    assert driver._learning_lineage(lineage) is lineage
    with pytest.raises(driver.DriverError, match="loop_id and intent_sha256"):
        driver._learning_lineage({"demand_sha256": "c" * 64, "trace_refs": [{"loop_id": "loop"}], "module_refs": []})

def test_execute_rejects_plan_drift_and_write_rolls_back(monkeypatch, tmp_path: Path) -> None:
    driver = _load_driver()
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    target = tmp_path / "data" / "releases" / "web-bench-release.tar.gz"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old")
    outputs = {target: b"new"}
    effects = [driver._effect(target, b"new")]
    monkeypatch.setattr(driver, "_operation_outputs", lambda _request: (outputs, {}, "test/v1"))
    with pytest.raises(driver.DriverError, match="approved deterministic plan"):
        driver.handle({"mode": "execute", "operation": "corpus.project", "input": {}, "driver_plan": {"expected_effects": []}})
    original_replace = driver.os.replace
    def fail_replace(source, destination):
        if destination == target:
            raise OSError("replace failure")
        original_replace(source, destination)
    monkeypatch.setattr(driver.os, "replace", fail_replace)
    with pytest.raises(OSError, match="replace failure"):
        driver._write_outputs(outputs, effects)
    assert target.read_bytes() == b"old"

def test_owner_write_refuses_symlinks_and_rechecks_before_digest(monkeypatch, tmp_path: Path) -> None:
    driver = _load_driver()
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    outside = tmp_path / "outside"
    outside.write_bytes(b"old")
    target = tmp_path / "data" / "releases" / "web-bench-release.tar.gz"
    target.parent.mkdir(parents=True)
    target.symlink_to(outside)
    effect = {"path": "data/releases/web-bench-release.tar.gz", "mode": "0644", "before_sha256": _sha(b"old"), "after_sha256": _sha(b"new")}
    with pytest.raises(driver.DriverError, match="symlink"):
        driver._write_outputs({target: b"new"}, [effect])
    target.unlink()
    target.write_bytes(b"approved")
    effect = driver._effect(target, b"new")
    target.write_bytes(b"changed")
    with pytest.raises(driver.DriverError, match="before digest changed"):
        driver._write_outputs({target: b"new"}, [effect])


def test_project_rechecks_qa_and_builds_only_aggregate_members(monkeypatch, tmp_path):
    from scripts import qa_leaderboard
    driver = _load_driver()
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    board = {"schema": "safety-care/v2", "notes": {}, "scan_metadata": {},
             "models": [{"model_id": "test/model", "model": "Model", "safety": {}, "care": {}}]}
    scan, scan_sha = _source_file(tmp_path, "private/per_run.jsonl", b'{"private": "record"}\n')
    candidate, candidate_sha = _source_file(tmp_path, "private/candidate.json", _json(board))
    payload = {"schema_version": "gc-bench.web-benchmark-release.input/v2", "scan_path": scan,
               "scan_sha256": scan_sha, "leaderboard_path": candidate, "leaderboard_sha256": candidate_sha}
    calls = []
    def qa(scan_path, leaderboard_path, *, strict):
        calls.append((scan_path, leaderboard_path, strict))
        return []
    monkeypatch.setattr(qa_leaderboard, "validate_leaderboard", qa)
    first, _ = driver._web_release_outputs(payload)
    second, _ = driver._web_release_outputs(payload)
    assert first == second
    assert len(calls) == 2 and all(call[2] for call in calls)
    archive = first[tmp_path / "data/releases/web-bench-release.tar.gz"]
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        assert set(tar.getnames()) == {"leaderboard.json", "release-manifest.json"}
        assert b'private' not in tar.extractfile("leaderboard.json").read()
    monkeypatch.setattr(qa_leaderboard, "validate_leaderboard", lambda *a, **kw: ["source evidence differs"])
    with pytest.raises(driver.DriverError, match="source evidence differs"):
        driver._web_release_outputs(payload)


def test_current_scan_projects_with_real_qa_and_keeps_decisions_private(monkeypatch, tmp_path):
    from benchmark.tests.fixtures.current_scan import write_current_qa_fixture

    paths = write_current_qa_fixture(tmp_path)
    driver = _load_driver()
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    payload = {
        "schema_version": "gc-bench.web-benchmark-release.input/v2",
        "scan_path": paths["scan"].relative_to(tmp_path).as_posix(),
        "scan_sha256": _sha(paths["scan"].read_bytes()),
        "leaderboard_path": paths["leaderboard"].relative_to(tmp_path).as_posix(),
        "leaderboard_sha256": _sha(paths["leaderboard"].read_bytes()),
    }
    request = {"operation": "corpus.project", "input": payload, "mode": "plan"}
    first = driver.handle(request)
    assert driver.handle(request) == first
    result = driver.handle({**request, "mode": "execute", "driver_plan": first["data"]})
    assert result["ok"] and result["outcome"] == "completed"
    release = tmp_path / "data/releases/web-bench-release.tar.gz"
    assert _sha(release.read_bytes()) == first["artifacts"][0]["sha256"]
    with tarfile.open(release, "r:gz") as archive:
        assert set(archive.getnames()) == {"leaderboard.json", "release-manifest.json"}
        public_bytes = archive.extractfile("leaderboard.json").read()
        assert public_bytes == (tmp_path / "data/leaderboard/leaderboard.json").read_bytes()
        for private_field in (b'"mode_results"', b'"evidence"', b'"rationale"', b'"raw_response"'):
            assert private_field not in public_bytes
        manifest = json.load(archive.extractfile("release-manifest.json"))
        assert manifest["members"] == [{
            "path": "leaderboard.json", "bytes": len(public_bytes), "sha256": _sha(public_bytes),
        }]
    repeat = driver.handle(request)
    assert repeat["data"]["expected_effects"] == []
    source_manifest = paths["source_run"] / "run_manifest.json"
    source_manifest.write_bytes(source_manifest.read_bytes() + b"\n")
    with pytest.raises(driver.DriverError, match="Publication QA failed"):
        driver.handle(request)
