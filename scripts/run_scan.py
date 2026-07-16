#!/usr/bin/env python3
"""Run the Safety/Care ModeEngine over existing transcripts.

LLM-dependent modes return UNCLEAR/NOT_APPLICABLE unless --enable-llm wires an
api_client. Regex/lexicon/corpus verifiers produce actionable signal on the
existing transcript corpus without model calls.

Output per run:
  - `results/safety_care_scan/<timestamp>/per_run.jsonl` — one line per (model, scenario)
  - `results/safety_care_scan/<timestamp>/blindspot_rates.json` — corpus-level rates
  - `results/safety_care_scan/<timestamp>/summary.md` — human-readable summary

Usage:
  uv run python scripts/run_scan.py <run_dir>
  uv run python scripts/run_scan.py results/run_20260330_130332
  uv run python scripts/run_scan.py results/run_20260330_130332 results/partial_runs/run_20260330_033649_up_to_deepseek
  uv run python scripts/run_scan.py --all
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

DEFAULT_SCAN_OUTPUT_ROOT = REPO_ROOT / "results" / "safety_care_scan"
CHECKPOINT_SCHEMA = "invisiblebench-scan-checkpoint/v1"
CHECKPOINT_FILENAME = "scan_state.json"
PARTIAL_FILENAME = "per_run.partial.jsonl"

from invisiblebench.api import (  # noqa: E402
    DEFAULT_JUDGE_MODEL,
    CostBudgetExceededError,
    ModelAPIClient,
    cost_tracker,
    maximum_reasonable_cost_ceiling,
)
from invisiblebench.evaluation.mode_engine import (  # noqa: E402
    ModeEngine,
    ModeEngineOutput,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("safety_care_scan")

from invisiblebench.judge import (  # noqa: E402
    apply_scan_profile,
    attach_scan_provenance,
    build_scan_plan,
    enrich_scenario_with_inferred_tags,
    load_scan_profile,
    load_scenario,
    scan_run,
    transcripts_for_run,
    write_outputs,
)


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def _create_output_dir(root: Path) -> Path:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    for suffix in range(100):
        name = stamp if suffix == 0 else f"{stamp}_{suffix:02d}"
        candidate = root / name
        try:
            candidate.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            continue
        return candidate
    raise FileExistsError(f"could not allocate a unique scan directory under {root}")


def _engine_output_from_record(record: dict[str, Any]) -> ModeEngineOutput:
    return ModeEngineOutput(
        overall_score=float(record["overall_score"]),
        hard_fail=bool(record["hard_fail"]),
        hard_fail_reasons=list(record.get("hard_fail_reasons") or []),
        dimension_scores=dict(record.get("dimension_scores") or {}),
        blindspot_profile=dict(record.get("blindspot_profile") or {}),
        mode_results=list(record.get("mode_results") or []),
        claim_surface=dict(record.get("claim_surface") or {}),
        engine_version=str(record.get("engine_version") or ""),
        eligible_count=int(record.get("eligible_count") or 0),
        resolved_count=int(record.get("resolved_count") or 0),
        unclear_count=int(record.get("unclear_count") or 0),
        coverage_rate=float(record.get("coverage_rate") or 0.0),
    )


def _load_partial(path: Path) -> tuple[list[dict[str, Any]], list[ModeEngineOutput]]:
    if not path.exists():
        return [], []
    records: list[dict[str, Any]] = []
    outputs: list[ModeEngineOutput] = []
    seen: set[tuple[str, str]] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError(f"non-object checkpoint row at {path}:{line_number}")
            key = (str(record.get("model_id") or ""), str(record.get("scenario_id") or ""))
            if not all(key):
                raise ValueError(f"checkpoint row missing identity at {path}:{line_number}")
            if key in seen:
                raise ValueError(f"duplicate checkpoint row for {key[0]} / {key[1]}")
            seen.add(key)
            records.append(record)
            outputs.append(_engine_output_from_record(record))
    return records, outputs


def _combined_cost_snapshot(
    previous: dict[str, Any], current: dict[str, Any], ceiling: float | None
) -> dict[str, Any]:
    by_model: dict[str, float] = {}
    for snapshot in (previous, current):
        for model, cost in (snapshot.get("by_model") or {}).items():
            by_model[str(model)] = by_model.get(str(model), 0.0) + float(cost)
    return {
        "total": float(previous.get("total") or 0.0) + float(current.get("total") or 0.0),
        "calls": int(previous.get("calls") or 0) + int(current.get("calls") or 0),
        "by_model": by_model,
        "max_cost_usd": ceiling,
    }


def _scan_signature(args: argparse.Namespace, run_dirs: list[Path]) -> dict[str, Any]:
    return {
        "run_dirs": [str(path) for path in run_dirs],
        "profile": args.profile,
        "enable_llm": bool(args.enable_llm),
        "llm_model": args.llm_model,
        "limit": args.limit,
        "filter": args.filter,
        "parallel": bool(args.parallel),
        "transcript_workers": max(args.transcript_workers, 1),
        "max_workers": args.max_workers,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "run_dirs",
        nargs="*",
        help="Path(s) to results/run_<timestamp>/ directory or other transcript roots",
    )
    ap.add_argument(
        "--all",
        action="store_true",
        help="Scan all run_* directories under results/",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit transcripts scanned (for smoke testing)",
    )
    ap.add_argument(
        "--filter",
        default=None,
        help="Only scan transcripts whose filename contains this substring",
    )
    ap.add_argument(
        "--output-root",
        default=str(DEFAULT_SCAN_OUTPUT_ROOT),
        help="Where to write scan outputs",
    )
    ap.add_argument(
        "--resume",
        type=Path,
        default=None,
        help=(
            "Resume an incomplete scan directory. Repeat the original run dirs and scan "
            "options; completed model/scenario rows are read from its durable checkpoint."
        ),
    )
    ap.add_argument(
        "--profile",
        default="publish",
        help="Scan profile: smoke, dev, full, or publish (default: publish).",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Write and print the scan plan without evaluating transcripts.",
    )
    ap.add_argument(
        "--enable-llm",
        action="store_true",
        help="Wire ModelAPIClient so LLM-primary modes run (costs tokens).",
    )
    ap.add_argument(
        "--max-cost-usd",
        type=float,
        default=None,
        help=(
            "Required ceiling for a live --enable-llm scan. The conservative "
            "scan budget must fit within this amount before any verifier calls run."
        ),
    )
    ap.add_argument(
        "--llm-model",
        default=DEFAULT_JUDGE_MODEL,
        help=f"Judge model for LLM verifiers (default: {DEFAULT_JUDGE_MODEL}).",
    )
    ap.add_argument(
        "--parallel",
        action="store_true",
        help="Run verifier checks concurrently within each transcript (faster, same results).",
    )
    ap.add_argument(
        "--transcript-workers",
        type=int,
        default=1,
        help="Run multiple transcripts concurrently (default: 1).",
    )
    ap.add_argument(
        "--max-workers",
        type=int,
        default=8,
        help="Max concurrent verifier threads when --parallel is set (default: 8).",
    )
    args = ap.parse_args()

    try:
        profile = load_scan_profile(args.profile)
    except ValueError as e:
        logger.error("%s", e)
        return 2

    api_client = None
    if args.enable_llm:
        try:
            api_client = ModelAPIClient()
            logger.info("LLM verifier enabled with model=%s", args.llm_model)
        except (ImportError, ValueError) as e:
            logger.error("Failed to initialize ModelAPIClient: %s", e)
            if not args.dry_run:
                # Fail closed: an explicitly requested --enable-llm scan must not
                # silently degrade to a deterministic-only scan where eligible
                # LLM checks vanish as NOT_APPLICABLE. Dry-run still plans.
                logger.error("Aborting: --enable-llm scan cannot run without an API client.")
                return 2
            logger.error("Dry-run continues; live scan would abort here.")

    engine = ModeEngine(llm_api_client=api_client, llm_model=args.llm_model)
    engine.modes, engine.routing = apply_scan_profile(engine.modes, engine.routing, profile)
    logger.info("Scan profile: %s (%s)", profile["name"], profile["description"])
    logger.info("Loaded %d checks from checks/", len(engine.modes))
    logger.info("Loaded %d routing entries", len(engine.routing))

    run_dirs: list[Path] = []
    if args.all:
        run_dirs = sorted(
            (REPO_ROOT / "results").glob("run_*"),
            key=lambda p: p.name,
            reverse=True,
        )
    elif args.run_dirs:
        resolved: list[Path] = []
        for run_dir_arg in args.run_dirs:
            p = Path(run_dir_arg).resolve()
            # Tolerate being handed the transcripts/ subdir: if the basename is
            # "transcripts" and the parent contains a run artifact, use the
            # parent as the run dir.
            if p.name == "transcripts" and (
                (p.parent / "run_manifest.json").exists()
                or (p.parent / "transcript_run.json").exists()
                or (p.parent / "all_results.json").exists()
            ):
                logger.info(
                    "Path looks like a transcripts/ subdir — using parent run dir: %s",
                    p.parent,
                )
                p = p.parent
            resolved.append(p)
        run_dirs = resolved
    else:
        # Default: most recent run
        candidates = sorted(
            (REPO_ROOT / "results").glob("run_*"),
            key=lambda p: p.name,
            reverse=True,
        )
        run_dirs = candidates[:1]

    if not run_dirs:
        logger.error("No run_* directories found")
        return 2

    plan_scenarios: list[dict[str, Any]] = []
    plan_pairs: list[dict[str, Any]] = []
    for run_dir in run_dirs:
        pairs = transcripts_for_run(run_dir)
        if args.filter:
            pairs = [
                p
                for p in pairs
                if args.filter.lower() in p["transcript_path"].name.lower()
            ]
        if args.limit:
            pairs = pairs[: args.limit]
        plan_pairs.extend(pairs)
        for pair in pairs:
            scenario = load_scenario(pair["scenario_id"])
            plan_scenarios.append(enrich_scenario_with_inferred_tags(scenario))

    plan_llm_enabled = bool(
        args.enable_llm if args.dry_run else args.enable_llm and api_client is not None
    )
    scan_plan_dict = build_scan_plan(
        plan_scenarios,
        engine.modes,
        engine.routing,
        profile,
        judge_model=args.llm_model,
        llm_enabled=plan_llm_enabled,
    )
    scan_plan_dict = attach_scan_provenance(
        scan_plan_dict,
        run_dirs=run_dirs,
        transcript_pairs=plan_pairs,
        selection={
            "filter": args.filter,
            "limit_per_source_run": args.limit,
            "source_run_count": len(run_dirs),
        },
    )
    scan_plan_dict["api_client_available"] = api_client is not None

    if args.dry_run:
        output_dir = Path(args.output_root) / f"plan_{time.strftime('%Y%m%d_%H%M%S')}"
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(output_dir / "scan_plan.json", "w", encoding="utf-8") as f:
            json.dump(scan_plan_dict, f, indent=2)
        with open(output_dir / "cost_report.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "profile": scan_plan_dict["profile"],
                    "llm_enabled": scan_plan_dict["llm_enabled"],
                    "judge_model": scan_plan_dict["judge_model"],
                    "planned_llm_calls": scan_plan_dict["planned_llm_calls"],
                    "base_llm_calls": scan_plan_dict["base_llm_calls"],
                    "conditional_llm_calls": scan_plan_dict["conditional_llm_calls"],
                    "budget_llm_calls": scan_plan_dict["budget_llm_calls"],
                    "estimated_base_cost_usd": scan_plan_dict[
                        "estimated_base_cost_usd"
                    ],
                    "estimated_budget_cost_usd": scan_plan_dict[
                        "estimated_budget_cost_usd"
                    ],
                    "estimated_cost_usd": scan_plan_dict["estimated_cost_usd"],
                    "maximum_reasonable_cost_ceiling_usd": scan_plan_dict[
                        "maximum_reasonable_cost_ceiling_usd"
                    ],
                    "pricing_known": scan_plan_dict["pricing_known"],
                    "cost_assumptions": scan_plan_dict["cost_assumptions"],
                },
                f,
                indent=2,
            )
        estimated_base = (
            "unknown"
            if scan_plan_dict["estimated_base_cost_usd"] is None
            else f"${scan_plan_dict['estimated_base_cost_usd']:.4f}"
        )
        estimated_budget = (
            "unknown"
            if scan_plan_dict["estimated_budget_cost_usd"] is None
            else f"${scan_plan_dict['estimated_budget_cost_usd']:.4f}"
        )
        print(f"Scan dry run: {output_dir}")
        print(f"Profile: {scan_plan_dict['profile']}")
        print(f"Transcripts: {scan_plan_dict['transcript_count']}")
        print(f"Eligible checks: {scan_plan_dict['eligible_checks']}")
        print(f"Base verifier LLM calls: {scan_plan_dict['base_llm_calls']}")
        print(
            "Conditional regex-edge LLM calls: "
            f"{scan_plan_dict['conditional_llm_calls']}"
        )
        print(f"Budgeted verifier LLM calls: {scan_plan_dict['budget_llm_calls']}")
        print(f"Estimated base verifier cost: {estimated_base}")
        print(f"Conservative verifier budget: {estimated_budget}")
        if scan_plan_dict["maximum_reasonable_cost_ceiling_usd"] is not None:
            print(
                "Maximum accepted runtime ceiling: "
                f"${scan_plan_dict['maximum_reasonable_cost_ceiling_usd']:.4f}"
            )
        return 0

    if args.enable_llm:
        budget = scan_plan_dict["estimated_budget_cost_usd"]
        if args.max_cost_usd is None:
            logger.error(
                "Refusing live LLM scan without --max-cost-usd. "
                "Run --dry-run first, then approve an explicit ceiling."
            )
            return 2
        if args.max_cost_usd < 0:
            logger.error("--max-cost-usd must be non-negative")
            return 2
        if budget is None:
            logger.error("Refusing live LLM scan because verifier pricing is unknown")
            return 2
        if budget > args.max_cost_usd:
            logger.error(
                "Refusing live LLM scan: conservative budget $%.4f exceeds "
                "--max-cost-usd $%.4f",
                budget,
                args.max_cost_usd,
            )
            return 2
        maximum_ceiling = maximum_reasonable_cost_ceiling(budget)
        if args.max_cost_usd > maximum_ceiling:
            logger.error(
                "Refusing live LLM scan: --max-cost-usd $%.4f is not a meaningful "
                "guardrail for the $%.4f conservative plan; use at most $%.4f",
                args.max_cost_usd,
                budget,
                maximum_ceiling,
            )
            return 2
        logger.info(
            "Cost gate passed: conservative budget $%.4f <= ceiling $%.4f",
            budget,
            args.max_cost_usd,
        )

    signature = _scan_signature(args, run_dirs)
    if args.resume is not None:
        output_dir = args.resume.resolve()
        state_path = output_dir / CHECKPOINT_FILENAME
        if not state_path.exists():
            logger.error("Resume checkpoint not found: %s", state_path)
            return 2
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Could not read resume checkpoint %s: %s", state_path, exc)
            return 2
        if state.get("schema") != CHECKPOINT_SCHEMA:
            logger.error("Unsupported resume checkpoint schema: %r", state.get("schema"))
            return 2
        if state.get("status") == "complete":
            logger.error("Scan is already complete: %s", output_dir)
            return 2
        if state.get("signature") != signature:
            logger.error("Resume options or source run dirs do not match the checkpoint")
            return 2
        previous_cost = dict(state.get("cost") or {})
        try:
            all_outputs, all_engine_outputs = _load_partial(
                output_dir / PARTIAL_FILENAME
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            logger.error("Could not read resume rows: %s", exc)
            return 2
        logger.info("Resuming %s with %d completed rows", output_dir, len(all_outputs))
    else:
        output_dir = _create_output_dir(Path(args.output_root))
        previous_cost = {"total": 0.0, "calls": 0, "by_model": {}}
        all_outputs = []
        all_engine_outputs = []
        state = {
            "schema": CHECKPOINT_SCHEMA,
            "status": "running",
            "signature": signature,
            "completed_rows": 0,
            "cost": previous_cost,
        }
        _atomic_write_json(output_dir / CHECKPOINT_FILENAME, state)

    remaining_ceiling = args.max_cost_usd
    if remaining_ceiling is not None:
        remaining_ceiling -= float(previous_cost.get("total") or 0.0)
        if remaining_ceiling < 0:
            logger.error(
                "Recorded checkpoint cost exceeds --max-cost-usd; increase the explicit ceiling"
            )
            return 2
    cost_tracker.reset(max_cost_usd=remaining_ceiling)
    checkpoint_path = output_dir / PARTIAL_FILENAME
    completed_keys = {
        (str(record["model_id"]), str(record["scenario_id"])) for record in all_outputs
    }

    def checkpoint(record: dict[str, Any], _output: ModeEngineOutput) -> None:
        key = (str(record["model_id"]), str(record["scenario_id"]))
        if key in completed_keys:
            raise ValueError(f"duplicate scan row for {key[0]} / {key[1]}")
        with checkpoint_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=str, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        completed_keys.add(key)
        state.update(
            status="running",
            completed_rows=len(completed_keys),
            cost=_combined_cost_snapshot(
                previous_cost, cost_tracker.snapshot(), args.max_cost_usd
            ),
        )
        _atomic_write_json(output_dir / CHECKPOINT_FILENAME, state)

    try:
        for run_dir in run_dirs:
            outputs, engine_outputs = scan_run(
                run_dir,
                engine,
                limit=args.limit,
                filename_filter=args.filter,
                parallel=getattr(args, "parallel", False),
                max_workers=getattr(args, "max_workers", 8),
                transcript_workers=max(args.transcript_workers, 1),
                skip_keys=completed_keys,
                progress_callback=checkpoint,
            )
            all_outputs.extend(outputs)
            all_engine_outputs.extend(engine_outputs)
    except CostBudgetExceededError as exc:
        snapshot = _combined_cost_snapshot(
            previous_cost, cost_tracker.snapshot(), args.max_cost_usd
        )
        state.update(status="cost_ceiling", completed_rows=len(completed_keys), cost=snapshot)
        _atomic_write_json(output_dir / CHECKPOINT_FILENAME, state)
        logger.error(
            "Scan stopped at runtime cost ceiling: %s. Recorded cost: $%.4f. "
            "Resume from %s with the same options and an adequate explicit ceiling.",
            exc,
            snapshot["total"],
            output_dir,
        )
        return 4
    except Exception:
        snapshot = _combined_cost_snapshot(
            previous_cost, cost_tracker.snapshot(), args.max_cost_usd
        )
        state.update(status="failed", completed_rows=len(completed_keys), cost=snapshot)
        _atomic_write_json(output_dir / CHECKPOINT_FILENAME, state)
        raise

    if not all_outputs:
        state.update(status="failed", completed_rows=0)
        _atomic_write_json(output_dir / CHECKPOINT_FILENAME, state)
        logger.error("No transcripts scanned")
        return 3

    paired_outputs = sorted(
        zip(all_outputs, all_engine_outputs, strict=True),
        key=lambda pair: (str(pair[0]["model_id"]), str(pair[0]["scenario_id"])),
    )
    all_outputs = [record for record, _output in paired_outputs]
    all_engine_outputs = [output for _record, output in paired_outputs]
    final_cost = _combined_cost_snapshot(
        previous_cost, cost_tracker.snapshot(), args.max_cost_usd
    )
    write_outputs(
        output_dir,
        all_outputs,
        all_engine_outputs,
        run_dirs,
        scan_plan_dict,
        cost_snapshot=final_cost,
    )
    state.update(status="complete", completed_rows=len(all_outputs), cost=final_cost)
    _atomic_write_json(output_dir / CHECKPOINT_FILENAME, state)
    checkpoint_path.unlink(missing_ok=True)

    print(f"\nScan complete: {output_dir}")
    print(f"See {output_dir}/summary.md for top-line blindspot rates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
