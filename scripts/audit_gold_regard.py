#!/usr/bin/env python3
"""Audit the current regard scorer against resolved gold quality labels."""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from collections import Counter
from pathlib import Path
from typing import Any

from invisiblebench.evaluation.orchestrator import ScoringOrchestrator
from invisiblebench.utils.benchmark_inventory import (
    collect_scenario_paths,
    get_private_confidential_dir,
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


def ordered_weighted_kappa(labels_a: list[str], labels_b: list[str]) -> float:
    if len(labels_a) != len(labels_b):
        raise ValueError("Label lists must have the same length")
    n = len(labels_a)
    if n == 0:
        return float("nan")

    index = {label: idx for idx, label in enumerate(ORDERED_LABELS)}
    k = len(ORDERED_LABELS)

    observed = [[0 for _ in range(k)] for _ in range(k)]
    count_a = [0 for _ in range(k)]
    count_b = [0 for _ in range(k)]
    for a, b in zip(labels_a, labels_b):
        i = index[a]
        j = index[b]
        observed[i][j] += 1
        count_a[i] += 1
        count_b[j] += 1

    def weight(i: int, j: int) -> float:
        return 1.0 - (abs(i - j) / (k - 1))

    p_o = sum(weight(i, j) * observed[i][j] for i in range(k) for j in range(k)) / n
    p_e = sum(
        weight(i, j) * (count_a[i] / n) * (count_b[j] / n)
        for i in range(k)
        for j in range(k)
    )
    if math.isclose(1.0 - p_e, 0.0):
        return 1.0 if math.isclose(p_o, 1.0) else float("nan")
    return (p_o - p_e) / (1.0 - p_e)


def _pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or not xs:
        return float("nan")
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if math.isclose(var_x, 0.0) or math.isclose(var_y, 0.0):
        return float("nan")
    return cov / math.sqrt(var_x * var_y)


def _format_ratio(numerator: int, denominator: int) -> str:
    return f"{numerator}/{denominator} = {(numerator / denominator):.3f}" if denominator else "n/a"


def _format_float(value: float) -> str:
    return "n/a" if math.isnan(value) else f"{value:.3f}"


def _load_candidates() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(CANDIDATES_PATH) as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _load_gold_labels() -> dict[str, dict[str, Any]]:
    labels: dict[str, dict[str, Any]] = {}
    for path in sorted(GOLD_LABELS_DIR.glob("*.json")):
        labels[path.stem] = json.loads(path.read_text())
    return labels


def _build_scenario_index() -> dict[str, Path]:
    index: dict[str, Path] = {}
    include_confidential = get_private_confidential_dir(PROJECT_ROOT) is not None
    for path in collect_scenario_paths(PROJECT_ROOT, include_confidential=include_confidential):
        scenario_path = Path(path)
        with open(scenario_path) as fh:
            scenario = json.load(fh)
        scenario_id = scenario.get("scenario_id", scenario_path.stem)
        index[scenario_id] = scenario_path
    return index


def _score_candidates(candidates: list[dict[str, Any]], mode: str) -> dict[str, dict[str, Any]]:
    orchestrator = ScoringOrchestrator(
        str(SCORING_CONFIG_PATH),
        enable_state_persistence=False,
        enable_llm=(mode == "llm"),
    )
    scenario_index = _build_scenario_index()
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
        axis_scores = {axis: float(breakdown.get(axis, 0.0)) for axis in REGARD_AXES}
        axis_labels = {axis: regard_score_to_label(score) for axis, score in axis_scores.items()}
        predictions[candidate["trace_id"]] = {
            "axis_scores": axis_scores,
            "axis_labels": axis_labels,
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


def _render_confusion(confusion: dict[str, dict[str, int]]) -> str:
    header = "| Gold \\ Pred | fail | mixed | pass |\n|---|---:|---:|---:|"
    rows = [header]
    for gold in ORDERED_LABELS:
        counts = confusion[gold]
        rows.append(f"| `{gold}` | {counts['fail']} | {counts['mixed']} | {counts['pass']} |")
    return "\n".join(rows)


def _render_report(
    axis_metrics: dict[str, dict[str, Any]],
    overall: dict[str, Any],
    mismatch_rows: list[dict[str, Any]],
    mode: str,
    elapsed: float,
) -> str:
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
        "## Overall summary",
        "",
        f"- exact 4-axis trace match: **{_format_ratio(overall['trace_exact'], overall['n'])}**",
        f"- trace match on at least 3/4 regard axes: **{_format_ratio(overall['trace_three_or_more'], overall['n'])}**",
        f"- gold-derived regard mean vs current regard base MAE: **{_format_float(overall['base_mae'])}**",
        f"- gold-derived regard mean vs current final regard score MAE: **{_format_float(overall['score_mae'])}**",
        f"- gold-derived regard mean vs current regard base Pearson r: **{_format_float(overall['base_pearson'])}**",
        f"- gold-derived regard mean vs current final regard score Pearson r: **{_format_float(overall['score_pearson'])}**",
        "",
        "## Per-axis agreement",
        "",
        "| Axis | Gold label distribution | Current label distribution | Exact accuracy | Weighted κ |",
        "|---|---|---|---:|---:|",
    ]
    for axis in REGARD_AXES:
        metrics = axis_metrics[axis]
        gold_dist = ", ".join(f"{k}={metrics['gold_counts'].get(k, 0)}" for k in ORDERED_LABELS)
        pred_dist = ", ".join(f"{k}={metrics['pred_counts'].get(k, 0)}" for k in ORDERED_LABELS)
        lines.append(
            f"| `{axis}` | {gold_dist} | {pred_dist} | {_format_ratio(metrics['exact'], metrics['n'])} | {_format_float(metrics['weighted_kappa'])} |"
        )

    for axis in REGARD_AXES:
        lines.extend([
            "",
            f"### Confusion: `{axis}`",
            "",
            _render_confusion(axis_metrics[axis]["confusion"]),
        ])

    if mismatch_rows:
        lines.extend([
            "",
            "## Largest mismatches",
            "",
            "| Trace | Matches | Gold mean | Current base | Notes |",
            "|---|---:|---:|---:|---|",
        ])
        for row in mismatch_rows[:15]:
            notes = ", ".join(
                f"{axis}:{row[f'gold_{axis}']}→{row[f'current_{axis}_label']}"
                for axis in REGARD_AXES
                if not row[f"{axis}_match"]
            )
            lines.append(
                f"| `{row['trace_id']}` | {row['matched_axes']}/4 | {row['gold_regard_mean']:.3f} | {row['current_regard_base']:.3f} | {notes} |"
            )

    lines.extend([
        "",
        "## Interpretation",
        "",
        "This report measures the current runtime regard scorer against the resolved gold quality labels already present in the 60-trace calibration set. It does not claim that the quality layer is automatically strong enough for headline leaderboard claims; it exists to replace `fixed-unvalidated` with an explicit measured state.",
    ])
    return "\n".join(lines) + "\n"


def _write_csv(rows: list[dict[str, Any]], out_path: Path) -> None:
    fieldnames = [
        "trace_id",
        "scenario_id",
        "model",
        "model_id",
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
                f"{axis}_match",
            ]
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})


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
    axis_metrics = {axis: _axis_metrics(rows, axis) for axis in REGARD_AXES}
    overall = _overall_metrics(rows)
    mismatch_rows = _top_mismatches(rows)
    report = _render_report(axis_metrics, overall, mismatch_rows, args.mode, elapsed)

    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.write_text(report)
    _write_csv(rows, args.out_csv)

    print(f"wrote {args.out_md.relative_to(PROJECT_ROOT)}")
    print(f"wrote {args.out_csv.relative_to(PROJECT_ROOT)}")
    print(
        "summary:",
        {
            "trace_exact": f"{overall['trace_exact']}/{overall['n']}",
            "trace_three_or_more": f"{overall['trace_three_or_more']}/{overall['n']}",
            "base_mae": round(overall['base_mae'], 3),
            "base_pearson": None if math.isnan(overall['base_pearson']) else round(overall['base_pearson'], 3),
        },
    )


if __name__ == "__main__":
    main()
