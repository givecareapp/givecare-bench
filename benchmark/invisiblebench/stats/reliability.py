"""Scorer inter-rater reliability analysis.

Runs LLM scorers multiple times on the same transcripts and computes
agreement metrics (Cohen's kappa / Krippendorff's alpha) to measure
scorer consistency.
"""

from __future__ import annotations

import json
import random
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional

from invisiblebench.stats import cohen_kappa_continuous as _cohen_kappa_continuous
from invisiblebench.utils.dimension_aliases import (
    V2_DIMENSIONS,
    extract_numeric_dimension_value,
    normalize_dimension_scores,
)


def _pairwise_kappas(
    all_scores: List[List[float]], n_bins: int = 5
) -> List[float]:
    """Compute Cohen's kappa for all pairs of runs."""
    kappas = []
    for i in range(len(all_scores)):
        for j in range(i + 1, len(all_scores)):
            k = _cohen_kappa_continuous(all_scores[i], all_scores[j], n_bins)
            kappas.append(k)
    return kappas


def _mean_absolute_deviation(all_scores: List[List[float]]) -> float:
    """Mean absolute deviation across runs for each item."""
    if not all_scores or not all_scores[0]:
        return 0.0
    n_items = len(all_scores[0])
    total = 0.0
    for item_idx in range(n_items):
        item_scores = [run[item_idx] for run in all_scores]
        mean = statistics.mean(item_scores)
        total += statistics.mean(abs(s - mean) for s in item_scores)
    return total / n_items


def _interpret_kappa(k: float) -> str:
    """Interpret kappa value using Landis & Koch scale."""
    if k >= 0.81:
        return "Almost Perfect"
    if k >= 0.61:
        return "Substantial"
    if k >= 0.41:
        return "Moderate"
    if k >= 0.21:
        return "Fair"
    if k >= 0.0:
        return "Slight"
    return "Poor"


LLM_SCORERS = V2_DIMENSIONS
DETERMINISTIC_SCORERS: List[str] = []


def find_transcripts(
    results_path: str, sample_size: int = 10
) -> List[Dict[str, Any]]:
    """Find transcript files from a results directory or file.

    Returns list of dicts with 'transcript_path', 'scenario_path', 'scenario_id'.
    """
    results_file = Path(results_path)
    if results_file.is_file():
        results_dir = results_file.parent
    else:
        results_dir = results_file

    # Find transcripts directory
    transcripts_dir = results_dir / "transcripts"
    if not transcripts_dir.exists():
        # Try parent
        transcripts_dir = results_dir.parent / "transcripts"

    if not transcripts_dir.exists():
        return []

    # Find all .jsonl transcript files
    transcripts = sorted(transcripts_dir.glob("*.jsonl"))
    if not transcripts:
        return []

    # Sample
    if len(transcripts) > sample_size:
        transcripts = random.sample(transcripts, sample_size)

    items = []
    for t in transcripts:
        items.append(
            {
                "transcript_path": str(t),
                "scenario_id": t.stem,
            }
        )
    return items


def run_reliability(
    results_path: str,
    n_runs: int = 5,
    sample_size: int = 10,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Run reliability analysis on existing transcripts.

    Scores each transcript n_runs times with cache disabled, then computes
    inter-rater agreement.

    Returns dict with per-dimension kappa scores and raw data.
    """
    from invisiblebench.api.client import (
        _SCORER_RESPONSE_CACHE,
    )
    from invisiblebench.evaluation.orchestrator import ScoringOrchestrator

    # Find transcripts
    items = find_transcripts(results_path, sample_size)
    if not items:
        return {"error": "No transcripts found", "dimensions": {}}

    # Find scenario files for these transcripts
    root = Path(__file__).parent.parent.parent.parent
    scenarios_dir = root / "benchmark" / "scenarios"
    rules_path = str(root / "benchmark" / "configs" / "rules" / "base.yaml")
    scoring_config = str(root / "benchmark" / "configs" / "scoring.yaml")

    # Map scenario IDs to scenario paths
    scenario_files = {}
    for f in scenarios_dir.rglob("*.json"):
        if "archive" in str(f) or "confidential" in str(f):
            continue
        try:
            data = json.loads(f.read_text())
            sid = data.get("scenario_id", f.stem)
            scenario_files[sid] = str(f)
            # Also map by stem
            scenario_files[f.stem] = str(f)
        except (json.JSONDecodeError, KeyError):
            continue

    # Run scoring multiple times
    dimension_runs: Dict[str, List[List[float]]] = {d: [] for d in LLM_SCORERS}

    for _run_idx in range(n_runs):
        # Clear cache before each run to force fresh LLM calls
        _SCORER_RESPONSE_CACHE._data.clear()

        orchestrator = ScoringOrchestrator(
            scoring_config_path=scoring_config,
            enable_state_persistence=False,
            enable_llm=True,
        )

        run_scores: Dict[str, List[float]] = {d: [] for d in LLM_SCORERS}

        for item in items:
            # Find matching scenario
            scenario_path = None
            sid = item["scenario_id"]
            # Try direct match, then partial match
            for key in [sid, sid.split("_", 1)[-1] if "_" in sid else sid]:
                if key in scenario_files:
                    scenario_path = scenario_files[key]
                    break

            if not scenario_path:
                # Skip if we can't find the scenario
                for dim in LLM_SCORERS:
                    run_scores[dim].append(0.0)
                continue

            try:
                result = orchestrator.score(
                    transcript_path=item["transcript_path"],
                    scenario_path=scenario_path,
                    rules_path=rules_path,
                )
                dim_scores = normalize_dimension_scores(result.get("dimension_scores", {}))
                for dim in LLM_SCORERS:
                    value = extract_numeric_dimension_value(dim_scores.get(dim, 0.0))
                    run_scores[dim].append(float(value) if isinstance(value, (int, float)) else 0.0)
            except Exception:
                for dim in LLM_SCORERS:
                    run_scores[dim].append(0.0)

        for dim in LLM_SCORERS:
            dimension_runs[dim].append(run_scores[dim])

    # Compute agreement metrics
    results: Dict[str, Any] = {"dimensions": {}, "n_runs": n_runs, "n_items": len(items)}

    for dim in LLM_SCORERS:
        runs = dimension_runs[dim]
        if not runs or not runs[0]:
            results["dimensions"][dim] = {"kappa": 0.0, "interpretation": "N/A"}
            continue

        kappas = _pairwise_kappas(runs)
        mean_kappa = statistics.mean(kappas) if kappas else 0.0
        mad = _mean_absolute_deviation(runs)

        results["dimensions"][dim] = {
            "kappa": round(mean_kappa, 3),
            "interpretation": _interpret_kappa(mean_kappa),
            "mean_abs_deviation": round(mad, 4),
            "pairwise_kappas": [round(k, 3) for k in kappas],
        }

    for dim in DETERMINISTIC_SCORERS:
        results["dimensions"][dim] = {
            "kappa": 1.0,
            "interpretation": "Deterministic",
            "mean_abs_deviation": 0.0,
        }

    # Save raw data if output_dir specified
    if output_dir:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        with open(out / "reliability_raw.json", "w") as f:
            json.dump(
                {
                    "n_runs": n_runs,
                    "n_items": len(items),
                    "items": [i["scenario_id"] for i in items],
                    "dimension_runs": dimension_runs,
                    "results": results,
                },
                f,
                indent=2,
            )

    return results


def format_reliability_report(results: Dict[str, Any]) -> str:
    """Format reliability results as a terminal-friendly table."""
    lines = []
    lines.append(
        f"Scorer Reliability Report ({results.get('n_runs', '?')} runs "
        f"x {results.get('n_items', '?')} transcripts)"
    )
    lines.append("")
    lines.append(f"{'Dimension':<18} {'Kappa':>7}  {'MAD':>7}  {'Interpretation'}")
    lines.append("─" * 60)

    dims = results.get("dimensions", {})

    # Show canonical scorers first, then any extra/legacy dimensions.
    ordered_dims: List[str] = []
    for dim in LLM_SCORERS + DETERMINISTIC_SCORERS:
        if dim in dims:
            ordered_dims.append(dim)
    for dim in sorted(dims.keys()):
        if dim not in ordered_dims:
            ordered_dims.append(dim)

    for dim in ordered_dims:
        d = dims[dim]
        kappa = d.get("kappa", 0.0)
        mad = d.get("mean_abs_deviation", 0.0)
        interp = d.get("interpretation", "N/A")
        lines.append(f"{dim:<18} {kappa:>7.3f}  {mad:>7.4f}  {interp}")

    return "\n".join(lines)
