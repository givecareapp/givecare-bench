#!/usr/bin/env python3
"""Compute inter-rater agreement for the golden set.

Compares annotator_a and annotator_b labels across the 60 candidates and emits:

  internal/evals/verifier/golden_set/kappa_report.md
  internal/evals/verifier/golden_set/labels/conflict_resolution/<trace_id>.json

κ is Cohen's κ for binary/categorical axes. For the soft_issues set axis we
report a Jaccard-mean-based agreement stat (not true κ, labeled as such).

Can also be run with --annotator-a ai_silver (etc.) to sanity-check the silver
labels against a human pass once one exists.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = ROOT / "internal/evals/verifier/golden_set"
CANDIDATES_PATH = GOLDEN_DIR / "candidates.jsonl"


def _load_candidates() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(CANDIDATES_PATH) as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _load_labels(label_dir: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not label_dir.exists():
        return out
    for path in sorted(label_dir.glob("*.json")):
        trace_id = path.stem
        with open(path) as fh:
            out[trace_id] = json.load(fh)
    return out


def cohen_kappa(labels_a: list[Any], labels_b: list[Any]) -> tuple[float, int, dict[str, int]]:
    """Cohen's κ over two parallel label lists. Returns (kappa, n, class_counts)."""
    assert len(labels_a) == len(labels_b)
    n = len(labels_a)
    if n == 0:
        return (float("nan"), 0, {})

    classes = sorted({str(x) for x in labels_a} | {str(x) for x in labels_b})
    if len(classes) <= 1:
        return (1.0 if labels_a == labels_b else float("nan"), n, Counter(str(x) for x in labels_a))

    agree = sum(1 for a, b in zip(labels_a, labels_b) if a == b)
    p_o = agree / n
    count_a = Counter(str(x) for x in labels_a)
    count_b = Counter(str(x) for x in labels_b)
    p_e = sum((count_a[c] / n) * (count_b[c] / n) for c in classes)
    if 1 - p_e == 0:
        kappa = 1.0 if p_o == 1.0 else float("nan")
    else:
        kappa = (p_o - p_e) / (1 - p_e)
    return (kappa, n, dict(count_a))


def jaccard_mean(labels_a: list[list[str]], labels_b: list[list[str]]) -> tuple[float, int]:
    assert len(labels_a) == len(labels_b)
    n = len(labels_a)
    if n == 0:
        return (float("nan"), 0)
    total = 0.0
    for a, b in zip(labels_a, labels_b):
        set_a, set_b = set(a), set(b)
        if not set_a and not set_b:
            total += 1.0
            continue
        union = set_a | set_b
        inter = set_a & set_b
        total += len(inter) / len(union) if union else 1.0
    return (total / n, n)


def confusion(labels_a: list[Any], labels_b: list[Any]) -> dict[str, dict[str, int]]:
    matrix: dict[str, dict[str, int]] = {}
    for a, b in zip(labels_a, labels_b):
        ka, kb = str(a), str(b)
        matrix.setdefault(ka, {}).setdefault(kb, 0)
        matrix[ka][kb] += 1
    return matrix


def _axis(label: dict[str, Any], *path: str) -> Any:
    node = label
    for key in path:
        if node is None:
            return None
        node = node.get(key)
    return node


def build_report(
    candidates: list[dict[str, Any]],
    a_labels: dict[str, dict[str, Any]],
    b_labels: dict[str, dict[str, Any]],
    a_name: str,
    b_name: str,
) -> tuple[str, list[dict[str, Any]]]:
    trace_ids = [c["trace_id"] for c in candidates]
    paired = [tid for tid in trace_ids if tid in a_labels and tid in b_labels]
    missing_a = [tid for tid in trace_ids if tid not in a_labels]
    missing_b = [tid for tid in trace_ids if tid not in b_labels]

    axes: list[tuple[str, tuple[str, ...], float]] = [
        ("public_hard_fail (bool)", ("verdict", "public_hard_fail"), 0.70),
        ("hard_fail_rule", ("verdict", "hard_fail_rule"), 0.60),
        ("safety_gate", ("verdict", "safety_gate"), 0.70),
        ("compliance_gate", ("verdict", "compliance_gate"), 0.70),
        ("agreement_with_current_scorer", ("agreement_with_current_scorer",), 0.50),
        ("confidence", ("confidence",), 0.40),
    ]

    lines: list[str] = []
    lines.append("# Golden Set Inter-Rater Report\n")
    lines.append(f"- annotator A source: `labels/{a_name}/`")
    lines.append(f"- annotator B source: `labels/{b_name}/`")
    lines.append(f"- candidates: {len(trace_ids)}")
    lines.append(f"- paired labels: {len(paired)}")
    lines.append(f"- missing in A: {len(missing_a)}")
    lines.append(f"- missing in B: {len(missing_b)}")
    lines.append("")

    if not paired:
        lines.append("No paired labels yet — agreement cannot be computed.")
        return "\n".join(lines), []

    lines.append("## Per-axis Cohen κ\n")
    lines.append("| Axis | κ | n | Target | Status |")
    lines.append("|---|---:|---:|---:|---|")
    disagreements: dict[str, list[str]] = {}
    for axis_name, path, target in axes:
        a_vals = [_axis(a_labels[t], *path) for t in paired]
        b_vals = [_axis(b_labels[t], *path) for t in paired]
        kappa, n, _classes = cohen_kappa(a_vals, b_vals)
        status = "—" if kappa != kappa else ("✅" if kappa >= target else "❌")
        kappa_fmt = "n/a" if kappa != kappa else f"{kappa:.3f}"
        lines.append(f"| `{axis_name}` | {kappa_fmt} | {n} | {target:.2f} | {status} |")
        for tid, a, b in zip(paired, a_vals, b_vals):
            if a != b:
                disagreements.setdefault(tid, []).append(f"{axis_name}: A={a!r} / B={b!r}")

    lines.append("")
    lines.append("## Soft-issue set agreement (Jaccard mean, not κ)\n")
    a_sets = [list(_axis(a_labels[t], "soft_issues") or []) for t in paired]
    b_sets = [list(_axis(b_labels[t], "soft_issues") or []) for t in paired]
    jmean, jn = jaccard_mean(a_sets, b_sets)
    lines.append(f"- Jaccard mean: **{jmean:.3f}** (n={jn}, target ≥ 0.50)")
    for tid, a, b in zip(paired, a_sets, b_sets):
        if set(a) != set(b):
            disagreements.setdefault(tid, []).append(
                f"soft_issues: A={sorted(a)!r} / B={sorted(b)!r}"
            )

    lines.append("")
    lines.append("## Confusion matrix: `hard_fail_rule`\n")
    a_vals = [_axis(a_labels[t], "verdict", "hard_fail_rule") for t in paired]
    b_vals = [_axis(b_labels[t], "verdict", "hard_fail_rule") for t in paired]
    matrix = confusion(a_vals, b_vals)
    all_classes = sorted({str(v) for v in a_vals} | {str(v) for v in b_vals})
    header = "| A \\ B | " + " | ".join(f"`{c}`" for c in all_classes) + " |"
    sep = "|---|" + "|".join("---:" for _ in all_classes) + "|"
    lines.append(header)
    lines.append(sep)
    for a_cls in all_classes:
        row = matrix.get(a_cls, {})
        cells = [str(row.get(b_cls, 0)) for b_cls in all_classes]
        lines.append(f"| `{a_cls}` | " + " | ".join(cells) + " |")

    lines.append("")
    lines.append("## Disagreement set\n")
    lines.append(f"- {len(disagreements)} traces with at least one axis disagreement")
    for tid, axes_dis in sorted(disagreements.items()):
        lines.append(f"\n### `{tid}`")
        for ax in axes_dis:
            lines.append(f"- {ax}")

    conflict_stubs: list[dict[str, Any]] = []
    for tid in disagreements:
        conflict_stubs.append({
            "trace_id": tid,
            "annotator_a": a_labels[tid],
            "annotator_b": b_labels[tid],
            "resolution": {
                "resolver": "__FILL__",
                "resolved_at": "__FILL_iso8601__",
                "final_label": "__FILL_label_json__",
                "rationale": "__FILL_why_this_resolution__",
            },
        })

    return "\n".join(lines), conflict_stubs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--annotator-a", default="annotator_a")
    parser.add_argument("--annotator-b", default="annotator_b")
    parser.add_argument("--no-write-conflicts", action="store_true")
    args = parser.parse_args()

    a_dir = GOLDEN_DIR / "labels" / args.annotator_a
    b_dir = GOLDEN_DIR / "labels" / args.annotator_b

    candidates = _load_candidates()
    a_labels = _load_labels(a_dir)
    b_labels = _load_labels(b_dir)

    report, conflict_stubs = build_report(
        candidates, a_labels, b_labels, args.annotator_a, args.annotator_b
    )

    report_path = GOLDEN_DIR / "kappa_report.md"
    report_path.write_text(report + "\n")
    print(f"wrote {report_path.relative_to(ROOT)}")

    if conflict_stubs and not args.no_write_conflicts:
        conflict_dir = GOLDEN_DIR / "labels" / "conflict_resolution"
        conflict_dir.mkdir(parents=True, exist_ok=True)
        for stub in conflict_stubs:
            out = conflict_dir / f"{stub['trace_id']}.json"
            if out.exists():
                continue
            with open(out, "w") as fh:
                json.dump(stub, fh, indent=2)
        print(f"wrote {len(conflict_stubs)} conflict stubs to {conflict_dir.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
