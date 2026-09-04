#!/usr/bin/env python3
"""Private Helm Evidence protocol adapter for gc-bench owner writes."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import math
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
WEB_RELEASE_VERSION = "v4.0.0"
WEB_RELEASE_ROOT = Path("data/publication-source/web-bench")
WEB_RELEASE_ARTIFACT = Path("data/releases/web-bench-release.tar.gz")
MAX_RELEASE_MANIFEST_BYTES = 1 * 1024 * 1024
MAX_RELEASE_MEMBER_BYTES = 64 * 1024 * 1024
MAX_RELEASE_EXPANDED_BYTES = 256 * 1024 * 1024
MAX_RELEASE_ARCHIVE_BYTES = 64 * 1024 * 1024
PUBLIC_LEADERBOARD_KEYS = frozenset({"schema", "notes", "scan_metadata", "models"})
FORBIDDEN_PUBLIC_KEYS = frozenset(
    {
        "_deprecated_v3",
        "overall_leaderboard",
        "overall_score",
        "rank",
        "composite",
        "hard_fail",
        "hard_fail_reasons",
        "primary_bucket",
        "legacy_bucket",
    }
)
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


def _release_manifest_members(
    *,
    directory: Path,
    manifest: Path,
    expected_schema: str,
    label: str,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    if manifest.stat().st_size > MAX_RELEASE_MANIFEST_BYTES:
        raise DriverError(f"{label} manifest exceeds the size limit")
    try:
        value = json.loads(manifest.read_bytes())
    except json.JSONDecodeError as error:
        raise DriverError(f"{label} manifest must contain valid JSON") from error
    if (
        not isinstance(value, dict)
        or value.get("schema") != expected_schema
        or not isinstance(value.get("models"), list)
        or len(value["models"]) != 4
    ):
        raise DriverError(f"{label} manifest must name exactly four public model bundles")
    members = {f"{label}/manifest.json": manifest.read_bytes()}
    seen: set[str] = set()
    for item in value["models"]:
        if not isinstance(item, dict):
            raise DriverError(f"{label} manifest model entry is invalid")
        filename = item.get("file")
        digest = item.get("sha256")
        if (
            not isinstance(filename, str)
            or Path(filename).name != filename
            or not filename.endswith(".json")
            or filename in seen
        ):
            raise DriverError(f"{label} manifest model filename is invalid")
        seen.add(filename)
        _require_sha256(digest, field=f"{label} manifest model sha256")
        path = directory / filename
        if path.is_symlink() or not path.is_file():
            raise DriverError(f"{label} bundle is not a regular file: {filename}")
        if path.stat().st_size > MAX_RELEASE_MEMBER_BYTES:
            raise DriverError(f"{label} bundle exceeds the size limit: {filename}")
        content = path.read_bytes()
        if _sha256(content) != digest:
            raise DriverError(f"{label} bundle digest does not match its manifest: {filename}")
        if item.get("bytes") != len(content):
            raise DriverError(f"{label} bundle byte count does not match its manifest: {filename}")
        members[f"{label}/{filename}"] = content
    return members, value


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _nonnegative_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and value >= 0
    )


def _model_pairs(
    models: Any,
    *,
    id_key: str,
    file_key: str,
    label: str,
) -> set[tuple[str, str]]:
    if not isinstance(models, list) or len(models) != 4:
        raise DriverError(f"{label} must name exactly four model bundles")
    pairs: set[tuple[str, str]] = set()
    model_ids: set[str] = set()
    filenames: set[str] = set()
    for item in models:
        if not isinstance(item, dict):
            raise DriverError(f"{label} model entry is invalid")
        model_id = item.get(id_key)
        filename = item.get(file_key)
        if not isinstance(model_id, str) or not model_id or not isinstance(filename, str) or not filename:
            raise DriverError(f"{label} model id and bundle file are required")
        pairs.add((model_id, filename))
        model_ids.add(model_id)
        filenames.add(filename)
    if len(pairs) != 4 or len(model_ids) != 4 or len(filenames) != 4:
        raise DriverError(f"{label} model ids and bundle files must be unique")
    return pairs


def _public_leaderboard_bytes(source: dict[str, Any]) -> bytes:
    if source.get("schema") != "safety-care/v1":
        raise DriverError("canonical leaderboard schema is invalid")
    if set(source) != PUBLIC_LEADERBOARD_KEYS:
        raise DriverError("canonical leaderboard has non-public fields")
    stack = [source]
    while stack:
        value = stack.pop()
        if isinstance(value, dict):
            if FORBIDDEN_PUBLIC_KEYS.intersection(value):
                raise DriverError("canonical leaderboard has forbidden public fields")
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value)
    models = source.get("models")
    if not isinstance(models, list) or len(models) != 4:
        raise DriverError("canonical leaderboard must name exactly four models")
    for model in models:
        if not isinstance(model, dict) or not isinstance(model.get("model"), str) or not model["model"]:
            raise DriverError("canonical leaderboard model is invalid")
        if "safety" not in model or "care" not in model:
            raise DriverError("canonical leaderboard model lacks public score data")
    return _json_bytes(source)


def _validate_web_release(
    *,
    current: dict[str, Any],
    evidence: dict[str, Any],
    scores: dict[str, Any],
    leaderboard: dict[str, Any],
) -> None:
    """Reject a public bundle whose own evidence disagrees across files."""
    score_release = current.get("scoringRelease")
    model_rows = current.get("models")
    if not isinstance(score_release, dict) or not isinstance(model_rows, list) or len(model_rows) != 4:
        raise DriverError("current_evidence has invalid scoringRelease or models")
    required_current = {
        "benchmarkVersion": str,
        "resultContractVersion": str,
        "releasePath": str,
        "scoreReleasePath": str,
        "scenarioCount": int,
        "checkCount": int,
    }
    required_score_release = {
        "status": str,
        "profile": str,
        "judgeModel": str,
        "judgeLabel": str,
        "modelCount": int,
        "scenarioCount": int,
        "rowCount": int,
        "modeResultCount": int,
        "actualCostUsd": (int, float),
        "actualBillableApiCalls": int,
        "sourceScanSha256": str,
        "strictQa": bool,
    }
    if set(score_release) != set(required_score_release):
        raise DriverError("current_evidence scoringRelease has invalid fields")
    if any(
        not isinstance(current.get(key), value_type)
        or (value_type is int and isinstance(current.get(key), bool))
        for key, value_type in required_current.items()
    ) or any(
        not isinstance(score_release.get(key), value_type)
        or (value_type is int and isinstance(score_release.get(key), bool))
        for key, value_type in required_score_release.items()
    ):
        raise DriverError("current_evidence has invalid typed release fields")
    if (
        not _nonnegative_int(current["scenarioCount"])
        or not _nonnegative_int(current["checkCount"])
        or not _nonnegative_int(score_release["modelCount"])
        or not _nonnegative_int(score_release["scenarioCount"])
        or not _nonnegative_int(score_release["rowCount"])
        or not _nonnegative_int(score_release["modeResultCount"])
        or not _nonnegative_int(score_release["actualBillableApiCalls"])
        or not _nonnegative_number(score_release["actualCostUsd"])
    ):
        raise DriverError("current_evidence has invalid numeric release fields")
    if not _nonnegative_int(current.get("claimReadyChecks")):
        raise DriverError("current_evidence has an invalid claim-ready check count")
    if score_release["modelCount"] != 4:
        raise DriverError("current_evidence scoringRelease.modelCount must be four")
    if (
        not score_release["status"]
        or not score_release["judgeModel"]
        or not score_release["judgeLabel"]
        or score_release["strictQa"] is not True
    ):
        raise DriverError("current_evidence scoringRelease has invalid public values")
    _require_sha256(score_release["sourceScanSha256"], field="current_evidence source scan sha256")
    if (
        current.get("benchmarkVersion") != WEB_RELEASE_VERSION.removeprefix("v")
        or current.get("benchmarkVersion") != evidence.get("benchmark_version")
        or current.get("benchmarkVersion") != scores.get("benchmark_version")
        or current.get("releasePath") != f"/bench/evidence/{WEB_RELEASE_VERSION}"
        or current.get("scoreReleasePath") != f"/bench/scores/{WEB_RELEASE_VERSION}"
        or current.get("resultContractVersion") != evidence.get("result_contract_version")
        or current.get("resultContractVersion") != scores.get("result_contract_version")
        or current.get("scenarioCount") != evidence.get("scenario_count")
        or current.get("scenarioCount") != scores.get("scenario_count")
        or current.get("checkCount") != scores.get("check_count")
        or score_release["scenarioCount"] != current["scenarioCount"]
        or score_release["scenarioCount"] != scores.get("scenario_count")
        or score_release["rowCount"] != scores.get("row_count")
        or score_release["modeResultCount"] != scores.get("mode_result_count")
    ):
        raise DriverError("current_evidence does not match the release manifests")
    if evidence.get("model_count") != 4 or scores.get("model_count") != 4:
        raise DriverError("release manifests must name exactly four models")
    if (
        not _nonnegative_int(evidence.get("claim_ready_check_count"))
        or not _nonnegative_int(scores.get("claim_ready_check_count"))
        or evidence["claim_ready_check_count"] != current["claimReadyChecks"]
        or scores["claim_ready_check_count"] != current["claimReadyChecks"]
    ):
        raise DriverError("release claim-ready check counts do not match current evidence")
    if not _nonnegative_int(evidence.get("transcript_count")):
        raise DriverError("transcript evidence has an invalid transcript count")
    if not all(_nonnegative_int(scores.get(key)) for key in ("row_count", "mode_result_count")):
        raise DriverError("score evidence has invalid count fields")
    expected_evidence = _model_pairs(
        evidence.get("models"),
        id_key="model_id",
        file_key="file",
        label="transcript evidence",
    )
    expected_scores = _model_pairs(
        scores.get("models"),
        id_key="model_id",
        file_key="file",
        label="score evidence",
    )
    actual = _model_pairs(
        model_rows,
        id_key="modelId",
        file_key="bundleFile",
        label="current_evidence",
    )
    if (
        score_release["modelCount"] != len(actual)
        or actual != expected_evidence
        or actual != expected_scores
    ):
        raise DriverError("current_evidence model ids and bundle files do not match the release")
    if any(item.get("corpusHash") != evidence.get("scenario_hash") for item in model_rows if isinstance(item, dict)):
        raise DriverError("current_evidence corpus hashes do not match transcript evidence")
    _require_sha256(evidence.get("scenario_hash"), field="transcript evidence scenario hash")
    transcript_counts: list[int] = []
    for item in model_rows:
        if not isinstance(item, dict) or not _nonnegative_int(item.get("transcripts")):
            raise DriverError("current_evidence model transcript counts are invalid")
        transcript_counts.append(item["transcripts"])
    if sum(transcript_counts) != evidence["transcript_count"]:
        raise DriverError("current_evidence transcript counts do not match transcript evidence")
    source_merge = scores.get("source_merge")
    required_source_merge = {
        "schema": str,
        "benchmark_version": str,
        "result_contract_version": str,
        "profile": str,
        "judge_model": str,
        "model_count": int,
        "scenario_count": int,
        "row_count": int,
        "actual_cost_usd": (int, float),
        "actual_billable_api_calls": int,
        "output_sha256": str,
    }
    if not isinstance(source_merge, dict) or any(
        not isinstance(source_merge.get(key), value_type)
        or (value_type is int and isinstance(source_merge.get(key), bool))
        for key, value_type in required_source_merge.items()
    ):
        raise DriverError("score evidence has invalid source_merge fields")
    if source_merge["schema"] != "invisiblebench-scan-merge/v1":
        raise DriverError("score evidence source_merge has an invalid schema")
    if (
        not _nonnegative_number(source_merge["actual_cost_usd"])
        or not _nonnegative_int(source_merge["actual_billable_api_calls"])
        or not _nonnegative_int(source_merge["model_count"])
        or not _nonnegative_int(source_merge["scenario_count"])
        or not _nonnegative_int(source_merge["row_count"])
    ):
        raise DriverError("score evidence has invalid numeric source_merge fields")
    _require_sha256(source_merge["output_sha256"], field="score evidence source merge sha256")
    if scores.get("source_scan_sha256") != source_merge["output_sha256"]:
        raise DriverError("score evidence source scan does not match its source merge")
    if any(
        scores.get(score_key) != source_merge.get(merge_key)
        for score_key, merge_key in (
            ("benchmark_version", "benchmark_version"),
            ("result_contract_version", "result_contract_version"),
            ("scenario_count", "scenario_count"),
            ("model_count", "model_count"),
            ("row_count", "row_count"),
            ("profile", "profile"),
            ("judge_model", "judge_model"),
        )
    ):
        raise DriverError("score evidence does not match its source merge")
    if (
        scores.get("profile") != score_release["profile"]
        or scores.get("judge_model") != score_release["judgeModel"]
    ):
        raise DriverError("score evidence does not match current scoring release")
    if any(
        score_release.get(current_key) != source_merge.get(source_key)
        for current_key, source_key in (
            ("profile", "profile"),
            ("judgeModel", "judge_model"),
            ("actualBillableApiCalls", "actual_billable_api_calls"),
            ("sourceScanSha256", "output_sha256"),
        )
    ):
        raise DriverError("current_evidence scoringRelease does not match score evidence")
    if not math.isclose(
        float(score_release["actualCostUsd"]),
        float(source_merge["actual_cost_usd"]),
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        raise DriverError("current_evidence score cost does not match score evidence")
    metadata = leaderboard.get("scan_metadata") if isinstance(leaderboard, dict) else None
    if not isinstance(metadata, dict) or any(
        metadata.get(key) != expected
        for key, expected in (
            ("benchmark_version", current["benchmarkVersion"]),
            ("total_models", score_release["modelCount"]),
            ("total_scenarios", current["scenarioCount"]),
            ("active_modes", current["checkCount"]),
        )
    ):
        raise DriverError("leaderboard does not match the public evidence release")


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


def _web_release_outputs(
    payload: Any,
) -> tuple[dict[Path, bytes], dict[str, Any]]:
    if not isinstance(payload, dict):
        raise DriverError("corpus.project input must be an object")
    allowed = {
        "schema_version",
        "leaderboard_path",
        "leaderboard_sha256",
        "qa_stamp_path",
        "qa_stamp_sha256",
        "current_evidence_path",
        "current_evidence_sha256",
        "evidence_manifest_path",
        "evidence_manifest_sha256",
        "scores_manifest_path",
        "scores_manifest_sha256",
        "learning_lineage",
    }
    required = allowed - {"learning_lineage"}
    fields = frozenset(payload)
    if fields not in {frozenset(required), frozenset(allowed)}:
        raise DriverError("corpus.project input has invalid fields")
    if payload["schema_version"] != "gc-bench.web-benchmark-release.input/v1":
        raise DriverError("corpus.project input has an invalid schema_version")
    if payload["leaderboard_path"] != "data/leaderboard/leaderboard.json":
        raise DriverError("leaderboard_path must name the canonical leaderboard")
    if payload["qa_stamp_path"] != "data/leaderboard/.qa-stamp":
        raise DriverError("qa_stamp_path must name the canonical strict-QA stamp")

    leaderboard = _read_bound_file(
        payload["leaderboard_path"],
        payload["leaderboard_sha256"],
        field="leaderboard",
        maximum_bytes=MAX_PROJECTION_BYTES,
    )
    qa_stamp = _read_bound_file(
        payload["qa_stamp_path"],
        payload["qa_stamp_sha256"],
        field="qa_stamp",
        maximum_bytes=MAX_RELEASE_MANIFEST_BYTES,
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
    projection_bytes = _public_leaderboard_bytes(source)

    current_evidence = _read_bound_file(
        payload["current_evidence_path"],
        payload["current_evidence_sha256"],
        field="current_evidence",
        maximum_bytes=MAX_RELEASE_MANIFEST_BYTES,
    )
    evidence_manifest = _read_bound_file(
        payload["evidence_manifest_path"],
        payload["evidence_manifest_sha256"],
        field="evidence_manifest",
        maximum_bytes=MAX_RELEASE_MANIFEST_BYTES,
    )
    scores_manifest = _read_bound_file(
        payload["scores_manifest_path"],
        payload["scores_manifest_sha256"],
        field="scores_manifest",
        maximum_bytes=MAX_RELEASE_MANIFEST_BYTES,
    )
    expected_paths = {
        "current_evidence": WEB_RELEASE_ROOT / "current-evidence.json",
        "evidence_manifest": WEB_RELEASE_ROOT / "evidence" / WEB_RELEASE_VERSION / "manifest.json",
        "scores_manifest": WEB_RELEASE_ROOT / "scores" / WEB_RELEASE_VERSION / "manifest.json",
    }
    actual_paths = {
        "current_evidence": current_evidence,
        "evidence_manifest": evidence_manifest,
        "scores_manifest": scores_manifest,
    }
    for label, expected_path in expected_paths.items():
        if actual_paths[label] != ROOT / expected_path:
            raise DriverError(f"{label}_path must name the fixed public release source")
    try:
        current_evidence_value = json.loads(current_evidence.read_bytes())
    except json.JSONDecodeError as error:
        raise DriverError("current_evidence must contain valid JSON") from error
    if not isinstance(current_evidence_value, dict) or set(current_evidence_value) != {
        "benchmarkVersion",
        "resultContractVersion",
        "releasePath",
        "scoreReleasePath",
        "transcriptNotice",
        "asOf",
        "scenarioCount",
        "categoryCounts",
        "checkCount",
        "claimReadyChecks",
        "scoringRelease",
        "validation",
        "contrastVariants",
        "models",
        "findings",
        "knownGaps",
    }:
        raise DriverError("current_evidence has an invalid public contract")
    evidence_members, evidence_value = _release_manifest_members(
        directory=evidence_manifest.parent,
        manifest=evidence_manifest,
        expected_schema="invisiblebench-transcripts/v1",
        label=f"evidence/{WEB_RELEASE_VERSION}",
    )
    score_members, score_value = _release_manifest_members(
        directory=scores_manifest.parent,
        manifest=scores_manifest,
        expected_schema="invisiblebench-score-evidence/v1",
        label=f"scores/{WEB_RELEASE_VERSION}",
    )
    _validate_web_release(
        current=current_evidence_value,
        evidence=evidence_value,
        scores=score_value,
        leaderboard=source,
    )
    members = {
        "leaderboard.json": projection_bytes,
        "current-evidence.json": current_evidence.read_bytes(),
        **evidence_members,
        **score_members,
    }
    if sum(len(content) for content in members.values()) > MAX_RELEASE_EXPANDED_BYTES:
        raise DriverError("public release exceeds the expanded size limit")
    release_manifest = _json_bytes(
        {
            "schema_version": "gc-bench.web-benchmark-release/v1",
            "release_version": WEB_RELEASE_VERSION,
            "members": [
                {"path": path, "sha256": _sha256(content), "bytes": len(content)}
                for path, content in sorted(members.items())
            ],
        }
    )
    archive_bytes = _deterministic_archive({"release-manifest.json": release_manifest, **members})
    if len(archive_bytes) > MAX_RELEASE_ARCHIVE_BYTES:
        raise DriverError("public release exceeds the archive size limit")
    projection_ref = _web_release_ref(_sha256(archive_bytes))
    result = {
        "schema_version": "gc-bench.web-benchmark-release/v1",
        "leaderboard": {
            "path": payload["leaderboard_path"],
            "sha256": payload["leaderboard_sha256"],
        },
        "qa_stamp": {
            "path": payload["qa_stamp_path"],
            "sha256": payload["qa_stamp_sha256"],
        },
        "release": projection_ref,
        "strict_qa": True,
        "member_count": len(members),
    }
    if "learning_lineage" in payload:
        learning_lineage = _learning_lineage(payload["learning_lineage"])
        result["learning_lineage"] = learning_lineage
    target = ROOT / WEB_RELEASE_ARTIFACT
    outputs = (
        {}
        if target.is_file() and target.read_bytes() == archive_bytes
        else {target: archive_bytes}
    )
    return outputs, result


def _operation_outputs(request: dict[str, Any]) -> tuple[dict[Path, bytes], dict[str, Any], str]:
    operation = request.get("operation")
    if operation == "corpus.apply":
        outputs, result = _candidate_outputs(request.get("input"))
        return outputs, result, "gc-bench.candidate-intake.result/v1"
    if operation == "corpus.project":
        outputs, result = _web_release_outputs(request.get("input"))
        return outputs, result, "gc-bench.web-benchmark-release/v1"
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
