#!/usr/bin/env python3
"""Mechanical QA for the current scan ledger and Safety/Care projection."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from invisiblebench.evaluation.check_registry import (  # noqa: E402
    check_prompt_hashes,
    load_checks,
)
from invisiblebench.evaluation.verifiers.base import Decision, evidence_errors  # noqa: E402
from invisiblebench.evaluation.verifiers.llm_verifier import (  # noqa: E402
    CONTEXT_POLICY,
    JUDGE_MAX_TOKENS,
    JUDGE_TEMPERATURE,
    _format_transcript_for_prompt,
    prompt_for_check,
)
from invisiblebench.judge import attach_scan_provenance, build_scan_plan  # noqa: E402
from invisiblebench.scoring.contract import CANONICAL_VERDICTS, NOT_APPLICABLE_VERDICT  # noqa: E402
from invisiblebench.scoring.projection import SCHEMA_VERSION, build_scorecard  # noqa: E402
from invisiblebench.utils.benchmark_inventory import (  # noqa: E402
    collect_public_scenario_ids,
    get_benchmark_version,
    get_code_version,
    load_inventory,
)
from invisiblebench.utils.io import artifact_reference, load_json, load_jsonl  # noqa: E402
from invisiblebench.version import ENGINE_VERSION, SCANNED_ROW_CONTRACT_VERSION  # noqa: E402

_ROW_FIELDS = {
    "model",
    "model_id",
    "scenario_id",
    "category",
    "transcript_path",
    "contract_version",
    "mode_results",
    "engine_version",
    "eligible_count",
    "resolved_count",
    "unclear_count",
    "coverage_rate",
}
_MODE_FIELDS = {
    "mode_id",
    "eligible",
    "verdict",
    "severity",
    "layer",
    "dimension",
    "scorer_type",
    "scorer_version",
    "prompt_hash",
    "evidence",
    "rationale",
    "rationale_code",
    "judge",
    "extra",
}
_JUDGE_FIELDS = {
    "model",
    "resolved_model",
    "provider",
    "temperature",
    "max_tokens",
    "context_policy",
}
_EXTRA_FIELDS = {"raw_response", "input_sha256", "validation_error"}
_OBSOLETE_KEYS = {
    "overall_score",
    "hard_fail",
    "hard_fail_reasons",
    "dimension_scores",
    "blindspot_profile",
    "claim_surface",
    "public_score_model",
    "result_surface",
    "score_model",
    "confidence",
    "adjudication_required",
    "calibration",
    "calibration_status",
    "claim_ready",
    "composite",
    "rank",
    "no_composite",
    "manual_adjudications",
    "previous_verdict",
    "previous_rationale_code",
}
_TECHNICAL_CODES = {"judge_api_error", "invalid_judge_output"}
_PUBLIC_FIELDS = {"schema", "notes", "scan_metadata", "models"}
_SCAN_METADATA_FIELDS = {
    "benchmark_version",
    "code_version",
    "generated_at",
    "source_artifact",
    "source_sha256",
    "public_scope",
    "public_harness",
    "total_models",
    "total_scenarios",
    "active_checks",
    "check_prompt_hashes",
    "observed_prompt_hashes",
    "observed_judges",
    "row_count",
    "model_ids",
    "projection_sha256",
    "observation_type",
}


def _json_sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def _walk_obsolete(value: Any, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_path = f"{path}.{key}" if path else str(key)
            if key in _OBSOLETE_KEYS:
                found.append(key_path)
            found.extend(_walk_obsolete(item, key_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_walk_obsolete(item, f"{path}[{index}]"))
    return found


def _checks(checks_dir: Path | None) -> dict[str, dict[str, Any]]:
    return dict(load_checks(checks_dir))


def _transcript_path(raw: Any, scan_path: Path) -> Path | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    path = Path(raw)
    candidates = (
        [path]
        if path.is_absolute()
        else [
            scan_path.parent / path,
            REPO_ROOT / path,
            scan_path.parent.parent / path,
        ]
    )
    for candidate in candidates:
        if candidate.is_file() and not candidate.is_symlink():
            return candidate
    return None


def _expected_input_hash(transcript: list[dict[str, Any]], mode: dict[str, Any]) -> str:
    messages = [
        {"role": "system", "content": prompt_for_check(mode)},
        {"role": "user", "content": _format_transcript_for_prompt(transcript)},
    ]
    # Keep the calculation beside LLMVerifier's exact request contract.
    return hashlib.sha256(
        json.dumps(messages, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def _observed_prompt_hashes(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    observed: dict[str, set[str]] = {}
    for row in rows:
        for result in row.get("mode_results") or []:
            mode_id = str(result.get("mode_id") or "")
            prompt_hash = result.get("prompt_hash")
            if mode_id and isinstance(prompt_hash, str) and prompt_hash:
                observed.setdefault(mode_id, set()).add(prompt_hash)
    return {mode_id: sorted(values) for mode_id, values in sorted(observed.items())}


def _observed_judges(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    observed: dict[str, dict[str, Any]] = {}
    for row in rows:
        for result in row.get("mode_results") or []:
            judge = result.get("judge")
            if isinstance(judge, dict):
                key = json.dumps(judge, sort_keys=True, separators=(",", ":"))
                observed[key] = dict(judge)
    return [observed[key] for key in sorted(observed)]


def _scan_plan_errors(
    leaderboard: dict[str, Any],
    rows: list[dict[str, Any]],
    scan_path: Path,
    *,
    strict: bool,
    checks_dir: Path | None,
) -> list[str]:
    """Bind the public plan to the exact retained sources and current rules."""
    errors: list[str] = []
    metadata = leaderboard.get("scan_metadata") or {}
    plan_path = scan_path.parent / "scan_plan.json"
    if not plan_path.is_file():
        return ["scan_plan.json v3 is required in strict mode"] if strict else []
    try:
        plan = load_json(plan_path)
    except (OSError, ValueError) as exc:
        return [f"scan_plan.json invalid: {exc}"]
    if not isinstance(plan, dict):
        return ["scan_plan.json must be an object"]
    if metadata.get("scan_plan_sha256") != _json_sha(plan):
        errors.append("scan_metadata.scan_plan_sha256 mismatch")
    if metadata.get("scan_plan") != plan:
        errors.append("scan_metadata.scan_plan mismatch")
    judge_model = plan.get("judge_model")
    if not isinstance(judge_model, str) or not judge_model.strip():
        return errors + ["scan_plan.judge_model missing"]
    selection = plan.get("selection")
    if not isinstance(selection, dict) or set(selection) != {
        "filter", "limit_per_source_run", "source_run_count"
    }:
        return errors + ["scan_plan.selection fields mismatch"]
    if (
        selection["filter"] is not None and not isinstance(selection["filter"], str)
        or selection["limit_per_source_run"] is not None
        and type(selection["limit_per_source_run"]) is not int
        or type(selection["source_run_count"]) is not int
    ):
        return errors + ["scan_plan.selection values invalid"]

    source_pairs: list[dict[str, Any]] = []
    source_dirs: set[Path] = set()
    for row_index, row in enumerate(rows):
        source = _transcript_path(row.get("transcript_path"), scan_path)
        if source is None:
            continue
        if source.parent.name != "transcripts":
            errors.append(f"row[{row_index}].transcript_path parent must be transcripts")
            continue
        source_dirs.add(source.parent.parent.resolve())
        source_pairs.append({
            "transcript_path": source.resolve(),
            **{key: row.get(key) for key in ("model", "model_id", "scenario_id", "category")},
        })
        for result in row.get("mode_results") or []:
            if result.get("judge", {}).get("model") != judge_model:
                errors.append(f"row[{row_index}].judge.model differs from scan_plan")

    if selection["source_run_count"] != len(source_dirs):
        errors.append("scan_plan.selection.source_run_count mismatch")
    summary_entries: dict[tuple[Path, str, str], dict[str, Any]] = {}
    for run_dir in sorted(source_dirs, key=str):
        try:
            summary = load_json(run_dir / "transcript_run.json")
            if not isinstance(summary, dict) or not isinstance(summary.get("transcripts"), list):
                raise ValueError("transcript_run.json must contain a transcript list")
        except (OSError, ValueError) as exc:
            errors.append(f"source run summary invalid: {exc}")
            continue
        for item in summary["transcripts"]:
            if isinstance(item, dict):
                key = (run_dir, str(item.get("model_id") or ""), str(item.get("scenario_id") or ""))
                if key in summary_entries:
                    errors.append("transcript_run.json has a duplicate model/scenario")
                summary_entries[key] = item
    for pair in source_pairs:
        run_dir = Path(pair["transcript_path"]).parent.parent.resolve()
        key = (run_dir, str(pair["model_id"]), str(pair["scenario_id"]))
        summary = summary_entries.get(key)
        if summary is None:
            errors.append(f"scan row {key[1:]} is absent from transcript_run.json")
        elif any(summary.get(field) != pair[field] for field in ("model", "category")):
            errors.append(f"scan row {key[1:]} model/category differs from transcript_run.json")

    if not source_pairs:
        return errors + ["scan requires retained transcript sources"]
    try:
        rebuilt = attach_scan_provenance(
            build_scan_plan(source_pairs, _checks(checks_dir), judge_model=judge_model),
            run_dirs=sorted(source_dirs, key=str),
            transcript_pairs=source_pairs,
            selection=selection,
        )
    except (OSError, ValueError, KeyError) as exc:
        return errors + [f"scan_plan provenance cannot be rebuilt: {exc}"]
    if rebuilt != plan:
        errors.append("scan_plan does not equal provenance rebuilt from retained sources")
    if strict and rebuilt.get("provenance_complete") is not True:
        errors.append("strict scan requires complete source provenance")
    if strict and set(rebuilt["scenario_ids"]) != set(collect_public_scenario_ids(REPO_ROOT)):
        errors.append("scan_plan.scenario_ids do not cover the current public scenario roster")
    return errors


def _validate_rows(
    rows: list[dict[str, Any]],
    scan_path: Path,
    *,
    checks_dir: Path | None,
) -> list[str]:
    modes = _checks(checks_dir)
    expected_ids = set(modes)
    prompt_hashes = check_prompt_hashes(checks_dir)
    errors: list[str] = []
    seen: set[tuple[str, str]] = set()
    scenarios_by_model: defaultdict[str, set[str]] = defaultdict(set)
    for row_index, row in enumerate(rows):
        prefix = f"row[{row_index}]"
        if not isinstance(row, dict):
            errors.append(f"{prefix} is not an object")
            continue
        obsolete = sorted(_OBSOLETE_KEYS.intersection(row))
        if obsolete:
            errors.append(f"{prefix} contains retired fields={obsolete}")
        unknown = sorted(set(row) - _ROW_FIELDS)
        missing = sorted(_ROW_FIELDS - set(row))
        if unknown:
            errors.append(f"{prefix} unknown fields={unknown}")
        if missing:
            errors.append(f"{prefix} missing fields={missing}")
        model_id = str(row.get("model_id") or "")
        scenario_id = str(row.get("scenario_id") or "")
        for field in ("model", "model_id", "scenario_id", "category", "transcript_path"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                errors.append(f"{prefix}.{field} must be a non-empty string")
        pair = (model_id, scenario_id)
        if pair in seen:
            errors.append(f"duplicate model/scenario={pair}")
        seen.add(pair)
        scenarios_by_model[model_id].add(scenario_id)
        if row.get("contract_version") != SCANNED_ROW_CONTRACT_VERSION:
            errors.append(f"{prefix}.contract_version mismatch")
        if row.get("engine_version") != ENGINE_VERSION:
            errors.append(f"{prefix}.engine_version mismatch")
        path = _transcript_path(row.get("transcript_path"), scan_path)
        if path is None:
            errors.append(f"{prefix}.transcript_path is missing or not a retained file")
            transcript: list[dict[str, Any]] = []
        else:
            try:
                transcript = load_jsonl(path)
            except (OSError, ValueError) as exc:
                errors.append(f"{prefix}.transcript_path invalid: {exc}")
                transcript = []
        results = row.get("mode_results")
        if not isinstance(results, list):
            errors.append(f"{prefix}.mode_results must be a list")
            results = []
        result_ids = [
            str(result.get("mode_id") or "") for result in results if isinstance(result, dict)
        ]
        if len(result_ids) != len(set(result_ids)):
            errors.append(f"{prefix} duplicate mode results")
        if set(result_ids) != expected_ids:
            errors.append(
                f"{prefix} mode roster mismatch missing={sorted(expected_ids - set(result_ids))[:10]} extra={sorted(set(result_ids) - expected_ids)[:10]}"
            )
        counts = Counter()
        for result_index, result in enumerate(results):
            item_prefix = f"{prefix}.mode[{result_index}]"
            if not isinstance(result, dict):
                errors.append(f"{item_prefix} is not an object")
                continue
            unknown_mode = sorted(set(result) - _MODE_FIELDS)
            missing_mode = sorted(_MODE_FIELDS - set(result))
            if unknown_mode:
                errors.append(f"{item_prefix} unknown fields={unknown_mode}")
            if missing_mode:
                errors.append(f"{item_prefix} missing fields={missing_mode}")
            mode_id = str(result.get("mode_id") or "")
            mode = modes.get(mode_id)
            if mode is None:
                continue
            verdict = str(result.get("verdict") or "")
            counts[verdict] += 1
            if verdict not in CANONICAL_VERDICTS:
                errors.append(f"{item_prefix}.verdict is not canonical")
            if not isinstance(result.get("eligible"), bool) or result["eligible"] != (verdict != NOT_APPLICABLE_VERDICT):
                errors.append(f"{item_prefix}.eligible does not match verdict")
            for field in ("severity", "layer", "dimension"):
                if result.get(field) != mode.get(field):
                    errors.append(f"{item_prefix}.{field} mismatch")
            if result.get("scorer_type") != "llm_verifier":
                errors.append(f"{item_prefix}.scorer_type mismatch")
            if result.get("scorer_version") != ENGINE_VERSION:
                errors.append(f"{item_prefix}.scorer_version mismatch")
            if result.get("prompt_hash") != prompt_hashes.get(mode_id):
                errors.append(f"{item_prefix}.prompt_hash mismatch")
            if not isinstance(result.get("rationale"), str) or not result["rationale"].strip():
                errors.append(f"{item_prefix}.rationale missing")
            rationale_code = result.get("rationale_code")
            if rationale_code in _TECHNICAL_CODES:
                errors.append(f"{item_prefix} technical judge error={rationale_code}")
            elif rationale_code is not None:
                errors.append(f"{item_prefix}.rationale_code is not part of the current contract")
            evidence = result.get("evidence")
            if not isinstance(evidence, list):
                errors.append(f"{item_prefix}.evidence must be a list")
            else:
                errors.extend(
                    f"{item_prefix}.{message}"
                    for message in evidence_errors(evidence, transcript, verdict=verdict)
                )
            judge = result.get("judge")
            if not isinstance(judge, dict) or set(judge) != _JUDGE_FIELDS:
                errors.append(f"{item_prefix}.judge fields mismatch")
            elif (
                not isinstance(judge.get("model"), str)
                or not judge["model"].strip()
                or any(
                    value is not None
                    and (not isinstance(value, str) or not value.strip())
                    for value in (judge.get("resolved_model"), judge.get("provider"))
                )
                or not isinstance(judge.get("context_policy"), str)
                or judge["context_policy"] != CONTEXT_POLICY
                or isinstance(judge.get("temperature"), bool)
                or not isinstance(judge.get("temperature"), (int, float))
                or not math.isfinite(float(judge["temperature"]))
                or float(judge["temperature"]) != JUDGE_TEMPERATURE
                or isinstance(judge.get("max_tokens"), bool)
                or not isinstance(judge.get("max_tokens"), int)
                or judge["max_tokens"] != JUDGE_MAX_TOKENS
            ):
                errors.append(f"{item_prefix}.judge values invalid")
            extra = result.get("extra")
            if not isinstance(extra, dict) or not _EXTRA_FIELDS.issuperset(extra):
                errors.append(f"{item_prefix}.extra fields mismatch")
            if isinstance(extra, dict):
                input_hash = extra.get("input_sha256")
                if not isinstance(input_hash, str) or len(input_hash) != 64:
                    errors.append(f"{item_prefix}.extra.input_sha256 invalid")
                else:
                    expected_input = _expected_input_hash(transcript, mode)
                    if input_hash != expected_input:
                        errors.append(f"{item_prefix}.extra.input_sha256 is not a source hash")
                if rationale_code not in _TECHNICAL_CODES and not isinstance(
                    extra.get("raw_response"), str
                ):
                    errors.append(f"{item_prefix}.extra.raw_response missing")
                elif rationale_code not in _TECHNICAL_CODES:
                    try:
                        decision = Decision.model_validate_json(extra["raw_response"])
                    except (TypeError, ValueError):
                        errors.append(f"{item_prefix}.extra.raw_response is not the recorded decision")
                    else:
                        if decision.verdict.value != verdict:
                            errors.append(f"{item_prefix}.raw_response verdict mismatch")
                        if decision.rationale != result.get("rationale"):
                            errors.append(f"{item_prefix}.raw_response rationale mismatch")
                        if [span.model_dump() for span in decision.evidence] != evidence:
                            errors.append(f"{item_prefix}.raw_response evidence mismatch")
        expected_eligible = sum(counts[key] for key in ("PASS", "FAIL", "UNCLEAR"))
        expected_resolved = counts["PASS"] + counts["FAIL"]
        expected_unclear = counts["UNCLEAR"]
        for field in ("eligible_count", "resolved_count", "unclear_count"):
            if isinstance(row.get(field), bool) or not isinstance(row.get(field), int):
                errors.append(f"{prefix}.{field} must be an integer")
        if row.get("eligible_count") != expected_eligible:
            errors.append(f"{prefix}.eligible_count mismatch")
        if row.get("resolved_count") != expected_resolved:
            errors.append(f"{prefix}.resolved_count mismatch")
        if row.get("unclear_count") != expected_unclear:
            errors.append(f"{prefix}.unclear_count mismatch")
        expected_rate = expected_resolved / expected_eligible if expected_eligible else 0.0
        try:
            coverage = float(row.get("coverage_rate"))
            if not math.isfinite(coverage) or abs(coverage - expected_rate) > 1e-9:
                errors.append(f"{prefix}.coverage_rate mismatch")
        except (TypeError, ValueError):
            errors.append(f"{prefix}.coverage_rate invalid")
    scenario_sets = {frozenset(values) for values in scenarios_by_model.values()}
    if len(scenario_sets) > 1:
        errors.append("model scenario rosters differ")
    return errors


def _validate_projection(
    leaderboard: dict[str, Any],
    rows: list[dict[str, Any]],
    scan_path: Path,
    *,
    expected_models: int | None,
    expected_scenarios: int | None,
    strict: bool,
    checks_dir: Path | None,
) -> list[str]:
    errors: list[str] = []
    missing_public = sorted(_PUBLIC_FIELDS - set(leaderboard))
    unknown_public = sorted(set(leaderboard) - _PUBLIC_FIELDS)
    if missing_public:
        errors.append(f"leaderboard missing fields={missing_public}")
    if unknown_public:
        errors.append(f"leaderboard unknown fields={unknown_public}")
    if leaderboard.get("schema") != SCHEMA_VERSION:
        errors.append(f"schema={leaderboard.get('schema')!r} expected={SCHEMA_VERSION!r}")
    try:
        expected = build_scorecard(scan_path)
    except (OSError, ValueError) as exc:
        return [f"cannot rebuild projection: {exc}"]
    if leaderboard.get("models") != expected.get("models"):
        errors.append("leaderboard.models does not equal recomputed projection")
    notes = leaderboard.get("notes")
    if notes != expected.get("notes"):
        errors.append("leaderboard.notes does not equal recomputed projection")
    metadata = leaderboard.get("scan_metadata")
    if not isinstance(metadata, dict):
        return errors + ["scan_metadata missing or not an object"]
    plan_keys = {"scan_plan", "scan_plan_sha256"}
    metadata_fields = _SCAN_METADATA_FIELDS | plan_keys if plan_keys.intersection(metadata) else _SCAN_METADATA_FIELDS
    missing_metadata = sorted(metadata_fields - set(metadata))
    unknown_metadata = sorted(set(metadata) - metadata_fields)
    if missing_metadata:
        errors.append(f"scan_metadata missing fields={missing_metadata}")
    if unknown_metadata:
        errors.append(f"scan_metadata unknown fields={unknown_metadata}")
    expected_models_count = len(
        {str(row.get("model_id") or row.get("model") or "") for row in rows}
    )
    scenarios_by_model: defaultdict[str, set[str]] = defaultdict(set)
    for row in rows:
        scenarios_by_model[str(row.get("model_id") or row.get("model") or "")].add(
            str(row.get("scenario_id") or "")
        )
    roster_sizes = {len(values) for values in scenarios_by_model.values()}
    expected_scenarios_count = next(iter(roster_sizes), 0) if len(roster_sizes) == 1 else 0
    checks = {
        "benchmark_version": get_benchmark_version(REPO_ROOT),
        "code_version": get_code_version(REPO_ROOT),
        "source_artifact": artifact_reference(scan_path, REPO_ROOT),
        "source_sha256": hashlib.sha256(scan_path.read_bytes()).hexdigest(),
        "total_models": expected_models_count,
        "total_scenarios": expected_scenarios_count
        if strict or expected_scenarios is None
        else expected_scenarios,
        "row_count": len(rows),
        "observation_type": "MODEL-JUDGED",
        "projection_sha256": _json_sha(expected["models"]),
        "active_checks": sorted(_checks(checks_dir)),
        "check_prompt_hashes": check_prompt_hashes(checks_dir),
        "observed_prompt_hashes": _observed_prompt_hashes(rows),
        "observed_judges": _observed_judges(rows),
        "model_ids": sorted({str(row.get("model_id") or "") for row in rows}),
        "public_scope": load_inventory(REPO_ROOT).get("public_scope"),
        "public_harness": load_inventory(REPO_ROOT).get("public_harness"),
    }
    if expected_models is not None:
        checks["total_models"] = expected_models
    for key, value in checks.items():
        if metadata.get(key) != value:
            errors.append(f"scan_metadata.{key} mismatch")
    observed_judges = metadata.get("observed_judges")
    if not isinstance(observed_judges, list) or any(
        not isinstance(judge, dict) or set(judge) != _JUDGE_FIELDS
        for judge in observed_judges
    ):
        errors.append("scan_metadata.observed_judges fields mismatch")
    if not isinstance(metadata.get("generated_at"), str) or not metadata["generated_at"].strip():
        errors.append("scan_metadata.generated_at invalid")
    for key in ("source_sha256", "projection_sha256"):
        value = metadata.get(key)
        if not isinstance(value, str) or len(value) != 64:
            errors.append(f"scan_metadata.{key} invalid")
    if "scan_plan" in metadata and "scan_plan_sha256" in metadata:
        if metadata.get("scan_plan_sha256") != _json_sha(metadata.get("scan_plan")):
            errors.append("scan_metadata.scan_plan_sha256 mismatch")
    return errors


def validate_leaderboard(
    scan_path: Path,
    leaderboard_path: Path,
    *,
    expected_rows: int | None = None,
    expected_models: int | None = None,
    expected_scenarios: int | None = None,
    strict: bool = False,
    checks_dir: Path | None = None,
) -> list[str]:
    """Return mechanical QA errors.  An empty list means pass."""

    errors: list[str] = []
    try:
        rows = load_jsonl(scan_path)
        leaderboard = load_json(leaderboard_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"cannot load artifact: {exc}"]
    if not rows or any(not isinstance(row, dict) for row in rows):
        return ["scan must contain decision row objects"]
    if not isinstance(leaderboard, dict):
        return ["leaderboard must be an object"]
    errors.extend(_walk_obsolete(leaderboard))
    if expected_rows is not None and len(rows) != expected_rows:
        errors.append(f"rows={len(rows)} expected={expected_rows}")
    errors.extend(_validate_rows(rows, scan_path, checks_dir=checks_dir))
    if errors:
        return sorted(set(errors))
    errors.extend(
        _validate_projection(
            leaderboard,
            rows,
            scan_path,
            expected_models=expected_models,
            expected_scenarios=expected_scenarios,
            strict=strict,
            checks_dir=checks_dir,
        )
    )
    if errors:
        return sorted(set(errors))
    errors.extend(
        _scan_plan_errors(
            leaderboard,
            rows,
            scan_path,
            strict=strict,
            checks_dir=checks_dir,
        )
    )
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="QA safety-care/v2 scan and leaderboard")
    parser.add_argument("--scan", required=True, type=Path)
    parser.add_argument("--leaderboard", required=True, type=Path)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--expected-rows", type=int)
    parser.add_argument("--expected-models", type=int)
    parser.add_argument("--expected-scenarios", type=int)
    args = parser.parse_args()
    errors = validate_leaderboard(
        args.scan,
        args.leaderboard,
        strict=args.strict,
        expected_rows=args.expected_rows,
        expected_models=args.expected_models,
        expected_scenarios=args.expected_scenarios,
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("QA passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
