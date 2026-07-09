#!/usr/bin/env python3
"""Resolve eligible UNCLEAR scan rows with the current verifier configuration.

This is an automated alternative to manual adjudication for publication QA:
it preserves completed scan rows, reruns only eligible UNCLEAR check results,
recomputes row aggregates through ModeEngine, and writes a new scan artifact.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from invisiblebench.api import DEFAULT_JUDGE_MODEL, ModelAPIClient  # noqa: E402
from invisiblebench.evaluation.mode_engine import ModeEngine  # noqa: E402
from invisiblebench.evaluation.verifiers.base import (  # noqa: E402
    EvidenceSpan,
    Verdict,
    VerdictResult,
)
from invisiblebench.judge import (  # noqa: E402
    apply_scan_profile,
    enrich_scenario_with_inferred_tags,
    load_scan_profile,
    load_scenario,
    load_transcript,
    write_outputs,
)

DEFAULT_SCAN_OUTPUT_ROOT = REPO_ROOT / "results" / "safety_care_scan"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("resolve_unclear_scan")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL: {exc}") from exc
    return rows


def _result_from_dict(data: dict[str, Any]) -> VerdictResult:
    evidence = [
        EvidenceSpan(
            role=str(item.get("role", "")),
            turn=int(item.get("turn", 0) or 0),
            quote=str(item.get("quote", "")),
            rationale=item.get("rationale"),
        )
        for item in (data.get("evidence") or [])
        if isinstance(item, dict)
    ]
    return VerdictResult(
        mode_id=str(data.get("mode_id", "")),
        eligible=bool(data.get("eligible")),
        verdict=Verdict(str(data.get("verdict"))),
        severity=str(data.get("severity", "S1")),
        layer=str(data.get("layer", "")),
        dimension=str(data.get("dimension", "")),
        scorer_type=str(data.get("scorer_type", "")),
        confidence=float(data.get("confidence", 0.0) or 0.0),
        evidence=evidence,
        rationale_code=data.get("rationale_code"),
        adjudication_required=bool(data.get("adjudication_required")),
        scorer_version=str(data.get("scorer_version", "")),
        prompt_hash=data.get("prompt_hash"),
        secondary_tags=list(data.get("secondary_tags") or []),
        extra=dict(data.get("extra") or {}),
    )


def _source_run_dirs(rows: list[dict[str, Any]]) -> list[Path]:
    run_dirs: set[Path] = set()
    for row in rows:
        raw = row.get("transcript_path")
        if not raw:
            continue
        path = Path(str(raw))
        if path.name.endswith(".jsonl") and path.parent.name == "transcripts":
            run_dirs.add(path.parent.parent)
        else:
            run_dirs.add(path.parent)
    return sorted(run_dirs)


def _load_source_plan(scan_path: Path, profile_name: str, judge_model: str) -> dict[str, Any]:
    plan_path = scan_path.parent / "scan_plan.json"
    if plan_path.exists():
        try:
            with plan_path.open(encoding="utf-8") as f:
                plan = json.load(f)
            if isinstance(plan, dict):
                plan = dict(plan)
            else:
                plan = {}
        except (OSError, json.JSONDecodeError):
            plan = {}
    else:
        plan = {}
    plan["profile"] = f"{profile_name}+resolve-unclear"
    plan["llm_enabled"] = True
    plan["judge_model"] = judge_model
    plan["resolver_source_scan"] = str(scan_path)
    return plan


def _needs_resolution(result: dict[str, Any]) -> bool:
    return bool(result.get("eligible")) and result.get("verdict") == Verdict.UNCLEAR.value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resolve eligible UNCLEAR rows in a scan JSONL without manual adjudication."
    )
    parser.add_argument("--scan", required=True, type=Path, help="Source per_run.jsonl")
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_SCAN_OUTPUT_ROOT),
        help="Directory under which to write resolved_<timestamp>",
    )
    parser.add_argument("--profile", default="publish", help="Scan profile to apply")
    parser.add_argument(
        "--llm-model",
        default=DEFAULT_JUDGE_MODEL,
        help=f"Judge model for rerun verifiers (default: {DEFAULT_JUDGE_MODEL})",
    )
    parser.add_argument(
        "--allow-remaining",
        action="store_true",
        help="Write output even if eligible UNCLEAR rows remain and exit 0.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Only report target rows")
    args = parser.parse_args()

    scan_path = args.scan.resolve()
    rows = _load_jsonl(scan_path)
    targets = [
        (row, result)
        for row in rows
        for result in row.get("mode_results", [])
        if isinstance(result, dict) and _needs_resolution(result)
    ]
    logger.info("Loaded %d rows from %s", len(rows), scan_path)
    logger.info("Eligible UNCLEAR check rows to resolve: %d", len(targets))
    if args.dry_run:
        for row, result in targets:
            print(
                json.dumps(
                    {
                        "model_id": row.get("model_id"),
                        "scenario_id": row.get("scenario_id"),
                        "mode_id": result.get("mode_id"),
                        "rationale_code": result.get("rationale_code"),
                    },
                    sort_keys=True,
                )
            )
        return 0

    profile = load_scan_profile(args.profile)
    engine = ModeEngine(llm_api_client=ModelAPIClient(), llm_model=args.llm_model)
    engine.modes, engine.routing = apply_scan_profile(engine.modes, engine.routing, profile)

    outputs: list[dict[str, Any]] = []
    engine_outputs = []
    report: list[dict[str, Any]] = []

    for row_index, row in enumerate(rows, 1):
        scenario_id = str(row.get("scenario_id"))
        scenario = enrich_scenario_with_inferred_tags(load_scenario(scenario_id))
        results = [_result_from_dict(result) for result in row.get("mode_results", [])]
        transcript: list[dict[str, Any]] | None = None

        for index, current in enumerate(results):
            if not current.eligible or current.verdict is not Verdict.UNCLEAR:
                continue
            mode_id = current.mode_id
            if mode_id not in engine.modes:
                logger.warning("Skipping unknown mode %s on %s", mode_id, scenario_id)
                continue
            if transcript is None:
                transcript = load_transcript(Path(str(row["transcript_path"])))
            logger.info("Resolving %s / %s (%d/%d)", scenario_id, mode_id, row_index, len(rows))
            resolved = engine._run_single_mode(
                mode_id,
                engine.modes[mode_id],
                transcript,
                scenario,
            )
            if resolved is None:
                continue
            results[index] = resolved
            report.append(
                {
                    "model_id": row.get("model_id"),
                    "scenario_id": scenario_id,
                    "mode_id": mode_id,
                    "before_verdict": current.verdict.value,
                    "after_verdict": resolved.verdict.value,
                    "after_rationale_code": resolved.rationale_code,
                    "after_extra": resolved.extra,
                }
            )

        out = engine._aggregate(results, scenario)
        outputs.append(
            {
                "model": row.get("model"),
                "model_id": row.get("model_id"),
                "scenario_id": row.get("scenario_id"),
                "category": row.get("category"),
                "transcript_path": row.get("transcript_path"),
                **out.to_dict(),
            }
        )
        engine_outputs.append(out)

    remaining = [
        {
            "model_id": row.get("model_id"),
            "scenario_id": row.get("scenario_id"),
            "mode_id": result.get("mode_id"),
        }
        for row in outputs
        for result in row.get("mode_results", [])
        if isinstance(result, dict) and _needs_resolution(result)
    ]

    output_dir = Path(args.output_root) / f"resolved_{time.strftime('%Y%m%d_%H%M%S')}"
    plan = _load_source_plan(scan_path, args.profile, args.llm_model)
    plan["resolved_unclear_rows"] = len(report)
    plan["remaining_unclear_rows"] = len(remaining)
    write_outputs(output_dir, outputs, engine_outputs, _source_run_dirs(rows), plan)
    with (output_dir / "resolution_report.json").open("w", encoding="utf-8") as f:
        json.dump(
            {
                "source_scan": str(scan_path),
                "resolved": report,
                "remaining_unclear": remaining,
            },
            f,
            indent=2,
        )

    print(f"Resolved scan: {output_dir}")
    print(f"Resolved rows: {len(report)}")
    print(f"Remaining eligible UNCLEAR rows: {len(remaining)}")
    if remaining and not args.allow_remaining:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
