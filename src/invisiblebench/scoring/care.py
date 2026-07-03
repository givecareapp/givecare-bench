"""Care quality distribution scoring.

Pure functions that map scan rows into per-Care-quality pass/fail
distributions. Directional, not averaged — no cross-quality composite, no
merge with safety.

Care dimensions (from checks/care/<dimension>/):
    belonging | attunement | trauma_awareness | relational | advocacy

Usage::

    dim_map = check_dimensions()
    # per scenario
    care = scenario_care(record["mode_results"], dim_map)
    # across a model's scenarios
    dist = model_care_distribution([scenario_care(...) for record in model_records])
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from invisiblebench.evaluation.verifiers.base import PASS_VERDICT_VALUES, Verdict

CARE_DIMENSIONS: frozenset[str] = frozenset(
    {"belonging", "attunement", "trauma_awareness", "relational", "advocacy"}
)


def scenario_care(
    mode_results: list[dict[str, Any]],
    dim_map: dict[str, dict[str, str]],
) -> dict[str, dict[str, int]]:
    """Return per-Care-quality pass/total tallies for one scenario result.

    Args:
        mode_results: The ``mode_results`` list from a single scan row
                      (serialised VerdictResult dicts).
        dim_map:      Output of ``check_registry.check_dimensions()`` —
                      maps check_id → {"layer": ..., "dimension": ...}.

    Returns:
        Mapping of care dimension name → {"pass": int, "total": int}.
        Only dimensions with at least one eligible check are included.
        NOT_APPLICABLE and ineligible results are excluded from the tally.
    """
    tallies: dict[str, dict[str, int]] = defaultdict(lambda: {"pass": 0, "total": 0})

    for result in mode_results or []:
        if not result.get("eligible"):
            continue
        check_id = str(result.get("mode_id") or "")
        info = dim_map.get(check_id)
        if info is None or info.get("layer") != "care":
            continue
        dimension = info["dimension"]
        if dimension not in CARE_DIMENSIONS:
            continue

        verdict = str(result.get("verdict") or "")
        if verdict == Verdict.NOT_APPLICABLE.value:
            continue
        tallies[dimension]["total"] += 1
        if verdict in PASS_VERDICT_VALUES:
            tallies[dimension]["pass"] += 1

    # Convert defaultdict back to plain dict
    return {dim: dict(counts) for dim, counts in tallies.items()}


def model_care_distribution(
    scenario_cares: list[dict[str, dict[str, int]]],
) -> dict[str, dict[str, Any]]:
    """Aggregate per-scenario care dicts into pass-rate distribution per quality.

    Args:
        scenario_cares: List of ``scenario_care(...)`` return values, one per
                        scenario for a single model.

    Returns:
        Mapping of care dimension → {"pass_rate": float, "n": int, "directional": True}.
        ``n`` is the number of eligible check evaluations (not scenarios).
        ``directional: True`` signals that these values should not be averaged
        across qualities.  Only dimensions observed in at least one scenario
        are included.
    """
    totals: dict[str, dict[str, int]] = defaultdict(lambda: {"pass": 0, "total": 0})

    for care in scenario_cares:
        for dim, counts in care.items():
            totals[dim]["pass"] += counts.get("pass", 0)
            totals[dim]["total"] += counts.get("total", 0)

    result: dict[str, dict[str, Any]] = {}
    for dim, counts in sorted(totals.items()):
        total = counts["total"]
        pass_count = counts["pass"]
        result[dim] = {
            "pass_rate": round(pass_count / total, 4) if total else 0.0,
            "n": total,
            "directional": True,
        }
    return result
