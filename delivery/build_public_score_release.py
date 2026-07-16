"""Build allowlisted public per-check evidence from a strict-QA-ready merged scan."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

CONTENT_NOTICE = (
    "Automated check verdicts over synthetic benchmark conversations. Model outputs may be "
    "unsafe or hallucinated. No check is a comparative Safety claim unless claim_ready; Care "
    "results are directional. This is research evidence, not medical, legal, crisis, or "
    "caregiving advice."
)
ROW_FIELDS = {
    "model",
    "model_id",
    "scenario_id",
    "category",
    "engine_version",
    "eligible_count",
    "resolved_count",
    "unclear_count",
    "coverage_rate",
}
MODE_FIELDS = {
    "mode_id",
    "eligible",
    "verdict",
    "severity",
    "layer",
    "dimension",
    "scorer_type",
    "confidence",
    "rationale_code",
    "adjudication_required",
    "scorer_version",
    "prompt_hash",
    "secondary_tags",
}
EVIDENCE_FIELDS = {"role", "turn", "quote", "rationale"}
EXTRA_FIELDS = {
    "repetitions",
    "planned_repetitions",
    "adaptive_repetitions",
    "aggregation",
    "all_verdicts",
    "automated_adjudication",
    "tiebreak_repetitions",
    "matched_pattern",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"expected object JSON at {path}")
    return value


def _read_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"non-object row at {path}:{line_number}")
        rows.append(row)
    if not rows:
        raise ValueError(f"empty scan: {path}")
    return rows


def _project_evidence(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        raise ValueError("mode evidence must be a list")
    projected: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("mode evidence item must be an object")
        projected.append({key: item[key] for key in EVIDENCE_FIELDS if key in item})
    return projected


def _project_mode(result: dict[str, Any]) -> dict[str, Any]:
    projected = {key: result.get(key) for key in MODE_FIELDS}
    projected["evidence"] = _project_evidence(result.get("evidence"))
    extra = result.get("extra") or {}
    if not isinstance(extra, dict):
        raise ValueError("mode extra must be an object")
    projected["extra"] = {key: extra[key] for key in EXTRA_FIELDS if key in extra}
    return projected


def _project_row(
    row: dict[str, Any], *, expected_mode_ids: set[str]
) -> dict[str, Any]:
    if int(row.get("unclear_count") or 0) != 0:
        raise ValueError(
            f"unresolved verdict for {row.get('model_id')} / {row.get('scenario_id')}"
        )
    mode_results = row.get("mode_results")
    if not isinstance(mode_results, list):
        raise ValueError("scan row mode_results must be a list")
    actual_mode_ids = {str(result.get("mode_id") or "") for result in mode_results}
    if actual_mode_ids != expected_mode_ids or len(mode_results) != len(expected_mode_ids):
        raise ValueError(
            f"check coverage mismatch for {row.get('model_id')} / {row.get('scenario_id')}"
        )
    if any(result.get("verdict") == "UNCLEAR" for result in mode_results):
        raise ValueError(
            f"unresolved verdict for {row.get('model_id')} / {row.get('scenario_id')}"
        )
    projected = {key: row.get(key) for key in ROW_FIELDS}
    projected["mode_results"] = [
        _project_mode(result) for result in sorted(mode_results, key=lambda item: item["mode_id"])
    ]
    return projected


def build_release(
    *,
    scan_path: Path,
    output_dir: Path,
    expected_scenario_ids: Iterable[str],
    expected_mode_ids: Iterable[str],
    benchmark_version: str,
    result_contract_version: str,
    claim_ready_check_count: int,
) -> Path:
    scan_path = scan_path.resolve()
    expected_scenario_ids = set(expected_scenario_ids)
    expected_mode_ids = set(expected_mode_ids)
    if not expected_scenario_ids or not expected_mode_ids:
        raise ValueError("expected scenario and check inventories must be non-empty")

    merge = _read_object(scan_path.parent / "merge_manifest.json")
    expected_merge = {
        "schema": "invisiblebench-scan-merge/v2",
        "benchmark_version": benchmark_version,
        "result_contract_version": result_contract_version,
        "provenance_complete": True,
        "profile": "publish",
        "output_file": scan_path.name,
        "output_sha256": _sha256(scan_path),
    }
    mismatches = {
        key: {"actual": merge.get(key), "expected": expected}
        for key, expected in expected_merge.items()
        if merge.get(key) != expected
    }
    if mismatches:
        raise ValueError(f"invalid merge manifest: {mismatches}")
    if (
        not isinstance(merge.get("comparability_fingerprint"), str)
        or len(merge["comparability_fingerprint"]) != 64
        or not isinstance(merge.get("scenario_corpus_sha256"), str)
        or len(merge["scenario_corpus_sha256"]) != 64
        or not isinstance(merge.get("scoring_config_sha256"), str)
        or len(merge["scoring_config_sha256"]) != 64
        or not isinstance(merge.get("check_definition_hashes"), dict)
        or not merge["check_definition_hashes"]
        or not isinstance(merge.get("sources"), list)
        or not merge["sources"]
        or any(
            not isinstance(source, dict)
            or not isinstance(source.get("scan_plan_sha256"), str)
            or len(source["scan_plan_sha256"]) != 64
            for source in merge["sources"]
        )
    ):
        raise ValueError("invalid merge manifest: incomplete provenance")

    rows_by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    model_names: dict[str, set[str]] = defaultdict(set)
    raw_rows = _read_rows(scan_path)
    for row in raw_rows:
        if row.get("contract_version") != result_contract_version:
            raise ValueError("scan row contract does not match merge manifest")
        model_id = str(row.get("model_id") or "")
        scenario_id = str(row.get("scenario_id") or "")
        if not model_id or not scenario_id:
            raise ValueError("scan row missing model_id or scenario_id")
        rows_by_model[model_id].append(
            _project_row(row, expected_mode_ids=expected_mode_ids)
        )
        model_names[model_id].add(str(row.get("model") or model_id))

    for model_id, rows in rows_by_model.items():
        scenarios = {str(row["scenario_id"]) for row in rows}
        if scenarios != expected_scenario_ids or len(rows) != len(expected_scenario_ids):
            raise ValueError(f"scenario coverage mismatch for {model_id}")
        if len(model_names[model_id]) != 1:
            raise ValueError(f"inconsistent model names for {model_id}")
    if len(raw_rows) != merge.get("row_count") or len(rows_by_model) != merge.get("model_count"):
        raise ValueError("merged scan counts do not match merge manifest")

    output_dir.mkdir(parents=True, exist_ok=True)
    model_entries: list[dict[str, Any]] = []
    for model_id, rows in sorted(rows_by_model.items()):
        bundle = {
            "schema": "invisiblebench-model-score-evidence/v1",
            "benchmark_version": benchmark_version,
            "result_contract_version": result_contract_version,
            "profile": merge["profile"],
            "judge_model": merge.get("judge_model"),
            "claim_posture": (
                "calibration_gated_safety_claims"
                if claim_ready_check_count
                else "research_evidence_only"
            ),
            "claim_ready_check_count": claim_ready_check_count,
            "content_notice": CONTENT_NOTICE,
            "model": next(iter(model_names[model_id])),
            "model_id": model_id,
            "row_count": len(rows),
            "mode_result_count": len(rows) * len(expected_mode_ids),
            "rows": sorted(rows, key=lambda row: str(row["scenario_id"])),
        }
        filename = f"{_slug(model_id)}.json"
        path = output_dir / filename
        path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n")
        model_entries.append(
            {
                "model": bundle["model"],
                "model_id": model_id,
                "file": filename,
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
                "row_count": bundle["row_count"],
                "mode_result_count": bundle["mode_result_count"],
            }
        )

    manifest = {
        "schema": "invisiblebench-score-evidence/v1",
        "benchmark_version": benchmark_version,
        "result_contract_version": result_contract_version,
        "generated_at": datetime.now(UTC).isoformat(),
        "profile": merge["profile"],
        "judge_model": merge.get("judge_model"),
        "model_count": len(model_entries),
        "scenario_count": len(expected_scenario_ids),
        "check_count": len(expected_mode_ids),
        "row_count": len(raw_rows),
        "mode_result_count": len(raw_rows) * len(expected_mode_ids),
        "claim_posture": (
            "calibration_gated_safety_claims"
            if claim_ready_check_count
            else "research_evidence_only"
        ),
        "claim_ready_check_count": claim_ready_check_count,
        "content_notice": CONTENT_NOTICE,
        "source_scan_sha256": merge["output_sha256"],
        "source_merge": merge,
        "models": model_entries,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return manifest_path


def main(argv: list[str] | None = None) -> int:
    from invisiblebench.evaluation.check_registry import load_checks
    from invisiblebench.utils.benchmark_inventory import collect_public_scenario_ids
    from invisiblebench.version import BENCHMARK_VERSION, SCANNED_ROW_CONTRACT_VERSION

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    modes, _ = load_checks()
    claim_ready_count = sum(
        1
        for mode in modes.values()
        if (mode.get("calibration") or {}).get("status") == "claim_ready"
    )
    try:
        path = build_release(
            scan_path=args.input,
            output_dir=args.output,
            expected_scenario_ids=collect_public_scenario_ids(REPO_ROOT),
            expected_mode_ids=modes,
            benchmark_version=BENCHMARK_VERSION,
            result_contract_version=SCANNED_ROW_CONTRACT_VERSION,
            claim_ready_check_count=claim_ready_count,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
