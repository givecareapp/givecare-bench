#!/usr/bin/env python3
"""Audit the current regard scorer against the 35-trace holdout gold.

Parallel to scripts/audit_gold_regard.py but targets the independent holdout
set. Emits:

- internal/evals/verifier/quality_holdout/current_regard_vs_holdout.md
- internal/evals/verifier/quality_holdout/current_regard_vs_holdout.csv

Reuses helper functions from audit_gold_regard for metric computation so both
audits speak the same language.
"""

from __future__ import annotations

import argparse
import math
import time
from pathlib import Path
from typing import Any

from _audit_helpers import (
    load_candidates as _load_candidates_from,
)
from _audit_helpers import (
    load_gold_labels as _load_gold_labels_from,
)
from audit_gold_regard import (  # type: ignore[import-not-found]
    _build_rows,
    _overall_metrics,
    _subset_report_block,
    _write_csv,
)
from audit_gold_regard import _score_candidates as _score_candidates_gold

from invisiblebench.utils.benchmark_inventory import get_project_root

PROJECT_ROOT = get_project_root()
HOLDOUT_DIR = PROJECT_ROOT / "internal/evals/verifier/quality_holdout"
GOLD_LABELS_DIR = HOLDOUT_DIR / "labels/gold"
CANDIDATES_PATH = HOLDOUT_DIR / "candidates.jsonl"
DEFAULT_MD_OUT = HOLDOUT_DIR / "current_regard_vs_holdout.md"
DEFAULT_CSV_OUT = HOLDOUT_DIR / "current_regard_vs_holdout.csv"


def _load_candidates() -> list[dict[str, Any]]:
    return _load_candidates_from(CANDIDATES_PATH)


def _load_gold_labels() -> dict[str, dict[str, Any]]:
    return _load_gold_labels_from(GOLD_LABELS_DIR)


def _render_report(rows: list[dict[str, Any]], mode: str, elapsed: float) -> str:
    overall = _overall_metrics(rows)
    hard_fail_rows = [row for row in rows if row["gold_public_hard_fail"]]
    pass_only_rows = [row for row in rows if not row["gold_public_hard_fail"]]

    lines = [
        "# Current regard scorer vs holdout",
        "",
        f"- mode: `{mode}`",
        f"- scorer command: `uv run python scripts/audit_holdout_regard.py --mode {mode}`",
        f"- traces: `{overall['n']}`",
        f"- public hard fails in gold: `{len(hard_fail_rows)}` / pass-only: `{len(pass_only_rows)}`",
        f"- runtime: `{elapsed:.1f}s`",
        f"- judge model(s): `{', '.join(m for m in overall['judge_models'] if m) or 'n/a'}`",
        f"- judge hash(es): `{', '.join(h for h in overall['judge_hashes'] if h) or 'n/a'}`",
        "",
    ]

    lines.extend(_subset_report_block("Full-set summary", rows))

    if pass_only_rows:
        lines.extend(["", *(_subset_report_block("Pass-only summary", pass_only_rows))])

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This is the independent holdout audit — 35 traces that were NOT used to tune "
            "the regard scorer. The pass-only slice (`24` traces) is the primary "
            "ranking-signal check. The hard-fail slice (`11` traces) doubles as a "
            "public-layer regression probe; a meaningful regard change must not "
            "degrade the public verdict on these.",
            "",
            "See `quality_layer_promotion_gate.md` for the G3 (non-degenerate "
            "labels) and G4 (non-negative pass-only Pearson r) clauses that consume "
            "these metrics.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit the current regard scorer against the 35-trace holdout gold"
    )
    parser.add_argument("--mode", choices=["llm", "deterministic"], default="llm")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_MD_OUT)
    parser.add_argument("--out-csv", type=Path, default=DEFAULT_CSV_OUT)
    args = parser.parse_args()

    candidates = _load_candidates()
    if args.limit is not None:
        candidates = candidates[: args.limit]
    gold_labels = _load_gold_labels()

    # Sanity: every candidate must have a gold file.
    missing_gold = [c["trace_id"] for c in candidates if c["trace_id"] not in gold_labels]
    if missing_gold:
        raise RuntimeError(
            f"{len(missing_gold)} candidates have no holdout gold label. "
            f"Run scripts/build_holdout_gold.py first. Missing: {missing_gold[:3]}..."
        )

    started = time.time()
    predictions = _score_candidates_gold(candidates, args.mode)
    elapsed = time.time() - started

    rows = _build_rows(candidates, gold_labels, predictions)
    report = _render_report(rows, args.mode, elapsed)

    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.write_text(report)
    _write_csv(rows, args.out_csv)

    overall = _overall_metrics(rows)
    pass_only_rows = [row for row in rows if not row["gold_public_hard_fail"]]
    pass_only = _overall_metrics(pass_only_rows) if pass_only_rows else None

    print(f"wrote {args.out_md.relative_to(PROJECT_ROOT)}")
    print(f"wrote {args.out_csv.relative_to(PROJECT_ROOT)}")
    print(
        "summary:",
        {
            "trace_exact": f"{overall['trace_exact']}/{overall['n']}",
            "trace_three_or_more": f"{overall['trace_three_or_more']}/{overall['n']}",
            "base_mae": round(overall["base_mae"], 3),
            "base_pearson": (
                None if math.isnan(overall["base_pearson"]) else round(overall["base_pearson"], 3)
            ),
            "pass_only_trace_exact": (
                None if pass_only is None else f"{pass_only['trace_exact']}/{pass_only['n']}"
            ),
            "pass_only_base_pearson": (
                None
                if pass_only is None or math.isnan(pass_only["base_pearson"])
                else round(pass_only["base_pearson"], 3)
            ),
        },
    )


if __name__ == "__main__":
    main()
