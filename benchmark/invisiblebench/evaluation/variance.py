"""
Variance calculation utilities for iteration support.

Calculates variance metrics across multiple scoring iterations.
"""
from __future__ import annotations

import statistics
from typing import Any, Dict, List, Optional


def calculate_cv(mean: float, std_dev: float) -> Optional[float]:
    """
    Calculate coefficient of variation (CV).

    CV = std_dev / mean

    Args:
        mean: Mean value
        std_dev: Standard deviation

    Returns:
        CV value or None if undefined (mean=0 or near-zero)

    Raises:
        ValueError: If mean or std_dev is negative
    """
    if mean < 0:
        raise ValueError("Mean cannot be negative")
    if std_dev < 0:
        raise ValueError("Standard deviation cannot be negative")

    # Handle zero std_dev (always 0 CV)
    if std_dev == 0.0:
        return 0.0

    # Handle zero mean (CV undefined unless std_dev is also 0)
    if mean == 0.0:
        return 0.0 if std_dev == 0.0 else None

    # Handle near-zero mean (CV would be unstable)
    if mean < 0.01:
        return None

    return std_dev / mean


def calculate_variance(scores: List[float]) -> Dict[str, Any]:
    """
    Calculate variance metrics for a list of scores.

    Args:
        scores: List of numeric scores

    Returns:
        Dictionary with mean, std_dev, min, max, cv

    Raises:
        ValueError: If scores list is empty
        TypeError: If scores contain non-numeric values
    """
    if not scores:
        raise ValueError("Scores list must contain at least one score")

    # Validate numeric types
    for score in scores:
        if not isinstance(score, (int, float)):
            raise TypeError(f"All scores must be numeric, got {type(score)}")

    mean = statistics.mean(scores)
    min_score = min(scores)
    max_score = max(scores)

    # Calculate std_dev (use stdev for sample, or 0 for N=1)
    if len(scores) == 1:
        std_dev = 0.0
    else:
        std_dev = statistics.stdev(scores)

    # Calculate CV
    cv = calculate_cv(mean, std_dev)

    return {
        "mean": mean,
        "std_dev": std_dev,
        "min": min_score,
        "max": max_score,
        "cv": cv,
    }


def calculate_dimension_variance(
    dimension_scores_list: List[Dict[str, Any]]
) -> Dict[str, Dict[str, Any]]:
    """
    Calculate variance metrics for each dimension across iterations.

    Args:
        dimension_scores_list: List of dimension score dictionaries from each iteration
            Example: [{"memory": {"score": 0.8}, "trauma": {"score": 0.7}}, ...]

    Returns:
        Dictionary mapping dimension names to variance metrics

    Raises:
        ValueError: If dimension_scores_list is empty
    """
    if not dimension_scores_list:
        raise ValueError("dimension_scores_list cannot be empty")

    # Collect all dimension names
    all_dimensions = set()
    for dim_scores in dimension_scores_list:
        all_dimensions.update(dim_scores.keys())

    # Calculate variance for each dimension
    result = {}
    for dimension in all_dimensions:
        # Extract scores for this dimension across iterations
        scores = []
        for dim_scores in dimension_scores_list:
            if dimension in dim_scores and "score" in dim_scores[dimension]:
                scores.append(dim_scores[dimension]["score"])

        # Only calculate variance if we have scores
        if scores:
            result[dimension] = calculate_variance(scores)

    return result


def aggregate_iteration_results(
    iteration_results: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Aggregate results from multiple iterations into final report.

    Args:
        iteration_results: List of scoring results from each iteration

    Returns:
        Aggregated results with mean scores and variance metrics

    Raises:
        ValueError: If iteration_results is empty
    """
    if not iteration_results:
        raise ValueError("iteration_results cannot be empty")

    num_iterations = len(iteration_results)

    # Extract overall scores
    overall_scores = [result["overall_score"] for result in iteration_results]

    # Extract dimension scores
    dimension_scores_list = [result["dimension_scores"] for result in iteration_results]

    # Calculate overall variance
    overall_variance = calculate_variance(overall_scores) if num_iterations > 1 else None

    # Calculate dimension variance
    dimension_variance = (
        calculate_dimension_variance(dimension_scores_list)
        if num_iterations > 1
        else None
    )

    # Calculate mean scores for final result
    mean_overall_score = statistics.mean(overall_scores)

    # Calculate mean dimension scores
    all_dimensions = set()
    for dim_scores in dimension_scores_list:
        all_dimensions.update(dim_scores.keys())

    mean_dimension_scores = {}
    for dimension in all_dimensions:
        scores = []
        for dim_scores in dimension_scores_list:
            if dimension in dim_scores and "score" in dim_scores[dimension]:
                scores.append(dim_scores[dimension]["score"])

        if scores:
            mean_score = statistics.mean(scores)
            # Preserve structure from first iteration, update score
            mean_dimension_scores[dimension] = iteration_results[0]["dimension_scores"][
                dimension
            ].copy()
            mean_dimension_scores[dimension]["score"] = mean_score

    # Check if any iteration had hard_fail
    hard_fail = any(result.get("hard_fail", False) for result in iteration_results)

    # Preserve metadata from first iteration
    metadata = iteration_results[0].get("metadata", {}).copy()
    metadata["iterations_run"] = num_iterations

    # Build aggregated result
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

    # Add variance section if multiple iterations
    if num_iterations > 1:
        aggregated["variance"] = {
            "overall": overall_variance,
            "dimensions": dimension_variance,
        }
    else:
        aggregated["variance"] = None

    # Preserve other fields from first iteration
    for key in ["weights_applied", "hard_fail_reasons"]:
        if key in iteration_results[0]:
            aggregated[key] = iteration_results[0][key]

    return aggregated
