"""Shared helpers for audit and evaluation scripts.

Consolidates data-loading, statistical, and formatting utilities that were
previously duplicated across audit_gold_regard, audit_gold_scorer,
audit_holdout_regard, audit_holdout_scorer, audit_holdout_regard_binary,
golden_set_kappa, and build_regard_pairwise_pilot.

Internal module — import directly, not through ``scripts.__init__``.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------


def load_candidates(path: Path) -> list[dict[str, Any]]:
    """Load a JSONL candidates file into a list of dicts."""
    rows: list[dict[str, Any]] = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_gold_labels(directory: Path) -> dict[str, dict[str, Any]]:
    """Load per-trace gold JSON files from *directory*, keyed by stem."""
    labels: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.glob("*.json")):
        labels[path.stem] = json.loads(path.read_text())
    return labels


def build_scenario_index(
    project_root: Path,
) -> dict[str, Path]:
    """Build a mapping from scenario_id to scenario file path."""
    from invisiblebench.utils.benchmark_inventory import (
        collect_scenario_paths,
        get_private_confidential_dir,
    )

    index: dict[str, Path] = {}
    include_confidential = get_private_confidential_dir(project_root) is not None
    for path_str in collect_scenario_paths(project_root, include_confidential=include_confidential):
        scenario_path = Path(path_str)
        with open(scenario_path) as fh:
            scenario = json.load(fh)
        scenario_id = scenario.get("scenario_id", scenario_path.stem)
        index[scenario_id] = scenario_path
    return index


# ---------------------------------------------------------------------------
# Statistical functions
# ---------------------------------------------------------------------------

ORDERED_LABELS = ("fail", "mixed", "pass")


def ordered_weighted_kappa(
    labels_a: Sequence[str],
    labels_b: Sequence[str],
    ordered_labels: Sequence[str] = ORDERED_LABELS,
) -> float:
    """Ordered (linear) weighted Cohen's kappa for ordinal labels."""
    if len(labels_a) != len(labels_b):
        raise ValueError("Label lists must have the same length")
    n = len(labels_a)
    if n == 0:
        return float("nan")

    index = {label: idx for idx, label in enumerate(ordered_labels)}
    k = len(ordered_labels)

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


def cohen_kappa(labels_a: Sequence[Any], labels_b: Sequence[Any]) -> float:
    """Unweighted Cohen's kappa for nominal labels."""
    assert len(labels_a) == len(labels_b)
    n = len(labels_a)
    if n == 0:
        return float("nan")

    classes = sorted({str(x) for x in labels_a} | {str(x) for x in labels_b})
    if len(classes) <= 1:
        return 1.0 if list(labels_a) == list(labels_b) else float("nan")

    agree = sum(1 for a, b in zip(labels_a, labels_b) if a == b)
    p_o = agree / n
    count_a: Counter[str] = Counter(str(x) for x in labels_a)
    count_b: Counter[str] = Counter(str(x) for x in labels_b)
    p_e = sum((count_a[c] / n) * (count_b[c] / n) for c in classes)
    if 1 - p_e == 0:
        return 1.0 if p_o == 1.0 else float("nan")
    return (p_o - p_e) / (1 - p_e)


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Pearson correlation coefficient."""
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


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def format_ratio(numerator: int, denominator: int) -> str:
    """Format a ratio as 'N/D = 0.XXX' or 'n/a' when denominator is zero."""
    return f"{numerator}/{denominator} = {(numerator / denominator):.3f}" if denominator else "n/a"


def format_float(value: float) -> str:
    """Format a float, returning 'n/a' for NaN."""
    return "n/a" if math.isnan(value) else f"{value:.3f}"


def format_kappa(value: float) -> str:
    """Format a kappa value, returning 'n/a' for NaN."""
    return "n/a" if value != value else f"{value:.3f}"
