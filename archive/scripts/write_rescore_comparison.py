from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = PROJECT_ROOT / "archive" / "internal" / "evals" / "verifier" / "rescore_comparison_2026-03-31.md"
RUN_DIRS = [
    PROJECT_ROOT / "results" / "run_20260330_021307",
    PROJECT_ROOT / "results" / "partial_runs" / "run_20260330_033649_up_to_deepseek",
    PROJECT_ROOT / "results" / "run_20260330_130332",
]


def load_rows(path: Path) -> list[dict]:
    return json.loads(path.read_text())


def before_file_for_run(run_dir: Path) -> Path:
    for name in (
        "all_results.pre_compliance_rescore.json",
        "all_results.pre_rescore.json",
        "all_results.json",
    ):
        candidate = run_dir / name
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"No results file found for {run_dir}")


def extract_rules(row: dict) -> list[str]:
    rules: list[str] = []
    for reason in row.get("hard_fail_reasons", []) or []:
        if isinstance(reason, dict):
            rule = reason.get("rule")
        else:
            rule = str(reason).split(" at turn ")[0]
        if rule:
            rules.append(str(rule))
    return rules


def summary(rows: list[dict]) -> dict:
    hard_fail_rows = [row for row in rows if row.get("hard_fail")]
    compliance_fail_rows = [
        row for row in rows if not (row.get("gates", {}).get("compliance", {}) or {}).get("passed", True)
    ]
    false_scope_rows = [row for row in rows if "false_scope_or_capability_claim" in extract_rules(row)]
    false_scope_only_rows = [
        row for row in rows if extract_rules(row) and set(extract_rules(row)) == {"false_scope_or_capability_claim"}
    ]
    medical_true_positive_rows = [
        row
        for row in rows
        if set(extract_rules(row))
        & {"diagnosis", "prescribing", "treatment_directive", "treatment"}
    ]

    category_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    model_scores: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        category = row.get("category", "unknown")
        category_counts[category][0] += 1
        if row.get("success"):
            category_counts[category][1] += 1
        model_scores[row["model"]].append(float(row.get("overall_score", 0.0)))

    rank_table = sorted(
        ((model, sum(scores) / len(scores)) for model, scores in model_scores.items()),
        key=lambda item: item[1],
        reverse=True,
    )

    return {
        "row_count": len(rows),
        "hard_fail_count": len(hard_fail_rows),
        "compliance_fail_count": len(compliance_fail_rows),
        "false_scope_count": len(false_scope_rows),
        "false_scope_only_count": len(false_scope_only_rows),
        "medical_true_positive_count": len(medical_true_positive_rows),
        "category_pass_rates": {
            category: passed / total if total else 0.0
            for category, (total, passed) in category_counts.items()
        },
        "model_ranks": rank_table,
    }


def main() -> int:
    before_rows: list[dict] = []
    after_rows: list[dict] = []
    for run_dir in RUN_DIRS:
        before_rows.extend(load_rows(before_file_for_run(run_dir)))
        after_rows.extend(load_rows(run_dir / "all_results.json"))

    before = summary(before_rows)
    after = summary(after_rows)
    before_ranks = {model: idx + 1 for idx, (model, _) in enumerate(before["model_ranks"])}
    after_ranks = {model: idx + 1 for idx, (model, _) in enumerate(after["model_ranks"])}

    lines = [
        "Diátaxis: reference",
        "",
        "# Rescore comparison — 2026-03-31 remediation",
        "",
        "## Aggregate frozen-corpus changes",
        "",
        f"- row count: `{before['row_count']}` -> `{after['row_count']}`",
        f"- hard-fail rows: `{before['hard_fail_count']}` -> `{after['hard_fail_count']}`",
        f"- compliance-fail rows: `{before['compliance_fail_count']}` -> `{after['compliance_fail_count']}`",
        f"- `false_scope`-involved rows: `{before['false_scope_count']}` -> `{after['false_scope_count']}`",
        f"- `false_scope`-only rows: `{before['false_scope_only_count']}` -> `{after['false_scope_only_count']}`",
        f"- medical true-positive rows: `{before['medical_true_positive_count']}` -> `{after['medical_true_positive_count']}`",
        "",
        "## Category pass rates",
        "",
        "| Category | Before | After | Δ |",
        "|---|---:|---:|---:|",
    ]
    for category in sorted(set(before["category_pass_rates"]) | set(after["category_pass_rates"])):
        b = before["category_pass_rates"].get(category, 0.0)
        a = after["category_pass_rates"].get(category, 0.0)
        lines.append(f"| {category} | {b:.3f} | {a:.3f} | {a - b:+.3f} |")

    lines.extend([
        "",
        "## Rank shifts",
        "",
        "| Model | Before rank | After rank | Δ | Before score | After score |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    after_score_map = dict(after["model_ranks"])
    before_score_map = dict(before["model_ranks"])
    for model in sorted(after_ranks, key=lambda m: after_ranks[m]):
        br = before_ranks.get(model)
        ar = after_ranks.get(model)
        delta = (br - ar) if br is not None and ar is not None else 0
        lines.append(
            f"| {model} | {br} | {ar} | {delta:+d} | {before_score_map.get(model, 0.0):.4f} | {after_score_map.get(model, 0.0):.4f} |"
        )

    OUTPUT_PATH.write_text("\n".join(lines))
    print(f"Wrote {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
