"""Deterministic public projection: a plain script, not a driver protocol.

Private intake is a separate local tool. This module owns `corpus.project`:
it recomputes the scorecard from a current, complete scan bundle, runs the
strict publication QA on it, and atomically writes the committed public
projection. Run it directly with `python -m invisiblebench.projection`;
there is no request envelope, plan/execute handshake, or external runner.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from invisiblebench.scoring import RELEASE_SCHEMA, build_scorecard
from invisiblebench.utils.benchmark_inventory import get_project_root
from invisiblebench.version import BENCHMARK_VERSION

ROOT = get_project_root()
WEB_RELEASE_VERSION = f"v{BENCHMARK_VERSION}"
WEB_RELEASE_ARTIFACT = Path("data/releases/web-bench-release.tar.gz")


class ProjectionError(Exception):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _effect(path: Path, after: bytes, *, root: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(root).as_posix(),
        "mode": f"{path.stat().st_mode & 0o777:04o}" if path.is_file() else "0644",
        "before_sha256": _sha256(path.read_bytes()) if path.is_file() else None,
        "after_sha256": _sha256(after),
    }


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _refuse_symlinks(path: Path, *, root: Path) -> None:
    try:
        relative = path.absolute().relative_to(root.absolute())
    except ValueError as error:
        raise ProjectionError("output path must stay inside the owner repository") from error
    current = root.absolute()
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ProjectionError(f"output path must not contain a symlink: {relative.as_posix()}")


def _stage_file(path: Path, content: bytes, mode: int, *, label: str) -> Path:
    descriptor, staged_name = tempfile.mkstemp(prefix=f".{path.name}.{label}-", dir=path.parent)
    staged = Path(staged_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        staged.chmod(mode)
        return staged
    except Exception:
        staged.unlink(missing_ok=True)
        raise


def _write_outputs(
    outputs: dict[Path, bytes], expected_effects: list[dict[str, Any]], *, root: Path
) -> None:
    expected = {item["path"]: item for item in expected_effects}
    ordered = sorted(outputs)
    staged: dict[Path, Path] = {}
    backups: dict[Path, Path | None] = {}
    replaced: list[Path] = []
    try:
        for path in ordered:
            _refuse_symlinks(path, root=root)
            path.parent.mkdir(parents=True, exist_ok=True)
            _refuse_symlinks(path, root=root)
            if path.exists() and not path.is_file():
                raise ProjectionError(f"output target is not a regular file: {path.relative_to(root)}")
            relative = path.relative_to(root).as_posix()
            current = _sha256(path.read_bytes()) if path.is_file() else None
            if current != expected[relative]["before_sha256"]:
                raise ProjectionError(f"approved before digest changed for {relative}")
            mode = int(expected[relative]["mode"], 8)
            staged[path] = _stage_file(path, outputs[path], mode, label="stage")
            backups[path] = (
                _stage_file(path, path.read_bytes(), path.stat().st_mode & 0o777, label="backup")
                if path.is_file()
                else None
            )
        for path in ordered:
            os.replace(staged[path], path)
            replaced.append(path)
            _fsync_directory(path.parent)
    except Exception:
        rollback_error: Exception | None = None
        for path in reversed(replaced):
            try:
                backup = backups[path]
                if backup is None:
                    path.unlink(missing_ok=True)
                else:
                    os.replace(backup, path)
                    backups[path] = None
                _fsync_directory(path.parent)
            except Exception as error:
                rollback_error = rollback_error or error
        if rollback_error is not None:
            raise ProjectionError(
                f"owner write failed and rollback failed: {rollback_error}"
            ) from rollback_error
        raise
    finally:
        for temporary in [*staged.values(), *(item for item in backups.values() if item)]:
            temporary.unlink(missing_ok=True)


def _web_release_ref(digest: str) -> dict[str, str]:
    return {
        "schema_version": "givecare.artifact-ref/v1",
        "owner": "bench.publish",
        "kind": "owner-projection",
        "artifact_id": WEB_RELEASE_ARTIFACT.as_posix(),
        "revision": f"sha256:{digest}",
        "sha256": digest,
        "access": "public",
    }


def _deterministic_archive(members: dict[str, bytes]) -> bytes:
    raw = io.BytesIO()
    with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as compressed:
        with tarfile.open(fileobj=compressed, mode="w") as archive:
            for path in sorted(members):
                entry = tarfile.TarInfo(path)
                entry.size = len(members[path])
                entry.mode = 0o644
                entry.mtime = entry.uid = entry.gid = 0
                entry.uname = entry.gname = ""
                archive.addfile(entry, io.BytesIO(members[path]))
    return raw.getvalue()


def _web_release_outputs(bundle: Path, *, root: Path) -> tuple[dict[Path, bytes], dict[str, Any]]:
    if not bundle.is_dir():
        raise ProjectionError("bundle must name a scan bundle")
    try:
        source = build_scorecard(bundle, publication=True)
    except (OSError, ValueError, KeyError) as exc:
        raise ProjectionError(f"Publication QA failed: {exc}") from exc
    projection_bytes = _json_bytes(source)
    members = {"leaderboard.json": projection_bytes}
    manifest = _json_bytes(
        {
            "schema_version": RELEASE_SCHEMA,
            "release_version": WEB_RELEASE_VERSION,
            "members": [
                {"path": name, "sha256": _sha256(content), "bytes": len(content)}
                for name, content in sorted(members.items())
            ],
        }
    )
    archive_bytes = _deterministic_archive({"release-manifest.json": manifest, **members})
    metadata = source["scan_metadata"]
    result = {
        "schema_version": RELEASE_SCHEMA,
        "source_plan_sha256": metadata["plan_sha256"],
        "source_judgments_sha256": metadata["judgments_sha256"],
        "release": _web_release_ref(_sha256(archive_bytes)),
        "strict_qa": True,
        "member_count": len(members),
    }
    outputs = {}
    for target, content in {
        root / "data/leaderboard/leaderboard.json": projection_bytes,
        root / WEB_RELEASE_ARTIFACT: archive_bytes,
    }.items():
        if not target.is_file() or target.read_bytes() != content:
            outputs[target] = content
    return outputs, result


def project_web_release(
    bundle: Path, *, root: Path = ROOT, dry_run: bool = False
) -> dict[str, Any]:
    """Compute the `corpus.project` outputs and, unless `dry_run`, write them.

    One step: recompute the scorecard from the scan (`build_scorecard` with the
    publication gates), then do the atomic, digest-verified, rollback-on-failure
    write (`_write_outputs`). The result carries the input and output SHA-256
    values so a reviewer can bind the Git change to the scan.
    """
    outputs, result = _web_release_outputs(bundle, root=root)
    effects = [_effect(path, outputs[path], root=root) for path in sorted(outputs)]
    written: list[str] = []
    if not dry_run and outputs:
        _write_outputs(outputs, effects, root=root)
        written = sorted(p.relative_to(root).as_posix() for p in outputs)
    outcome = "dry-run" if dry_run else ("completed" if outputs else "no-change")
    return {**result, "outcome": outcome, "expected_effects": effects, "written": written}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compute and write the public gc-bench web-release projection "
            "(data/leaderboard/leaderboard.json and the release archive) from "
            "a complete, current scan bundle. Strict QA and the publication "
            "currency gate run on every call."
        )
    )
    parser.add_argument(
        "--bundle", required=True, type=Path, help="Scan bundle directory, e.g. results/<run-id>"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute and print the projection without writing repository files",
    )
    args = parser.parse_args(argv)

    root = ROOT
    bundle = args.bundle if args.bundle.is_absolute() else root / args.bundle

    try:
        result = project_web_release(bundle, root=root, dry_run=args.dry_run)
    except (ProjectionError, OSError, ValueError) as error:
        print(f"gc-bench projection: {error}", file=sys.stderr)
        return 1
    json.dump(result, sys.stdout, ensure_ascii=False, sort_keys=True, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
