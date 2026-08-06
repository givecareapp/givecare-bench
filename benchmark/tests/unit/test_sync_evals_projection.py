"""Fixed local Evals owner-projection sync tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import sync_evals_projection as sync


def _source(content: bytes) -> dict[str, str]:
    digest = hashlib.sha256(content).hexdigest()
    return {
        "schema_version": "givecare.artifact-ref/v1",
        "owner": "evals.dataset",
        "kind": "owner-projection",
        "artifact_id": "data/all.jsonl",
        "revision": f"sha256:{digest}",
        "sha256": digest,
        "access": "public",
    }


def test_sync_materializes_one_verified_fixed_projection(monkeypatch, tmp_path: Path) -> None:
    owner = tmp_path / "gc-evals"
    run_id = "a" * 64
    (owner / ".hound" / "runs" / run_id).mkdir(parents=True)
    content = b'{"id":"case-1","input":"Help"}\n'
    owner_file = owner / "data" / "all.jsonl"
    owner_file.parent.mkdir(parents=True)
    owner_file.write_bytes(content)
    target = tmp_path / "gc-bench" / "data" / "imports" / "evals" / "all.jsonl"
    provenance = target.with_name("provenance.json")
    (tmp_path / "gc-bench").mkdir()
    monkeypatch.setattr(sync, "ROOT", tmp_path / "gc-bench")
    monkeypatch.setattr(sync, "OWNER_ROOT", owner)
    monkeypatch.setattr(sync, "TARGET", target)
    monkeypatch.setattr(sync, "PROVENANCE", provenance)
    monkeypatch.setattr(sync, "verified_source", lambda _run_id: _source(content))

    result = sync.sync(owner / ".hound" / "runs" / run_id)

    assert target.read_bytes() == content
    assert target.stat().st_mode & 0o777 == 0o644
    assert json.loads(provenance.read_text())["source"] == _source(content)
    assert result["source_run_id"] == run_id


def test_sync_rejects_owner_projection_symlinks(monkeypatch, tmp_path: Path) -> None:
    owner = tmp_path / "gc-evals"
    run_id = "a" * 64
    (owner / ".hound" / "runs" / run_id).mkdir(parents=True)
    outside = tmp_path / "outside.jsonl"
    outside.write_text('{"id":"case-1"}\n')
    owner_file = owner / "data" / "all.jsonl"
    owner_file.parent.mkdir()
    owner_file.symlink_to(outside)
    target = tmp_path / "gc-bench" / "data" / "imports" / "evals" / "all.jsonl"
    (tmp_path / "gc-bench").mkdir()
    monkeypatch.setattr(sync, "ROOT", tmp_path / "gc-bench")
    monkeypatch.setattr(sync, "OWNER_ROOT", owner)
    monkeypatch.setattr(sync, "TARGET", target)
    monkeypatch.setattr(sync, "PROVENANCE", target.with_name("provenance.json"))
    monkeypatch.setattr(sync, "verified_source", lambda _run_id: _source(outside.read_bytes()))

    with pytest.raises(sync.ProjectionSyncError, match="symbolic link"):
        sync.sync(owner / ".hound" / "runs" / run_id)


def test_sync_rejects_oversized_owner_projection_before_reading(monkeypatch, tmp_path: Path) -> None:
    owner = tmp_path / "gc-evals"
    run_id = "a" * 64
    (owner / ".hound" / "runs" / run_id).mkdir(parents=True)
    owner_file = owner / "data" / "all.jsonl"
    owner_file.parent.mkdir()
    with owner_file.open("wb") as stream:
        stream.truncate(sync.MAX_MATERIALIZATION_BYTES + 1)
    target = tmp_path / "gc-bench" / "data" / "imports" / "evals" / "all.jsonl"
    (tmp_path / "gc-bench").mkdir()
    monkeypatch.setattr(sync, "ROOT", tmp_path / "gc-bench")
    monkeypatch.setattr(sync, "OWNER_ROOT", owner)
    monkeypatch.setattr(sync, "TARGET", target)
    monkeypatch.setattr(sync, "PROVENANCE", target.with_name("provenance.json"))
    monkeypatch.setattr(sync, "verified_source", lambda _run_id: _source(b""))

    with pytest.raises(sync.ProjectionSyncError, match="exceeds the size limit"):
        sync.sync(owner / ".hound" / "runs" / run_id)


def test_local_load_rejects_provenance_symlink(monkeypatch, tmp_path: Path) -> None:
    content = b'{"id":"case-1"}\n'
    target = tmp_path / "data" / "imports" / "evals" / "all.jsonl"
    provenance = target.with_name("provenance.json")
    target.parent.mkdir(parents=True)
    target.write_bytes(content)
    outside = tmp_path / "outside.json"
    outside.write_text("{}")
    provenance.symlink_to(outside)
    monkeypatch.setattr(sync, "ROOT", tmp_path)
    monkeypatch.setattr(sync, "TARGET", target)
    monkeypatch.setattr(sync, "PROVENANCE", provenance)

    with pytest.raises(sync.ProjectionSyncError, match="symbolic link"):
        sync.load_materialized_source()


def test_local_load_never_revalidates_or_reads_the_foreign_owner(monkeypatch, tmp_path: Path) -> None:
    content = b'{"id":"case-1"}\n'
    target = tmp_path / "data" / "imports" / "evals" / "all.jsonl"
    provenance = target.with_name("provenance.json")
    target.parent.mkdir(parents=True)
    target.write_bytes(content)
    provenance.write_text(json.dumps({"schema_version": "gc-bench.evals-materialization/v1", "source_run_id": "b" * 64, "source": _source(content)}))
    monkeypatch.setattr(sync, "TARGET", target)
    monkeypatch.setattr(sync, "PROVENANCE", provenance)
    monkeypatch.setattr(sync, "ROOT", tmp_path)
    monkeypatch.setattr(sync, "verified_source", lambda _run_id: pytest.fail("local load must not read the foreign owner"))

    run_id, source, loaded = sync.load_materialized_source()

    assert run_id == "b" * 64
    assert source == _source(content)
    assert loaded == content
