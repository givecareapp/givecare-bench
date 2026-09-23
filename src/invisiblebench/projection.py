"""Deterministic public projection driver; private intake is a separate local tool."""

from __future__ import annotations

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

from invisiblebench.scoring import RELEASE_SCHEMA, check_leaderboard
from invisiblebench.utils.benchmark_inventory import get_project_root
from invisiblebench.version import BENCHMARK_VERSION

ROOT = get_project_root()
RESPONSE_SCHEMA = "hound.driver.response.v1"
MAX_PROJECTION_BYTES = 2_000_000
WEB_RELEASE_VERSION = f"v{BENCHMARK_VERSION}"
WEB_RELEASE_ARTIFACT = Path("data/releases/web-bench-release.tar.gz")
ARTIFACT_FIELDS = {
    "schema_version",
    "owner",
    "kind",
    "artifact_id",
    "revision",
    "sha256",
    "access",
}


class DriverError(Exception):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _response(
    *,
    ok: bool,
    outcome: str,
    data_schema: str,
    data: dict[str, Any],
    diagnostics: list[str] | None = None,
    artifacts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": RESPONSE_SCHEMA,
        "ok": ok,
        "outcome": outcome,
        "data_schema": data_schema,
        "data": data,
        "artifacts": artifacts or [],
        "proofs": [],
        "diagnostics": diagnostics or [],
    }


def _repo_path(value: Any, *, field: str, root: Path) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise DriverError(f"{field} must be a non-empty repo-relative POSIX path")
    relative = Path(value)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise DriverError(f"{field} must stay inside the owner repository")
    path = root.absolute()
    for part in relative.parts:
        path /= part
        if path.is_symlink():
            raise DriverError(f"{field} must not contain a symbolic link")
    return path


def _require_sha256(value: Any, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise DriverError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _read_bound_file(
    path_value: Any, digest_value: Any, *, field: str, root: Path, maximum_bytes: int | None = None
) -> Path:
    path = _repo_path(path_value, field=f"{field}_path", root=root)
    expected = _require_sha256(digest_value, field=f"{field}_sha256")
    if not path.is_file():
        raise DriverError(f"{field}_path is not a file: {path.relative_to(root)}")
    if maximum_bytes is not None and path.stat().st_size > maximum_bytes:
        raise DriverError(f"{field}_path exceeds the size limit")
    if _sha256(path.read_bytes()) != expected:
        raise DriverError(f"{field}_sha256 does not match {field}_path")
    return path


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
        raise DriverError("output path must stay inside the owner repository") from error
    current = root.absolute()
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise DriverError(f"output path must not contain a symlink: {relative.as_posix()}")


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
    actual_paths = {path.relative_to(root).as_posix() for path in outputs}
    if actual_paths != set(expected):
        raise DriverError("execute outputs do not match the approved plan")
    for path, content in outputs.items():
        relative = path.relative_to(root).as_posix()
        if _sha256(content) != expected[relative]["after_sha256"]:
            raise DriverError(f"execute bytes drifted for {relative}")

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
                raise DriverError(f"output target is not a regular file: {path.relative_to(root)}")
            relative = path.relative_to(root).as_posix()
            current = _sha256(path.read_bytes()) if path.is_file() else None
            if current != expected[relative]["before_sha256"]:
                raise DriverError(f"approved before digest changed for {relative}")
            mode = int(expected[relative]["mode"], 8)
            staged[path] = _stage_file(path, outputs[path], mode, label="stage")
            backups[path] = (
                _stage_file(path, path.read_bytes(), path.stat().st_mode & 0o777, label="backup")
                if path.is_file()
                else None
            )
        for path in ordered:
            relative = path.relative_to(root).as_posix()
            _refuse_symlinks(path, root=root)
            current = _sha256(path.read_bytes()) if path.is_file() else None
            if current != expected[relative]["before_sha256"]:
                raise DriverError(f"approved before digest changed for {relative}")
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
            raise DriverError(
                f"owner write failed and rollback failed: {rollback_error}"
            ) from rollback_error
        raise
    finally:
        for temporary in [*staged.values(), *(item for item in backups.values() if item)]:
            temporary.unlink(missing_ok=True)


def _web_release_ref(digest: str) -> dict[str, str]:
    _require_sha256(digest, field="projection sha256")
    return {
        "schema_version": "givecare.artifact-ref/v1",
        "owner": "bench.publish",
        "kind": "owner-projection",
        "artifact_id": WEB_RELEASE_ARTIFACT.as_posix(),
        "revision": f"sha256:{digest}",
        "sha256": digest,
        "access": "public",
    }


def _learning_lineage(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"demand_sha256", "trace_refs", "module_refs"}:
        raise DriverError(
            "learning_lineage must contain demand_sha256, trace_refs, and module_refs"
        )
    _require_sha256(value["demand_sha256"], field="learning_lineage.demand_sha256")
    trace_refs = value["trace_refs"]
    if not isinstance(trace_refs, list) or len(trace_refs) > 500:
        raise DriverError("learning_lineage.trace_refs must contain at most 500 items")
    seen: set[tuple[str, str]] = set()
    for index, ref in enumerate(trace_refs):
        label = f"learning_lineage.trace_refs[{index}]"
        if not isinstance(ref, dict) or set(ref) != {"loop_id", "intent_sha256"}:
            raise DriverError(f"{label} must contain loop_id and intent_sha256")
        if not isinstance(ref["loop_id"], str) or not ref["loop_id"]:
            raise DriverError(f"{label}.loop_id must be a non-empty string")
        digest = _require_sha256(ref["intent_sha256"], field=f"{label}.intent_sha256")
        key = (ref["loop_id"], digest)
        if key in seen:
            raise DriverError("learning_lineage.trace_refs must be unique")
        seen.add(key)
    module_refs = value["module_refs"]
    if not isinstance(module_refs, list) or len(module_refs) > 100:
        raise DriverError("learning_lineage.module_refs must contain at most 100 items")
    canonical: set[bytes] = set()
    for index, ref in enumerate(module_refs):
        label = f"learning_lineage.module_refs[{index}]"
        if not isinstance(ref, dict) or set(ref) != ARTIFACT_FIELDS:
            raise DriverError(f"{label} must be an exact givecare.artifact-ref/v1 object")
        _require_sha256(ref.get("sha256"), field=f"{label}.sha256")
        if ref.get("schema_version") != "givecare.artifact-ref/v1":
            raise DriverError(f"{label}.schema_version is invalid")
        if any(not isinstance(ref.get(field), str) or not ref[field] for field in ARTIFACT_FIELDS):
            raise DriverError(f"{label} fields must be non-empty strings")
        if ref["access"] not in {"restricted", "workspace", "public"}:
            raise DriverError(f"{label}.access is invalid")
        encoded = json.dumps(ref, sort_keys=True, separators=(",", ":")).encode()
        if encoded in canonical:
            raise DriverError("learning_lineage.module_refs must be unique")
        canonical.add(encoded)
    return value


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


def _web_release_outputs(payload: Any, *, root: Path) -> tuple[dict[Path, bytes], dict[str, Any]]:
    from invisiblebench.judge import LEDGER_FILE, PLAN_FILE

    required = {
        "schema_version",
        "bundle_path",
        "plan_sha256",
        "judgments_sha256",
        "leaderboard_path",
        "leaderboard_sha256",
    }
    if not isinstance(payload, dict) or set(payload) not in (
        required,
        required | {"learning_lineage"},
    ):
        raise DriverError("corpus.project input has invalid fields")
    if payload["schema_version"] != "gc-bench.web-benchmark-release.input/v3":
        raise DriverError("corpus.project input has an invalid schema_version")
    bundle = _repo_path(payload["bundle_path"], field="bundle_path", root=root)
    if not bundle.is_dir():
        raise DriverError("bundle_path must name a scan bundle")
    relative = bundle.relative_to(root).as_posix()
    _read_bound_file(f"{relative}/{PLAN_FILE}", payload["plan_sha256"], field="plan", root=root)
    _read_bound_file(
        f"{relative}/{LEDGER_FILE}", payload["judgments_sha256"], field="judgments", root=root
    )
    candidate = _read_bound_file(
        payload["leaderboard_path"],
        payload["leaderboard_sha256"],
        field="leaderboard",
        maximum_bytes=MAX_PROJECTION_BYTES,
        root=root,
    )
    try:
        source = check_leaderboard(bundle, candidate)
    except (OSError, ValueError, KeyError) as exc:
        raise DriverError(f"Publication QA failed: {exc}") from exc
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
    result = {
        "schema_version": RELEASE_SCHEMA,
        "source_plan_sha256": payload["plan_sha256"],
        "source_judgments_sha256": payload["judgments_sha256"],
        "release": _web_release_ref(_sha256(archive_bytes)),
        "strict_qa": True,
        "member_count": len(members),
    }
    if "learning_lineage" in payload:
        result["learning_lineage"] = _learning_lineage(payload["learning_lineage"])
    outputs = {}
    for target, content in {
        root / "data/leaderboard/leaderboard.json": projection_bytes,
        root / WEB_RELEASE_ARTIFACT: archive_bytes,
    }.items():
        if not target.is_file() or target.read_bytes() != content:
            outputs[target] = content
    return outputs, result


def handle(request: dict[str, Any]) -> dict[str, Any]:
    mode = request.get("mode")
    if mode == "check":
        return _response(
            ok=True,
            outcome="completed",
            data_schema="gc-bench.hound.check/v1",
            data={"protocol": "hound.protocol.v1"},
        )
    if mode not in {"plan", "execute"}:
        raise DriverError(f"unsupported mode: {mode!r}")
    if request.get("operation") != "corpus.project":
        raise DriverError(f"unsupported operation: {request.get('operation')!r}")
    outputs, result = _web_release_outputs(request.get("input"), root=ROOT)
    effects = [_effect(path, outputs[path], root=ROOT) for path in sorted(outputs)]
    artifacts = [result["release"]]
    if mode == "plan":
        return _response(
            ok=True,
            outcome="planned",
            data_schema=RELEASE_SCHEMA,
            data={**result, "expected_effects": effects},
            artifacts=artifacts,
        )
    plan = request.get("driver_plan")
    if not isinstance(plan, dict) or plan.get("expected_effects") != effects:
        raise DriverError("execute does not match the approved deterministic plan")
    _write_outputs(outputs, effects, root=ROOT)
    return _response(
        ok=True,
        outcome="completed" if outputs else "no-change",
        data_schema=RELEASE_SCHEMA,
        artifacts=artifacts,
        data={**result, "written": sorted(p.relative_to(ROOT).as_posix() for p in outputs)},
    )


def main() -> int:
    try:
        request = json.load(sys.stdin)
        if not isinstance(request, dict):
            raise DriverError("request must be an object")
        response = handle(request)
    except (DriverError, json.JSONDecodeError, OSError, UnicodeError, ValueError) as error:
        response = _response(
            ok=False,
            outcome="failed",
            data_schema="gc-bench.hound.error/v1",
            data={},
            diagnostics=[f"gc-bench driver: {error}"],
        )
    json.dump(response, sys.stdout, ensure_ascii=False, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
