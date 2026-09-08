#!/usr/bin/env python3
"""Private Helm Evidence protocol adapter for gc-bench owner writes."""

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

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

RESPONSE_SCHEMA = "hound.driver.response.v1"
SHA256_LEN = 64
MAX_CANDIDATES = 1
MAX_PROJECTION_BYTES = 2_000_000
from invisiblebench.scoring import RELEASE_SCHEMA  # noqa: E402
from invisiblebench.version import BENCHMARK_VERSION  # noqa: E402

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
TRACE_REF_FIELDS = {"loop_id", "intent_sha256"}


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


def _repo_path(value: Any, *, field: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise DriverError(f"{field} must be a non-empty repo-relative POSIX path")
    relative = Path(value)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise DriverError(f"{field} must stay inside the owner repository")
    path = ROOT.absolute()
    for part in relative.parts:
        path /= part
        if path.is_symlink():
            raise DriverError(f"{field} must not contain a symbolic link")
    return path


def _require_sha256(value: Any, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != SHA256_LEN
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise DriverError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _read_bound_file(
    path_value: Any,
    digest_value: Any,
    *,
    field: str,
    maximum_bytes: int | None = None,
) -> Path:
    path = _repo_path(path_value, field=f"{field}_path")
    expected = _require_sha256(digest_value, field=f"{field}_sha256")
    if not path.is_file():
        raise DriverError(f"{field}_path is not a file: {path.relative_to(ROOT)}")
    if maximum_bytes is not None and path.stat().st_size > maximum_bytes:
        raise DriverError(f"{field}_path exceeds the size limit")
    actual = _sha256(path.read_bytes())
    if actual != expected:
        raise DriverError(f"{field}_sha256 does not match {field}_path")
    return path


def _effect(path: Path, after: bytes) -> dict[str, Any]:
    before = _sha256(path.read_bytes()) if path.is_file() else None
    mode = f"{path.stat().st_mode & 0o777:04o}" if path.is_file() else "0644"
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "mode": mode,
        "before_sha256": before,
        "after_sha256": _sha256(after),
    }


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _refuse_symlinks(path: Path) -> None:
    try:
        relative = path.absolute().relative_to(ROOT.absolute())
    except ValueError as error:
        raise DriverError("output path must stay inside the owner repository") from error
    current = ROOT.absolute()
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


def _web_release_ref(sha256: str) -> dict[str, str]:
    digest = _require_sha256(sha256, field="projection sha256")
    return {
        "schema_version": "givecare.artifact-ref/v1",
        "owner": "bench.publish",
        "kind": "owner-projection",
        "artifact_id": WEB_RELEASE_ARTIFACT.as_posix(),
        "revision": f"sha256:{digest}",
        "sha256": digest,
        "access": "public",
    }


def _artifact_ref(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != ARTIFACT_FIELDS:
        raise DriverError(f"{label} must be an exact givecare.artifact-ref/v1 object")
    _require_sha256(value.get("sha256"), field=f"{label}.sha256")
    if value.get("schema_version") != "givecare.artifact-ref/v1":
        raise DriverError(f"{label}.schema_version is invalid")
    if any(not isinstance(value.get(field), str) or not value[field] for field in ARTIFACT_FIELDS):
        raise DriverError(f"{label} fields must be non-empty strings")
    if value["access"] not in {"restricted", "workspace", "public"}:
        raise DriverError(f"{label}.access is invalid")
    return value


def _materialized_evals_projection() -> tuple[str, dict[str, Any], bytes]:
    """Read the fixed gc-bench Evals materialization, never a sibling repo."""
    from scripts.sync_evals_projection import ProjectionSyncError, load_materialized_source

    try:
        source_run_id, source, projection = load_materialized_source()
    except ProjectionSyncError as error:
        raise DriverError(str(error)) from error
    if len(projection) > MAX_PROJECTION_BYTES:
        raise DriverError(f"projection bytes must contain 1 to {MAX_PROJECTION_BYTES} bytes")
    return source_run_id, source, projection


def _candidate_records(
    payload: dict[str, Any],
) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    source_run_id, source, projection = _materialized_evals_projection()

    by_id: dict[str, dict[str, Any]] = {}
    for line_number, line in enumerate(projection.splitlines(), start=1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise DriverError(f"projection line {line_number} is invalid JSON") from error
        if not isinstance(record, dict) or not isinstance(record.get("id"), str) or not record["id"]:
            raise DriverError(f"projection line {line_number} must have a non-empty id")
        if record["id"] in by_id:
            raise DriverError(f"projection contains duplicate id {record['id']!r}")
        by_id[record["id"]] = record

    selected = payload["selected_ids"]
    if (
        not isinstance(selected, list)
        or len(selected) != MAX_CANDIDATES
        or any(not isinstance(value, str) or not value for value in selected)
        or selected != sorted(set(selected))
    ):
        raise DriverError(
            "selected_ids must contain exactly one id"
        )
    missing = [record_id for record_id in selected if record_id not in by_id]
    if missing:
        raise DriverError(f"selected_ids are absent from the bound projection: {missing[:10]}")
    return source_run_id, source, [by_id[record_id] for record_id in selected]


def _write_outputs(outputs: dict[Path, bytes], expected_effects: list[dict[str, Any]]) -> None:
    expected = {item["path"]: item for item in expected_effects}
    actual_paths = {path.relative_to(ROOT).as_posix() for path in outputs}
    if actual_paths != set(expected):
        raise DriverError("execute outputs do not match the approved plan")
    for path, content in outputs.items():
        relative = path.relative_to(ROOT).as_posix()
        if _sha256(content) != expected[relative]["after_sha256"]:
            raise DriverError(f"execute bytes drifted for {relative}")

    ordered = sorted(outputs)
    staged: dict[Path, Path] = {}
    backups: dict[Path, Path | None] = {}
    replaced: list[Path] = []
    try:
        for path in ordered:
            _refuse_symlinks(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            _refuse_symlinks(path)
            if path.exists() and not path.is_file():
                raise DriverError(f"output target is not a regular file: {path.relative_to(ROOT)}")
            relative = path.relative_to(ROOT).as_posix()
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
            relative = path.relative_to(ROOT).as_posix()
            _refuse_symlinks(path)
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
            raise DriverError(f"owner write failed and rollback failed: {rollback_error}") from rollback_error
        raise
    finally:
        for temporary in [*staged.values(), *(item for item in backups.values() if item)]:
            temporary.unlink(missing_ok=True)


def _candidate_outputs(payload: Any) -> tuple[dict[Path, bytes], dict[str, Any]]:
    from scripts.intake.import_evals import (
        eval_to_scenario,
        find_near_duplicates,
        is_duplicate,
        load_existing_scenario_fingerprints,
        resolve_bench_category,
        slugify,
    )

    if not isinstance(payload, dict) or set(payload) != {
        "schema_version",
        "selected_ids",
    }:
        raise DriverError(
            "corpus.apply input must contain only schema_version and selected_ids"
        )
    if payload["schema_version"] != "gc-bench.candidate-intake.input/v2":
        raise DriverError("corpus.apply input has an invalid schema_version")
    source_run_id, source, records = _candidate_records(payload)

    fingerprints = load_existing_scenario_fingerprints(ROOT / "benchmark" / "scenarios")
    outputs: dict[Path, bytes] = {}
    skipped: list[str] = []
    for record in sorted(records, key=lambda item: str(item.get("id") if isinstance(item, dict) else "")):
        if not isinstance(record, dict):
            raise DriverError("each candidate record must be an object")
        if not isinstance(record.get("id"), str) or not record["id"]:
            raise DriverError("each candidate record must have a non-empty id")
        if not isinstance(record.get("input"), str) or not record["input"]:
            raise DriverError(f"candidate {record['id']!r} must have non-empty input")

        scenario = eval_to_scenario(record)
        scenario["metadata"]["source_projection"] = source
        scenario["metadata"]["source_projection_run_id"] = source_run_id
        duplicate = is_duplicate(scenario, fingerprints)
        if duplicate:
            skipped.append(str(record["id"]))
            continue
        near = sorted(find_near_duplicates(scenario, fingerprints))
        if near:
            scenario["metadata"]["near_duplicates"] = near
        category, subdir = resolve_bench_category(record)
        target = ROOT / "benchmark" / "scenarios" / category
        if subdir:
            target /= subdir
        target /= f"{slugify(record['id'])}.json"
        outputs[target] = _json_bytes(scenario)

        fingerprints["ids"].add(scenario["scenario_id"])
        message = scenario["turns"][0]["user_message"].lower().strip()
        if message:
            fingerprints["messages"].add(message)

    return outputs, {
        "schema_version": "gc-bench.candidate-intake.result/v1",
        "candidate_count": len(outputs),
        "promotion": "canonical-benchmark-scenario",
        "source": source,
        "source_run_id": source_run_id,
        "skipped_duplicate_ids": skipped,
        "paths": sorted(path.relative_to(ROOT).as_posix() for path in outputs),
    }


def _learning_lineage(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "demand_sha256",
        "trace_refs",
        "module_refs",
    }:
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
        if not isinstance(ref, dict) or set(ref) != TRACE_REF_FIELDS:
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
    canonical_module_refs: set[bytes] = set()
    for index, ref in enumerate(module_refs):
        validated = _artifact_ref(ref, label=f"learning_lineage.module_refs[{index}]")
        encoded = json.dumps(validated, sort_keys=True, separators=(",", ":")).encode()
        if encoded in canonical_module_refs:
            raise DriverError("learning_lineage.module_refs must be unique")
        canonical_module_refs.add(encoded)
    return value


def _deterministic_archive(members: dict[str, bytes]) -> bytes:
    raw = io.BytesIO()
    with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as compressed:
        with tarfile.open(fileobj=compressed, mode="w") as archive:
            for path in sorted(members):
                entry = tarfile.TarInfo(path)
                entry.size = len(members[path])
                entry.mode = 0o644
                entry.mtime = 0
                entry.uid = 0
                entry.gid = 0
                entry.uname = ""
                entry.gname = ""
                archive.addfile(entry, io.BytesIO(members[path]))
    return raw.getvalue()


def _web_release_outputs(payload: Any) -> tuple[dict[Path, bytes], dict[str, Any]]:
    """Publish a checked aggregate. The ledger and source bundle remain private."""
    from invisiblebench.judge import LEDGER_FILE, PLAN_FILE
    from invisiblebench.scoring import check_leaderboard

    required = {"schema_version", "bundle_path", "plan_sha256", "judgments_sha256",
                "leaderboard_path", "leaderboard_sha256"}
    if not isinstance(payload, dict) or set(payload) not in (required, required | {"learning_lineage"}):
        raise DriverError("corpus.project input has invalid fields")
    if payload["schema_version"] != "gc-bench.web-benchmark-release.input/v3":
        raise DriverError("corpus.project input has an invalid schema_version")
    bundle = _repo_path(payload["bundle_path"], field="bundle_path")
    if not bundle.is_dir():
        raise DriverError("bundle_path must name a scan bundle")
    relative = bundle.relative_to(ROOT).as_posix()
    _read_bound_file(f"{relative}/{PLAN_FILE}", payload["plan_sha256"], field="plan")
    _read_bound_file(f"{relative}/{LEDGER_FILE}", payload["judgments_sha256"], field="judgments")
    candidate = _read_bound_file(payload["leaderboard_path"], payload["leaderboard_sha256"],
                                 field="leaderboard", maximum_bytes=MAX_PROJECTION_BYTES)
    try:
        source = check_leaderboard(bundle, candidate)
    except (OSError, ValueError, KeyError) as exc:
        raise DriverError(f"Publication QA failed: {exc}") from exc
    projection_bytes = _json_bytes(source)
    members = {"leaderboard.json": projection_bytes}
    release_manifest = _json_bytes({
        "schema_version": RELEASE_SCHEMA, "release_version": WEB_RELEASE_VERSION,
        "members": [{"path": name, "sha256": _sha256(content), "bytes": len(content)}
                    for name, content in sorted(members.items())],
    })
    archive_bytes = _deterministic_archive({"release-manifest.json": release_manifest, **members})
    projection_ref = _web_release_ref(_sha256(archive_bytes))
    result = {"schema_version": RELEASE_SCHEMA,
              "source_plan_sha256": payload["plan_sha256"],
              "source_judgments_sha256": payload["judgments_sha256"], "release": projection_ref,
              "strict_qa": True, "member_count": len(members)}
    if "learning_lineage" in payload:
        result["learning_lineage"] = _learning_lineage(payload["learning_lineage"])
    outputs = {}
    for target, content in {
        ROOT / "data/leaderboard/leaderboard.json": projection_bytes,
        ROOT / WEB_RELEASE_ARTIFACT: archive_bytes,
    }.items():
        if not target.is_file() or target.read_bytes() != content:
            outputs[target] = content
    return outputs, result


def _operation_outputs(request: dict[str, Any]) -> tuple[dict[Path, bytes], dict[str, Any], str]:
    operation = request.get("operation")
    if operation == "corpus.apply":
        outputs, result = _candidate_outputs(request.get("input"))
        return outputs, result, "gc-bench.candidate-intake.result/v1"
    if operation == "corpus.project":
        outputs, result = _web_release_outputs(request.get("input"))
        return outputs, result, RELEASE_SCHEMA
    raise DriverError(f"unsupported operation: {operation!r}")


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

    outputs, result, data_schema = _operation_outputs(request)
    effects = [_effect(path, outputs[path]) for path in sorted(outputs)]
    if mode == "plan":
        artifacts = [result["release"]] if "release" in result else []
        return _response(
            ok=True,
            outcome="planned",
            data_schema=data_schema,
            data={**result, "expected_effects": effects},
            artifacts=artifacts,
        )

    driver_plan = request.get("driver_plan")
    if not isinstance(driver_plan, dict) or driver_plan.get("expected_effects") != effects:
        raise DriverError("execute does not match the approved deterministic plan")
    _write_outputs(outputs, effects)
    artifacts = [result["release"]] if "release" in result else []
    return _response(
        ok=True,
        outcome="completed" if outputs else "no-change",
        data_schema=data_schema,
        data={**result, "written": sorted(path.relative_to(ROOT).as_posix() for path in outputs)},
        artifacts=artifacts,
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
