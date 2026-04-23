#!/usr/bin/env python3
"""Reconcile leaderboard.json quality_layer metadata with actual scorer state.

Phase A (interim honest text) — updates the note fields so the public
metadata no longer overclaims "Regard v2 deployed" when in fact the Regard v2
prototype was reverted on 2026-04-17 and the current scorer saturates to pass
on every regard axis on the gold audit.

Phase B (post-gate) is handled separately once the promotion gate clears.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LEADERBOARD = PROJECT_ROOT / "data/leaderboard/leaderboard.json"

PHASE_A_NOTE = (
    "Regard scorer currently saturates to 'pass' across all four axes on the "
    "60-trace gold audit (fail=0, mixed=0, pass=60 on every axis). The prior "
    "Regard v2 prototype was reverted on 2026-04-17 for over-correction and is "
    "not running in production. Holdout gold (35 traces) is now merged at "
    "internal/evals/verifier/quality_holdout/labels/gold/; holdout audit is "
    "the next validation step. See "
    "internal/evals/verifier/quality_layer_promotion_gate.md for the gate "
    "criteria the scorer must clear before promotion."
)
PHASE_A_HOLDOUT_NOTE = (
    "35-trace holdout gold merged 2026-04-22 (27 A+B-agreed + 8 adjudicated, "
    "11 public hard fails, 24 pass). Scorer-vs-holdout audits not yet run. "
    "See internal/evals/verifier/quality_holdout/gold_resolution_summary.md."
)


def _infer_results_benchmark_version(data: dict) -> str | None:
    versions = {
        str(row.get("benchmark_version"))
        for row in data.get("overall_leaderboard", [])
        if row.get("benchmark_version")
    }
    if not versions:
        return None
    if len(versions) == 1:
        return next(iter(versions))
    raise ValueError(f"Mixed benchmark versions in leaderboard rows: {sorted(versions)}")


def main() -> None:
    data = json.loads(LEADERBOARD.read_text())
    metadata = data["metadata"]
    ql = metadata["methodology"]["validation"]["quality_layer"]

    metadata["benchmark_updated_at"] = datetime.now(timezone.utc).isoformat()
    metadata["results_benchmark_version"] = _infer_results_benchmark_version(data)

    ql["note"] = PHASE_A_NOTE

    regard = ql["components"]["regard"]
    regard["status"] = "calibrated-diagnostic"
    regard["note"] = (
        "Runtime scorer saturates to pass on all four regard axes in the "
        "60-trace gold audit. Regard v2 prototype reverted 2026-04-17. Next "
        "step: audit against 35-trace holdout gold (merged 2026-04-22)."
    )

    holdout = ql.get("holdout", {})
    holdout["status"] = "labels_merged_audit_pending"
    holdout["traces"] = 35
    holdout["public_hard_fails"] = 11
    holdout["public_pass"] = 24
    holdout["conflict_resolution"] = "2026-04-20"
    holdout["gold_merged"] = "2026-04-22"
    holdout["note"] = PHASE_A_HOLDOUT_NOTE
    # Drop stale claims.
    holdout.pop("confirmed_fn_rate", None)
    holdout.pop("iaa_confirmed", None)
    ql["holdout"] = holdout

    ql["promotion_gate"] = {
        "doc": "internal/evals/verifier/quality_layer_promotion_gate.md",
        "status": "pre_registered_2026-04-22",
    }

    LEADERBOARD.write_text(json.dumps(data, indent=2) + "\n")
    print(f"updated {LEADERBOARD}")


if __name__ == "__main__":
    main()
