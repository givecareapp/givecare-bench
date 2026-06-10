#!/usr/bin/env python3
"""InvisibleBench CLI runner."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import statistics
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from invisiblebench.api.client import ModelAPIClient
    from invisiblebench.evaluation.mode_engine import ModeEngine

from dotenv import load_dotenv

from invisiblebench._agent_cli import (
    confirm_or_abort,
    emit_json,
)
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
from invisiblebench.cli.agent_commands import (
    _run_doctor,
    _run_get,
    _run_leaderboard_mutation_json,
    _run_leaderboard_status_json,
)
from invisiblebench.cli.diff import (
    _infer_run_dir_for_output,
    diff_command,
)
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
from invisiblebench.harnesses import adapter_name, is_mode_implemented, resolve_harness_mode
from invisiblebench.models.config import MODELS_FULL as CONFIG_MODELS_FULL
from invisiblebench.models.results import SUCCESS_THRESHOLD, is_result_success
from invisiblebench.results_io import write_json, write_model_results
from invisiblebench.run_artifacts import (
    detect_transcripts_dir,
    load_result_rows,
    write_aggregate_results,
)
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

        # Minimum coverage gate: if coverage rate is below 80%, mark invalid
        if output.coverage_rate < 0.80:
            result["coverage_invalid"] = True
            result["coverage_invalid_reason"] = (
                f"Coverage {output.coverage_rate:.0%} below 80% threshold"
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

    print("\nTranscripts generated. Score with V3 ModeEngine:")
    print(f"  uv run python scripts/run_scan.py {output_dir / 'transcripts'}")

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


def report_command(args) -> int:
    """Generate HTML report from any supported results source."""
    console = Console() if RICH_AVAILABLE else None

    results_path = Path(args.results)
    if not results_path.exists():
        msg = f"Results file not found: {results_path}"
        if console:
            console.print(f"[red]{msg}[/red]")
        else:
            print(msg)
        return 1

    try:
        results = load_result_rows(results_path)
    except (OSError, json.JSONDecodeError, ValueError) as e:
        msg = f"Could not load results: {e}"
        if console:
            console.print(f"[red]{msg}[/red]")
        else:
            print(msg)
        return 1

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = _infer_run_dir_for_output(results_path) / "report.html"

    try:
        from invisiblebench.export.reports import ReportGenerator

        reporter = ReportGenerator()
        reporter.generate_batch_report(
            results,
            str(output_path),
            metadata={"source": str(results_path)},
        )
        if console:
            console.print(f"[green]✓[/green] Report generated: {output_path}")
        else:
            print(f"Report generated: {output_path}")
        return 0
    except (ImportError, OSError) as e:
        msg = f"Failed to generate report: {e}"
        if console:
            console.print(f"[red]{msg}[/red]")
        else:
            print(msg)
        return 1


def diagnose_command(args) -> int:
    """Generate diagnostic report from results JSON."""
    console = Console() if RICH_AVAILABLE else None

    results_path = Path(args.results)
    if not results_path.exists():
        msg = f"Results file not found: {results_path}"
        if console:
            console.print(f"[red]{msg}[/red]")
        else:
            print(msg)
        return 1

    # Determine transcripts directory
    transcripts_dir = Path(args.transcripts) if args.transcripts else detect_transcripts_dir(results_path)

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = (results_path if results_path.is_dir() else results_path.parent) / "diagnostic_report.md"

    try:
        from invisiblebench.export.diagnostic import generate_diagnostic_report

        if results_path.is_file():
            diagnostic_input = results_path
        elif (results_path / "all_results.json").exists():
            diagnostic_input = results_path / "all_results.json"
        else:
            diagnostic_input = write_aggregate_results(results_path)

        report = generate_diagnostic_report(
            results_path=str(diagnostic_input),
            transcripts_dir=str(transcripts_dir) if transcripts_dir else None,
            previous_results_path=args.previous,
            output_path=str(output_path),
        )

        if console:
            console.print(f"[green]✓[/green] Diagnostic report generated: {output_path}")
        else:
            print(f"Diagnostic report generated: {output_path}")

        # Print summary
        lines = report.split("\n")
        summary_start = None
        for i, line in enumerate(lines):
            if line.startswith("## Summary"):
                summary_start = i
                break

        if summary_start and console:
            console.print("\n[bold]Summary:[/bold]")
            for line in lines[summary_start + 2 : summary_start + 10]:
                if line.strip():
                    console.print(f"  {line}")

        return 0
    except (ImportError, OSError, json.JSONDecodeError) as e:
        msg = f"Failed to generate diagnostic report: {e}"
        if console:
            console.print(f"[red]{msg}[/red]")
        else:
            print(msg)
        import traceback

        traceback.print_exc()
        return 1


def audit_command(args) -> int:
    """Generate run audit artifacts from a run/results source."""
    console = Console() if RICH_AVAILABLE else None

    results_path = Path(args.results)
    if not results_path.exists():
        msg = f"Results source not found: {results_path}"
        if console:
            console.print(f"[red]{msg}[/red]")
        else:
            print(msg)
        return 1

    try:
        audit = audit_results_source(
            results_path,
            expected_scenario_count=args.expected_scenarios,
            harness=args.harness,
            mode=args.mode,
            previous_source=args.previous,
        )
    except (OSError, json.JSONDecodeError, ValueError) as e:
        msg = f"Failed to audit results: {e}"
        if console:
            console.print(f"[red]{msg}[/red]")
        else:
            print(msg)
        return 1

    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = _infer_run_dir_for_output(results_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "run_audit.json", audit)
    (output_dir / "run_audit.md").write_text(render_audit_markdown(audit))

    _print_audit_summary(audit, console)
    if console:
        console.print(f"[green]✓[/green] Audit written: {output_dir / 'run_audit.json'}")
    else:
        print(f"Audit written: {output_dir / 'run_audit.json'}")
    return 0 if audit.get("run_valid") else 1


# _infer_run_dir_for_output, resolve_run_reference, load_run_results, aggregate_results_by_model,
# compute_run_diff, _format_score/_delta/_status_counts, _print_diff_table, diff_command
# moved to invisiblebench.cli.diff


# resolve_run_reference, load_run_results, aggregate_results_by_model, compute_run_diff,
# _format_score/_delta/_status_counts, _print_diff_table, diff_command: all moved to invisiblebench.cli.diff



# ---------- agent-friendly helpers ----------
# Note: _collect_runs and _run_runs stay in this module (tests monkeypatch them here)


def _collect_runs() -> list[dict[str, Any]]:
    """Return run records sorted newest first, with narrow fields."""
    from invisiblebench.cli.agent_commands import _runs_dir
    from invisiblebench.cli.archive import list_runs

    results_dir = _runs_dir()
    if not results_dir.exists():
        return []
    runs = list_runs(results_dir)
    runs.sort(key=lambda r: r.get("date") or datetime.min, reverse=True)
    records: list[dict[str, Any]] = []
    for r in runs:
        records.append(
            {
                "id": r["name"],
                "date": r["date"].strftime("%Y-%m-%d") if r.get("date") else None,
                "models": r.get("models", []),
                "scenarios": r.get("scenarios", 0),
                "size_mb": round(r.get("size_mb", 0.0), 2),
                "has_results": r.get("has_results", False),
            }
        )
    return records


def _run_runs(
    *,
    limit: int,
    offset: int,
    json_output: bool,
    out_path: str | None = None,
) -> int:
    """Handle `bench runs` with optional --limit/--offset/--json/--out."""
    from invisiblebench.cli.agent_commands import _emit_or_write_json

    records = _collect_runs()
    total = len(records)
    if offset < 0:
        offset = 0
    if limit is None or limit < 0:
        limit = 25
    sliced = records[offset : offset + limit]

    if json_output or out_path:
        payload = {
            "total": total,
            "limit": limit,
            "offset": offset,
            "runs": sliced,
        }
        return _emit_or_write_json(
            command="runs",
            data=payload,
            record_count=len(sliced),
            out_path=out_path,
        )

    if not sliced:
        print("No runs found.")
        return 0

    if RICH_AVAILABLE:
        console = Console()
        table = Table(title=f"Benchmark Runs ({offset + 1}-{offset + len(sliced)} of {total})")
        table.add_column("Date", style="cyan")
        table.add_column("Run ID")
        table.add_column("Models")
        table.add_column("Scenarios", justify="right")
        table.add_column("Size", justify="right")
        table.add_column("Results")
        for r in sliced:
            models = ", ".join(r["models"][:2])
            if len(r["models"]) > 2:
                models += f" +{len(r['models']) - 2}"
            table.add_row(
                r["date"] or "unknown",
                r["id"],
                models or "-",
                str(r["scenarios"]) if r["scenarios"] else "-",
                f"{r['size_mb']:.1f}MB",
                "yes" if r["has_results"] else "no",
            )
        console.print(table)
    else:
        for r in sliced:
            print(f"{r['date'] or 'unknown'} | {r['id']} | {r['size_mb']:.1f}MB")

    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="InvisibleBench - AI Safety Benchmark Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  # Model Evaluation (raw LLM capability)
  uv run bench --full -y                    All {len(CONFIG_MODELS_FULL)} models (run --dry-run for current estimate)
  uv run bench -m deepseek -y               Single model by name
  uv run bench -m gpt-5.2,claude -y         Multiple models by name
  uv run bench -m 1-4 -y                    Models 1-4 (by index)
  uv run bench -m 7 -y                      Model 7 = DeepSeek V3.2
  uv run bench -c safety,empathy -y         Safety + empathy categories only
  uv run bench --harness llm --mode raw -m deepseek -y

  # Eval Harness (GiveCare/Mira product)
  uv run bench --harness givecare --mode v2 -y                Full V2 runtime path
  uv run bench --provider givecare -y                         Alias for givecare/v2
  INVISIBLEBENCH_PRIVATE_CONFIDENTIAL_SCENARIOS_DIR=/path/to/private/confidential uv run bench --harness givecare --mode v2 -y --confidential
  uv run bench --harness givecare --mode v2 -c safety -y

  # Diagnostics
  uv run bench --provider givecare -y --diagnose  Run with diagnostic report
  uv run bench diagnose results.json              Generate diagnostic from results

  # Leaderboard
  uv run bench leaderboard add results/run_*/all_results.json  Add model to leaderboard
  uv run bench leaderboard rebuild    Rebuild from canonical files
  uv run bench leaderboard status     Health check (alias for 'bench health')

  # Statistics & Reliability
  uv run bench stats results/run_*/all_results.json       Score distributions + bootstrap CIs
  uv run bench stats results/leaderboard_ready/ -o s.md   With markdown output
  uv run bench reliability results/run_20260211/           Scorer inter-rater reliability
  uv run bench annotate export results/run_20260211/       Export annotation kit
  uv run bench annotate import results/annotations/scores.csv  Compute agreement

  # Utilities
  uv run bench report results.json    Regenerate HTML report
  uv run bench health                 Check leaderboard for issues
  uv run bench runs                   List all benchmark runs
  uv run bench diff <base> <new>      Compare two benchmark runs
  uv run bench archive --keep 5       Keep 5 most recent runs
        """,
    )

    parser.add_argument(
        "--json",
        "--format",
        dest="json_output",
        action="store_const",
        const="json",
        default=None,
        help="Emit agent-friendly JSON envelope (runs/stats/leaderboard[add|rebuild|status]/get)",
    )

    subparsers = parser.add_subparsers(dest="command")

    # Doctor subcommand
    subparsers.add_parser("doctor", help="Validate env vars and runs dir")

    # Get subcommand (read single run by id)
    get_parser = subparsers.add_parser("get", help="Read a single run's metadata by id")
    get_parser.add_argument("run_id", type=str, help="Run directory name or prefix")
    get_parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Write full JSON payload to PATH; stdout gets {path,byte_count,record_count} summary",
    )

    # Report subcommand
    report_parser = subparsers.add_parser("report", help="Generate HTML report from results JSON")
    report_parser.add_argument("results", type=str, help="Path to all_results.json")
    report_parser.add_argument("--output", "-o", type=str, default=None, help="Output HTML path")

    # Health subcommand
    health_parser = subparsers.add_parser("health", help="Check leaderboard health and flag issues")
    health_parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed info")

    # Archive subcommand
    archive_parser = subparsers.add_parser("archive", help="Archive old benchmark runs")
    archive_parser.add_argument("--before", type=str, help="Archive runs before date (YYYYMMDD)")
    archive_parser.add_argument("--keep", type=int, help="Keep N most recent runs")
    archive_parser.add_argument(
        "--list", action="store_true", dest="list_runs", help="List runs (dry run)"
    )
    archive_parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be archived"
    )

    # Clean subcommand (alias for archive)
    clean_parser = subparsers.add_parser("clean", help="Clean up old runs (alias for archive)")
    clean_parser.add_argument("--before", type=str, help="Archive runs before date (YYYYMMDD)")
    clean_parser.add_argument("--keep", type=int, help="Keep N most recent runs")
    clean_parser.add_argument(
        "--list", action="store_true", dest="list_runs", help="List runs (dry run)"
    )
    clean_parser.add_argument("--dry-run", action="store_true", help="Show what would be archived")

    # Runs subcommand (list runs)
    runs_parser = subparsers.add_parser("runs", help="List all benchmark runs")
    runs_parser.add_argument("--limit", type=int, default=25, help="Max rows (default 25)")
    runs_parser.add_argument("--offset", type=int, default=0, help="Skip N rows (default 0)")
    runs_parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Write full JSON payload to PATH; stdout gets {path,byte_count,record_count} summary",
    )

    # Diff subcommand
    diff_parser = subparsers.add_parser("diff", help="Compare two benchmark runs")
    diff_parser.add_argument("base_run", type=str, help="Base run reference")
    diff_parser.add_argument("new_run", type=str, help="New run reference")

    # Rescore subcommand
    rescore_parser = subparsers.add_parser(
        "rescore", help="Rescore existing transcripts without re-running models"
    )
    rescore_parser.add_argument("run_dir", type=str, help="Path to run directory with transcripts/")
    rescore_parser.add_argument(
        "--update-leaderboard", action="store_true", help="Update leaderboard after rescoring"
    )

    # Diagnose subcommand
    diagnose_parser = subparsers.add_parser(
        "diagnose", help="Generate diagnostic report from results"
    )
    diagnose_parser.add_argument("results", type=str, help="Path to results JSON")
    diagnose_parser.add_argument("--transcripts", "-t", type=str, help="Transcripts directory")
    diagnose_parser.add_argument(
        "--previous", "-p", type=str, help="Previous results for comparison"
    )
    diagnose_parser.add_argument("--output", "-o", type=str, help="Output markdown path")

    audit_parser = subparsers.add_parser(
        "audit", help="Audit a run/results source and classify benchmark failure modes"
    )
    audit_parser.add_argument("results", type=str, help="Path to run dir, results JSON, or model_results/")
    audit_parser.add_argument("--previous", "-p", type=str, help="Previous run/results source for comparability checks")
    audit_parser.add_argument("--expected-scenarios", type=int, default=None, help="Expected scenario count per model/provider")
    audit_parser.add_argument("--harness", type=str, choices=["llm", "givecare"], default=None)
    audit_parser.add_argument("--mode", type=str, default=None)
    audit_parser.add_argument("--output-dir", type=str, default=None, help="Directory for run_audit.json and run_audit.md")

    # Leaderboard subcommand
    lb_parser = subparsers.add_parser(
        "leaderboard", help="Manage leaderboard (add, rebuild, status)"
    )
    lb_parser.add_argument(
        "action",
        choices=["add", "rebuild", "status"],
        help="add: add results to leaderboard, rebuild: regenerate from canonical files, status: health check",
    )
    lb_parser.add_argument(
        "results", nargs="?", default=None, help="Path to all_results.json (for 'add')"
    )
    lb_parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed info")
    lb_parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="For --json status: write full leaderboard to PATH; stdout gets summary envelope",
    )

    # Stats subcommand
    stats_parser = subparsers.add_parser(
        "stats", help="Statistical analysis: distributions, bootstrap CIs, pairwise comparisons"
    )
    stats_parser.add_argument(
        "results", type=str, help="Path to all_results.json or leaderboard_ready/ directory"
    )
    stats_parser.add_argument(
        "--output", "-o", type=str, default=None, help="Output markdown path"
    )
    stats_parser.add_argument(
        "--bootstrap", type=int, default=10000, help="Number of bootstrap samples (default: 10000)"
    )

    # Reliability subcommand
    rel_parser = subparsers.add_parser(
        "reliability", help="Scorer inter-rater reliability (runs LLM scorers N times)"
    )
    rel_parser.add_argument(
        "results", type=str, help="Path to results directory with transcripts"
    )
    rel_parser.add_argument(
        "--runs", "-n", type=int, default=5, help="Number of scoring runs (default: 5)"
    )
    rel_parser.add_argument(
        "--sample", type=int, default=10, help="Number of transcripts to sample (default: 10)"
    )
    rel_parser.add_argument(
        "--output", "-o", type=str, default=None, help="Output directory for raw data"
    )

    # Annotate subcommand
    annotate_parser = subparsers.add_parser(
        "annotate", help="Human annotation kit for human-LLM agreement"
    )
    annotate_parser.add_argument(
        "action",
        choices=["export", "import"],
        help="export: create scoring forms, import: compute agreement",
    )
    annotate_parser.add_argument(
        "path", type=str, help="Results path (export) or annotations CSV path (import)"
    )
    annotate_parser.add_argument(
        "--output", "-o", type=str, default=None, help="Output directory (export) or unused (import)"
    )
    annotate_parser.add_argument(
        "--sample", type=int, default=20, help="Number of transcripts to sample (default: 20)"
    )
    annotate_parser.add_argument(
        "--llm-scores", type=str, default=None, help="Path to _llm_scores.json (for import)"
    )

    # Main run arguments (default command)
    parser.add_argument("--full", action="store_true", help=f"All {len(CONFIG_MODELS_FULL)} models × all scenarios")

    parser.add_argument("--output", type=Path, default=None, help="Output directory")
    parser.add_argument(
        "--harness",
        type=str,
        choices=["llm", "givecare"],
        default=None,
        help="Evaluation surface to run: 'llm' (benchmark core) or 'givecare' (system harnesses)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default=None,
        help="Harness mode. LLM: raw. GiveCare: v2",
    )
    parser.add_argument("--dry-run", action="store_true", help="Estimate costs only")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-confirm")
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Write per-scenario JSON/HTML reports with turn flags",
    )
    parser.add_argument(
        "--category",
        "-c",
        type=str,
        default=None,
        help="Filter to specific categories (e.g., 'safety' or 'safety,empathy')",
    )
    parser.add_argument(
        "--scenario",
        "-s",
        type=str,
        default=None,
        help="Filter to specific scenarios by ID or name (comma-separated)",
    )
    parser.add_argument(
        "--parallel",
        "-p",
        type=int,
        default=None,
        metavar="N",
        help="Run N models in parallel (default: sequential)",
    )
    parser.add_argument(
        "--scenario-parallel",
        type=int,
        default=1,
        metavar="N",
        help="Run up to N scenarios concurrently per model for the llm/raw harness (default: 1)",
    )
    parser.add_argument(
        "--models",
        "-m",
        type=str,
        default=None,
        metavar="SPEC",
        help="Select models by name or number: 'deepseek', 'gpt-5.2,claude', '1-4', '7', '1,deepseek'",
    )
    parser.add_argument(
        "--update-leaderboard",
        action="store_true",
        help="Update public leaderboard after run completes (llm/raw only)",
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=["openrouter", "givecare"],
        default="openrouter",
        help="Select the eval harness target (openrouter=LLM, givecare=V2 system)",
    )
    parser.add_argument(
        "--confidential",
        action="store_true",
        help=(
            "Include private confidential scenarios via "
            "INVISIBLEBENCH_PRIVATE_CONFIDENTIAL_SCENARIOS_DIR"
        ),
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="Generate diagnostic report after run (actionable fix suggestions)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        metavar="N",
        help="Run each scenario N times and take median score (default: 1)",
    )

    args = parser.parse_args(argv)

    json_output = bool(getattr(args, "json_output", None))

    if args.command == "doctor":
        return _run_doctor()

    if args.command == "get":
        return _run_get(
            args.run_id,
            json_output=json_output,
            out_path=getattr(args, "out", None),
        )

    if args.command == "report":
        return report_command(args)

    if args.command == "audit":
        return audit_command(args)

    if args.command == "health":
        from invisiblebench.cli.health import run_health

        return run_health(verbose=args.verbose)

    if args.command in ("archive", "clean"):
        from invisiblebench.cli.archive import run_archive, run_list

        if args.list_runs:
            return run_list()
        if args.before is None and args.keep is None:
            print(
                f"{args.command}: pass --before YYYYMMDD or --keep N",
                file=sys.stderr,
            )
            return 2
        if not args.dry_run:
            if args.before and args.keep is not None:
                prompt = f"archive runs older than {args.before}, keeping {args.keep} most recent"
            elif args.before:
                prompt = f"archive runs older than {args.before}"
            else:
                prompt = f"archive runs keeping {args.keep} most recent"
            confirm_or_abort(prompt, yes=bool(getattr(args, "yes", False)))
        return run_archive(before=args.before, keep=args.keep, dry_run=args.dry_run)

    if args.command == "runs":
        return _run_runs(
            limit=getattr(args, "limit", 25),
            offset=getattr(args, "offset", 0),
            json_output=json_output,
            out_path=getattr(args, "out", None),
        )

    if args.command == "diff":
        return diff_command(args)

    if args.command == "rescore":
        print("ERROR: V2 rescore has been archived. Use V3 ModeEngine scoring:")
        print("  uv run python scripts/run_scan.py <run_dir>")
        return 1

    if args.command == "diagnose":
        return diagnose_command(args)

    if args.command == "leaderboard":
        if args.action in ("add", "rebuild"):
            confirm_or_abort(
                f"leaderboard {args.action}"
                + (f" {args.results}" if args.results else ""),
                yes=bool(getattr(args, "yes", False)),
            )
        if json_output:
            if args.action == "status":
                return _run_leaderboard_status_json(out_path=getattr(args, "out", None))
            if args.action in ("add", "rebuild"):
                return _run_leaderboard_mutation_json(args.action, args.results)
        from invisiblebench.cli.leaderboard import run_leaderboard

        return run_leaderboard(
            action=args.action,
            results_path=args.results,
            verbose=args.verbose,
        )

    if args.command == "stats":
        from invisiblebench.stats.analysis import (
            compute_stats,
            format_stats_markdown,
            format_stats_report,
        )

        stats = compute_stats(args.results, n_bootstrap=args.bootstrap)
        if "error" in stats:
            if json_output:
                emit_json(status="error", command="stats", error=stats["error"])
            else:
                print(f"Error: {stats['error']}")
            return 1
        if json_output:
            emit_json(command="stats", data=stats)
        else:
            print(format_stats_report(stats))
        if args.output:
            Path(args.output).write_text(format_stats_markdown(stats))
            if not json_output:
                print(f"\nMarkdown report written to {args.output}")
            else:
                print(f"wrote: {args.output}", file=sys.stderr)
        return 0

    if args.command == "reliability":
        print("ERROR: V2 reliability analysis has been archived.")
        print("V3 uses per-mode K-repetition voting for reliability.")
        print("Run: uv run python scripts/run_scan.py --enable-llm <run_dir>")
        return 1

    if args.command == "annotate":
        if args.action == "export":
            from invisiblebench.stats.annotation import export_annotation_kit

            out_dir = args.output or "results/annotations"
            result = export_annotation_kit(
                args.path, out_dir, sample_size=args.sample
            )
            if "error" in result:
                print(f"Error: {result['error']}")
                return 1
            print(f"Exported {result['exported']} transcripts to {result['output_dir']}/")
            print(f"  Forms: {len(result['files']['forms'])} markdown files")
            print(f"  CSV template: {result['files']['csv_template']}")
            print(f"  Instructions: {result['files']['instructions']}")
            return 0
        else:  # import
            from invisiblebench.stats.annotation import (
                format_agreement_report,
                import_annotations,
            )

            result = import_annotations(args.path, llm_scores_path=args.llm_scores)
            if "error" in result:
                print(f"Error: {result['error']}")
                return 1
            print(format_agreement_report(result))
            return 0

    category_filter = None
    if args.category:
        category_filter = [c.strip().lower() for c in args.category.split(",")]

    scenario_filter = None
    if args.scenario:
        scenario_filter = [s.strip().lower() for s in args.scenario.split(",")]

    try:
        harness_name, harness_mode = resolve_harness_mode(
            harness=args.harness,
            provider=args.provider,
            mode=args.mode,
        )
    except ValueError as e:
        print(str(e))
        return 1

    if not is_mode_implemented(harness_name, harness_mode):
        print(
            f"Harness mode not implemented yet: {harness_name}/{harness_mode}. "
            f"Use '{harness_name}/{'v2' if harness_name == 'givecare' else 'raw'}' for now."
        )
        return 1

    if harness_name == "givecare":
        return run_givecare_eval(
            category_filter=category_filter,
            scenario_filter=scenario_filter,
            include_confidential=args.confidential,
            verbose=True,
            dry_run=args.dry_run,
            auto_confirm=args.yes,
            generate_diagnostic=args.diagnose,
            output_dir=args.output,
            adapter_name=adapter_name(harness_name, harness_mode),
            harness_mode=harness_mode,
            update_leaderboard=args.update_leaderboard,
        )

    # Default: raw LLM benchmark via llm/raw harness
    all_models = MODELS_FULL

    # Resolve which models to run
    if args.full:
        models = all_models
    elif args.models:
        try:
            indices = resolve_models(args.models, all_models)
            if not indices:
                msg = f"No models match '{args.models}' (have {len(all_models)} models)"
                print(msg)
                return 1
            models = [all_models[i] for i in indices]
            selected = [m["name"] for m in models]
            if RICH_AVAILABLE:
                Console().print(f"[cyan]Models: {', '.join(selected)}[/cyan]")
            else:
                print(f"Models: {', '.join(selected)}")
        except ValueError as e:
            if RICH_AVAILABLE:
                Console().print(f"[red]{e}[/red]")
            else:
                print(str(e))
            return 1
    else:
        # No --full and no -m: show catalog and exit
        if RICH_AVAILABLE:
            c = Console()
            c.print("[bold]No model selected.[/bold] Use [cyan]--full[/cyan] or [cyan]-m SPEC[/cyan].\n")
            c.print("[bold]Available models:[/bold]")
            for i, m in enumerate(all_models):
                c.print(f"  [dim]{i+1:>2}.[/dim] {m['name']:<24} [dim]{m['id']}[/dim]")
            c.print("\n[dim]Examples:  bench --full -y  |  bench -m deepseek -y  |  bench -m 1-4 -y[/dim]")
        else:
            print("No model selected. Use --full or -m SPEC.\n")
            print("Available models:")
            for i, m in enumerate(all_models):
                print(f"  {i+1:>2}. {m['name']:<24} {m['id']}")
            print("\nExamples:  bench --full -y  |  bench -m deepseek -y  |  bench -m 1-4 -y")
        return 1

    if args.output:
        output_dir = args.output
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(f"results/run_{timestamp}")

    return run_benchmark(
        models=models,
        output_dir=output_dir,
        dry_run=args.dry_run,
        auto_confirm=args.yes,
        category_filter=category_filter,
        scenario_filter=scenario_filter,
        parallel=args.parallel,
        scenario_parallel=args.scenario_parallel,
        detailed_output=args.detailed,
        update_leaderboard=args.update_leaderboard,
        generate_diagnostic=args.diagnose,
        runs=getattr(args, "runs", 1),
        include_confidential=args.confidential,
    )


if __name__ == "__main__":
    sys.exit(main())
