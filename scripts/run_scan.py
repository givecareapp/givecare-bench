#!/usr/bin/env python3
"""Plan or run the full-conversation LLM judge over saved transcripts."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

DEFAULT_SCAN_OUTPUT_ROOT = REPO_ROOT / "results" / "safety_care_scan"
CHECKPOINT_SCHEMA = "invisiblebench-scan-checkpoint/v2"
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
    attach_scan_provenance,
    build_scan_plan,
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
        mode_results=record["mode_results"], engine_version=record["engine_version"],
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_dirs", nargs="+", type=Path)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--filter")
    ap.add_argument("--output-root", type=Path, default=DEFAULT_SCAN_OUTPUT_ROOT)
    ap.add_argument("--resume", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--plan", type=Path, help="Required for a live scan: scan_plan.json from a dry run.")
    ap.add_argument("--max-cost-usd", type=float)
    ap.add_argument("--llm-model", default=DEFAULT_JUDGE_MODEL)
    args = ap.parse_args()
    if args.limit is not None and args.limit < 1:
        ap.error("--limit must be positive")
    run_dirs = [path.resolve() for path in args.run_dirs]
    engine = ModeEngine(llm_model=args.llm_model)
    plan_pairs = []
    try:
        for run_dir in run_dirs:
            pairs = transcripts_for_run(run_dir)
            if args.filter:
                pairs = [p for p in pairs if args.filter.lower() in p["transcript_path"].name.lower()]
            if args.limit is not None:
                pairs = pairs[:args.limit]
            plan_pairs.extend(pairs)
        keys = [(p["model_id"], p["scenario_id"]) for p in plan_pairs]
        if not keys or len(keys) != len(set(keys)):
            raise ValueError("No transcripts selected, or duplicate model/scenario pairs")
        scan_plan_dict = attach_scan_provenance(
            build_scan_plan(plan_pairs, engine.modes, judge_model=args.llm_model),
            run_dirs=run_dirs, transcript_pairs=plan_pairs,
            selection={"filter": args.filter, "limit_per_source_run": args.limit,
                       "source_run_count": len(run_dirs)},
        )
    except (OSError, ValueError, KeyError) as exc:
        logger.error("Cannot plan scan: %s", exc)
        return 2

    if args.dry_run:
        output_dir = _create_output_dir(args.output_root)
        _atomic_write_json(output_dir / "scan_plan.json", scan_plan_dict)
        print(f"Scan plan: {output_dir / 'scan_plan.json'}")
        print(f"Transcripts: {len(plan_pairs)}")
        print(f"Judge calls: {scan_plan_dict['planned_llm_calls']}")
        print(f"Estimated cost envelope: {scan_plan_dict['estimated_cost_usd']} USD")
        print(f"Current publication provenance: {scan_plan_dict['provenance_complete']}")
        return 0

    if args.plan is None:
        logger.error("Run --dry-run first; pass its scan_plan.json with --plan.")
        return 2
    try:
        saved_plan = json.loads(args.plan.read_text())
    except (OSError, ValueError) as exc:
        logger.error("Cannot read dry-run plan: %s", exc)
        return 2
    if saved_plan != json.loads(json.dumps(scan_plan_dict)):
        logger.error("Dry-run plan differs from current inputs. Run --dry-run again.")
        return 2
    budget = scan_plan_dict["estimated_cost_usd"]
    if args.max_cost_usd is None or not math.isfinite(args.max_cost_usd) or args.max_cost_usd <= 0:
        logger.error("A live scan requires a finite, positive --max-cost-usd.")
        return 2
    if budget is None or budget > args.max_cost_usd:
        logger.error("Unknown pricing or estimated cost exceeds --max-cost-usd.")
        return 2
    if args.max_cost_usd > maximum_reasonable_cost_ceiling(budget):
        logger.error("The cost ceiling exceeds the plan's accepted maximum: %s",
                     maximum_reasonable_cost_ceiling(budget))
        return 2
    try:
        engine = ModeEngine(llm_api_client=ModelAPIClient(), llm_model=args.llm_model)
    except (ImportError, ValueError) as exc:
        logger.error("Cannot initialize judge: %s", exc)
        return 2
    signature = {
        "run_dirs": [str(path) for path in run_dirs],
        "plan_sha256": hashlib.sha256(json.dumps(scan_plan_dict, sort_keys=True).encode()).hexdigest(),
    }
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

    if len(all_outputs) != len(plan_pairs):
        state.update(status="failed", completed_rows=0)
        _atomic_write_json(output_dir / CHECKPOINT_FILENAME, state)
        logger.error("Scan does not contain every planned transcript")
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
    print(f"See {output_dir}/summary.md for decision counts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
