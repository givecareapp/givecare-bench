#!/usr/bin/env python3
"""Run v3 mode_engine over existing transcripts — deterministic-only.

First runnable v3 benchmark. LLM-dependent modes return UNCLEAR/NOT_APPLICABLE
since no api_client is wired in for this scan (by design, for a clean
deterministic baseline). Regex/lexicon/corpus verifiers produce actionable
signal on the existing transcript corpus.

Output per run:
  - `results/v3_scan/<timestamp>/per_run.jsonl` — one line per (model, scenario)
  - `results/v3_scan/<timestamp>/blindspot_rates.json` — corpus-level rates
  - `results/v3_scan/<timestamp>/summary.md` — human-readable summary

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
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from invisiblebench.api import ModelAPIClient  # noqa: E402
from invisiblebench.evaluation.mode_engine import (  # noqa: E402
    ModeEngine,
    ModeEngineOutput,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("v3_scan")

from invisiblebench.judge import (  # noqa: E402
    apply_scan_profile,
    build_scan_plan,
    enrich_scenario_with_inferred_tags,
    load_scan_profile,
    load_scenario,
    scan_run,
    transcripts_for_run,
    write_outputs,
)


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
        default=str(REPO_ROOT / "results" / "v3_scan"),
        help="Where to write scan outputs",
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
        "--llm-model",
        default="google/gemini-2.5-flash-lite",
        help="Judge model for LLM verifiers (default: Gemini flash-lite).",
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
            logger.error("LLM modes will short-circuit to UNCLEAR / NOT_APPLICABLE.")

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
        run_dirs = [Path(run_dir).resolve() for run_dir in args.run_dirs]
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
        for pair in pairs:
            scenario = load_scenario(pair["scenario_id"])
            plan_scenarios.append(enrich_scenario_with_inferred_tags(scenario))

    scan_plan_dict = build_scan_plan(
        plan_scenarios,
        engine.modes,
        engine.routing,
        profile,
        judge_model=args.llm_model,
        llm_enabled=bool(args.enable_llm and api_client is not None),
    )

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
                    "estimated_cost_usd": scan_plan_dict["estimated_cost_usd"],
                    "pricing_known": scan_plan_dict["pricing_known"],
                },
                f,
                indent=2,
            )
        estimated = (
            "unknown"
            if scan_plan_dict["estimated_cost_usd"] is None
            else f"${scan_plan_dict['estimated_cost_usd']:.4f}"
        )
        print(f"Scan dry run: {output_dir}")
        print(f"Profile: {scan_plan_dict['profile']}")
        print(f"Transcripts: {scan_plan_dict['transcript_count']}")
        print(f"Eligible checks: {scan_plan_dict['eligible_checks']}")
        print(f"Planned verifier LLM calls: {scan_plan_dict['planned_llm_calls']}")
        print(f"Estimated verifier cost: {estimated}")
        return 0

    all_outputs: list[dict[str, Any]] = []
    all_engine_outputs: list[ModeEngineOutput] = []

    for run_dir in run_dirs:
        outputs, engine_outputs = scan_run(
            run_dir,
            engine,
            limit=args.limit,
            filename_filter=args.filter,
            parallel=getattr(args, "parallel", False),
            max_workers=getattr(args, "max_workers", 8),
            transcript_workers=max(args.transcript_workers, 1),
        )
        all_outputs.extend(outputs)
        all_engine_outputs.extend(engine_outputs)

    if not all_outputs:
        logger.error("No transcripts scanned")
        return 3

    output_dir = Path(args.output_root) / time.strftime("%Y%m%d_%H%M%S")
    write_outputs(output_dir, all_outputs, all_engine_outputs, run_dirs, scan_plan_dict)

    print(f"\nScan complete: {output_dir}")
    print(f"See {output_dir}/summary.md for top-line blindspot rates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
