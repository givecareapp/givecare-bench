"""Fixed local Evals owner-projection sync tests."""

from __future__ import annotations

import hashlib
import json
import os
import stat
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


def _materialization(content: bytes, run_id: str = "b" * 64) -> bytes:
    return sync._json_bytes(
        {
            "schema_version": "gc-bench.evals-materialization/v2",
            "source_run_id": run_id,
            "source": _source(content),
            "projection_jsonl": content.decode("utf-8"),
        }
    )


def test_sync_materializes_one_verified_fixed_projection(monkeypatch, tmp_path: Path) -> None:
    owner = tmp_path / "gc-evals"
    run_id = "a" * 64
    (owner / ".hound" / "runs" / run_id).mkdir(parents=True)
    content = b'{"id":"case-1","input":"Help"}\n'
    owner_file = owner / "data" / "all.jsonl"
    owner_file.parent.mkdir(parents=True)
    owner_file.write_bytes(content)
    target = tmp_path / "gc-bench" / "data" / "imports" / "evals" / "materialization.json"
    (tmp_path / "gc-bench").mkdir()
    monkeypatch.setattr(sync, "ROOT", tmp_path / "gc-bench")
    monkeypatch.setattr(sync, "OWNER_ROOT", owner)
    monkeypatch.setattr(sync, "TARGET", target)
    monkeypatch.setattr(sync, "verified_source", lambda _run_id: _source(content))

    result = sync.sync(owner / ".hound" / "runs" / run_id)

    materialized = json.loads(target.read_bytes())
    assert materialized["projection_jsonl"].encode() == content
    assert materialized["source"] == _source(content)
    assert target.stat().st_mode & 0o777 == 0o644
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
    target = tmp_path / "gc-bench" / "data" / "imports" / "evals" / "materialization.json"
    (tmp_path / "gc-bench").mkdir()
    monkeypatch.setattr(sync, "ROOT", tmp_path / "gc-bench")
    monkeypatch.setattr(sync, "OWNER_ROOT", owner)
    monkeypatch.setattr(sync, "TARGET", target)
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
        stream.truncate(sync.MAX_SOURCE_BYTES + 1)
    target = tmp_path / "gc-bench" / "data" / "imports" / "evals" / "materialization.json"
    (tmp_path / "gc-bench").mkdir()
    monkeypatch.setattr(sync, "ROOT", tmp_path / "gc-bench")
    monkeypatch.setattr(sync, "OWNER_ROOT", owner)
    monkeypatch.setattr(sync, "TARGET", target)
    monkeypatch.setattr(sync, "verified_source", lambda _run_id: _source(b""))

    with pytest.raises(sync.ProjectionSyncError, match="exceeds the size limit"):
        sync.sync(owner / ".hound" / "runs" / run_id)


def test_local_load_rejects_materialization_symlink(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "data" / "imports" / "evals" / "materialization.json"
    target.parent.mkdir(parents=True)
    outside = tmp_path / "outside.json"
    outside.write_text("{}")
    target.symlink_to(outside)
    monkeypatch.setattr(sync, "ROOT", tmp_path)
    monkeypatch.setattr(sync, "TARGET", target)

    with pytest.raises(sync.ProjectionSyncError, match="symbolic link"):
        sync.load_materialized_source()


def test_local_load_never_revalidates_or_reads_the_foreign_owner(monkeypatch, tmp_path: Path) -> None:
    content = b'{"id":"case-1"}\n'
    target = tmp_path / "data" / "imports" / "evals" / "materialization.json"
    target.parent.mkdir(parents=True)
    target.write_bytes(_materialization(content))
    monkeypatch.setattr(sync, "TARGET", target)
    monkeypatch.setattr(sync, "ROOT", tmp_path)
    monkeypatch.setattr(sync, "verified_source", lambda _run_id: pytest.fail("local load must not read the foreign owner"))

    run_id, source, loaded = sync.load_materialized_source()

    assert run_id == "b" * 64
    assert source == _source(content)
    assert loaded == content


def test_atomic_install_failure_before_rename_keeps_old_generation(
    monkeypatch, tmp_path: Path
) -> None:
    target = tmp_path / "data" / "imports" / "evals" / "materialization.json"
    target.parent.mkdir(parents=True)
    old = _materialization(b'{"id":"old"}\n')
    new = _materialization(b'{"id":"new"}\n')
    target.write_bytes(old)
    monkeypatch.setattr(sync, "ROOT", tmp_path)
    monkeypatch.setattr(sync, "TARGET", target)

    def fail_replace(_source: Path, _target: Path) -> None:
        raise OSError("interrupted before rename")

    monkeypatch.setattr(sync.os, "replace", fail_replace)
    with pytest.raises(OSError, match="interrupted"):
        sync._replace_materialization(new)

    assert target.read_bytes() == old


def test_atomic_install_interruption_after_rename_exposes_complete_new_generation(
    monkeypatch, tmp_path: Path
) -> None:
    target = tmp_path / "data" / "imports" / "evals" / "materialization.json"
    target.parent.mkdir(parents=True)
    target.write_bytes(_materialization(b'{"id":"old"}\n'))
    new_content = b'{"id":"new"}\n'
    new = _materialization(new_content)
    monkeypatch.setattr(sync, "ROOT", tmp_path)
    monkeypatch.setattr(sync, "TARGET", target)
    real_fsync = os.fsync

    def interrupt_directory_fsync(descriptor: int) -> None:
        if stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise KeyboardInterrupt
        real_fsync(descriptor)

    monkeypatch.setattr(sync.os, "fsync", interrupt_directory_fsync)
    with pytest.raises(KeyboardInterrupt):
        sync._replace_materialization(new)

    assert target.read_bytes() == new
    assert sync.load_materialized_source()[2] == new_content
