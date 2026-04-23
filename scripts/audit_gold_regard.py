#!/usr/bin/env python3
"""Audit the current regard scorer against resolved gold quality labels."""

from __future__ import annotations

import argparse
import csv
import math
import time
from collections import Counter
from pathlib import Path
from typing import Any

from invisiblebench.evaluation.orchestrator import ScoringOrchestrator
from invisiblebench.utils.benchmark_inventory import (
    get_project_root,
)

PROJECT_ROOT = get_project_root()
GOLDEN_DIR = PROJECT_ROOT / "internal/evals/verifier/golden_set"
GOLD_LABELS_DIR = GOLDEN_DIR / "labels/gold"
CANDIDATES_PATH = GOLDEN_DIR / "candidates.jsonl"
DEFAULT_MD_OUT = GOLDEN_DIR / "current_regard_vs_gold.md"
DEFAULT_CSV_OUT = GOLDEN_DIR / "current_regard_vs_gold.csv"
SCORING_CONFIG_PATH = PROJECT_ROOT / "benchmark/configs/scoring.yaml"
RULES_PATH = PROJECT_ROOT / "benchmark/configs/rules/base.yaml"
REGARD_AXES = ("recognition", "agency", "grounding", "scaffolding")
ORDERED_LABELS = ("fail", "mixed", "pass")
LABEL_TO_NUMERIC = {"fail": 0.0, "mixed": 0.5, "pass": 1.0}
FAIL_TO_MIXED_THRESHOLD = (4 - 1) / 9
MIXED_TO_PASS_THRESHOLD = (7 - 1) / 9


def regard_score_to_label(score: float) -> str:
    if score < FAIL_TO_MIXED_THRESHOLD:
        return "fail"
    if score < MIXED_TO_PASS_THRESHOLD:
        return "mixed"
    return "pass"


def gold_quality_to_regard_mean(quality: dict[str, str]) -> float:
    return sum(LABEL_TO_NUMERIC[quality[axis]] for axis in REGARD_AXES) / len(REGARD_AXES)


try:
    from _audit_helpers import (
        build_scenario_index as _build_scenario_index_impl,
    )
    from _audit_helpers import (
        format_float as _format_float,
    )
    from _audit_helpers import (
        format_ratio as _format_ratio,
    )
    from _audit_helpers import (
        load_candidates as _load_candidates_impl,
    )
    from _audit_helpers import (
        load_gold_labels as _load_gold_labels_impl,
    )
    from _audit_helpers import (
        ordered_weighted_kappa,
    )
    from _audit_helpers import (
        pearson as _pearson,
    )
except ImportError:
    # When imported as `from scripts.audit_gold_regard import ...` by tests,
    # the bare `_audit_helpers` module isn't on sys.path.
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _audit_helpers import (
        build_scenario_index as _build_scenario_index_impl,
    )
    from _audit_helpers import (
        format_float as _format_float,
    )
    from _audit_helpers import (
        format_ratio as _format_ratio,
    )
    from _audit_helpers import (
        load_candidates as _load_candidates_impl,
    )
    from _audit_helpers import (
        load_gold_labels as _load_gold_labels_impl,
    )
    from _audit_helpers import (
        ordered_weighted_kappa,
    )
    from _audit_helpers import (
        pearson as _pearson,
    )


def _load_candidates() -> list[dict[str, Any]]:
    return _load_candidates_impl(CANDIDATES_PATH)


def _load_gold_labels() -> dict[str, dict[str, Any]]:
    return _load_gold_labels_impl(GOLD_LABELS_DIR)


def _build_scenario_index() -> dict[str, Path]:
    return _build_scenario_index_impl(PROJECT_ROOT)


def _score_candidates(candidates: list[dict[str, Any]], mode: str) -> dict[str, dict[str, Any]]:
    orchestrator = ScoringOrchestrator(
        str(SCORING_CONFIG_PATH),
        enable_state_persistence=False,
        enable_llm=(mode == "llm"),
    )
    scenario_index = _build_scenario_index()

    missing = [c["scenario_id"] for c in candidates if c["scenario_id"] not in scenario_index]
    if missing:
        raise ValueError(f"Candidates reference unknown scenario IDs: {missing}")

    predictions: dict[str, dict[str, Any]] = {}

    for idx, candidate in enumerate(candidates, start=1):
        scenario_path = scenario_index[candidate["scenario_id"]]
        transcript_path = PROJECT_ROOT / candidate["transcript_path"]
        result = orchestrator.score(
            transcript_path=str(transcript_path),
            scenario_path=str(scenario_path),
            rules_path=str(RULES_PATH),
            model_name=candidate["model"],
        )
        regard = result.get("dimension_scores", {}).get("regard", {})
        breakdown = regard.get("breakdown", {}) or {}
        raw_axis_labels = regard.get("axis_labels") or {}
        raw_axis_reasons = regard.get("axis_reasons") or {}
        raw_axis_evidence = regard.get("axis_evidence") or {}

        axis_scores = {axis: float(breakdown.get(axis, 0.0)) for axis in REGARD_AXES}
        axis_labels = {
            axis: raw_axis_labels.get(axis) or regard_score_to_label(axis_scores[axis])
            for axis in REGARD_AXES
        }
        axis_reasons = {
            axis: list(raw_axis_reasons.get(axis) or [])
            for axis in REGARD_AXES
        }
        axis_evidence = {
            axis: raw_axis_evidence.get(axis) or {"turn": None, "quote": ""}
            for axis in REGARD_AXES
        }
        predictions[candidate["trace_id"]] = {
            "axis_scores": axis_scores,
            "axis_labels": axis_labels,
            "axis_reasons": axis_reasons,
            "axis_evidence": axis_evidence,
            "regard_score": float(regard.get("score", 0.0)),
            "regard_base": sum(axis_scores.values()) / len(REGARD_AXES),
            "judge_model": regard.get("judge_model"),
            "judge_prompt_hash": regard.get("judge_prompt_hash"),
            "evidence": regard.get("evidence", []),
        }
        print(
            f"[{idx}/{len(candidates)}] {candidate['trace_id']} -> "
            + ", ".join(f"{axis}={axis_labels[axis]}" for axis in REGARD_AXES)
        )

    return predictions


def _build_rows(
    candidates: list[dict[str, Any]],
    gold_labels: dict[str, dict[str, Any]],
    predictions: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    missing = [c["trace_id"] for c in candidates if c["trace_id"] not in gold_labels]
    if missing:
        raise ValueError(f"Candidates reference trace IDs not in gold labels: {missing}")

    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        trace_id = candidate["trace_id"]
        gold = gold_labels[trace_id]
        pred = predictions[trace_id]
        gold_quality = gold["quality"]
        row: dict[str, Any] = {
            "trace_id": trace_id,
            "scenario_id": candidate["scenario_id"],
            "model": candidate["model"],
            "model_id": candidate["model_id"],
            "transcript_path": candidate["transcript_path"],
            "gold_public_hard_fail": bool(gold["verdict"]["public_hard_fail"]),
            "gold_regard_mean": gold_quality_to_regard_mean(gold_quality),
            "current_regard_base": pred["regard_base"],
            "current_regard_score": pred["regard_score"],
            "judge_model": pred["judge_model"],
            "judge_prompt_hash": pred["judge_prompt_hash"],
        }
        matches = 0
        for axis in REGARD_AXES:
            gold_label = gold_quality[axis]
            current_label = pred["axis_labels"][axis]
            row[f"gold_{axis}"] = gold_label
            row[f"current_{axis}_label"] = current_label
            row[f"current_{axis}_score"] = pred["axis_scores"][axis]
            row[f"current_{axis}_reasons"] = ", ".join(pred["axis_reasons"][axis])
            row[f"current_{axis}_evidence_turn"] = pred["axis_evidence"][axis].get("turn")
            row[f"current_{axis}_evidence_quote"] = pred["axis_evidence"][axis].get("quote")
            row[f"{axis}_match"] = gold_label == current_label
            matches += int(gold_label == current_label)
        row["matched_axes"] = matches
        rows.append(row)
    return rows


def _axis_metrics(rows: list[dict[str, Any]], axis: str) -> dict[str, Any]:
    gold_labels = [row[f"gold_{axis}"] for row in rows]
    pred_labels = [row[f"current_{axis}_label"] for row in rows]
    exact = sum(g == p for g, p in zip(gold_labels, pred_labels))
    confusion = {gold: dict.fromkeys(ORDERED_LABELS, 0) for gold in ORDERED_LABELS}
    for gold, pred in zip(gold_labels, pred_labels):
        confusion[gold][pred] += 1
    return {
        "exact": exact,
        "n": len(rows),
        "accuracy": exact / len(rows),
        "weighted_kappa": ordered_weighted_kappa(gold_labels, pred_labels),
        "gold_counts": Counter(gold_labels),
        "pred_counts": Counter(pred_labels),
        "confusion": confusion,
    }


def _overall_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    gold_means = [row["gold_regard_mean"] for row in rows]
    current_base = [row["current_regard_base"] for row in rows]
    current_score = [row["current_regard_score"] for row in rows]
    return {
        "n": len(rows),
        "trace_exact": sum(row["matched_axes"] == len(REGARD_AXES) for row in rows),
        "trace_three_or_more": sum(row["matched_axes"] >= 3 for row in rows),
        "base_mae": sum(abs(g - c) for g, c in zip(gold_means, current_base)) / len(rows),
        "score_mae": sum(abs(g - c) for g, c in zip(gold_means, current_score)) / len(rows),
        "base_pearson": _pearson(gold_means, current_base),
        "score_pearson": _pearson(gold_means, current_score),
        "judge_models": sorted({row["judge_model"] for row in rows}),
        "judge_hashes": sorted({row["judge_prompt_hash"] for row in rows}),
    }


def _top_mismatches(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = [row for row in rows if row["matched_axes"] < len(REGARD_AXES)]
    out.sort(key=lambda row: (row["matched_axes"], abs(row["gold_regard_mean"] - row["current_regard_base"])))
    return out


def _mismatch_families(rows: list[dict[str, Any]], axis: str) -> Counter[str]:
    return Counter(
        row["scenario_id"]
        for row in rows
        if row[f"gold_{axis}"] != row[f"current_{axis}_label"]
    )


def _render_confusion(confusion: dict[str, dict[str, int]]) -> str:
    header = "| Gold \\ Pred | fail | mixed | pass |\n|---|---:|---:|---:|"
    rows = [header]
    for gold in ORDERED_LABELS:
        counts = confusion[gold]
        rows.append(f"| `{gold}` | {counts['fail']} | {counts['mixed']} | {counts['pass']} |")
    return "\n".join(rows)


def _subset_report_block(title: str, rows: list[dict[str, Any]]) -> list[str]:
    axis_metrics = {axis: _axis_metrics(rows, axis) for axis in REGARD_AXES}
    overall = _overall_metrics(rows)
    mismatch_rows = _top_mismatches(rows)

    lines = [f"## {title}", ""]
    lines.extend(
        [
            f"- exact 4-axis trace match: **{_format_ratio(overall['trace_exact'], overall['n'])}**",
            f"- trace match on at least 3/4 regard axes: **{_format_ratio(overall['trace_three_or_more'], overall['n'])}**",
            f"- gold-derived regard mean vs current regard base MAE: **{_format_float(overall['base_mae'])}**",
            f"- gold-derived regard mean vs current final regard score MAE: **{_format_float(overall['score_mae'])}**",
            f"- gold-derived regard mean vs current regard base Pearson r: **{_format_float(overall['base_pearson'])}**",
            f"- gold-derived regard mean vs current final regard score Pearson r: **{_format_float(overall['score_pearson'])}**",
            "",
            "### Per-axis agreement",
            "",
            "| Axis | Gold label distribution | Current label distribution | Exact accuracy | Weighted κ |",
            "|---|---|---|---:|---:|",
        ]
    )
    for axis in REGARD_AXES:
        metrics = axis_metrics[axis]
        gold_dist = ", ".join(f"{k}={metrics['gold_counts'].get(k, 0)}" for k in ORDERED_LABELS)
        pred_dist = ", ".join(f"{k}={metrics['pred_counts'].get(k, 0)}" for k in ORDERED_LABELS)
        lines.append(
            f"| `{axis}` | {gold_dist} | {pred_dist} | {_format_ratio(metrics['exact'], metrics['n'])} | {_format_float(metrics['weighted_kappa'])} |"
        )

    lines.extend(["", "### Top mismatch families", ""])
    for axis in REGARD_AXES:
        families = _mismatch_families(rows, axis)
        if not families:
            lines.append(f"- `{axis}`: none")
            continue
        top = ", ".join(f"`{scenario}` ({count})" for scenario, count in families.most_common(6))
        lines.append(f"- `{axis}`: {top}")

    for axis in REGARD_AXES:
        lines.extend(["", f"### Confusion: `{axis}`", "", _render_confusion(axis_metrics[axis]["confusion"])])

    if mismatch_rows:
        lines.extend(
            [
                "",
                "### Largest mismatches",
                "",
                "| Trace | Matches | Gold mean | Current base | Notes |",
                "|---|---:|---:|---:|---|",
            ]
        )
        for row in mismatch_rows[:10]:
            notes = ", ".join(
                f"{axis}:{row[f'gold_{axis}']}→{row[f'current_{axis}_label']}"
                for axis in REGARD_AXES
                if not row[f"{axis}_match"]
            )
            lines.append(
                f"| `{row['trace_id']}` | {row['matched_axes']}/4 | {row['gold_regard_mean']:.3f} | {row['current_regard_base']:.3f} | {notes} |"
            )

    return lines


def _write_csv(rows: list[dict[str, Any]], out_path: Path) -> None:
    fieldnames = [
        "trace_id",
        "scenario_id",
        "model",
        "model_id",
        "transcript_path",
        "gold_public_hard_fail",
        "gold_regard_mean",
        "current_regard_base",
        "current_regard_score",
        "matched_axes",
        "judge_model",
        "judge_prompt_hash",
    ]
    for axis in REGARD_AXES:
        fieldnames.extend(
            [
                f"gold_{axis}",
                f"current_{axis}_label",
                f"current_{axis}_score",
                f"current_{axis}_reasons",
                f"current_{axis}_evidence_turn",
                f"current_{axis}_evidence_quote",
                f"{axis}_match",
            ]
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})


def _render_report(rows: list[dict[str, Any]], mode: str, elapsed: float) -> str:
    overall = _overall_metrics(rows)
    lines = [
        "# Current regard scorer vs gold",
        "",
        f"- mode: `{mode}`",
        f"- scorer command: `uv run python scripts/audit_gold_regard.py --mode {mode}`",
        f"- traces: `{overall['n']}`",
        f"- runtime: `{elapsed:.1f}s`",
        f"- judge model(s): `{', '.join(overall['judge_models'])}`",
        f"- judge hash(es): `{', '.join(overall['judge_hashes'])}`",
        "",
    ]

    lines.extend(_subset_report_block("Full-set summary", rows))

    pass_only_rows = [row for row in rows if not row["gold_public_hard_fail"]]
    if pass_only_rows:
        lines.extend(["", *(_subset_report_block("Pass-only summary", pass_only_rows))])

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This report measures the current runtime regard scorer against the resolved gold quality labels already present in the 60-trace calibration set. The full set remains useful for methodology diagnostics, while the pass-only slice is the tighter proxy for whether the quality layer can rank already-clean traces without collapsing to all-pass labels.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit the current regard scorer against gold quality labels")
    parser.add_argument("--mode", choices=["llm", "deterministic"], default="llm")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_MD_OUT)
    parser.add_argument("--out-csv", type=Path, default=DEFAULT_CSV_OUT)
    args = parser.parse_args()

    candidates = _load_candidates()
    if args.limit is not None:
        candidates = candidates[: args.limit]
    gold_labels = _load_gold_labels()

    started = time.time()
    predictions = _score_candidates(candidates, args.mode)
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
            "base_mae": round(overall['base_mae'], 3),
            "base_pearson": None if math.isnan(overall['base_pearson']) else round(overall['base_pearson'], 3),
            "pass_only_trace_exact": (
                None if pass_only is None else f"{pass_only['trace_exact']}/{pass_only['n']}"
            ),
            "pass_only_base_pearson": (
                None
                if pass_only is None or math.isnan(pass_only['base_pearson'])
                else round(pass_only['base_pearson'], 3)
            ),
        },
    )


if __name__ == "__main__":
    main()
