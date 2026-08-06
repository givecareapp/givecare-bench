#!/usr/bin/env python3
"""Private Hound protocol adapter for gc-bench owner writes."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
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
    resolved = (ROOT / relative).resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError as error:
        raise DriverError(f"{field} must stay inside the owner repository") from error
    return resolved


def _require_sha256(value: Any, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != SHA256_LEN
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise DriverError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _read_bound_file(path_value: Any, digest_value: Any, *, field: str) -> Path:
    path = _repo_path(path_value, field=f"{field}_path")
    expected = _require_sha256(digest_value, field=f"{field}_sha256")
    if not path.is_file():
        raise DriverError(f"{field}_path is not a file: {path.relative_to(ROOT)}")
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


def _projection_ref(sha256: str) -> dict[str, str]:
    digest = _require_sha256(sha256, field="projection sha256")
    return {
        "schema_version": "givecare.artifact-ref/v1",
        "owner": "bench.publish",
        "kind": "owner-projection",
        "artifact_id": "data/leaderboard/leaderboard_web.json",
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


def _verified_evals_projection(source_plan_id: Any) -> tuple[dict[str, Any], bytes]:
    plan_id = _require_sha256(source_plan_id, field="source_plan_id")
    givecare_root = ROOT.parent
    owner_root = givecare_root / "gc-evals"
    run_dir = owner_root / ".hound" / "runs" / plan_id
    protocol_cli = givecare_root / "scripts" / "givecare_protocol.py"
    if not protocol_cli.is_file():
        raise DriverError("shared GiveCare projection verifier is missing")
    try:
        verification = subprocess.run(
            [
                sys.executable,
                str(protocol_cli),
                "--root",
                str(givecare_root),
                "projection-ref",
                "--run-dir",
                str(run_dir),
                "--owner-repo",
                "gc-evals",
                "--driver-id",
                "gc-evals",
                "--artifact-owner",
                "evals.dataset",
                "--artifact-id",
                "data/all.jsonl",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise DriverError(f"gc-evals projection verification failed: {error}") from error
    if verification.returncode != 0:
        detail = verification.stderr.strip() or verification.stdout.strip()
        raise DriverError(f"gc-evals projection verification failed: {detail}")
    try:
        source = _artifact_ref(json.loads(verification.stdout), label="source")
    except json.JSONDecodeError as error:
        raise DriverError("shared projection verifier emitted invalid JSON") from error
    projection_path = owner_root / "data" / "all.jsonl"
    if not projection_path.is_file() or projection_path.is_symlink():
        raise DriverError("verified gc-evals owner projection is not a regular file")
    projection = projection_path.read_bytes()
    if not projection or len(projection) > MAX_PROJECTION_BYTES:
        raise DriverError(f"projection bytes must contain 1 to {MAX_PROJECTION_BYTES} bytes")
    digest = _sha256(projection)
    if source != {
        "schema_version": "givecare.artifact-ref/v1",
        "owner": "evals.dataset",
        "kind": "owner-projection",
        "artifact_id": "data/all.jsonl",
        "revision": f"sha256:{digest}",
        "sha256": digest,
        "access": "public",
    }:
        raise DriverError("verified source does not match the gc-evals owner projection")
    return source, projection


def _candidate_records(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source, projection = _verified_evals_projection(payload["source_plan_id"])

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
    return source, [by_id[record_id] for record_id in selected]


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
        "source_plan_id",
        "selected_ids",
    }:
        raise DriverError(
            "corpus.apply input must contain only schema_version, source_plan_id, "
            "and selected_ids"
        )
    if payload["schema_version"] != "gc-bench.candidate-intake.input/v1":
        raise DriverError("corpus.apply input has an invalid schema_version")
    source, records = _candidate_records(payload)

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
        "source_plan_id": payload["source_plan_id"],
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


def _leaderboard_outputs(
    payload: Any,
) -> tuple[dict[Path, bytes], dict[str, Any]]:
    from delivery.sync_web_bench import project_leaderboard

    if not isinstance(payload, dict):
        raise DriverError("corpus.project input must be an object")
    allowed = {
        "schema_version",
        "leaderboard_path",
        "leaderboard_sha256",
        "qa_stamp_path",
        "qa_stamp_sha256",
        "learning_lineage",
    }
    required = allowed - {"learning_lineage"}
    fields = frozenset(payload)
    if fields not in {frozenset(required), frozenset(allowed)}:
        raise DriverError("corpus.project input has invalid fields")
    if payload["schema_version"] != "gc-bench.leaderboard-projection.input/v1":
        raise DriverError("corpus.project input has an invalid schema_version")
    if payload["leaderboard_path"] != "data/leaderboard/leaderboard.json":
        raise DriverError("leaderboard_path must name the canonical leaderboard")
    if payload["qa_stamp_path"] != "data/leaderboard/.qa-stamp":
        raise DriverError("qa_stamp_path must name the canonical strict-QA stamp")

    learning_lineage = None
    if "learning_lineage" in payload:
        learning_lineage = _learning_lineage(payload["learning_lineage"])

    leaderboard = _read_bound_file(
        payload["leaderboard_path"],
        payload["leaderboard_sha256"],
        field="leaderboard",
    )
    qa_stamp = _read_bound_file(
        payload["qa_stamp_path"],
        payload["qa_stamp_sha256"],
        field="qa_stamp",
    )
    try:
        stamp = json.loads(qa_stamp.read_bytes())
    except json.JSONDecodeError as error:
        raise DriverError("qa_stamp must contain valid JSON") from error
    if not isinstance(stamp, dict) or stamp.get("strict") is not True:
        raise DriverError("qa_stamp.strict must be true")
    if stamp.get("leaderboard_sha256") != payload["leaderboard_sha256"]:
        raise DriverError("qa_stamp.leaderboard_sha256 must match the canonical leaderboard")

    try:
        source = json.loads(leaderboard.read_bytes())
    except json.JSONDecodeError as error:
        raise DriverError("canonical leaderboard must contain valid JSON") from error
    if not isinstance(source, dict):
        raise DriverError("canonical leaderboard must be an object")
    try:
        projection_bytes = _json_bytes(project_leaderboard(source))
    except ValueError as error:
        raise DriverError(f"canonical leaderboard schema is invalid: {error}") from error

    projection_sha = _sha256(projection_bytes)
    projection_ref = _projection_ref(projection_sha)
    result = {
        "schema_version": "gc-bench.leaderboard-projection/v1",
        "source": {
            "path": payload["leaderboard_path"],
            "sha256": payload["leaderboard_sha256"],
        },
        "qa_stamp": {
            "path": payload["qa_stamp_path"],
            "sha256": payload["qa_stamp_sha256"],
        },
        "projection": projection_ref,
        "strict_qa": True,
    }
    if learning_lineage is not None:
        result["learning_lineage"] = learning_lineage
    target = ROOT / "data" / "leaderboard" / "leaderboard_web.json"
    outputs = (
        {}
        if target.is_file() and target.read_bytes() == projection_bytes
        else {target: projection_bytes}
    )
    return outputs, result


def _operation_outputs(request: dict[str, Any]) -> tuple[dict[Path, bytes], dict[str, Any], str]:
    operation = request.get("operation")
    if operation == "corpus.apply":
        outputs, result = _candidate_outputs(request.get("input"))
        return outputs, result, "gc-bench.candidate-intake.result/v1"
    if operation == "corpus.project":
        outputs, result = _leaderboard_outputs(request.get("input"))
        return outputs, result, "gc-bench.leaderboard-projection/v1"
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
        artifacts = [result["projection"]] if "projection" in result else []
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
    artifacts = [result["projection"]] if "projection" in result else []
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
