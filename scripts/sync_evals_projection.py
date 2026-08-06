#!/usr/bin/env python3
"""Materialize one verified gc-evals owner projection for gc-bench."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
PROTOCOL = WORKSPACE_ROOT / "scripts" / "givecare_protocol.py"
OWNER_ROOT = WORKSPACE_ROOT / "gc-evals"
SOURCE_ARTIFACT = "data/all.jsonl"
TARGET = ROOT / "data" / "imports" / "evals" / "materialization.json"
MAX_SOURCE_BYTES = 2_000_000
MAX_MATERIALIZATION_BYTES = 5_000_000
SHA256 = re.compile(r"[0-9a-f]{64}")
ARTIFACT_FIELDS = {
    "schema_version",
    "owner",
    "kind",
    "artifact_id",
    "revision",
    "sha256",
    "access",
}


class ProjectionSyncError(RuntimeError):
    """The foreign owner projection could not be proven and materialized."""


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _refuse_symlinks(path: Path, *, root: Path) -> None:
    """Reject a path when any component from root to path is a symbolic link."""
    try:
        relative = path.absolute().relative_to(root.absolute())
    except ValueError as error:
        raise ProjectionSyncError("path must stay inside its declared repository") from error
    current = root.absolute()
    if current.is_symlink():
        raise ProjectionSyncError("repository root must not be a symbolic link")
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ProjectionSyncError("materialization path must not contain a symbolic link")


def _run_dir(value: str) -> Path:
    run_dir = Path(value)
    if run_dir.is_symlink():
        raise ProjectionSyncError("--run-dir must not be a symbolic link")
    try:
        resolved = run_dir.resolve(strict=True)
    except OSError as error:
        raise ProjectionSyncError("--run-dir is not a readable directory") from error
    expected_parent = (OWNER_ROOT / ".hound" / "runs").resolve()
    if (
        not resolved.is_dir()
        or resolved.parent != expected_parent
        or SHA256.fullmatch(resolved.name) is None
    ):
        raise ProjectionSyncError(
            "--run-dir must be exactly gc-evals/.hound/runs/<64-hex-plan-id>"
        )
    return resolved


def verified_source(run_id: str) -> dict[str, str]:
    """Return the exact Hound-proven gc-evals ArtifactRef for one run id."""
    if SHA256.fullmatch(run_id) is None:
        raise ProjectionSyncError("source run id must be a lowercase SHA-256 plan id")
    result = subprocess.run(
        [
            sys.executable,
            str(PROTOCOL),
            "--root",
            str(WORKSPACE_ROOT),
            "projection-ref",
            "--run-dir",
            str(OWNER_ROOT / ".hound" / "runs" / run_id),
            "--owner-repo",
            "gc-evals",
            "--driver-id",
            "gc-evals",
            "--artifact-owner",
            "evals.dataset",
            "--artifact-id",
            SOURCE_ARTIFACT,
        ],
        cwd=WORKSPACE_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ProjectionSyncError(detail or "gc-evals projection verification failed")
    try:
        reference = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ProjectionSyncError("projection-ref returned invalid JSON") from error
    digest = reference.get("sha256") if isinstance(reference, dict) else None
    expected = {
        "schema_version": "givecare.artifact-ref/v1",
        "owner": "evals.dataset",
        "kind": "owner-projection",
        "artifact_id": SOURCE_ARTIFACT,
        "revision": f"sha256:{digest}",
        "sha256": digest,
        "access": "public",
    }
    if (
        not isinstance(reference, dict)
        or set(reference) != ARTIFACT_FIELDS
        or not isinstance(digest, str)
        or SHA256.fullmatch(digest) is None
        or reference != expected
    ):
        raise ProjectionSyncError("projection-ref returned the wrong gc-evals identity")
    return {key: str(reference[key]) for key in ARTIFACT_FIELDS}


def load_materialized_source() -> tuple[str, dict[str, str], bytes]:
    """Read only gc-bench's fixed, previously verified Evals materialization."""
    _refuse_symlinks(TARGET, root=ROOT)
    if TARGET.is_symlink() or not TARGET.is_file():
        raise ProjectionSyncError("gc-evals materialization is not a regular file")
    if TARGET.stat().st_size > MAX_MATERIALIZATION_BYTES:
        raise ProjectionSyncError("gc-evals materialization exceeds the size limit")
    try:
        materialized = json.loads(TARGET.read_bytes())
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ProjectionSyncError("gc-evals materialization is unreadable") from error
    if not isinstance(materialized, dict) or set(materialized) != {
        "schema_version",
        "source_run_id",
        "source",
        "projection_jsonl",
    }:
        raise ProjectionSyncError("gc-evals materialization has invalid fields")
    source_run_id = materialized["source_run_id"]
    source = materialized["source"]
    projection_jsonl = materialized["projection_jsonl"]
    if (
        materialized["schema_version"] != "gc-bench.evals-materialization/v2"
        or not isinstance(source_run_id, str)
        or SHA256.fullmatch(source_run_id) is None
        or not isinstance(source, dict)
        or not isinstance(projection_jsonl, str)
    ):
        raise ProjectionSyncError("gc-evals materialization is invalid")
    digest = source.get("sha256")
    expected_source = {
        "schema_version": "givecare.artifact-ref/v1",
        "owner": "evals.dataset",
        "kind": "owner-projection",
        "artifact_id": SOURCE_ARTIFACT,
        "revision": f"sha256:{digest}",
        "sha256": digest,
        "access": "public",
    }
    if (
        set(source) != ARTIFACT_FIELDS
        or not isinstance(digest, str)
        or SHA256.fullmatch(digest) is None
        or source != expected_source
    ):
        raise ProjectionSyncError("gc-evals materialization ArtifactRef is invalid")
    content = projection_jsonl.encode("utf-8")
    if (
        not content
        or len(content) > MAX_SOURCE_BYTES
        or _sha256(content) != source["sha256"]
    ):
        raise ProjectionSyncError(
            "gc-evals materialization does not match the verified ArtifactRef"
        )
    return source_run_id, {key: str(source[key]) for key in ARTIFACT_FIELDS}, content


def _stage(path: Path, content: bytes) -> Path:
    descriptor, raw_path = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    staged = Path(raw_path)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        staged.chmod(0o644)
        return staged
    except BaseException:
        staged.unlink(missing_ok=True)
        raise


@contextmanager
def _consumer_lock() -> Iterator[None]:
    descriptor = os.open(ROOT, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _replace_materialization(content: bytes) -> None:
    """Install one complete generation with one atomic rename."""
    with _consumer_lock():
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        _refuse_symlinks(TARGET, root=ROOT)
        if TARGET.exists() and not stat.S_ISREG(
            TARGET.stat(follow_symlinks=False).st_mode
        ):
            raise ProjectionSyncError(
                f"materialization target is not a regular file: {TARGET}"
            )
        before = TARGET.read_bytes() if TARGET.exists() else None
        staged = _stage(TARGET, content)
        try:
            now = TARGET.read_bytes() if TARGET.exists() else None
            if now != before:
                raise ProjectionSyncError("gc-evals materialization changed during sync")
            os.replace(staged, TARGET)
            staged = None
            descriptor = os.open(TARGET.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        finally:
            if staged is not None:
                staged.unlink(missing_ok=True)


def sync(run_dir: Path) -> dict[str, Any]:
    run_dir = _run_dir(str(run_dir))
    source = verified_source(run_dir.name)
    owner_file = OWNER_ROOT / SOURCE_ARTIFACT
    _refuse_symlinks(owner_file, root=OWNER_ROOT)
    if not owner_file.is_file():
        raise ProjectionSyncError("gc-evals owner projection is not a regular file")
    if owner_file.stat().st_size > MAX_SOURCE_BYTES:
        raise ProjectionSyncError("gc-evals owner projection exceeds the size limit")
    content = owner_file.read_bytes()
    if _sha256(content) != source["sha256"]:
        raise ProjectionSyncError("gc-evals owner projection changed after verification")
    try:
        projection_jsonl = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ProjectionSyncError("gc-evals owner projection is not UTF-8") from error
    materialization = _json_bytes(
        {
            "schema_version": "gc-bench.evals-materialization/v2",
            "source_run_id": run_dir.name,
            "source": source,
            "projection_jsonl": projection_jsonl,
        }
    )
    if len(materialization) > MAX_MATERIALIZATION_BYTES:
        raise ProjectionSyncError("gc-evals materialization exceeds the size limit")
    _replace_materialization(materialization)
    return {
        "schema_version": "gc-bench.evals-materialization-result/v2",
        "source_run_id": run_dir.name,
        "source": source,
        "target": TARGET.relative_to(ROOT).as_posix(),
    }


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args(argv)
    try:
        result = sync(_run_dir(args.run_dir))
    except (ProjectionSyncError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
