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

    for input_path in inputs:
        input_path = input_path.resolve()
        plan = _read_object(input_path.parent / "scan_plan.json")
        cost = _read_object(input_path.parent / "cost_report.json")
        scan_rows = _read_rows(input_path)
        model_ids = sorted({str(row.get("model_id") or "") for row in scan_rows})
        if not model_ids or "" in model_ids:
            raise ValueError(f"scan has a row without model_id: {input_path}")
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
        "schema": "invisiblebench-scan-merge/v1",
        "benchmark_version": benchmark_version,
        "result_contract_version": result_contract_version,
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
    from invisiblebench.version import BENCHMARK_VERSION, RESULT_CONTRACT_VERSION

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest = combine_scans(
            inputs=args.input,
            output=args.output,
            benchmark_version=BENCHMARK_VERSION,
            result_contract_version=RESULT_CONTRACT_VERSION,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote {args.output} and {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
