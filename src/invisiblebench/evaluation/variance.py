"""Variance metrics across multiple scoring iterations."""

from __future__ import annotations

import statistics
from typing import Any, Optional


def calculate_cv(mean: float, std_dev: float) -> Optional[float]:
    """CV = std_dev / mean. Returns None when mean is near-zero (unstable)."""
    if mean < 0:
        raise ValueError("Mean cannot be negative")
    if std_dev < 0:
        raise ValueError("Standard deviation cannot be negative")

    if std_dev == 0.0:
        return 0.0
    if mean == 0.0:
        return 0.0 if std_dev == 0.0 else None
    if mean < 0.01:
        return None

    return std_dev / mean


def calculate_variance(scores: list[float]) -> dict[str, Any]:
    """Return {mean, std_dev, min, max, cv} for a list of scores."""
    if not scores:
        raise ValueError("Scores list must contain at least one score")

    for score in scores:
        if not isinstance(score, (int, float)):
            raise TypeError(f"All scores must be numeric, got {type(score)}")

    mean = statistics.mean(scores)
    min_score = min(scores)
    max_score = max(scores)
    std_dev = 0.0 if len(scores) == 1 else statistics.stdev(scores)
    cv = calculate_cv(mean, std_dev)

    return {
        "mean": mean,
        "std_dev": std_dev,
        "min": min_score,
        "max": max_score,
        "cv": cv,
    }


def calculate_dimension_variance(
    dimension_scores_list: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Variance metrics per dimension across iterations."""
    if not dimension_scores_list:
        raise ValueError("dimension_scores_list cannot be empty")

    all_dimensions: set[str] = set()
    for dim_scores in dimension_scores_list:
        all_dimensions.update(dim_scores.keys())

    result: dict[str, dict[str, Any]] = {}
    for dimension in all_dimensions:
        scores = []
        for dim_scores in dimension_scores_list:
            if dimension in dim_scores and "score" in dim_scores[dimension]:
                scores.append(dim_scores[dimension]["score"])

        if scores:
            result[dimension] = calculate_variance(scores)

    return result


def aggregate_iteration_results(iteration_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate results from multiple iterations into a single result with variance."""
    if not iteration_results:
        raise ValueError("iteration_results cannot be empty")

    num_iterations = len(iteration_results)
    overall_scores = [result["overall_score"] for result in iteration_results]
    dimension_scores_list = [result["dimension_scores"] for result in iteration_results]
    overall_variance = calculate_variance(overall_scores) if num_iterations > 1 else None
    dimension_variance = (
        calculate_dimension_variance(dimension_scores_list) if num_iterations > 1 else None
    )

    mean_overall_score = statistics.mean(overall_scores)

    all_dimensions: set[str] = set()
    for dim_scores in dimension_scores_list:
        all_dimensions.update(dim_scores.keys())

    mean_dimension_scores: dict[str, Any] = {}
    for dimension in all_dimensions:
        scores = []
        for dim_scores in dimension_scores_list:
            if dimension in dim_scores and "score" in dim_scores[dimension]:
                scores.append(dim_scores[dimension]["score"])

        if scores:
            mean_score = statistics.mean(scores)
            mean_dimension_scores[dimension] = iteration_results[0]["dimension_scores"][
                dimension
            ].copy()
            mean_dimension_scores[dimension]["score"] = mean_score

    # Any iteration hard-fail zeros the overall score (gate policy)
    hard_fail = any(result.get("hard_fail", False) for result in iteration_results)
    if hard_fail:
        mean_overall_score = 0.0
        all_hard_fail_reasons = []
        for result in iteration_results:
            if result.get("hard_fail", False):
                all_hard_fail_reasons.extend(result.get("hard_fail_reasons", []))

    metadata = iteration_results[0].get("metadata", {}).copy()
    metadata["iterations_run"] = num_iterations

    aggregated = {
        "overall_score": mean_overall_score,
        "dimension_scores": mean_dimension_scores,
        "hard_fail": hard_fail,
        "metadata": metadata,
        "iterations": [
            {
                "iteration": i + 1,
                "overall_score": result["overall_score"],
                "dimension_scores": result["dimension_scores"],
                "hard_fail": result.get("hard_fail", False),
            }
            for i, result in enumerate(iteration_results)
        ],
    }

    confidence_entries: list[dict[str, Any]] = [
        result["confidence"] for result in iteration_results
        if isinstance(result.get("confidence"), dict)
    ]
    if confidence_entries:
        overall_confidences: list[float] = [
            float(entry["overall"]) for entry in confidence_entries
            if entry.get("overall") is not None
        ]
        dimension_confidence: dict[str, list[float]] = {}
        for entry in confidence_entries:
            for dimension, value in entry.get("dimensions", {}).items():
                if value is None:
                    continue
                dimension_confidence.setdefault(dimension, []).append(value)

        aggregated_confidence = {
            "overall": statistics.mean(overall_confidences) if overall_confidences else None,
            "dimensions": {
                dimension: statistics.mean(values)
                for dimension, values in dimension_confidence.items()
            },
        }
        aggregated["confidence"] = aggregated_confidence

    if num_iterations > 1:
        aggregated["variance"] = {
            "overall": overall_variance,
            "dimensions": dimension_variance,
        }
    else:
        aggregated["variance"] = None

    for key in ["weights_applied"]:
        if key in iteration_results[0]:
            aggregated[key] = iteration_results[0][key]

    if hard_fail:
        aggregated["hard_fail_reasons"] = all_hard_fail_reasons
    elif "hard_fail_reasons" in iteration_results[0]:
        aggregated["hard_fail_reasons"] = iteration_results[0]["hard_fail_reasons"]

    return aggregated
