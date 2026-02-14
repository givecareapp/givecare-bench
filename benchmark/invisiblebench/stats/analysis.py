"""Statistical analysis for benchmark results.

Computes score distributions, bootstrap confidence intervals,
hard-fail rates, success rates, and pairwise model comparisons.
"""

from __future__ import annotations

import json
import random
import statistics
from pathlib import Path
from typing import Any, Dict, List, Tuple

from invisiblebench.utils.dimension_aliases import (
    extract_numeric_dimension_value,
    normalize_category,
    normalize_dimension_scores,
)

# Default threshold matching ScenarioResult.SUCCESS_THRESHOLD
SUCCESS_THRESHOLD = 0.6


def _bootstrap_ci(
    scores: List[float],
    n_bootstrap: int = 10000,
    ci: float = 0.95,
    seed: int = 42,
) -> Tuple[float, float, float]:
    """Compute bootstrap confidence interval for the mean.

    Returns (mean, lower, upper).
    """
    if not scores:
        return (0.0, 0.0, 0.0)
    if len(scores) == 1:
        return (scores[0], scores[0], scores[0])

    rng = random.Random(seed)
    means = []
    n = len(scores)
    for _ in range(n_bootstrap):
        sample = [rng.choice(scores) for _ in range(n)]
        means.append(statistics.mean(sample))

    means.sort()
    alpha = (1.0 - ci) / 2.0
    lo_idx = int(alpha * n_bootstrap)
    hi_idx = int((1.0 - alpha) * n_bootstrap) - 1

    return (statistics.mean(scores), means[lo_idx], means[hi_idx])


def _bootstrap_proportion_ci(
    successes: int,
    total: int,
    n_bootstrap: int = 10000,
    ci: float = 0.95,
    seed: int = 42,
) -> Tuple[float, float, float]:
    """Bootstrap CI for a proportion (success rate).

    Returns (rate, lower, upper).
    """
    if total == 0:
        return (0.0, 0.0, 0.0)
    rate = successes / total
    if total == 1:
        return (rate, 0.0, 1.0)

    outcomes = [1] * successes + [0] * (total - successes)
    rng = random.Random(seed)
    rates: List[float] = []
    for _ in range(n_bootstrap):
        sample = [rng.choice(outcomes) for _ in range(total)]
        rates.append(sum(sample) / total)

    rates.sort()
    alpha = (1.0 - ci) / 2.0
    lo_idx = int(alpha * n_bootstrap)
    hi_idx = int((1.0 - alpha) * n_bootstrap) - 1

    return (rate, rates[lo_idx], rates[hi_idx])


def _is_success(result: Dict[str, Any]) -> bool:
    """Determine success from a result dict, using pre-computed field or fallback."""
    if "success" in result and result["success"] is not None:
        return bool(result["success"])
    # Fallback: gates passed + score >= threshold
    if result.get("hard_fail"):
        return False
    gates = result.get("gates", {})
    for gate in gates.values():
        if isinstance(gate, dict) and not gate.get("passed", True):
            return False
    return result.get("overall_score", 0.0) >= SUCCESS_THRESHOLD


def compute_success_rates(
    results: List[Dict[str, Any]],
    n_bootstrap: int = 10000,
) -> Dict[str, Any]:
    """Compute success rates by category with bootstrap CIs.

    Returns:
        {
            "categories": {category: {pass, fail, total, rate, ci_lo, ci_hi}},
            "total": {pass, fail, total, rate, ci_lo, ci_hi},
        }
    """
    by_cat: Dict[str, List[bool]] = {}
    for r in results:
        cat = normalize_category(r.get("category", r.get("tier", "unknown")))
        by_cat.setdefault(cat, []).append(_is_success(r))

    categories: Dict[str, Dict[str, Any]] = {}
    all_successes = 0
    all_total = 0
    for cat in sorted(by_cat.keys()):
        outcomes = by_cat[cat]
        n_pass = sum(outcomes)
        n_fail = len(outcomes) - n_pass
        rate, ci_lo, ci_hi = _bootstrap_proportion_ci(
            n_pass, len(outcomes), n_bootstrap
        )
        categories[cat] = {
            "pass": n_pass,
            "fail": n_fail,
            "total": len(outcomes),
            "rate": rate,
            "ci_lo": ci_lo,
            "ci_hi": ci_hi,
        }
        all_successes += n_pass
        all_total += len(outcomes)

    total_rate, total_ci_lo, total_ci_hi = _bootstrap_proportion_ci(
        all_successes, all_total, n_bootstrap
    )
    return {
        "categories": categories,
        "total": {
            "pass": all_successes,
            "fail": all_total - all_successes,
            "total": all_total,
            "rate": total_rate,
            "ci_lo": total_ci_lo,
            "ci_hi": total_ci_hi,
        },
    }


def compute_failure_buckets(results: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count failures by bucket (from failure_categories.primary_category).

    Only counts results where success=False.
    """
    buckets: Dict[str, int] = {}
    for r in results:
        if _is_success(r):
            continue
        fc = r.get("failure_categories", {})
        primary = fc.get("primary_category")
        if primary:
            buckets[primary] = buckets.get(primary, 0) + 1
        elif r.get("hard_fail"):
            reasons = r.get("hard_fail_reasons", [])
            if reasons:
                bucket = reasons[0].split(":")[0].strip().lower().replace(" ", "_")
                buckets[bucket] = buckets.get(bucket, 0) + 1
            else:
                buckets["unknown"] = buckets.get("unknown", 0) + 1
        elif r.get("status") == "error":
            buckets["error"] = buckets.get("error", 0) + 1
        else:
            buckets["low_score"] = buckets.get("low_score", 0) + 1
    return dict(sorted(buckets.items(), key=lambda x: -x[1]))


def _bootstrap_diff_ci(
    scores_a: List[float],
    scores_b: List[float],
    n_bootstrap: int = 10000,
    ci: float = 0.95,
    seed: int = 42,
) -> Tuple[float, float, float, bool]:
    """Bootstrap CI for the difference in means (A - B).

    Returns (mean_diff, lower, upper, significant).
    Significant = True if CI excludes zero.
    """
    if not scores_a or not scores_b:
        return (0.0, 0.0, 0.0, False)

    rng = random.Random(seed)
    diffs = []
    n_a, n_b = len(scores_a), len(scores_b)

    for _ in range(n_bootstrap):
        sample_a = [rng.choice(scores_a) for _ in range(n_a)]
        sample_b = [rng.choice(scores_b) for _ in range(n_b)]
        diffs.append(statistics.mean(sample_a) - statistics.mean(sample_b))

    diffs.sort()
    alpha = (1.0 - ci) / 2.0
    lo_idx = int(alpha * n_bootstrap)
    hi_idx = int((1.0 - alpha) * n_bootstrap) - 1

    mean_diff = statistics.mean(scores_a) - statistics.mean(scores_b)
    lo, hi = diffs[lo_idx], diffs[hi_idx]
    significant = lo > 0 or hi < 0  # CI excludes zero

    return (mean_diff, lo, hi, significant)


def load_results(results_path: str) -> List[Dict[str, Any]]:
    """Load results from a JSON file.

    Handles both formats:
    - List of scenario results (all_results.json)
    - Dict with 'scenarios' key (leaderboard_ready/)
    """
    with open(results_path) as f:
        data = json.load(f)

    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "scenarios" in data:
        model = data.get("model_name", data.get("model", "Unknown"))
        for s in data["scenarios"]:
            s.setdefault("model", model)
        return data["scenarios"]
    return []


def _get_category(result: Dict[str, Any]) -> str:
    """Extract category from a result dict."""
    return normalize_category(result.get("category", result.get("tier")))


def compute_stats(results_path: str, n_bootstrap: int = 10000) -> Dict[str, Any]:
    """Compute full statistical analysis from results.

    Args:
        results_path: Path to all_results.json or leaderboard_ready/ directory.
        n_bootstrap: Number of bootstrap samples for CIs.

    Returns dict with:
        - models: per-model stats
        - pairwise: pairwise comparisons
        - category_stats: per-category distributions
    """
    path = Path(results_path)

    # Load all results
    all_results: List[Dict[str, Any]] = []
    if path.is_dir():
        for f in sorted(path.glob("*.json")):
            all_results.extend(load_results(str(f)))
    else:
        all_results = load_results(str(path))

    if not all_results:
        return {"error": "No results loaded", "models": {}}

    # Group by model
    by_model: Dict[str, List[Dict[str, Any]]] = {}
    for r in all_results:
        model = r.get("model", "Unknown")
        by_model.setdefault(model, []).append(r)

    # Per-model stats
    model_stats: Dict[str, Dict[str, Any]] = {}
    for model, scenarios in by_model.items():
        scores = [s.get("overall_score", 0.0) for s in scenarios]
        hard_fails = [s for s in scenarios if s.get("hard_fail", False)]
        errors = [s for s in scenarios if s.get("status") == "error"]

        mean, ci_lo, ci_hi = _bootstrap_ci(scores, n_bootstrap)

        # By category
        by_cat: Dict[str, List[float]] = {}
        hf_by_cat: Dict[str, int] = {}
        total_by_cat: Dict[str, int] = {}
        for s in scenarios:
            cat = _get_category(s)
            by_cat.setdefault(cat, []).append(s.get("overall_score", 0.0))
            total_by_cat[cat] = total_by_cat.get(cat, 0) + 1
            if s.get("hard_fail", False):
                hf_by_cat[cat] = hf_by_cat.get(cat, 0) + 1

        cat_stats = {}
        for cat, cat_scores in by_cat.items():
            cat_mean = statistics.mean(cat_scores)
            cat_std = statistics.stdev(cat_scores) if len(cat_scores) > 1 else 0.0
            cat_stats[cat] = {
                "mean": round(cat_mean, 3),
                "std": round(cat_std, 3),
                "min": round(min(cat_scores), 3),
                "max": round(max(cat_scores), 3),
                "count": len(cat_scores),
                "hard_fails": hf_by_cat.get(cat, 0),
                "ceiling": cat_mean > 0.9,
                "floor": cat_mean < 0.5,
            }

        # Dimension score averages
        dim_avgs: Dict[str, float] = {}
        dim_keys = set()
        for s in scenarios:
            dims = normalize_dimension_scores(s.get("dimensions", s.get("dimension_scores", {})))
            dim_keys.update(dims.keys())
        for dim in sorted(dim_keys):
            vals = []
            for s in scenarios:
                dims = normalize_dimension_scores(s.get("dimensions", s.get("dimension_scores", {})))
                if dim in dims:
                    value = extract_numeric_dimension_value(dims[dim])
                    if isinstance(value, (int, float)):
                        vals.append(float(value))
            if vals:
                dim_avgs[dim] = round(statistics.mean(vals), 3)

        # Success rate (v2.1 explicit field) + derived fallback for legacy datasets.
        explicit_success_values = [s.get("success") for s in scenarios if s.get("success") is not None]
        success_count = sum(1 for v in explicit_success_values if v is True)
        success_rate = round(success_count / len(scenarios), 3) if scenarios else 0.0

        derived_success_count = sum(1 for s in scenarios if _is_success(s))
        derived_success_rate = round(derived_success_count / len(scenarios), 3) if scenarios else 0.0

        if explicit_success_values:
            success_source = "explicit"
        else:
            success_source = "derived"

        # Judge model (v2.1) — pick from first scenario that has one
        judge_model = None
        for s in scenarios:
            jm = s.get("judge_model")
            if jm:
                judge_model = jm
                break

        model_stats[model] = {
            "n_scenarios": len(scenarios),
            "overall_mean": round(mean, 3),
            "ci_95": [round(ci_lo, 3), round(ci_hi, 3)],
            "std": round(statistics.stdev(scores), 3) if len(scores) > 1 else 0.0,
            "hard_fail_count": len(hard_fails),
            "hard_fail_rate": round(len(hard_fails) / len(scenarios), 3) if scenarios else 0.0,
            "error_count": len(errors),
            "success_count": success_count,
            "success_rate": success_rate,
            "derived_success_count": derived_success_count,
            "derived_success_rate": derived_success_rate,
            "success_source": success_source,
            "judge_model": judge_model,
            "categories": cat_stats,
            "dimensions": dim_avgs,
        }

    # Pairwise comparisons
    model_names = sorted(by_model.keys())
    pairwise: List[Dict[str, Any]] = []

    for i, model_a in enumerate(model_names):
        for j, model_b in enumerate(model_names):
            if i >= j:
                continue
            scores_a = [s.get("overall_score", 0.0) for s in by_model[model_a]]
            scores_b = [s.get("overall_score", 0.0) for s in by_model[model_b]]

            diff, lo, hi, sig = _bootstrap_diff_ci(scores_a, scores_b, n_bootstrap)

            pairwise.append(
                {
                    "model_a": model_a,
                    "model_b": model_b,
                    "diff": round(diff, 3),
                    "ci_95": [round(lo, 3), round(hi, 3)],
                    "significant": sig,
                    "direction": (
                        f"{model_a} > {model_b}" if diff > 0 else f"{model_b} > {model_a}"
                    ),
                }
            )

    # Sort pairwise by absolute difference (largest first)
    pairwise.sort(key=lambda x: abs(x["diff"]), reverse=True)

    # Check for ceiling/floor effects across models
    warnings: List[str] = []
    all_categories = set()
    for ms in model_stats.values():
        all_categories.update(ms.get("categories", {}).keys())

    for cat in sorted(all_categories):
        cat_means = []
        for ms in model_stats.values():
            cs = ms.get("categories", {}).get(cat)
            if cs:
                cat_means.append(cs["mean"])
        if cat_means:
            above_90 = sum(1 for m in cat_means if m > 0.9)
            if above_90 / len(cat_means) > 0.8:
                warnings.append(
                    f"Ceiling effect in '{cat}': {above_90}/{len(cat_means)} models score >0.9"
                )
            below_50 = sum(1 for m in cat_means if m < 0.5)
            if below_50 / len(cat_means) > 0.8:
                warnings.append(
                    f"Floor effect in '{cat}': {below_50}/{len(cat_means)} models score <0.5"
                )

    return {
        "models": model_stats,
        "pairwise": pairwise,
        "warnings": warnings,
        "n_models": len(model_stats),
        "n_bootstrap": n_bootstrap,
    }


def format_stats_report(stats: Dict[str, Any]) -> str:
    """Format stats as a terminal-friendly report."""
    lines: List[str] = []
    models = stats.get("models", {})
    pairwise = stats.get("pairwise", [])
    warnings = stats.get("warnings", [])

    if not models:
        return "No results to analyze."

    # Header
    lines.append(f"Statistical Analysis ({len(models)} models)")

    # Show judge model if available
    judge_models = {ms.get("judge_model") for ms in models.values() if ms.get("judge_model")}
    if judge_models:
        lines.append(f"Judge: {', '.join(sorted(judge_models))}")
    lines.append("")

    # Score Distribution by Category
    lines.append("Score Distribution by Category")
    all_cats = set()
    for ms in models.values():
        all_cats.update(ms.get("categories", {}).keys())
    cats = sorted(all_cats)

    # Header row
    header = f"{'Model':<24}"
    for cat in cats:
        header += f" {cat[:8]:>10}"
    header += f" {'Overall':>18}"
    lines.append(header)
    lines.append("─" * len(header))

    # Sort by overall score
    sorted_models = sorted(models.items(), key=lambda x: x[1]["overall_mean"], reverse=True)

    for model, ms in sorted_models:
        row = f"{model[:23]:<24}"
        for cat in cats:
            cs = ms.get("categories", {}).get(cat)
            if cs:
                row += f" {cs['mean']:.2f}±{cs['std']:.2f}"
            else:
                row += f" {'--':>10}"
        ci = ms["ci_95"]
        row += f"  {ms['overall_mean']:.2f} [{ci[0]:.2f}, {ci[1]:.2f}]"
        lines.append(row)

    # Hard-Fail Rates
    lines.append("")
    lines.append("Hard-Fail Rates")
    header = f"{'Model':<24}"
    for cat in cats:
        header += f" {cat[:8]:>10}"
    header += f" {'Total':>10}"
    lines.append(header)
    lines.append("─" * len(header))

    for model, ms in sorted_models:
        row = f"{model[:23]:<24}"
        total_hf = 0
        total_n = 0
        for cat in cats:
            cs = ms.get("categories", {}).get(cat)
            if cs:
                hf = cs.get("hard_fails", 0)
                n = cs["count"]
                total_hf += hf
                total_n += n
                row += f" {hf}/{n:>7}"
            else:
                row += f" {'--':>10}"
        pct = f"({total_hf/total_n*100:.0f}%)" if total_n > 0 else ""
        row += f" {total_hf}/{total_n} {pct:>5}"
        lines.append(row)

    # Success Rates (v2.1 explicit field, with derived fallback for legacy datasets)
    has_explicit_success = any(ms.get("success_source") == "explicit" for ms in models.values())
    has_any_success_data = bool(models)
    if has_any_success_data:
        lines.append("")
        if has_explicit_success:
            lines.append("Success Rates")
        else:
            lines.append("Success Rates (derived)")
        lines.append(f"{'Model':<24} {'Success':>10} {'Rate':>8}")
        lines.append("─" * 44)
        for model, ms in sorted_models:
            n = ms.get("n_scenarios", 0)
            if ms.get("success_source") == "explicit":
                sc = ms.get("success_count", 0)
                sr = ms.get("success_rate", 0.0)
            else:
                sc = ms.get("derived_success_count", 0)
                sr = ms.get("derived_success_rate", 0.0)
            lines.append(f"{model[:23]:<24} {sc}/{n:>7}  {sr*100:>5.1f}%")

    # Pairwise Comparisons (significant only)
    sig_pairs = [p for p in pairwise if p["significant"]]
    if sig_pairs:
        lines.append("")
        lines.append(f"Significant Pairwise Differences ({len(sig_pairs)}/{len(pairwise)} pairs)")
        lines.append(f"{'Comparison':<45} {'Diff':>7}  {'95% CI':>16}")
        lines.append("─" * 72)
        for p in sig_pairs[:15]:  # Top 15
            ci = p["ci_95"]
            lines.append(
                f"{p['direction']:<45} {p['diff']:>+.3f}  [{ci[0]:>+.3f}, {ci[1]:>+.3f}]"
            )
    else:
        lines.append("")
        lines.append("No statistically significant pairwise differences found.")

    # Warnings
    if warnings:
        lines.append("")
        lines.append("Warnings")
        for w in warnings:
            lines.append(f"  ! {w}")

    return "\n".join(lines)


def format_stats_markdown(stats: Dict[str, Any]) -> str:
    """Format stats as markdown for file output."""
    lines: List[str] = []
    models = stats.get("models", {})
    pairwise = stats.get("pairwise", [])
    warnings = stats.get("warnings", [])

    lines.append(f"# Statistical Analysis ({len(models)} models)")
    lines.append("")

    # Show judge model if available
    judge_models = {ms.get("judge_model") for ms in models.values() if ms.get("judge_model")}
    if judge_models:
        lines.append(f"**Judge model:** {', '.join(sorted(judge_models))}")
        lines.append("")

    # Score Distribution
    lines.append("## Score Distribution by Category")
    lines.append("")

    all_cats = set()
    for ms in models.values():
        all_cats.update(ms.get("categories", {}).keys())
    cats = sorted(all_cats)

    header = "| Model |"
    sep = "|-------|"
    for cat in cats:
        header += f" {cat.capitalize()} |"
        sep += "--------|"
    header += " Overall (95% CI) |"
    sep += "-----------------|"
    lines.append(header)
    lines.append(sep)

    sorted_models = sorted(models.items(), key=lambda x: x[1]["overall_mean"], reverse=True)
    for model, ms in sorted_models:
        row = f"| {model} |"
        for cat in cats:
            cs = ms.get("categories", {}).get(cat)
            if cs:
                row += f" {cs['mean']:.2f} ± {cs['std']:.2f} |"
            else:
                row += " -- |"
        ci = ms["ci_95"]
        row += f" **{ms['overall_mean']:.2f}** [{ci[0]:.2f}, {ci[1]:.2f}] |"
        lines.append(row)

    # Hard-Fail Rates
    lines.append("")
    lines.append("## Hard-Fail Rates")
    lines.append("")
    header = "| Model |"
    sep = "|-------|"
    for cat in cats:
        header += f" {cat.capitalize()} |"
        sep += "--------|"
    header += " Total |"
    sep += "-------|"
    lines.append(header)
    lines.append(sep)

    for model, ms in sorted_models:
        row = f"| {model} |"
        total_hf = 0
        total_n = 0
        for cat in cats:
            cs = ms.get("categories", {}).get(cat)
            if cs:
                hf = cs.get("hard_fails", 0)
                n = cs["count"]
                total_hf += hf
                total_n += n
                row += f" {hf}/{n} |"
            else:
                row += " -- |"
        pct = f"({total_hf/total_n*100:.0f}%)" if total_n > 0 else ""
        row += f" {total_hf}/{total_n} {pct} |"
        lines.append(row)

    # Pairwise
    lines.append("")
    lines.append("## Pairwise Comparisons")
    lines.append("")
    lines.append("| Comparison | Diff | 95% CI | Significant |")
    lines.append("|------------|------|--------|-------------|")
    for p in pairwise[:20]:
        ci = p["ci_95"]
        sig = "Yes" if p["significant"] else "No"
        lines.append(
            f"| {p['direction']} | {p['diff']:+.3f} | [{ci[0]:+.3f}, {ci[1]:+.3f}] | {sig} |"
        )

    # Warnings
    if warnings:
        lines.append("")
        lines.append("## Warnings")
        lines.append("")
        for w in warnings:
            lines.append(f"- {w}")

    return "\n".join(lines)
