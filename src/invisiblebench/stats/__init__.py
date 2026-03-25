"""Statistical analysis tools for InvisibleBench."""

from __future__ import annotations

from typing import Dict, List, Tuple


def cohen_kappa_continuous(
    ratings_a: List[float], ratings_b: List[float], n_bins: int = 5
) -> float:
    """Compute Cohen's kappa by binning continuous scores.

    Bins scores into n_bins equal-width bins on [0, 1], then computes
    standard Cohen's kappa on the discretized ratings.
    """
    if len(ratings_a) != len(ratings_b) or len(ratings_a) == 0:
        return 0.0

    bin_edges = [i / n_bins for i in range(n_bins + 1)]

    def _bin(v: float) -> int:
        for i in range(n_bins):
            if v <= bin_edges[i + 1]:
                return i
        return n_bins - 1

    bins_a = [_bin(v) for v in ratings_a]
    bins_b = [_bin(v) for v in ratings_b]

    n = len(bins_a)
    categories = list(range(n_bins))

    # Build confusion matrix
    matrix: Dict[Tuple[int, int], int] = {}
    for ca in categories:
        for cb in categories:
            matrix[(ca, cb)] = 0
    for a, b in zip(bins_a, bins_b):
        matrix[(a, b)] = matrix.get((a, b), 0) + 1

    # Observed agreement
    p_o = sum(matrix.get((c, c), 0) for c in categories) / n

    # Expected agreement
    p_e = 0.0
    for c in categories:
        row_sum = sum(matrix.get((c, cb), 0) for cb in categories) / n
        col_sum = sum(matrix.get((ca, c), 0) for ca in categories) / n
        p_e += row_sum * col_sum

    if p_e >= 1.0:
        return 1.0
    return (p_o - p_e) / (1.0 - p_e)
