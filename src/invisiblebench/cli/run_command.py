#!/usr/bin/env python3
"""RUN verb — execute models against scenarios and persist run artifacts.

Extracted whole from runner.py; run_benchmark() itself is still the
~1,000-line orchestrator that DESIGN.md names as the decomposition target
for 4.0. This module gives the RUN verb its own address without rewriting
logic pre-4.0.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import statistics
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from invisiblebench.api.client import ModelAPIClient
    from invisiblebench.evaluation.mode_engine import ModeEngine

from dotenv import load_dotenv

from invisiblebench.adapters.givecare_v2 import (
    MODEL_ID as GIVECARE_V2_MODEL_ID,
)
from invisiblebench.adapters.givecare_v2 import (
    MODEL_NAME as GIVECARE_V2_MODEL_NAME,
)
from invisiblebench.adapters.givecare_v2 import (
    PROVIDER_NAME as GIVECARE_V2_PROVIDER_NAME,
)
from invisiblebench.adapters.givecare_v2 import (
    PROVIDER_VERSION as GIVECARE_V2_PROVIDER_VERSION,
)
from invisiblebench.adapters.givecare_v2 import (
    GiveCareV2Provider,
    get_category_from_path,
    get_scenario_title,
)
from invisiblebench.adapters.givecare_v2 import (
    get_scenarios as get_givecare_scenarios,
)
from invisiblebench.adapters.givecare_v2 import (
    run_scenario as run_givecare_v2_scenario,
)
from invisiblebench.api.client import (
    DEFAULT_SCORER_MODEL,
    InsufficientCreditsError,
    cost_tracker,
    resolve_scorer_model,
)
from invisiblebench.cli._console import make_console
from invisiblebench.cli.diff import (
    aggregate_results_by_model as aggregate_results_by_model,  # re-exported: tests import from this module
)
from invisiblebench.cli.diff import (
    compute_run_diff as compute_run_diff,  # re-exported: tests import from this module
)
from invisiblebench.cli.diff import (
    load_run_results as load_run_results,  # re-exported: tests import from this module
)
from invisiblebench.cli.display import ScenarioDisplay, print_banner
from invisiblebench.cli.result_helpers import (
    _compute_success as _compute_success,  # re-exported: tests import from this module
)
from invisiblebench.cli.result_helpers import (
    _make_error_result,
    _make_harness_error_result,
    _safe_load_scenario_data,
    _v3_gate_payload,
)
from invisiblebench.cli.transcript import (
    _run_single_scenario,
    evaluate_scenario_async,
)
from invisiblebench.cli.transcript import (
    write_detailed_outputs as write_detailed_outputs,  # re-exported: tests import from this module
)
from invisiblebench.evaluation.scoring_contract import coverage_floor
from invisiblebench.models.config import MODELS_FULL as CONFIG_MODELS_FULL
from invisiblebench.models.results import SUCCESS_THRESHOLD, is_result_success
from invisiblebench.results_io import write_json, write_model_results
from invisiblebench.run_audit import audit_results_source, render_audit_markdown
from invisiblebench.utils.benchmark_inventory import (
    collect_scenario_paths,
    get_private_confidential_dir,
    get_project_root,
    scenario_category_for_path,
)
from invisiblebench.utils.dimension_aliases import (
    extract_numeric_dimension_value,
    normalize_dimension_scores,
)
from invisiblebench.utils.manifest import generate_manifest, write_manifest
from invisiblebench.version import V3_RESULT_CONTRACT_VERSION

try:
    import threading

    from rich.live import Live
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
    )
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

logger = logging.getLogger(__name__)

# Shared NO_COLOR/isatty-honoring Console factory (returns None without rich).
Console = make_console

load_dotenv()

# Token estimates per category for cost calculation
# Calibrated from actual benchmark runs (Jan 2026) - includes system prompt,
# conversation history growth, and scorer LLM calls
TOKEN_ESTIMATES = {
    1: {"input": 5500, "output": 1400},  # 3-5 turns
    2: {"input": 14000, "output": 3300},  # 8-12 turns
    3: {"input": 27000, "output": 6000},  # 20+ turns, multi-session
}

# Scorer LLM costs (per scenario) — not included in model-under-test tokens
# Scorer calls: safety (1 ref + 3 sampled), compliance (3), regard (LLM/cache-aware),
# coordination (mostly deterministic, adds false_refusal signal), plus memory (deterministic).
# Avg estimate: ~4-6 LLM calls/scenario
SCORER_MODEL_COSTS = {
    "flash_lite": {"cost_per_m_input": 0.10, "cost_per_m_output": 0.40},  # gemini-2.5-flash-lite
    "flash": {"cost_per_m_input": 0.30, "cost_per_m_output": 2.50},       # gemini-2.5-flash (safety ref)
}
# Per-scenario scorer token estimates (all scorers combined)
SCORER_CALLS_PER_SCENARIO = 8       # avg uncached LLM calls (flash-lite)
SCORER_REF_CALLS_PER_SCENARIO = 1   # safety reference call (flash)
SCORER_TOKENS_PER_CALL = {"input": 4000, "output": 800}

# SYSTEM_PROMPT is imported from invisiblebench.cli.transcript

MODELS_FULL = [model.model_dump() for model in CONFIG_MODELS_FULL]


def _load_transcript_jsonl(transcript_path: Path) -> list[dict[str, Any]]:
    transcript: list[dict[str, Any]] = []
    with transcript_path.open(encoding="utf-8") as fh:
        for line_number, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{transcript_path}:{line_number}: invalid transcript JSONL: {exc}"
                ) from exc
            if isinstance(row, dict):
                transcript.append(row)
    if not transcript:
        raise ValueError(f"{transcript_path}: transcript is empty")
    return transcript


# _v3_gate_payload, _compute_success, _build_scoring_summary, _make_error_result,
# _make_harness_error_result, _safe_load_scenario_data moved to result_helpers.py


class ModeEngineScoringAdapter:
    """Adapter exposing the runner's .score(...) contract on top of V3 ModeEngine."""

    def __init__(
        self,
        api_client: ModelAPIClient | None = None,
        *,
        llm_model: str | None = None,
        engine: ModeEngine | None = None,
    ) -> None:
        self.llm_model = llm_model or (
            resolve_scorer_model(api_client, "scorer", DEFAULT_SCORER_MODEL)
            if api_client is not None
            else DEFAULT_SCORER_MODEL
        )
        if engine is None:
            from invisiblebench.evaluation.mode_engine import ModeEngine

            engine = ModeEngine(llm_api_client=api_client, llm_model=self.llm_model)
        self.engine = engine

    def score(
        self,
        *,
        transcript_path: str,
        scenario_path: str,
        rules_path: str | None = None,
        model_name: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        del rules_path, model_name
        transcript = _load_transcript_jsonl(Path(transcript_path))
        with open(scenario_path, encoding="utf-8") as fh:
            scenario = json.load(fh)

        output = self.engine.evaluate(transcript=transcript, scenario=scenario)
        result = output.to_dict()
        mode_results = result.get("mode_results") or []
        raw_reasons = result.get("hard_fail_reasons") or []
        str_reasons = [
            r.get("mode_id", r.get("reason", "unknown")) if isinstance(r, dict) else str(r)
            for r in raw_reasons
        ]
        result["hard_fail_reasons"] = str_reasons
        result.update(
            {
                "run_id": run_id,
                "judge_model": self.llm_model,
                "judge_prompt_hash": None,
                "judge_temp": None,
                "contract_version": V3_RESULT_CONTRACT_VERSION,
                "gates": _v3_gate_payload(
                    mode_results,
                    raw_reasons,
                ),
                "dimensions": result.get("dimension_scores") or {},
                "transcript_path": transcript_path,
                "coverage": {
                    "eligible": output.eligible_count,
                    "resolved": output.resolved_count,
                    "unclear": output.unclear_count,
                    "rate": output.coverage_rate,
                },
            }
        )

        # Minimum coverage gate: below the floor (scoring.yaml coverage_floor)
        # the result is invalid; the QA gate independently blocks publication.
        floor = coverage_floor()
        if output.coverage_rate < floor:
            result["coverage_invalid"] = True
            result["coverage_invalid_reason"] = (
                f"Coverage {output.coverage_rate:.0%} below {floor:.0%} threshold"
            )

        return result


def run_givecare_eval(
    category_filter: list[str] | None = None,
    scenario_filter: list[str] | None = None,
    include_confidential: bool = False,
    verbose: bool = True,
    dry_run: bool = False,
    auto_confirm: bool = False,
    generate_diagnostic: bool = False,
    output_dir: Path | None = None,
    adapter_name: str = "givecare-v2",
    harness_mode: str = "v2",
    update_leaderboard: bool = False,
) -> int:
    """Run the GiveCare V2 system harness against the benchmark core."""
    root = get_project_root()

    MODEL_ID = GIVECARE_V2_MODEL_ID
    MODEL_NAME = GIVECARE_V2_MODEL_NAME
    PROVIDER_NAME = GIVECARE_V2_PROVIDER_NAME
    PROVIDER_VERSION = GIVECARE_V2_PROVIDER_VERSION

    scenarios_dir = root / "benchmark" / "scenarios"
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = root / "results" / "givecare" / f"run_{timestamp}"

    try:
        scenario_paths = get_givecare_scenarios(
            scenarios_dir,
            category_filter=category_filter,
            include_confidential=include_confidential,
        )
    except RuntimeError as e:
        print(str(e))
        return 1
    if scenario_filter:
        scenario_paths = [
            path
            for path in scenario_paths
            if any(
                _scenario_matches_filter(
                    {"path": str(path), "name": path.stem.replace("_", " "), "scenario_id": path.stem},
                    pattern,
                )
                for pattern in scenario_filter
            )
        ]

    if not scenario_paths:
        print("No scenarios found")
        return 1

    scenario_count = len(scenario_paths)
    conf_note = " (including private confidential set)" if include_confidential else ""
    print(
        f"GiveCare V2 System Harness [{harness_mode}]: "
        f"{scenario_count} scenario(s){conf_note}"
    )

    if dry_run:
        print("\nDry run - no transcripts will be generated")
        for p in scenario_paths:
            print(f"  - {p.stem}")
        return 0

    if not auto_confirm:
        confirm = input(
            f"\nRun {scenario_count} scenarios against the GiveCare V2 system harness? [y/N] "
        )
        if confirm.lower() != "y":
            print("Aborted")
            return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = generate_manifest(
        project_root=root,
        model_ids=[MODEL_ID],
        harness="givecare",
        mode=harness_mode,
        include_confidential=include_confidential,
    )
    write_manifest(manifest, output_dir)

    # Run scenarios
    try:
        provider = GiveCareV2Provider()
        if verbose:
            print(f"Health: {json.dumps(provider.healthcheck(), indent=2)}")
    except (ValueError, RuntimeError, OSError) as e:
        print(f"Error: GiveCare V2 harness is not ready: {e}")
        return 1
    transcript_data = []
    results: list[dict[str, Any]] = []

    try:
        for scenario_path in scenario_paths:
            try:
                transcript_path, scenario_data = run_givecare_v2_scenario(
                    provider,
                    str(scenario_path),
                    output_dir / "transcripts",
                    verbose=verbose,
                )
                transcript_data.append((transcript_path, scenario_path, scenario_data))
            except Exception as e:
                scenario_data = _safe_load_scenario_data(scenario_path)
                results.append(
                    _make_harness_error_result(
                        model_name=MODEL_NAME,
                        model_id=MODEL_ID,
                        provider=PROVIDER_NAME,
                        scenario_name=get_scenario_title(scenario_data, scenario_path),
                        scenario_id=scenario_data.get("scenario_id", scenario_path.stem),
                        category=get_category_from_path(scenario_path),
                        reason=f"Transcript generation failed: {e}",
                    )
                )
                print(f"  {scenario_path.stem}: ERROR ({e})")
    finally:
        provider.close()

    print(f"\nGenerated {len(transcript_data)} transcript(s)")

    run_timestamp = datetime.now().isoformat()
    output_data = {
        "metadata": {
            "provider": PROVIDER_NAME,
            "provider_version": PROVIDER_VERSION,
            "model": MODEL_NAME,
            "model_id": MODEL_ID,
            "timestamp": run_timestamp,
            "scenario_count": len(scenario_paths),
            "include_confidential": include_confidential,
        },
        "results": results,
    }

    model_results_dir = output_dir / "model_results"
    write_model_results(
        results,
        model_results_dir,
        benchmark_version=manifest.get("benchmark_version", "unknown"),
        timestamp=run_timestamp,
        mode=adapter_name,
        run_metadata={
            "adapter": adapter_name,
            "provider": PROVIDER_NAME,
            "include_confidential": include_confidential,
        },
    )

    write_json(output_dir / "all_results.json", results)
    results_path = output_dir / "givecare_results.json"
    write_json(results_path, output_data)

    # When transcripts were generated but no inline result rows exist (the normal
    # path: V2 inline scoring was superseded by the V3 ModeEngine), skip the
    # legacy zero-row summary and BLOCK audit printout — they are misleading.
    # Instead emit a single actionable status line and return success.
    if transcript_data and not results:
        print(
            f"\n{len(transcript_data)} transcripts generated; "
            "inline V2 scoring is deprecated — score with: "
            f"uv run python scripts/run_scan.py {output_dir}"
        )
        # Write audit artifacts for downstream contract consumers, but suppress
        # the console summary (which would read "BLOCK | valid=no" for zero rows).
        _write_run_audit(
            results_path,
            output_dir=output_dir,
            expected_scenario_count=len(scenario_paths),
            harness="givecare",
            mode=harness_mode,
        )
        return 0

    audit = _write_run_audit(
        results_path,
        output_dir=output_dir,
        expected_scenario_count=len(scenario_paths),
        harness="givecare",
        mode=harness_mode,
    )

    # Summary
    passed = sum(1 for r in results if is_result_success(r))
    failed = len(results) - passed
    avg_score = sum(r["overall_score"] for r in results) / len(results) * 100 if results else 0

    print(f"\n{'='*50}")
    print("GiveCare V2 Eval Results")
    print(f"{'='*50}")
    print(f"Scenarios: {len(results)}")
    print(f"Passed:    {passed}")
    print(f"Failed:    {failed}")
    print(f"Average:   {avg_score:.1f}%")
    print(f"{'='*50}")
    print(f"Saved: {results_path}")

    if generate_diagnostic:
        print("\nGenerating diagnostic report...")
        try:
            from invisiblebench.export.diagnostic import generate_diagnostic_report

            diag_path = output_dir / "diagnostic_report.md"
            transcripts_path = output_dir / "transcripts"

            generate_diagnostic_report(
                results_path=str(results_path),
                transcripts_dir=str(transcripts_path) if transcripts_path.exists() else None,
                output_path=str(diag_path),
            )
            print(f"Diagnostic: {diag_path}")
        except (ImportError, OSError) as e:
            print(f"Warning: Could not generate diagnostic report: {e}")

    _print_audit_summary(audit)
    print(f"Audit files: {output_dir / 'run_audit.json'} , {output_dir / 'run_audit.md'}")

    if update_leaderboard:
        print(
            "Skipping leaderboard update: public leaderboard accepts only benchmark-core "
            "(llm/raw) runs. GiveCare harnesses remain experimental/internal."
        )

    return 0 if failed == 0 else 1


# Map categories to token estimate keys (for cost calculation)
CATEGORY_TOKEN_MAP = {
    "safety": 1,      # 3-5 turns
    "empathy": 2,     # 8-12 turns
    "context": 1,     # 3-5 turns
    "continuity": 3,  # 20+ turns, multi-session
}


def _normalize_scenario_token(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def _scenario_matches_filter(scenario: dict[str, Any], pattern: str) -> bool:
    pattern = pattern.strip().lower()
    if not pattern:
        return False

    path_stem = Path(str(scenario["path"])).stem.lower()
    scenario_id = str(scenario.get("scenario_id", "")).lower()
    name = str(scenario.get("name", "")).lower()

    targets = [scenario_id, path_stem, name]
    normalized_pattern = _normalize_scenario_token(pattern)
    normalized_targets = [_normalize_scenario_token(target) for target in targets]

    if any(pattern == target or pattern in target for target in targets):
        return True
    if normalized_pattern and any(
        normalized_pattern == target or normalized_pattern in target for target in normalized_targets
    ):
        return True
    return False


def get_scenarios(
    *,
    category_filter: list[str] | None = None,
    include_confidential: bool = False,
) -> list[dict[str, Any]]:
    """Get scenario configurations for the selected benchmark scope."""
    root = get_project_root()
    private_confidential_dir = get_private_confidential_dir(root)

    scenarios = []
    for path in collect_scenario_paths(
        root,
        category_filter=category_filter,
        include_confidential=include_confidential,
    ):
        scenarios.append(
            {
                "category": scenario_category_for_path(path, private_confidential_dir),
                "path": str(path),
                "name": path.stem.replace("_", " ").title(),
            }
        )

    return scenarios


def estimate_cost(category: str, model: dict[str, Any]) -> float:
    """Estimate cost for a single evaluation (model-under-test + scorer LLM calls)."""
    token_key = CATEGORY_TOKEN_MAP.get(category, 1)
    tokens = TOKEN_ESTIMATES.get(token_key, TOKEN_ESTIMATES[1])

    # Model-under-test cost
    model_cost = (tokens["input"] / 1_000_000) * model["cost_per_m_input"] + (
        tokens["output"] / 1_000_000
    ) * model["cost_per_m_output"]

    # Scorer LLM costs (flash-lite for most scorers + flash for safety reference)
    st = SCORER_TOKENS_PER_CALL
    fl = SCORER_MODEL_COSTS["flash_lite"]
    scorer_cost = SCORER_CALLS_PER_SCENARIO * (
        (st["input"] / 1_000_000) * fl["cost_per_m_input"]
        + (st["output"] / 1_000_000) * fl["cost_per_m_output"]
    )
    fr = SCORER_MODEL_COSTS["flash"]
    scorer_cost += SCORER_REF_CALLS_PER_SCENARIO * (
        (st["input"] / 1_000_000) * fr["cost_per_m_input"]
        + (st["output"] / 1_000_000) * fr["cost_per_m_output"]
    )

    return model_cost + scorer_cost


def resolve_models(spec: str, all_models: list[dict[str, Any]]) -> list[int]:
    """Resolve model spec string into list of 0-indexed model indices.

    Accepts numbers, names, or mixed:
        '4'           -> [3]           (4th model, 1-indexed)
        '1-4'         -> [0,1,2,3]     (models 1 through 4)
        '4-'          -> [3,4,5,...]   (4th onwards)
        '1,3,5'       -> [0,2,4]       (specific models)
        'deepseek'    -> [6]           (case-insensitive partial match)
        'claude'      -> [0,3,11]      (matches all Claude models)
        '1,deepseek'  -> [0,6]         (mixed numbers and names)

    Raises:
        ValueError: If a name token matches no models.
    """
    total = len(all_models)
    indices: set[int] = set()

    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue

        # Try numeric range first (e.g. '1-4', '4-', '4')
        if part[0].isdigit() or (part.startswith("-") and len(part) > 1 and part[1:].isdigit()):
            if "-" in part:
                left, right = part.split("-", 1)
                start = int(left) if left else 1
                end = int(right) if right else total
                for i in range(start, end + 1):
                    if 1 <= i <= total:
                        indices.add(i - 1)
            else:
                i = int(part)
                if 1 <= i <= total:
                    indices.add(i - 1)
        else:
            # Name-based lookup (case-insensitive partial match)
            needle = part.lower()
            matched = [
                idx
                for idx, m in enumerate(all_models)
                if needle in m["name"].lower() or needle in m["id"].lower()
            ]
            if not matched and "/" in part:
                # Pass-through: any OpenRouter model id ("org/model") can be
                # benchmarked, not just the published roster. Costs are
                # estimated with generic pricing; the dry-run shows them.
                all_models.append(
                    {
                        "id": part,
                        "name": part,
                        "provider": "openrouter",
                        "cost_per_m_input": 1.0,
                        "cost_per_m_output": 3.0,
                    }
                )
                matched = [len(all_models) - 1]
            if not matched:
                names = [f"  {i+1}. {m['name']}" for i, m in enumerate(all_models)]
                raise ValueError(
                    f"No model matching '{part}'. Available models:\n" + "\n".join(names)
                )
            indices.update(matched)

    return sorted(indices)


# ScenarioDisplay and print_banner moved to invisiblebench.cli.display

# ScenarioDisplay and print_banner moved to invisiblebench.cli.display

def _aggregate_multi_run_results(run_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate N run results with median score and reliability stats."""
    if len(run_results) == 1:
        return run_results[0]

    def _score_value(result: dict[str, Any]) -> float:
        score = result.get("overall_score", 0.0)
        return float(score) if isinstance(score, (int, float)) else 0.0

    sorted_results = sorted(run_results, key=_score_value)
    median_idx = len(sorted_results) // 2
    final = sorted_results[median_idx].copy()
    run_count = len(run_results)

    scores = [_score_value(r) for r in run_results]
    hard_fail_flags = [bool(r.get("hard_fail", False)) for r in run_results]
    pass_flags = [not hf and _score_value(r) >= SUCCESS_THRESHOLD for hf, r in zip(hard_fail_flags, run_results, strict=True)]
    pass_count = sum(1 for p in pass_flags if p)
    hard_fail_count = sum(1 for hf in hard_fail_flags if hf)

    dimension_values: dict[str, list[float]] = {}
    for result in run_results:
        raw_dims = result.get("dimensions") or result.get("dimension_scores", {})
        dims = normalize_dimension_scores(raw_dims)
        for dim, value in dims.items():
            score = extract_numeric_dimension_value(value)
            if isinstance(score, (int, float)):
                dimension_values.setdefault(dim, []).append(float(score))

    def _stats(values: list[float]) -> tuple[float, float, float]:
        if not values:
            return 0.0, 0.0, 0.0
        if len(values) == 1:
            return values[0], 0.0, 1.0 if values[0] >= SUCCESS_THRESHOLD else 0.0
        return (
            statistics.mean(values),
            statistics.pstdev(values),
            sum(1 for v in values if v >= SUCCESS_THRESHOLD) / len(values),
        )

    # Gate handling: if ANY run triggers a gate failure, the scenario fails
    any_hard_fail = any(r.get("hard_fail") for r in run_results)
    if any_hard_fail:
        final["hard_fail"] = True
        all_reasons: list[str] = []
        for r in run_results:
            for reason in r.get("hard_fail_reasons", []):
                if reason not in all_reasons:
                    all_reasons.append(reason)
        final["hard_fail_reasons"] = all_reasons
        final["status"] = "fail"

    final["runs"] = [
        {
            "run": i + 1,
            "overall_score": _score_value(r),
            "hard_fail": r.get("hard_fail", False),
        }
        for i, r in enumerate(run_results)
    ]
    final["run_stats"] = {
        "median": scores[median_idx],
        "min": min(scores),
        "max": max(scores),
        "mean": statistics.mean(scores),
        "std": statistics.pstdev(scores) if len(scores) > 1 else 0.0,
        "n": run_count,
        "pass_count": pass_count,
        "pass_rate": pass_count / run_count,
        "hard_fail_count": hard_fail_count,
        "hard_fail_rate": hard_fail_count / run_count,
    }
    final["run_summary"] = {
        "n": run_count,
        "pass_count": pass_count,
        "pass_rate": pass_count / run_count,
        "hard_fail_count": hard_fail_count,
        "hard_fail_rate": hard_fail_count / run_count,
        "dimension_stats": {
            dim: {"mean": mean, "std": std, "pass_rate": pass_rate}
            for dim, (mean, std, pass_rate) in {
                d: _stats(values) for d, values in dimension_values.items()
            }.items()
        },
    }
    final["overall_score"] = scores[median_idx]
    final["cost"] = sum(r.get("cost", 0) for r in run_results)

    return final


def _update_leaderboard(results_path: Path) -> None:
    """Add results to leaderboard (merges with existing canonical files)."""
    from invisiblebench.cli.leaderboard import add_results

    add_results(results_path)


def _write_run_audit(
    source: Path,
    *,
    output_dir: Path,
    expected_scenario_count: int | None,
    harness: str,
    mode: str,
    previous_source: Path | None = None,
) -> dict[str, Any]:
    """Generate run audit artifacts and return the audit dict."""
    audit = audit_results_source(
        source,
        expected_scenario_count=expected_scenario_count,
        harness=harness,
        mode=mode,
        previous_source=previous_source,
    )
    write_json(output_dir / "run_audit.json", audit)
    (output_dir / "run_audit.md").write_text(render_audit_markdown(audit))
    return audit


def _print_audit_summary(audit: dict[str, Any], console: Console | None = None) -> None:
    """Print compact audit summary to console/stdout."""
    msg = (
        f"Audit: {audit.get('summary_status', 'WARN')} | "
        f"valid={'yes' if audit.get('run_valid') else 'no'} | "
        f"publishable={'yes' if audit.get('publishable') else 'no'} | "
        f"owner={audit.get('primary_owner', 'benchmark')}"
    )
    if console:
        color = "green" if audit.get("summary_status") == "PASS" else "yellow" if audit.get("summary_status") == "WARN" else "red"
        console.print(f"[{color}]{msg}[/{color}]")
    else:
        print(msg)


def run_benchmark(
    models: list[dict[str, Any]],
    output_dir: Path,
    dry_run: bool = False,
    auto_confirm: bool = False,
    category_filter: list[str] | None = None,
    scenario_filter: list[str] | None = None,
    parallel: int | None = None,
    scenario_parallel: int = 1,
    detailed_output: bool = False,
    update_leaderboard: bool = False,
    generate_diagnostic: bool = False,
    runs: int = 1,
    include_confidential: bool = False,
) -> int:
    """Run the benchmark."""
    console = Console() if RICH_AVAILABLE else None

    try:
        scenarios = get_scenarios(
            category_filter=category_filter,
            include_confidential=include_confidential,
        )
    except RuntimeError as e:
        if console:
            console.print(f"[red]{e}[/red]")
        else:
            print(str(e))
        return 1

    # Apply category filter
    if category_filter:
        scenarios = [s for s in scenarios if s["category"] in category_filter]

    # Apply scenario filter (exact, normalized, or substring match on id/path/name)
    if scenario_filter:
        scenarios = [
            scenario
            for scenario in scenarios
            if any(_scenario_matches_filter(scenario, pattern) for pattern in scenario_filter)
        ]

    if not scenarios:
        if console:
            console.print("[red]No scenarios match the filters[/red]")
        else:
            print("No scenarios match the filters")
        return 1

    total = len(models) * len(scenarios)
    n_runs = max(1, runs)
    scenario_parallel = max(1, scenario_parallel)
    total_cost = sum(estimate_cost(s["category"], m) for m in models for s in scenarios) * n_runs

    output_dir.mkdir(parents=True, exist_ok=True)

    # Write reproducibility manifest
    root = get_project_root()
    manifest = generate_manifest(
        project_root=root,
        model_ids=[m["id"] for m in models],
        harness="llm",
        mode="raw",
        include_confidential=include_confidential,
    )
    write_manifest(manifest, output_dir)
    model_results_dir = output_dir / "model_results"

    def persist_model_results(model_rows: list[dict[str, Any]]) -> None:
        if not model_rows:
            return
        write_model_results(
            model_rows,
            model_results_dir,
            benchmark_version=manifest.get("benchmark_version", "unknown"),
            mode="benchmark",
            run_metadata={"run_id": run_id, "provider": "openrouter"},
        )

    if RICH_AVAILABLE and console:
        print_banner(console, "full", models, scenarios, total_cost)
        if n_runs > 1:
            console.print(
                f"[cyan]Running {n_runs}\u00d7 per scenario (median + reliability stats)[/cyan]\n"
            )
    else:
        print("\nInvisibleBench")
        print(f"Models: {len(models)}, Scenarios: {len(scenarios)}")
        print(f"Total: {total} evaluations, Est. cost: ${total_cost:.2f}\n")
        if n_runs > 1:
            print(f"Running {n_runs}x per scenario (median + reliability stats)")

    if dry_run:
        if RICH_AVAILABLE and console:
            console.print("[yellow]DRY RUN[/yellow] - No evaluations will be run\n")
            console.print("[bold]Selected models:[/bold]")
            all_catalog = MODELS_FULL
            for m in models:
                idx = next(
                    (i for i, c in enumerate(all_catalog) if c["id"] == m["id"]),
                    None,
                )
                num = f"#{idx + 1}" if idx is not None else "#?"
                cost = sum(estimate_cost(s["category"], m) for s in scenarios)
                console.print(
                    f"  [dim]{num:<4}[/dim] {m['name']:<24} [magenta]~${cost:.2f}[/magenta]"
                )
        else:
            print("DRY RUN - No evaluations will be run")
            print("\nSelected models:")
            all_catalog = MODELS_FULL
            for m in models:
                idx = next(
                    (i for i, c in enumerate(all_catalog) if c["id"] == m["id"]),
                    None,
                )
                num = f"#{idx + 1}" if idx is not None else "#?"
                print(f"  {num:<4} {m['name']}")
        return 0

    if not os.getenv("OPENROUTER_API_KEY"):
        print("ERROR: OPENROUTER_API_KEY not set")
        return 1

    if not auto_confirm:
        response = input("Proceed? (y/n): ")
        if response.lower() != "y":
            print("Cancelled")
            return 0

    try:
        from invisiblebench.api.client import ModelAPIClient

        api_client = ModelAPIClient()
    except (ImportError, ValueError) as e:
        print(f"ERROR: Failed to initialize API client: {e}")
        return 1

    root = get_project_root()
    rules_path = root / "benchmark" / "configs" / "rules" / "base.yaml"
    orchestrator = ModeEngineScoringAdapter(api_client)

    run_id = str(uuid.uuid4())

    results = []
    start_time = time.time()
    passed = 0
    failed = 0
    credits_exhausted = False

    # Parallel execution mode - runs N MODELS in parallel
    if parallel and parallel > 1:
        if RICH_AVAILABLE and console:
            # Track progress per model
            model_progress: dict[str, tuple] = (
                {}
            )  # model_name -> (completed, total, current_scenario)
            progress_lock = threading.Lock()
            all_results: list[dict[str, Any]] = []
            results_lock = threading.Lock()

            async def run_model_scenarios(model: dict[str, Any]) -> list[dict[str, Any]]:
                """Run all scenarios for a single model sequentially."""
                model_results = []
                model_name = model["name"]

                for i, scenario in enumerate(scenarios):
                    with progress_lock:
                        model_progress[model_name] = (i, len(scenarios), scenario["name"][:20])

                    # Use a dummy semaphore (no limit within model)
                    dummy_sem = asyncio.Semaphore(1)
                    if n_runs > 1:
                        run_results = []
                        for run_idx in range(n_runs):
                            r = await evaluate_scenario_async(
                                model, scenario, api_client, orchestrator,
                                output_dir, dummy_sem,
                                detailed_output=detailed_output,
                                run_suffix=f"_run{run_idx + 1}",
                                run_id=run_id,
                            )
                            run_results.append(r)
                        result = _aggregate_multi_run_results(run_results)
                    else:
                        result = await evaluate_scenario_async(
                            model, scenario, api_client, orchestrator,
                            output_dir, dummy_sem,
                            detailed_output=detailed_output,
                            run_id=run_id,
                        )
                    model_results.append(result)

                    with results_lock:
                        all_results.append(result)

                with progress_lock:
                    model_progress[model_name] = (len(scenarios), len(scenarios), "Done")

                persist_model_results(model_results)
                return model_results

            async def run_models_parallel():
                semaphore = asyncio.Semaphore(parallel)

                async def run_with_sem(model):
                    async with semaphore:
                        return await run_model_scenarios(model)

                tasks = [run_with_sem(m) for m in models]
                return await asyncio.gather(*tasks)

            console.print(f"[cyan]Running {min(parallel, len(models))} models in parallel[/cyan]\n")

            async def run_and_display():
                import asyncio as aio

                task = aio.create_task(run_models_parallel())

                with Progress(
                    SpinnerColumn(),
                    TextColumn("[bold blue]{task.fields[model_name]:<18}[/bold blue]"),
                    BarColumn(bar_width=20),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                    TextColumn("{task.completed}/{task.total}"),
                    TextColumn("[dim]|[/dim]"),
                    TextColumn("[cyan]{task.fields[scenario]:<25}[/cyan]"),
                    console=console,
                    transient=False,
                ) as progress:
                    model_tasks = {}
                    for model in models:
                        model_tasks[model["name"]] = progress.add_task(
                            model["name"],
                            total=len(scenarios),
                            model_name=model["name"],
                            scenario="waiting...",
                        )

                    while not task.done():
                        with progress_lock:
                            for mname, (comp, tot, scen) in model_progress.items():
                                if mname in model_tasks:
                                    progress.update(
                                        model_tasks[mname],
                                        completed=comp,
                                        scenario=scen if comp < tot else "[green]Done[/green]",
                                    )

                        await aio.sleep(0.3)

                    # Final update - mark all complete
                    for _mname, task_id in model_tasks.items():
                        progress.update(
                            task_id, completed=len(scenarios), scenario="[green]Done[/green]"
                        )

                return await task

            try:
                asyncio.run(run_and_display())
            except InsufficientCreditsError:
                credits_exhausted = True
                console.print(
                    "\n[bold red]Credits exhausted.[/bold red] Saving partial results."
                )
            except Exception as e:
                print(f"ERROR: Parallel execution failed: {e}")
                return 1
            for r in all_results:
                if r.get("status") in ("fail", "error") or r.get("hard_fail"):
                    failed += 1
                else:
                    passed += 1
            results = all_results
        else:
            # Non-rich parallel fallback - still parallelize by model
            all_results: list[dict[str, Any]] = []

            async def run_model_scenarios_simple(model: dict[str, Any]) -> list[dict[str, Any]]:
                model_results = []
                for scenario in scenarios:
                    dummy_sem = asyncio.Semaphore(1)
                    if n_runs > 1:
                        run_results = []
                        for run_idx in range(n_runs):
                            r = await evaluate_scenario_async(
                                model, scenario, api_client, orchestrator,
                                output_dir, dummy_sem,
                                detailed_output=detailed_output,
                                run_suffix=f"_run{run_idx + 1}",
                                run_id=run_id,
                            )
                            run_results.append(r)
                        result = _aggregate_multi_run_results(run_results)
                    else:
                        result = await evaluate_scenario_async(
                            model, scenario, api_client, orchestrator,
                            output_dir, dummy_sem,
                            detailed_output=detailed_output,
                            run_id=run_id,
                        )
                    model_results.append(result)
                persist_model_results(model_results)
                return model_results

            async def run_parallel():
                semaphore = asyncio.Semaphore(parallel)

                async def run_with_sem(model):
                    async with semaphore:
                        return await run_model_scenarios_simple(model)

                tasks = [run_with_sem(m) for m in models]
                nested = await asyncio.gather(*tasks)
                return [r for model_results in nested for r in model_results]

            try:
                results = asyncio.run(run_parallel())
            except InsufficientCreditsError:
                credits_exhausted = True
                print("\nCredits exhausted. Saving partial results.")
            except Exception as e:
                print(f"ERROR: Parallel execution failed: {e}")
                return 1
            for r in results:
                if r.get("status") in ("fail", "error") or r.get("hard_fail"):
                    failed += 1
                else:
                    passed += 1

    elif scenario_parallel > 1:
        print(f"Running up to {scenario_parallel} scenarios in parallel per model\n")

        async def run_one_scenario_concurrent(
            model: dict[str, Any],
            scenario: dict[str, Any],
            semaphore: asyncio.Semaphore,
        ) -> dict[str, Any]:
            scenario_path = Path(scenario["path"])
            if not scenario_path.exists():
                return _make_error_result(
                    model,
                    scenario["name"],
                    scenario_path.stem,
                    scenario["category"],
                    "Scenario file not found",
                )

            try:
                if n_runs > 1:
                    run_results = []
                    for run_idx in range(n_runs):
                        run_results.append(
                            await evaluate_scenario_async(
                                model,
                                scenario,
                                api_client,
                                orchestrator,
                                output_dir,
                                semaphore,
                                detailed_output=detailed_output,
                                run_suffix=f"_run{run_idx + 1}",
                                run_id=run_id,
                            )
                        )
                    return _aggregate_multi_run_results(run_results)

                return await evaluate_scenario_async(
                    model,
                    scenario,
                    api_client,
                    orchestrator,
                    output_dir,
                    semaphore,
                    detailed_output=detailed_output,
                    run_id=run_id,
                )
            except InsufficientCreditsError:
                raise
            except Exception as e:
                logger.exception("Scenario run failed: %s", e)
                return _make_error_result(
                    model,
                    scenario["name"],
                    scenario_path.stem,
                    scenario["category"],
                    f"Unexpected scenario run failure: {e}",
                )

        async def run_model_scenarios_concurrent(
            model: dict[str, Any],
        ) -> list[dict[str, Any]]:
            semaphore = asyncio.Semaphore(scenario_parallel)

            async def run_indexed(
                index: int,
                scenario: dict[str, Any],
            ) -> tuple[int, dict[str, Any]]:
                return index, await run_one_scenario_concurrent(model, scenario, semaphore)

            tasks = [
                asyncio.create_task(run_indexed(index, scenario))
                for index, scenario in enumerate(scenarios)
            ]
            completed: list[tuple[int, dict[str, Any]]] = []

            try:
                for task in asyncio.as_completed(tasks):
                    idx, result = await task
                    completed.append((idx, result))
                    is_error = result.get("status") in ("fail", "error") or result.get("hard_fail")
                    status = "FAIL" if is_error else "PASS"
                    print(
                        f"[{len(completed)}/{len(tasks)}] {model['name']} → "
                        f"{result.get('scenario', 'unknown')} {status}"
                    )
            except InsufficientCreditsError:
                for task in tasks:
                    task.cancel()
                raise

            return [result for _, result in sorted(completed, key=lambda item: item[0])]

        for model in models:
            try:
                model_results = asyncio.run(run_model_scenarios_concurrent(model))
            except InsufficientCreditsError:
                credits_exhausted = True
                break

            results.extend(model_results)
            persist_model_results(model_results)
            for r in model_results:
                if r.get("status") in ("fail", "error") or r.get("hard_fail"):
                    failed += 1
                else:
                    passed += 1

    elif RICH_AVAILABLE and console:
        cats = sorted({s["category"] for s in scenarios})
        scenarios_by_cat = {c: [s for s in scenarios if s["category"] == c] for c in cats}

        for model in models:
            model_results: list[dict[str, Any]] = []
            display = ScenarioDisplay(model["name"], scenarios, start_time)

            with Live(
                display,
                console=console,
                refresh_per_second=4,
                transient=True,
                vertical_overflow="crop",
            ) as _live:
                for cat in cats:
                    cat_scenarios = scenarios_by_cat[cat]

                    for scenario in cat_scenarios:
                        display.set_running(scenario["path"], cat)

                        scenario_path = Path(scenario["path"])
                        if not scenario_path.exists():
                            display.set_complete(scenario["path"], 0.0, False, cat)
                            failed += 1
                            continue

                        with open(scenario_path) as f:
                            scenario_data = json.load(f)

                        scenario_id = scenario_data.get("scenario_id", scenario_path.stem)
                        run_results = []

                        for run_idx in range(n_runs):
                            run_suffix = f"_run{run_idx + 1}" if n_runs > 1 else ""
                            try:
                                run_results.append(
                                    _run_single_scenario(
                                        model=model,
                                        scenario=scenario,
                                        scenario_path=scenario_path,
                                        scenario_id=scenario_id,
                                        run_suffix=run_suffix,
                                        output_dir=output_dir,
                                        api_client=api_client,
                                        orchestrator=orchestrator,
                                        rules_path=rules_path,
                                        detailed_output=detailed_output,
                                        run_id=run_id,
                                    )
                                )
                            except InsufficientCreditsError:
                                credits_exhausted = True
                                break
                            except Exception as e:
                                logger.exception("Scenario run failed: %s", e)
                                run_results.append(
                                    _make_error_result(
                                        model,
                                        scenario["name"],
                                        scenario_id,
                                        scenario["category"],
                                        f"Unexpected scenario run failure: {e}",
                                    )
                                )

                        if credits_exhausted and not run_results:
                            break

                        if not run_results:
                            final = _make_error_result(
                                model,
                                scenario["name"],
                                scenario_id,
                                scenario["category"],
                                "No runs completed",
                            )
                        elif n_runs > 1:
                            final = _aggregate_multi_run_results(run_results)
                        else:
                            final = run_results[0]

                        results.append(final)
                        model_results.append(final)

                        score = final["overall_score"]
                        is_pass = not final.get("hard_fail")
                        is_coverage_invalid = final.get("coverage_invalid", False)
                        score_display = ""
                        if "run_stats" in final:
                            stats = final["run_stats"]
                            lo = int(stats["min"] * 100)
                            hi = int(stats["max"] * 100)
                            pass_rate = int(stats["pass_rate"] * 100)
                            if pass_rate == 100:
                                score_display = f"{int(score * 100)}% [{lo}-{hi}%] pass@1"
                            else:
                                score_display = (
                                    f"{int(score * 100)}% [{lo}-{hi}%] "
                                    f"pass@1={pass_rate}%"
                                )
                        display.set_complete(
                            scenario["path"],
                            score,
                            is_pass and not is_coverage_invalid,
                            cat,
                            score_display=score_display,
                            coverage=final.get("coverage"),
                            coverage_invalid=is_coverage_invalid,
                        )

                        if is_coverage_invalid or not is_pass:
                            failed += 1
                        else:
                            passed += 1

                        if credits_exhausted:
                            break

                    # Mark category as done
                    display.set_category_done(cat)
                    if credits_exhausted:
                        break

            # Print final state after Live exits (since transient=True clears it)
            console.print(display)
            persist_model_results(model_results)

    else:
        # Fallback without rich - still run actual evaluations
        eval_num = 0
        for model in models:
            model_results: list[dict[str, Any]] = []
            for scenario in scenarios:
                eval_num += 1
                print(
                    f"[{eval_num}/{total}] {model['name']} → {scenario['name']}",
                    end=" ",
                    flush=True,
                )

                scenario_path = Path(scenario["path"])
                if not scenario_path.exists():
                    print("SKIP (not found)")
                    failed += 1
                    continue

                with open(scenario_path) as f:
                    scenario_data = json.load(f)

                scenario_id = scenario_data.get("scenario_id", scenario_path.stem)
                run_results = []

                for run_idx in range(n_runs):
                    run_suffix = f"_run{run_idx + 1}" if n_runs > 1 else ""
                    try:
                        run_results.append(
                            _run_single_scenario(
                                model=model,
                                scenario=scenario,
                                scenario_path=scenario_path,
                                scenario_id=scenario_id,
                                run_suffix=run_suffix,
                                output_dir=output_dir,
                                api_client=api_client,
                                orchestrator=orchestrator,
                                rules_path=rules_path,
                                detailed_output=detailed_output,
                                run_id=run_id,
                            )
                        )
                    except InsufficientCreditsError:
                        credits_exhausted = True
                        break
                    except Exception as e:
                        logger.exception("Scenario run failed: %s", e)
                        run_results.append(
                            _make_error_result(
                                model,
                                scenario["name"],
                                scenario_id,
                                scenario["category"],
                                f"Unexpected scenario run failure: {e}",
                            )
                        )

                if credits_exhausted and not run_results:
                    break

                if not run_results:
                    final = _make_error_result(
                        model, scenario["name"], scenario_id,
                        scenario["category"], "No runs completed",
                    )
                elif n_runs > 1:
                    final = _aggregate_multi_run_results(run_results)
                else:
                    final = run_results[0]

                results.append(final)
                model_results.append(final)

                score_val = final["overall_score"]
                is_pass = not final.get("hard_fail")
                if "run_stats" in final:
                    stats = final["run_stats"]
                    print(
                        f"{'FAIL' if not is_pass else 'PASS'} ({int(score_val * 100)}% "
                        f"[{int(stats['min'] * 100)}-{int(stats['max'] * 100)}%], "
                        f"pass@1={int(stats['pass_rate'] * 100)}%)"
                    )
                elif is_pass:
                    print(f"PASS ({int(score_val * 100)}%)")
                else:
                    print(f"FAIL ({int(score_val * 100)}%)")

                if is_pass:
                    passed += 1
                else:
                    failed += 1

                if credits_exhausted:
                    break
            persist_model_results(model_results)
            if credits_exhausted:
                break

    elapsed = time.time() - start_time

    if not results:
        if credits_exhausted:
            msg = "Credits exhausted before any scenarios completed."
            if RICH_AVAILABLE and console:
                console.print(f"\n[bold red]{msg}[/bold red]")
                console.print("[yellow]Add credits at https://openrouter.ai/settings/credits[/yellow]")
            else:
                print(f"\n{msg}")
                print("Add credits at https://openrouter.ai/settings/credits")
        return 1

    # Save results
    write_model_results(
        results,
        model_results_dir,
        benchmark_version=manifest.get("benchmark_version", "unknown"),
        mode="benchmark",
        run_metadata={"run_id": run_id, "provider": "openrouter"},
    )
    results_path = output_dir / "all_results.json"
    write_json(results_path, results)

    report_path = output_dir / "report.html"
    try:
        from invisiblebench.export.reports import ReportGenerator

        reporter = ReportGenerator()
        model_names = ", ".join(m["name"] for m in models)
        reporter.generate_batch_report(
            results,
            str(report_path),
            metadata={"model": model_names, "mode": "llm-raw"},
        )
    except (ImportError, OSError) as e:
        print(f"Warning: Could not generate HTML report: {e}")

    # Generate diagnostic report if requested
    diag_path = None
    if generate_diagnostic:
        try:
            from invisiblebench.export.diagnostic import generate_diagnostic_report

            diag_path = output_dir / "diagnostic_report.md"
            transcripts_path = output_dir / "transcripts"

            generate_diagnostic_report(
                results_path=str(results_path),
                transcripts_dir=str(transcripts_path) if transcripts_path.exists() else None,
                output_path=str(diag_path),
            )
        except (ImportError, OSError) as e:
            print(f"Warning: Could not generate diagnostic report: {e}")

    audit = _write_run_audit(
        results_path,
        output_dir=output_dir,
        expected_scenario_count=len(scenarios),
        harness="llm",
        mode="raw",
    )

    # Print summary — use actual metered cost from OpenRouter
    if RICH_AVAILABLE and console:
        avg_score = sum(r["overall_score"] for r in results) / len(results) * 100 if results else 0
        actual_total = cost_tracker.total
        elapsed_str = f"{int(elapsed // 60)}:{int(elapsed % 60):02d}"
        cost_snap = cost_tracker.snapshot()

        # ── Success Rate table (primary metric) ──
        try:
            from invisiblebench.stats.analysis import (
                compute_failure_buckets,
                compute_success_rates,
            )

            sr = compute_success_rates(results)
            sr_total = sr["total"]
            console.print()
            console.print("[bold]SUCCESS RATE[/bold]")
            sr_table = Table(show_header=True, show_lines=False, pad_edge=False)
            sr_table.add_column("Category", style="bold")
            sr_table.add_column("Pass", justify="right")
            sr_table.add_column("Fail", justify="right")
            sr_table.add_column("Rate", justify="right")
            sr_table.add_column("95% CI", justify="right")

            for cat, cs in sr["categories"].items():
                rate_str = f"{cs['rate'] * 100:.1f}%"
                ci_str = f"[{cs['ci_lo'] * 100:.1f}%, {cs['ci_hi'] * 100:.1f}%]"
                rate_color = "green" if cs["rate"] >= 0.8 else "yellow" if cs["rate"] >= 0.6 else "red"
                sr_table.add_row(
                    cat,
                    str(cs["pass"]),
                    str(cs["fail"]),
                    f"[{rate_color}]{rate_str}[/{rate_color}]",
                    f"[dim]{ci_str}[/dim]",
                )
            # Total row
            total_rate_str = f"{sr_total['rate'] * 100:.1f}%"
            total_ci_str = f"[{sr_total['ci_lo'] * 100:.1f}%, {sr_total['ci_hi'] * 100:.1f}%]"
            total_color = "green" if sr_total["rate"] >= 0.8 else "yellow" if sr_total["rate"] >= 0.6 else "red"
            sr_table.add_row(
                "[bold]TOTAL[/bold]",
                f"[bold]{sr_total['pass']}[/bold]",
                f"[bold]{sr_total['fail']}[/bold]",
                f"[bold {total_color}]{total_rate_str}[/bold {total_color}]",
                f"[dim]{total_ci_str}[/dim]",
            )
            console.print(sr_table)

            # Failure buckets
            buckets = compute_failure_buckets(results)
            if buckets:
                console.print("\n[bold]FAILURE BUCKETS[/bold]")
                for bucket, count in buckets.items():
                    label = bucket.replace("_", " ").title()
                    console.print(f"  [red]{label}:[/red]  {count}")
        except ImportError as _e:
            logger.debug("Success rate table rendering failed: %s", _e)

        console.print()
        if credits_exhausted:
            completed = len(results)
            console.print(
                f"[bold yellow]⚠ Partial[/bold yellow]  "
                f"{completed}/{total} scenarios  "
                f"[bold]{avg_score:.0f}%[/bold]  "
                f"[green]{passed}[/green]/[red]{failed}[/red]  "
                f"[magenta]${actual_total:.3f}[/magenta]  "
                f"[dim]{elapsed_str}[/dim]"
            )
            console.print(
                "[yellow]Credits exhausted. Results saved. "
                "Add credits at https://openrouter.ai/settings/credits[/yellow]"
            )
        else:
            console.print(
                f"[bold green]✓ Done[/bold green]  "
                f"[bold]{avg_score:.0f}%[/bold]  "
                f"[green]{passed}[/green]/[red]{failed}[/red]  "
                f"[magenta]${actual_total:.3f}[/magenta]  "
                f"[dim]{elapsed_str}[/dim]"
            )
        # Show cost breakdown by model if more than one model used
        if len(cost_snap["by_model"]) > 1:
            for m, c in sorted(cost_snap["by_model"].items(), key=lambda x: -x[1]):
                short = m.split("/")[-1][:25]
                console.print(f"  [dim]{short:<27}[/dim] [magenta]${c:.4f}[/magenta]")

        # Failure report - include hard fails, low scores, or status=fail
        failures = [
            r
            for r in results
            if r.get("hard_fail")
            or r.get("overall_score", 1) < SUCCESS_THRESHOLD
            or r.get("status") == "fail"
        ]
        if failures:
            console.print("\n[bold red]Failures & Violations[/bold red]")
            for f in failures:
                score_pct = int(f["overall_score"] * 100)
                console.print(
                    f"\n  [red]✗[/red] [bold]{f['scenario']}[/bold] [dim]{f.get('category', '')}[/dim]  {score_pct}%"
                )

                # Show run stats if multi-run
                if f.get("run_stats"):
                    stats = f["run_stats"]
                    console.print(
                        f"    [dim]Runs: {stats['n']}×  "
                        f"[{int(stats['min']*100)}-{int(stats['max']*100)}%]  "
                        f"pass@1={int(stats['pass_rate']*100)}%  hard_fail@1={int(stats['hard_fail_rate']*100)}%[/dim]"
                    )

                # Show hard fail reasons
                if f.get("hard_fail_reasons"):
                    for reason in f["hard_fail_reasons"]:
                        console.print(f"    [red]→[/red] {reason}")

                # Show failure categories
                categories = f.get("failure_categories", {})
                if categories.get("details"):
                    for cat, details in categories["details"].items():
                        cat_display = cat.replace("_", " ").title()
                        console.print(f"    [yellow]•[/yellow] {cat_display}")
                        for detail in details[:2]:  # limit to 2 details per category
                            console.print(f"      [dim]{detail}[/dim]")

                # Show gate status
                gates = f.get("gates", {})
                gate_parts = []
                for gate_name in ("safety", "compliance"):
                    gate = gates.get(gate_name, {})
                    if gate.get("passed") is False:
                        gate_parts.append(f"[red]{gate_name}:FAIL[/red]")
                    elif gate.get("passed") is True:
                        gate_parts.append(f"[green]{gate_name}:OK[/green]")
                if gate_parts:
                    console.print(f"    Gates: {' '.join(gate_parts)}")

                # Show quality dimension scores
                dims = f.get("dimensions", {})
                dim_parts = []
                for k in ("regard", "coordination"):
                    v = dims.get(k)
                    if isinstance(v, (int, float)):
                        color = (
                            "red" if v < SUCCESS_THRESHOLD else "yellow" if v < 0.7 else "green"
                        )
                        dim_parts.append(f"[{color}]{k}:{int(v*100)}%[/{color}]")
                if dim_parts:
                    console.print(f"    Quality: {' '.join(dim_parts)}")

        # Safety report card + quality leaderboard
        try:
            from invisiblebench.export.safety_report_card import generate_safety_report_card

            report_card = generate_safety_report_card(results)
            if report_card["models"]:
                # --- Gate summary table ---
                console.print("\n[bold]SAFETY REPORT CARD[/bold]")
                card_table = Table(show_header=True, show_lines=False, pad_edge=False)
                card_table.add_column("Model", style="bold")
                card_table.add_column("Safety", justify="right")
                card_table.add_column("Compliance", justify="right")
                card_table.add_column("Status")

                for m in report_card["models"]:
                    sg = m["safety_gate"]
                    cg = m["compliance_gate"]
                    safety_str = f"{sg['passed']}/{sg['total']}"
                    compliance_str = f"{cg['passed']}/{cg['total']}"
                    total_failures = sg["failed"] + cg["failed"]
                    if total_failures == 0:
                        status = "[green]Clean[/green]"
                    else:
                        status = f"[yellow]{total_failures} failure{'s' if total_failures != 1 else ''}[/yellow]"
                    card_table.add_row(m["model"], safety_str, compliance_str, status)

                console.print(card_table)

                # --- Per-scenario matrix (only show scenarios with at least one FAIL) ---
                matrix = report_card["scenario_matrix"]
                names = report_card["scenario_names"]
                models_list = [m["model"] for m in report_card["models"]]
                failed_scenarios = [
                    sid for sid, model_map in matrix.items()
                    if any(v == "FAIL" for v in model_map.values())
                ]
                if failed_scenarios:
                    console.print("\n[bold]GATE FAILURES BY SCENARIO[/bold]")
                    mtx_table = Table(show_header=True, show_lines=False, pad_edge=False)
                    mtx_table.add_column("Scenario", style="bold")
                    for model in models_list:
                        # Shorten model name for column header
                        short = model[:20]
                        mtx_table.add_column(short, justify="center")

                    for sid in failed_scenarios:
                        display = names.get(sid, sid)
                        if len(display) > 30:
                            display = display[:28] + ".."
                        cells = []
                        for model in models_list:
                            status = matrix.get(sid, {}).get(model, "?")
                            if status == "PASS":
                                cells.append("[green]PASS[/green]")
                            else:
                                cells.append("[red]FAIL[/red]")
                        mtx_table.add_row(display, *cells)

                    console.print(mtx_table)

                # --- Quality leaderboard ---
                quality = report_card.get("quality", [])
                if quality:
                    passers = [q for q in quality if q["all_gates_pass"]]
                    failers = [q for q in quality if not q["all_gates_pass"]]

                    if passers:
                        console.print("\n[bold]QUALITY LEADERBOARD[/bold] [dim](passed safety gate)[/dim]")
                        q_table = Table(show_header=True, show_lines=False, pad_edge=False)
                        q_table.add_column("Model", style="bold")
                        q_table.add_column("Regard", justify="right")
                        q_table.add_column("Coordination", justify="right")
                        q_table.add_column("Overall", justify="right")
                        for q in passers:
                            q_table.add_row(
                                q["model"],
                                f"{q['regard']:.2f}",
                                f"{q['coordination']:.2f}",
                                f"[bold]{q['quality_score']:.2f}[/bold]",
                            )
                        console.print(q_table)

                    if failers:
                        console.print("\n[bold red]FAILED SAFETY GATE[/bold red]")
                        # Show each failer with their specific failure reasons
                        fail_lookup = {m["model"]: m["failures"] for m in report_card["models"]}
                        for q in failers:
                            failure_list = fail_lookup.get(q["model"], [])
                            if failure_list:
                                reasons = ", ".join(
                                    f"{f['scenario']} ({f['reasons'][0]})" if f["reasons"]
                                    else f["scenario"]
                                    for f in failure_list[:3]
                                )
                                if len(failure_list) > 3:
                                    reasons += f" +{len(failure_list) - 3} more"
                            else:
                                reasons = "gate failure"
                            console.print(f"  [red]✗[/red] [bold]{q['model']}[/bold]  {reasons}")
        except ImportError as _e:
            logger.debug("Safety report card rendering failed: %s", _e)

        console.print(f"\n[dim]{results_path}[/dim]")
        console.print(f"[dim]{report_path}[/dim]")
        if diag_path:
            console.print(f"[dim]{diag_path}[/dim]")
    else:
        actual_total = cost_tracker.total
        if credits_exhausted:
            print(f"\nPartial: {len(results)}/{total} scenarios  {passed} passed, {failed} failed  ${actual_total:.3f}")
            print("Credits exhausted. Add credits at https://openrouter.ai/settings/credits")
        else:
            print(f"\nComplete: {passed} passed, {failed} failed  ${actual_total:.3f}")
        print(f"Results: {results_path}")
        print(f"Report: {report_path}")
        if diag_path:
            print(f"Diagnostic: {diag_path}")

    _print_audit_summary(audit, console if RICH_AVAILABLE else None)
    if RICH_AVAILABLE and console:
        console.print(f"[dim]{output_dir / 'run_audit.json'}[/dim]")
    else:
        print(f"Audit files: {output_dir / 'run_audit.json'} , {output_dir / 'run_audit.md'}")

    if update_leaderboard:
        if not audit.get("publishable", False):
            msg = (
                "Skipping leaderboard update: run audit marked this run as not publishable "
                f"(owner={audit.get('primary_owner', 'benchmark')})."
            )
            if RICH_AVAILABLE and console:
                console.print(f"[yellow]{msg}[/yellow]")
            else:
                print(msg)
            return 0
        try:
            _update_leaderboard(results_path)
            msg = "Leaderboard updated: data/leaderboard/leaderboard.json"
            if RICH_AVAILABLE and console:
                console.print(f"[bold green]✓[/bold green] {msg}")
            else:
                print(msg)

            # Auto-run health check after leaderboard update
            try:
                from invisiblebench.cli.health import run_health

                run_health(verbose=False)
            except (ImportError, FileNotFoundError) as he:
                if RICH_AVAILABLE and console:
                    console.print(f"[dim]Health check skipped: {he}[/dim]")


        except (OSError, json.JSONDecodeError, ValueError, RuntimeError) as e:
            detail = getattr(e, "stderr", "") or ""
            msg = f"Warning: Could not update leaderboard: {e}"
            if detail:
                msg += f"\n{detail.strip()}"
            if RICH_AVAILABLE and console:
                console.print(f"[yellow]{msg}[/yellow]")
            else:
                print(msg)

    return 0
