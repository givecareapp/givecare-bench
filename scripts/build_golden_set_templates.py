#!/usr/bin/env python3
"""Produce one empty label template per candidate in the golden set.

Reads:  internal/evals/verifier/golden_set/candidates.jsonl
Writes: internal/evals/verifier/golden_set/labels/template/<trace_id>.json

Each template has context prefilled (trace_id, scenario_id, model_id,
current_scorer verdict) and schema-required fields stubbed with sentinel
values so annotators can see the required shape without an IDE.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANDIDATES = ROOT / "internal/evals/verifier/golden_set/candidates.jsonl"
TEMPLATE_DIR = ROOT / "internal/evals/verifier/golden_set/labels/template"

TEMPLATE_SHAPE = {
    "verdict": {
        "safety_gate": "__FILL_pass_or_fail__",
        "compliance_gate": "__FILL_pass_or_fail__",
        "public_hard_fail": False,
        "hard_fail_rule": None,
    },
    "quality": {
        "recognition": "__FILL_pass_mixed_fail__",
        "agency": "__FILL_pass_mixed_fail__",
        "grounding": "__FILL_pass_mixed_fail__",
        "scaffolding": "__FILL_pass_mixed_fail__",
        "resources": "__FILL_pass_mixed_fail__",
        "navigation": "__FILL_pass_mixed_fail__",
        "barriers": "__FILL_pass_mixed_fail__",
        "engagement": "__FILL_pass_mixed_fail__",
    },
    "soft_issues": [],
    "evidence": [
        {
            "turn": 1,
            "quote": "__FILL_exact_assistant_text__",
            "supports": "__FILL_why_this_quote_supports_the_verdict__",
        }
    ],
    "agreement_with_current_scorer": "__FILL_agreement_enum__",
    "disagreement_labels": [],
    "confidence": "__FILL_high_medium_low__",
    "summary": {
        "rationale": "__FILL_one_to_two_sentences__",
        "notes": "",
    },
}


def _load_candidates() -> list[dict]:
    rows = []
    with open(CANDIDATES) as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main() -> None:
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    for row in _load_candidates():
        trace_id = row["trace_id"]
        template = {
            "scenario_id": row["scenario_id"],
            "model": row["model"],
            "model_id": row["model_id"],
            "_context": {
                "trace_id": trace_id,
                "bucket": row["bucket"],
                "transcript_path": row["transcript_path"],
                "current_scorer": row["current_scorer"],
                "instructions": (
                    "Read transcript_path + the scenario contract. "
                    "Replace every __FILL_* sentinel. Remove this _context "
                    "block before committing your label."
                ),
            },
            **TEMPLATE_SHAPE,
        }
        out_path = TEMPLATE_DIR / f"{trace_id}.json"
        with open(out_path, "w") as fh:
            json.dump(template, fh, indent=2)
    print(f"wrote {len(list(TEMPLATE_DIR.glob('*.json')))} templates to {TEMPLATE_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
