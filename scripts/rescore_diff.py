#!/usr/bin/env python3
"""Behavior-freeze gate: re-judge a frozen scan and diff verdicts.

Re-evaluates every transcript referenced by a frozen per_run.jsonl using the
deterministic (smoke-profile) engine and compares against the stored results:

- deterministic checks (regex / scenario_rule scorers): verdict + eligibility
  must match exactly;
- LLM-judged checks: eligibility (routing + scope decisions) must match;
  verdicts are not reproducible without --enable-llm and are skipped.

Exit 0 when the diff is empty, 1 on any divergence, 2 on usage errors.
This is the definition-of-done check for refactor commits (see DESIGN.md).

Usage:
    uv run python scripts/rescore_diff.py
    uv run python scripts/rescore_diff.py --frozen results/v3_scan/merged_phase2/per_run.jsonl --limit 50
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from run_scan import (  # noqa: E402
    apply_scan_profile,
    enrich_scenario_with_inferred_tags,
    load_scan_profile,
    load_scenario,
    load_transcript,
)

from invisiblebench.evaluation.mode_engine import ModeEngine  # noqa: E402

DETERMINISTIC_SCORERS = {"regex", "scenario_rule", "corpus", "lexicon"}

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("rescore_diff")


def build_engine() -> ModeEngine:
    profile = load_scan_profile("smoke")
    engine = ModeEngine(llm_api_client=None)
    engine.modes, engine.routing = apply_scan_profile(engine.modes, engine.routing, profile)
    return engine


def compare_row(
    stored: dict[str, Any],
    rescored: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    diffs: list[dict[str, Any]] = []
    new_by_mode = {m["mode_id"]: m for m in rescored}

    for old in stored["mode_results"]:
        mode_id = old["mode_id"]
        old_scorer = old.get("scorer_type", "")
        new = new_by_mode.get(mode_id)

        if old_scorer in DETERMINISTIC_SCORERS:
            if new is None:
                diffs.append({"mode_id": mode_id, "field": "presence", "old": "present", "new": "missing"})
                continue
            for field in ("eligible", "verdict"):
                if old.get(field) != new.get(field):
                    diffs.append(
                        {"mode_id": mode_id, "field": field, "old": old.get(field), "new": new.get(field)}
                    )
        elif new is not None and old.get("eligible") != new.get("eligible"):
            # LLM-judged: verdicts not reproducible offline, but routing/scope
            # eligibility decisions must not drift.
            diffs.append(
                {"mode_id": mode_id, "field": "eligible", "old": old.get("eligible"), "new": new.get("eligible")}
            )
    return diffs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--frozen",
        default=str(REPO_ROOT / "results" / "v3_scan" / "merged_phase2" / "per_run.jsonl"),
        help="Frozen scan JSONL to diff against",
    )
    ap.add_argument("--limit", type=int, default=None, help="Only check the first N rows")
    ap.add_argument("--verbose", action="store_true", help="Print every diff, not a summary")
    args = ap.parse_args()

    frozen_path = Path(args.frozen)
    if not frozen_path.exists():
        print(f"error: frozen scan not found: {frozen_path}", file=sys.stderr)
        return 2

    with open(frozen_path, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    if args.limit:
        rows = rows[: args.limit]

    engine = build_engine()
    scenario_cache: dict[str, dict[str, Any]] = {}

    total_pairs = 0
    diff_rows = 0
    skipped = 0
    all_diffs: list[tuple[str, str, dict[str, Any]]] = []

    for row in rows:
        tpath = Path(row["transcript_path"])
        if not tpath.exists():
            skipped += 1
            continue
        transcript = load_transcript(tpath)
        if not transcript:
            skipped += 1
            continue

        sid = row["scenario_id"]
        if sid not in scenario_cache:
            scenario_cache[sid] = enrich_scenario_with_inferred_tags(load_scenario(sid))
        scenario = scenario_cache[sid]

        out = engine.evaluate(transcript=transcript, scenario=scenario)
        rescored = out.mode_results

        diffs = compare_row(row, rescored)
        total_pairs += len(row["mode_results"])
        if diffs:
            diff_rows += 1
            for d in diffs:
                all_diffs.append((row["model"], sid, d))

    print(f"rows checked:      {len(rows) - skipped} (skipped {skipped})")
    print(f"verdict pairs:     {total_pairs}")
    print(f"rows with diffs:   {diff_rows}")
    print(f"total diffs:       {len(all_diffs)}")

    if all_diffs:
        shown = all_diffs if args.verbose else all_diffs[:20]
        for model, sid, d in shown:
            print(f"  DIFF {model} / {sid} / {d['mode_id']} [{d['field']}]: {d['old']} -> {d['new']}")
        if not args.verbose and len(all_diffs) > 20:
            print(f"  ... and {len(all_diffs) - 20} more (--verbose to show)")
        return 1

    print("CLEAN: rescore matches frozen scan.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
