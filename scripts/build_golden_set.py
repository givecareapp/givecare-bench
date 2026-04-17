#!/usr/bin/env python3
"""Build the stratified golden-set candidate pool from the verifier corpus manifest.

Reads:  internal/evals/verifier/corpus_manifest.jsonl
Writes: internal/evals/verifier/golden_set/candidates.jsonl

Follows internal/evals/verifier/golden_set/sampling_plan.md.
"""

from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SEED = 20260417
TARGET_PER_MODEL_MIN = 2
TARGET_PER_MODEL_MAX = 7

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "internal/evals/verifier/corpus_manifest.jsonl"
OUT = ROOT / "internal/evals/verifier/golden_set/candidates.jsonl"
META_JUDGE_TRACES_DIR = ROOT / "internal/evals/meta_judge/traces"

BUCKET_RULES: dict[str, list[tuple[str, int, str]]] = {
    "contested_false_scope": [
        ("tier1_scope_honesty_001", 3, "mixed"),
        ("context_regulatory_data_privacy_001", 3, "mixed"),
        ("context_regulatory_misrepresentation_001", 3, "mixed"),
        ("tier1_attachment_002", 3, "mixed"),
        ("tier2_attachment_001", 3, "mixed"),
    ],
    "clinical_boundary": [
        ("context_regulatory_therapy_function_001", 5, "mixed"),
        ("tier1_false_refusal_med_001", 5, "mixed"),
        ("tier1_boundaries_therapy_001", 3, "mixed"),
        ("tier2_regulatory_001_minor_disclosure", 2, "mixed"),
    ],
    "crisis": [
        ("tier1_crisis_indirect_bridge_001", 8, "mixed"),
        ("tier1_crisis_cssrs_passive_001", 3, "mixed"),
        ("tier1_crisis_cssrs_passive_sms_001", 2, "mixed"),
        ("tier1_crisis_dual_concern_001", 2, "mixed"),
    ],
}

CLEAN_POOL_SCENARIOS = {
    "tier1_gray_cultural_001",
    "tier2_cultural_004",
    "tier1_gray_humor_001",
    "tier1_gray_venting_001",
    "tier1_gray_compassion_001",
    "tier2_grief_001",
    "tier2_sandwich_001",
    "tier2_burnout_male_spousal_001",
    "tier2_burnout_parent_chronic_001",
}
CLEAN_BUCKET_SIZE = 15
CLEAN_MAX_PER_SCENARIO = 2
CLEAN_MAX_PER_MODEL = 2

META_JUDGE_SCENARIOS_RESERVED: set[str] = set()


def _load_manifest() -> list[dict[str, Any]]:
    rows = []
    with open(MANIFEST) as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _load_meta_judge_reserved() -> set[tuple[str, str]]:
    reserved: set[tuple[str, str]] = set()
    if not META_JUDGE_TRACES_DIR.exists():
        return reserved
    return reserved


def _eligible(row: dict[str, Any]) -> bool:
    if row.get("transcript_path") is None:
        return False
    if not row.get("transcript_found"):
        return False
    reasons = row.get("hard_fail_reasons") or []
    for reason in reasons:
        if isinstance(reason, str) and reason.startswith("error"):
            return False
    status = row.get("status")
    if status == "error":
        return False
    return True


def _trace_id(row: dict[str, Any]) -> str:
    model_id = row["model_id"].replace("/", "_")
    return f"{model_id}__{row['scenario_id']}"


def _pick_mixed(rng: random.Random, rows: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
    """Prefer a mix of hard_fail=True and hard_fail=False when available."""
    pos = [r for r in rows if r.get("hard_fail")]
    neg = [r for r in rows if not r.get("hard_fail")]
    rng.shuffle(pos)
    rng.shuffle(neg)

    want_pos = (n * 2) // 3
    want_neg = n - want_pos

    chosen: list[dict[str, Any]] = []
    chosen.extend(pos[:want_pos])
    chosen.extend(neg[:want_neg])

    deficit = n - len(chosen)
    if deficit > 0:
        remaining = [r for r in pos[want_pos:] + neg[want_neg:] if r not in chosen]
        rng.shuffle(remaining)
        chosen.extend(remaining[:deficit])

    return chosen[:n]


def _bucket_family_map(bucket_name: str) -> dict[str, str]:
    return {
        scenario_id: bucket_name
        for (scenario_id, _n, _mode) in BUCKET_RULES.get(bucket_name, [])
    }


def build_candidates() -> list[dict[str, Any]]:
    rng = random.Random(SEED)
    manifest = _load_manifest()
    eligible = [r for r in manifest if _eligible(r)]

    by_scenario: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in eligible:
        by_scenario[r["scenario_id"]].append(r)

    picked: list[dict[str, Any]] = []
    model_count: Counter[str] = Counter()

    for bucket_name, rules in BUCKET_RULES.items():
        for scenario_id, n, _mode in rules:
            pool = by_scenario.get(scenario_id, [])
            if not pool:
                print(f"[warn] no manifest rows for {scenario_id}")
                continue
            chosen = _pick_mixed(rng, pool, n)
            for row in chosen:
                picked.append({"row": row, "bucket": bucket_name})
                model_count[row["model_id"]] += 1

    clean_pool = [
        r for r in eligible
        if r["scenario_id"] in CLEAN_POOL_SCENARIOS
        and not r.get("hard_fail")
        and (r.get("overall_score") or 0.0) >= 0.8
    ]
    rng.shuffle(clean_pool)
    per_scenario_cap: Counter[str] = Counter()
    per_model_cap_clean: Counter[str] = Counter()
    clean_chosen: list[dict[str, Any]] = []
    for row in clean_pool:
        if len(clean_chosen) >= CLEAN_BUCKET_SIZE:
            break
        if per_scenario_cap[row["scenario_id"]] >= CLEAN_MAX_PER_SCENARIO:
            continue
        if per_model_cap_clean[row["model_id"]] >= CLEAN_MAX_PER_MODEL:
            continue
        clean_chosen.append(row)
        per_scenario_cap[row["scenario_id"]] += 1
        per_model_cap_clean[row["model_id"]] += 1
        model_count[row["model_id"]] += 1

    for row in clean_chosen:
        picked.append({"row": row, "bucket": "clean_pass"})

    missing_models = [
        m for m in {r["model_id"] for r in eligible}
        if model_count[m] < TARGET_PER_MODEL_MIN
    ]
    if missing_models:
        print(f"[info] models under min spread ({TARGET_PER_MODEL_MIN}): {missing_models}")
    hot_models = [m for m, c in model_count.items() if c > TARGET_PER_MODEL_MAX]
    if hot_models:
        print(f"[info] models over max spread ({TARGET_PER_MODEL_MAX}): {hot_models}")

    out_rows: list[dict[str, Any]] = []
    for entry in picked:
        row = entry["row"]
        out_rows.append({
            "trace_id": _trace_id(row),
            "bucket": entry["bucket"],
            "scenario_id": row["scenario_id"],
            "scenario_family": row["scenario_id"],
            "model": row["model"],
            "model_id": row["model_id"],
            "transcript_path": row["transcript_path"],
            "current_scorer": {
                "overall_score": row.get("overall_score"),
                "hard_fail": bool(row.get("hard_fail")),
                "hard_fail_reasons": row.get("hard_fail_reasons") or [],
                "judge_model": row.get("judge_model"),
            },
        })
    return out_rows


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = build_candidates()
    with open(OUT, "w") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")

    by_bucket = Counter(r["bucket"] for r in rows)
    by_model = Counter(r["model_id"] for r in rows)
    by_scenario = Counter(r["scenario_id"] for r in rows)
    print(f"wrote {len(rows)} candidates to {OUT.relative_to(ROOT)}")
    print(f"  by bucket: {dict(by_bucket)}")
    print(f"  distinct models: {len(by_model)} (min={min(by_model.values())}, max={max(by_model.values())})")
    print(f"  distinct scenarios: {len(by_scenario)}")


if __name__ == "__main__":
    main()
