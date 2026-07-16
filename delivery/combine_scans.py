"""Combine complete single-profile scans with auditable lineage."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"expected object JSON at {path}")
    return value


def _read_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"non-object row at {path}:{line_number}")
        rows.append(row)
    if not rows:
        raise ValueError(f"empty scan: {path}")
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_sha256(value: object, *, field: str, path: Path) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"scan plan has invalid {field}: {path}")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"scan plan has invalid {field}: {path}") from exc
    return value


def _transcript_source_artifacts(rows: list[dict[str, Any]]) -> list[str]:
    artifacts: set[str] = set()
    for row in rows:
        path = Path(str(row.get("transcript_path") or ""))
        if path.parent.name != "transcripts" or not path.parent.parent.name:
            raise ValueError(
                "scan row transcript_path does not identify a source run artifact: "
                f"{row.get('model_id')} / {row.get('scenario_id')}"
            )
        artifacts.add(path.parent.parent.name)
    return sorted(artifacts)


def combine_scans(
    *,
    inputs: list[Path],
    output: Path,
    benchmark_version: str,
    result_contract_version: str,
) -> Path:
    if len(inputs) < 2:
        raise ValueError("at least two scans are required")

    rows: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    profiles: set[str] = set()
    judges: set[str] = set()
    comparability_fingerprints: set[str] = set()
    check_definition_snapshots: set[str] = set()
    scenario_corpus_hashes: set[str] = set()
    scoring_config_hashes: set[str] = set()
    check_definition_hashes: dict[str, str] | None = None

    for input_path in inputs:
        input_path = input_path.resolve()
        plan_path = input_path.parent / "scan_plan.json"
        plan = _read_object(plan_path)
        cost = _read_object(input_path.parent / "cost_report.json")
        scan_rows = _read_rows(input_path)
        model_ids = sorted({str(row.get("model_id") or "") for row in scan_rows})
        scenario_ids = sorted({str(row.get("scenario_id") or "") for row in scan_rows})
        if not model_ids or "" in model_ids:
            raise ValueError(f"scan has a row without model_id: {input_path}")
        if not scenario_ids or "" in scenario_ids:
            raise ValueError(f"scan has a row without scenario_id: {input_path}")
        if plan.get("schema") != "invisiblebench-scan-plan/v2":
            raise ValueError(f"publication merge requires scan plan v2: {input_path}")
        if plan.get("provenance_complete") is not True:
            raise ValueError(f"incomplete scan provenance: {input_path}")
        if plan.get("benchmark_version") != benchmark_version:
            raise ValueError(f"scan plan benchmark version mismatch: {input_path}")
        if plan.get("result_contract_version") != result_contract_version:
            raise ValueError(f"scan plan result contract mismatch: {input_path}")
        if sorted(plan.get("model_ids") or []) != model_ids:
            raise ValueError(f"scan plan model roster mismatch: {input_path}")
        if sorted(plan.get("scenario_ids") or []) != scenario_ids:
            raise ValueError(f"scan plan scenario roster mismatch: {input_path}")
        row_contracts = {row.get("contract_version") for row in scan_rows}
        if row_contracts != {result_contract_version}:
            raise ValueError(f"scan row contract mismatch: {input_path}")

        fingerprint = _require_sha256(
            plan.get("comparability_fingerprint"),
            field="comparability_fingerprint",
            path=input_path,
        )
        comparability_fingerprints.add(fingerprint)
        scenario_corpus_hashes.add(
            _require_sha256(
                plan.get("scenario_corpus_sha256"),
                field="scenario_corpus_sha256",
                path=input_path,
            )
        )
        scoring_config_hashes.add(
            _require_sha256(
                plan.get("scoring_config_sha256"),
                field="scoring_config_sha256",
                path=input_path,
            )
        )

        plan_check_hashes = plan.get("check_definition_hashes")
        if not isinstance(plan_check_hashes, dict) or not plan_check_hashes:
            raise ValueError(f"scan plan lacks check definition hashes: {input_path}")
        normalized_check_hashes = {
            str(check_id): _require_sha256(
                value,
                field=f"check_definition_hashes.{check_id}",
                path=input_path,
            )
            for check_id, value in plan_check_hashes.items()
        }
        snapshot = json.dumps(normalized_check_hashes, sort_keys=True, separators=(",", ":"))
        check_definition_snapshots.add(snapshot)
        check_definition_hashes = normalized_check_hashes

        source_runs = plan.get("source_runs")
        if not isinstance(source_runs, list) or not source_runs:
            raise ValueError(f"scan plan lacks source run provenance: {input_path}")
        for source in source_runs:
            if not isinstance(source, dict) or source.get("complete") is not True:
                raise ValueError(f"incomplete source run provenance: {input_path}")
            _require_sha256(
                source.get("run_manifest_sha256"),
                field="source_runs.run_manifest_sha256",
                path=input_path,
            )
            _require_sha256(
                source.get("transcript_run_sha256"),
                field="source_runs.transcript_run_sha256",
                path=input_path,
            )

        transcript_hashes = plan.get("transcript_hashes")
        if not isinstance(transcript_hashes, list):
            raise ValueError(f"scan plan lacks transcript hashes: {input_path}")
        planned_pairs: set[tuple[str, str]] = set()
        for transcript in transcript_hashes:
            if not isinstance(transcript, dict):
                raise ValueError(f"invalid scan plan transcript hash: {input_path}")
            key = (str(transcript.get("model_id") or ""), str(transcript.get("scenario_id") or ""))
            if "" in key or key in planned_pairs:
                raise ValueError(f"invalid scan plan transcript roster: {input_path}")
            planned_pairs.add(key)
            _require_sha256(
                transcript.get("sha256"),
                field="transcript_hashes.sha256",
                path=input_path,
            )
        row_pairs = {
            (str(row.get("model_id") or ""), str(row.get("scenario_id") or ""))
            for row in scan_rows
        }
        if planned_pairs != row_pairs:
            raise ValueError(f"scan plan transcript roster mismatch: {input_path}")

        profile = str(plan.get("profile") or "")
        judge = str(plan.get("judge_model") or "")
        if not profile or not judge:
            raise ValueError(f"scan plan lacks profile or judge_model: {input_path}")
        actual_cost = cost.get("actual_cost_usd")
        actual_calls = cost.get("actual_billable_api_calls")
        if (
            isinstance(actual_cost, bool)
            or not isinstance(actual_cost, (int, float))
            or actual_cost < 0
            or isinstance(actual_calls, bool)
            or not isinstance(actual_calls, int)
            or actual_calls < 0
        ):
            raise ValueError(f"scan lacks valid actual cost accounting: {input_path}")
        profiles.add(profile)
        judges.add(judge)
        rows.extend(scan_rows)
        sources.append(
            {
                "artifact_id": input_path.parent.name,
                "file": input_path.name,
                "sha256": _sha256(input_path),
                "scan_plan_sha256": _sha256(plan_path),
                "row_count": len(scan_rows),
                "model_ids": model_ids,
                "transcript_source_artifacts": _transcript_source_artifacts(scan_rows),
                "actual_cost_usd": actual_cost,
                "actual_billable_api_calls": actual_calls,
            }
        )

    if len(profiles) != 1:
        raise ValueError(f"mixed profile values: {sorted(profiles)}")
    if len(judges) != 1:
        raise ValueError(f"mixed judge_model values: {sorted(judges)}")
    if len(comparability_fingerprints) != 1:
        raise ValueError("mixed comparability fingerprints")
    if len(check_definition_snapshots) != 1:
        raise ValueError("mixed check definition snapshots")
    if len(scenario_corpus_hashes) != 1 or len(scoring_config_hashes) != 1:
        raise ValueError("mixed corpus or scoring config snapshots")
    if profiles != {"publish"}:
        raise ValueError(f"publication merge requires profile=publish, got {sorted(profiles)}")

    seen: set[tuple[str, str]] = set()
    scenarios_by_model: dict[str, set[str]] = {}
    for row in rows:
        model_id = str(row.get("model_id") or "")
        scenario_id = str(row.get("scenario_id") or "")
        if not scenario_id:
            raise ValueError(f"scan row has no scenario_id for model={model_id}")
        key = (model_id, scenario_id)
        if key in seen:
            raise ValueError(f"duplicate model/scenario row: {key}")
        seen.add(key)
        scenarios_by_model.setdefault(model_id, set()).add(scenario_id)

    scenario_sets = {frozenset(value) for value in scenarios_by_model.values()}
    if len(scenario_sets) != 1:
        counts = {model_id: len(value) for model_id, value in scenarios_by_model.items()}
        raise ValueError(f"scenario coverage mismatch: {counts}")

    rows.sort(key=lambda row: (str(row["model_id"]), str(row["scenario_id"])))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))

    costs = [source["actual_cost_usd"] for source in sources]
    calls = [source["actual_billable_api_calls"] for source in sources]
    manifest = {
        "schema": "invisiblebench-scan-merge/v2",
        "benchmark_version": benchmark_version,
        "result_contract_version": result_contract_version,
        "provenance_complete": True,
        "comparability_fingerprint": next(iter(comparability_fingerprints)),
        "scenario_corpus_sha256": next(iter(scenario_corpus_hashes)),
        "scoring_config_sha256": next(iter(scoring_config_hashes)),
        "check_definition_hashes": check_definition_hashes,
        "generated_at": datetime.now(UTC).isoformat(),
        "profile": next(iter(profiles)),
        "judge_model": next(iter(judges)),
        "model_count": len(scenarios_by_model),
        "scenario_count": len(next(iter(scenario_sets))),
        "row_count": len(rows),
        "actual_cost_usd": sum(float(value) for value in costs if value is not None),
        "actual_billable_api_calls": sum(int(value) for value in calls if value is not None),
        "output_file": output.name,
        "output_sha256": _sha256(output),
        "sources": sources,
    }
    manifest_path = output.parent / "merge_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest_path


def main(argv: list[str] | None = None) -> int:
    from invisiblebench.version import BENCHMARK_VERSION, SCANNED_ROW_CONTRACT_VERSION

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest = combine_scans(
            inputs=args.input,
            output=args.output,
            benchmark_version=BENCHMARK_VERSION,
            result_contract_version=SCANNED_ROW_CONTRACT_VERSION,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote {args.output} and {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
