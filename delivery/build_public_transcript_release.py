"""Build a public, provenance-complete transcript evidence release."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

PUBLIC_TURN_FIELDS = {
    "turn",
    "role",
    "content",
    "branch_id",
    "session_number",
    "time_elapsed",
    "session_context",
    "truncated",
}
CONTENT_NOTICE = (
    "Contains synthetic benchmark conversations and unverified model outputs, including "
    "intentionally unsafe or hallucinated content. It is research evidence, not medical, "
    "legal, crisis, or caregiving advice."
)


def _read_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"expected object JSON at {path}")
    return data


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _slug(model_id: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", model_id.lower()).strip("-")


def _transcript_path(run_dir: Path, value: str) -> Path:
    path = Path(value)
    resolved = path.resolve() if path.is_absolute() else (run_dir / path).resolve()
    if not resolved.is_relative_to(run_dir.resolve()):
        raise ValueError(f"transcript path escapes run directory: {value}")
    if not resolved.is_file():
        raise ValueError(f"transcript not found: {resolved}")
    return resolved


def _load_turns(path: Path) -> list[dict[str, Any]]:
    turns: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        turn = json.loads(line)
        if not isinstance(turn, dict):
            raise ValueError(f"non-object transcript row at {path}:{line_number}")
        if turn.get("role") not in {"user", "assistant", "system"}:
            raise ValueError(f"invalid transcript role at {path}:{line_number}")
        if not isinstance(turn.get("content"), str):
            raise ValueError(f"missing transcript content at {path}:{line_number}")
        turns.append({key: value for key, value in turn.items() if key in PUBLIC_TURN_FIELDS})
    if not turns:
        raise ValueError(f"empty transcript: {path}")
    return turns


def _source_run(
    run_dir: Path,
    manifest: dict[str, Any],
    transcript_run: dict[str, Any],
    model_id: str,
) -> dict[str, Any]:
    by_model = transcript_run.get("actual_cost_by_model_usd") or {}
    return {
        "artifact_id": run_dir.name,
        "manifest_run_id": manifest.get("run_id"),
        "benchmark_version": manifest.get("benchmark_version"),
        "git_sha": manifest.get("git_sha"),
        "run_date": manifest.get("run_date"),
        "model_actual_cost_usd": by_model.get(model_id),
        "run_actual_cost_usd": transcript_run.get("actual_cost_usd"),
        "run_actual_billable_api_calls": transcript_run.get("actual_billable_api_calls"),
        "runtime_cost_ceiling_usd": transcript_run.get("runtime_cost_ceiling_usd"),
    }


def build_release(
    *,
    sources: dict[str, list[Path]],
    output_dir: Path,
    expected_scenario_ids: Iterable[str],
    benchmark_version: str,
    result_contract_version: str,
    claim_ready_check_count: int = 0,
) -> Path:
    expected_scenario_ids = set(expected_scenario_ids)
    if not sources:
        raise ValueError("at least one model source is required")
    if not expected_scenario_ids:
        raise ValueError("expected scenario inventory is empty")

    scenario_hashes: set[str] = set()
    model_bundles: list[dict[str, Any]] = []

    for model_id, run_dirs in sorted(sources.items()):
        transcripts: dict[str, dict[str, Any]] = {}
        source_runs: list[dict[str, Any]] = []
        model_names: set[str] = set()

        for run_dir in run_dirs:
            manifest = _read_object(run_dir / "run_manifest.json")
            transcript_run = _read_object(run_dir / "transcript_run.json")
            scenario_hash = str(manifest.get("scenario_hash") or "")
            if not scenario_hash:
                raise ValueError(f"run {run_dir.name} has no scenario_hash")
            scenario_hashes.add(scenario_hash)
            source_runs.append(_source_run(run_dir, manifest, transcript_run, model_id))

            entries = transcript_run.get("transcripts")
            if not isinstance(entries, list):
                raise ValueError(f"run {run_dir.name} has no transcript inventory")
            for entry in entries:
                if not isinstance(entry, dict) or entry.get("model_id") != model_id:
                    continue
                scenario_id = str(entry.get("scenario_id") or "")
                if not scenario_id:
                    raise ValueError(f"run {run_dir.name} has a transcript without scenario_id")
                path = _transcript_path(run_dir, str(entry.get("transcript_path") or ""))
                raw = path.read_bytes()
                record = {
                    "scenario_id": scenario_id,
                    "scenario": entry.get("scenario"),
                    "category": entry.get("category"),
                    "sha256": _sha256(raw),
                    "turns": _load_turns(path),
                }
                existing = transcripts.get(scenario_id)
                if existing and existing["sha256"] != record["sha256"]:
                    raise ValueError(
                        f"conflicting transcripts for model={model_id} scenario={scenario_id}"
                    )
                transcripts[scenario_id] = record
                model_names.add(str(entry.get("model") or model_id))

        actual_scenario_ids = set(transcripts)
        if actual_scenario_ids != expected_scenario_ids:
            missing = sorted(expected_scenario_ids - actual_scenario_ids)
            extra = sorted(actual_scenario_ids - expected_scenario_ids)
            raise ValueError(
                f"scenario coverage mismatch for {model_id}: missing={missing} extra={extra}"
            )
        if len(model_names) != 1:
            raise ValueError(f"inconsistent model names for {model_id}: {sorted(model_names)}")

        model_bundles.append(
            {
                "schema": "invisiblebench-model-transcripts/v1",
                "benchmark_version": benchmark_version,
                "synthetic_scenarios": True,
                "content_notice": CONTENT_NOTICE,
                "model": next(iter(model_names)),
                "model_id": model_id,
                "scenario_hash": next(iter(scenario_hashes)) if len(scenario_hashes) == 1 else None,
                "source_runs": source_runs,
                "transcript_count": len(transcripts),
                "transcripts": [transcripts[key] for key in sorted(transcripts)],
            }
        )

    if len(scenario_hashes) != 1:
        raise ValueError(f"mixed scenario hashes: {sorted(scenario_hashes)}")
    scenario_hash = next(iter(scenario_hashes))

    output_dir.mkdir(parents=True, exist_ok=True)
    model_entries: list[dict[str, Any]] = []
    for bundle in model_bundles:
        bundle["scenario_hash"] = scenario_hash
        filename = f"{_slug(str(bundle['model_id']))}.json"
        path = output_dir / filename
        payload = json.dumps(bundle, indent=2, ensure_ascii=False).encode() + b"\n"
        path.write_bytes(payload)
        model_entries.append(
            {
                "model": bundle["model"],
                "model_id": bundle["model_id"],
                "file": filename,
                "sha256": _sha256(payload),
                "bytes": len(payload),
                "transcript_count": bundle["transcript_count"],
                "source_runs": bundle["source_runs"],
            }
        )

    manifest = {
        "schema": "invisiblebench-transcripts/v1",
        "benchmark_version": benchmark_version,
        "result_contract_version": result_contract_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scenario_hash": scenario_hash,
        "model_count": len(model_entries),
        "scenario_count": len(expected_scenario_ids),
        "transcript_count": len(model_entries) * len(expected_scenario_ids),
        "claim_posture": (
            "quantitative_claims" if claim_ready_check_count else "descriptive_evidence_only"
        ),
        "claim_ready_check_count": claim_ready_check_count,
        "synthetic_scenarios": True,
        "content_notice": CONTENT_NOTICE,
        "models": model_entries,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return manifest_path


def _parse_sources(values: list[str]) -> dict[str, list[Path]]:
    sources: dict[str, list[Path]] = defaultdict(list)
    for value in values:
        if "=" not in value:
            raise ValueError(f"source must be MODEL_ID=RUN_DIR, got {value!r}")
        model_id, run_dir = value.split("=", 1)
        sources[model_id].append(Path(run_dir).resolve())
    return dict(sources)


def main(argv: list[str] | None = None) -> int:
    from invisiblebench.evaluation.check_registry import load_checks
    from invisiblebench.utils.benchmark_inventory import collect_public_scenario_ids
    from invisiblebench.version import BENCHMARK_VERSION, RESULT_CONTRACT_VERSION

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        action="append",
        required=True,
        help="MODEL_ID=RUN_DIR; repeat recovery runs for the same model",
    )
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
            sources=_parse_sources(args.source),
            output_dir=args.output,
            expected_scenario_ids=collect_public_scenario_ids(REPO_ROOT),
            benchmark_version=BENCHMARK_VERSION,
            result_contract_version=RESULT_CONTRACT_VERSION,
            claim_ready_check_count=claim_ready_count,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
