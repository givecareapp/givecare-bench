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
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

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
    DEFAULT_JUDGE_MODEL,
    CostBudgetExceededError,
    InsufficientCreditsError,
    cost_tracker,
    maximum_reasonable_cost_ceiling,
)
from invisiblebench.cli._console import make_console
from invisiblebench.cli.display import print_banner
from invisiblebench.cli.result_helpers import (
    _compute_success as _compute_success,  # re-exported: tests import from this module
)
from invisiblebench.cli.result_helpers import (
    _make_harness_error_result,
    _safe_load_scenario_data,
)
from invisiblebench.cli.transcript import (
    evaluate_scenario_async,
)
from invisiblebench.models.config import MODELS_FULL as CONFIG_MODELS_FULL
from invisiblebench.models.results import (
    PUBLIC_SCORE_MODEL,
    RAW_RESULT_SURFACE,
    RAW_SCORE_MODEL,
    is_result_success,
)
from invisiblebench.results_io import write_json, write_model_results
from invisiblebench.run_audit import audit_results_source, render_audit_markdown
from invisiblebench.utils.benchmark_inventory import (
    collect_scenario_paths,
    get_private_confidential_dir,
    get_project_root,
    scenario_category_for_path,
)
from invisiblebench.utils.manifest import generate_manifest, write_manifest

try:
    import rich  # noqa: F401 — availability probe for RICH_AVAILABLE

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

logger = logging.getLogger(__name__)

# Shared NO_COLOR/isatty-honoring Console factory (returns None without rich).
Console = make_console

load_dotenv()


# Token estimates per category for cost calculation
# Calibrated from actual benchmark runs (Jan 2026) - includes system prompt
# and conversation history growth
TOKEN_ESTIMATES = {
    1: {"input": 5500, "output": 1400},  # 3-5 turns
    2: {"input": 14000, "output": 3300},  # 8-12 turns
    3: {"input": 27000, "output": 6000},  # 20+ turns, multi-session
}
# The 2026-07-10 six-model live canary cost 1.34x its token-table estimate.
# Reserve 1.5x so the number shown before a paid transcript run is a budget,
# not a best-case point estimate.
TRANSCRIPT_COST_SAFETY_FACTOR = 1.5

# SYSTEM_PROMPT is imported from invisiblebench.cli.transcript

MODELS_FULL = [model.model_dump() for model in CONFIG_MODELS_FULL]


def run_givecare_eval(
    category_filter: list[str] | None = None,
    scenario_filter: list[str] | None = None,
    include_confidential: bool = False,
    verbose: bool = True,
    dry_run: bool = False,
    auto_confirm: bool = False,
    output_dir: Path | None = None,
    adapter_name: str = "givecare-v2",
    harness_mode: str = "v2",
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
    # path: V2 inline scoring was superseded by the ModeEngine), skip the
    # raw zero-row summary and BLOCK audit printout — they are misleading.
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
    print(f"Surface:   {RAW_RESULT_SURFACE} ({RAW_SCORE_MODEL}); public model {PUBLIC_SCORE_MODEL}")
    print(f"Average:   {avg_score:.1f}% raw diagnostic score")
    print(f"{'='*50}")
    print(f"Saved: {results_path}")

    _print_audit_summary(audit)
    print(f"Audit files: {output_dir / 'run_audit.json'} , {output_dir / 'run_audit.md'}")

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
        scenario_id = path.stem
        title = path.stem.replace("_", " ").title()
        try:
            with path.open(encoding="utf-8") as fh:
                scenario_data = json.load(fh)
            scenario_id = str(scenario_data.get("scenario_id") or scenario_id)
            title = str(scenario_data.get("title") or title)
        except (OSError, json.JSONDecodeError):
            pass
        scenarios.append(
            {
                "category": scenario_category_for_path(path, private_confidential_dir),
                "path": str(path),
                "name": title,
                "scenario_id": scenario_id,
            }
        )

    return scenarios


def estimate_cost(category: str, model: dict[str, Any]) -> float:
    """Return a conservative budget for one target-model transcript run."""
    token_key = CATEGORY_TOKEN_MAP.get(category, 1)
    tokens = TOKEN_ESTIMATES.get(token_key, TOKEN_ESTIMATES[1])

    base_cost = (tokens["input"] / 1_000_000) * model["cost_per_m_input"] + (
        tokens["output"] / 1_000_000
    ) * model["cost_per_m_output"]
    return base_cost * TRANSCRIPT_COST_SAFETY_FACTOR


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


def _write_transcript_run_summary(
    *,
    output_dir: Path,
    manifest: dict[str, Any],
    models: list[dict[str, Any]],
    scenarios: list[dict[str, Any]],
    results: list[dict[str, Any]],
    elapsed_seconds: float,
    cost_snapshot: dict[str, Any],
    abort_reason: str | None = None,
) -> Path:
    ready = [r for r in results if r.get("status") == "transcript_ready"]
    errors = [r for r in results if r.get("status") != "transcript_ready"]
    expected_transcripts = len(models) * len(scenarios)
    missing_count = max(expected_transcripts - len(ready) - len(errors), 0)
    is_complete = (
        len(ready) == expected_transcripts
        and not errors
        and missing_count == 0
        and abort_reason is None
    )

    def _artifact_transcript_path(row: dict[str, Any]) -> str | None:
        raw_path = row.get("transcript_path")
        if not isinstance(raw_path, str) or not raw_path:
            return None
        path = Path(raw_path)
        try:
            resolved = path if path.is_absolute() else path.resolve()
            return str(resolved.relative_to(output_dir.resolve()))
        except ValueError:
            return str(path)

    summary = {
        "artifact_type": "transcript_run/v1",
        "run_id": manifest.get("run_id"),
        "benchmark_version": manifest.get("benchmark_version"),
        "contract_version": manifest.get("contract_version"),
        "stage": "transcripts",
        "status": "complete" if is_complete else "partial",
        "model_ids": [m["id"] for m in models],
        "scenario_count": len(scenarios),
        "expected_transcripts": expected_transcripts,
        "transcript_count": len(ready),
        "error_count": len(errors),
        "missing_count": missing_count,
        "abort_reason": abort_reason,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "actual_cost_usd": cost_snapshot["total"],
        "actual_billable_api_calls": cost_snapshot["calls"],
        "actual_cost_by_model_usd": cost_snapshot["by_model"],
        "runtime_cost_ceiling_usd": cost_snapshot["max_cost_usd"],
        "transcripts": [
            {
                "model": r.get("model"),
                "model_id": r.get("model_id"),
                "scenario": r.get("scenario"),
                "scenario_id": r.get("scenario_id"),
                "category": r.get("category"),
                "transcript_path": _artifact_transcript_path(r),
            }
            for r in ready
        ],
        "errors": [
            {
                "model": r.get("model"),
                "model_id": r.get("model_id"),
                "scenario": r.get("scenario"),
                "scenario_id": r.get("scenario_id"),
                "category": r.get("category"),
                "reason": "; ".join(str(x) for x in r.get("hard_fail_reasons", []))
                or r.get("error")
                or r.get("status"),
            }
            for r in errors
        ],
        "next_steps": {
            "dev_scan": (
                "uv run python scripts/run_scan.py --profile dev --enable-llm "
                "--max-cost-usd 25 "
                f"--llm-model {DEFAULT_JUDGE_MODEL} "
                f"{output_dir}"
            ),
            "publish_scan_dry_run": (
                "uv run python scripts/run_scan.py --profile publish --dry-run --enable-llm "
                f"--llm-model {DEFAULT_JUDGE_MODEL} "
                f"{output_dir}"
            ),
        },
    }
    path = output_dir / "transcript_run.json"
    write_json(path, summary)
    return path


def _print_transcript_next_steps(output_dir: Path, console: Console | None = None) -> None:
    dev_cmd = (
        "uv run python scripts/run_scan.py --profile dev --enable-llm "
        "--max-cost-usd 25 "
        f"--llm-model {DEFAULT_JUDGE_MODEL} "
        f"{output_dir}"
    )
    publish_dry_run_cmd = (
        "uv run python scripts/run_scan.py --profile publish --dry-run --enable-llm "
        f"--llm-model {DEFAULT_JUDGE_MODEL} "
        f"{output_dir}"
    )
    if console:
        console.print("[cyan]Next stage: judge transcripts with Safety/Care scan[/cyan]")
        console.print(f"[dim]{dev_cmd}[/dim]")
        console.print(f"[dim]{publish_dry_run_cmd}[/dim]")
    else:
        print("Next stage: judge transcripts with Safety/Care scan")
        print(dev_cmd)
        print(publish_dry_run_cmd)


def run_benchmark(
    models: list[dict[str, Any]],
    output_dir: Path,
    dry_run: bool = False,
    auto_confirm: bool = False,
    category_filter: list[str] | None = None,
    scenario_filter: list[str] | None = None,
    parallel: int | None = None,
    scenario_parallel: int = 1,
    include_confidential: bool = False,
    max_cost_usd: float | None = None,
) -> int:
    """Run the benchmark (transcript-only; judging happens later via run_scan)."""
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
    scenario_parallel = max(1, scenario_parallel)
    total_cost = sum(
        estimate_cost(s["category"], m)
        for m in models
        for s in scenarios
    )

    if RICH_AVAILABLE and console:
        print_banner(console, "full", models, scenarios, total_cost)
        console.print("[cyan]Transcript-only mode: judge/scorer calls are skipped[/cyan]\n")
    else:
        print("\nInvisibleBench")
        print(f"Models: {len(models)}, Scenarios: {len(scenarios)}")
        print(f"Total: {total} evaluations, Est. cost: ${total_cost:.2f}\n")
        print("Transcript-only mode: judge/scorer calls are skipped")

    if dry_run:
        if RICH_AVAILABLE and console:
            console.print("[yellow]DRY RUN[/yellow] - No evaluations will be run\n")
            console.print(
                "[cyan]Conservative budget includes target transcript generation only. "
                f"Use scripts/run_scan.py --dry-run for {DEFAULT_JUDGE_MODEL} judging cost.[/cyan]\n"
            )
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
            print(
                "Conservative budget includes target transcript generation only. "
                f"Use scripts/run_scan.py --dry-run for {DEFAULT_JUDGE_MODEL} judging cost."
            )
            print("\nSelected models:")
            all_catalog = MODELS_FULL
            for m in models:
                idx = next(
                    (i for i, c in enumerate(all_catalog) if c["id"] == m["id"]),
                    None,
                )
                num = f"#{idx + 1}" if idx is not None else "#?"
                print(f"  {num:<4} {m['name']}")
        print(
            "Maximum accepted runtime ceiling: "
            f"${maximum_reasonable_cost_ceiling(total_cost):.2f}"
        )
        return 0

    if max_cost_usd is None:
        print(
            "ERROR: Live transcript generation requires --max-cost-usd. "
            "Run with --dry-run first."
        )
        return 2
    if max_cost_usd < 0:
        print("ERROR: --max-cost-usd must be non-negative")
        return 2
    if total_cost > max_cost_usd:
        print(
            f"ERROR: Conservative transcript budget ${total_cost:.2f} exceeds "
            f"--max-cost-usd ${max_cost_usd:.2f}"
        )
        return 2
    maximum_ceiling = maximum_reasonable_cost_ceiling(total_cost)
    if max_cost_usd > maximum_ceiling:
        print(
            f"ERROR: --max-cost-usd ${max_cost_usd:.2f} is not a meaningful guardrail "
            f"for the ${total_cost:.2f} conservative plan; use at most ${maximum_ceiling:.2f}"
        )
        return 2

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

        cost_tracker.reset(max_cost_usd=max_cost_usd)
        api_client = ModelAPIClient()
    except (ImportError, ValueError) as e:
        print(f"ERROR: Failed to initialize API client: {e}")
        return 1

    root = get_project_root()

    run_id = str(uuid.uuid4())
    manifest = generate_manifest(
        project_root=root,
        model_ids=[m["id"] for m in models],
        run_id=run_id,
        harness="llm",
        mode="raw",
        include_confidential=include_confidential,
    )
    manifest["artifact_type"] = "transcript_run/v1"
    manifest["stage"] = "transcripts"
    manifest["scoring"] = "deferred_to_run_scan"
    write_manifest(manifest, output_dir)

    start_time = time.time()
    passed = 0
    failed = 0

    print(f"Generating transcripts only ({len(models)} model(s), {len(scenarios)} scenario(s))")
    print("Scoring is deferred to scripts/run_scan.py\n")
    transcript_rows: list[dict[str, Any]] = []

    async def run_transcript_model(model: dict[str, Any]) -> list[dict[str, Any]]:
        semaphore = asyncio.Semaphore(scenario_parallel)

        async def run_indexed(
            index: int,
            scenario: dict[str, Any],
        ) -> tuple[int, dict[str, Any]]:
            result = await evaluate_scenario_async(
                model,
                scenario,
                api_client,
                output_dir,
                semaphore,
                run_id=run_id,
            )
            return index, result

        tasks = [
            asyncio.create_task(run_indexed(index, scenario))
            for index, scenario in enumerate(scenarios)
        ]
        completed: list[tuple[int, dict[str, Any]]] = []

        try:
            for task in asyncio.as_completed(tasks):
                idx, result = await task
                completed.append((idx, result))
                transcript_rows.append(result)
                is_error = result.get("status") in ("fail", "error") or result.get("hard_fail")
                status = "ERROR" if is_error else "TRANSCRIPT"
                print(
                    f"[{len(completed)}/{len(tasks)}] {model['name']} - "
                    f"{result.get('scenario', 'unknown')} {status}"
                )
        except (InsufficientCreditsError, CostBudgetExceededError):
            for task in tasks:
                task.cancel()
            raise

        return [result for _, result in sorted(completed, key=lambda item: item[0])]

    async def run_transcripts() -> list[dict[str, Any]]:
        model_parallel = max(1, parallel or 1)
        if model_parallel <= 1:
            rows: list[dict[str, Any]] = []
            for model in models:
                rows.extend(await run_transcript_model(model))
            return rows

        model_semaphore = asyncio.Semaphore(model_parallel)

        async def run_model_with_sem(model: dict[str, Any]) -> list[dict[str, Any]]:
            async with model_semaphore:
                return await run_transcript_model(model)

        nested = await asyncio.gather(*(run_model_with_sem(model) for model in models))
        return [row for model_rows in nested for row in model_rows]

    try:
        results = asyncio.run(run_transcripts())
    except CostBudgetExceededError as exc:
        results = transcript_rows
        print(f"\n{exc}. Saving transcript summary for completed scenarios.")
        abort_reason = "cost_budget_exceeded"
    except InsufficientCreditsError:
        results = transcript_rows
        print("\nCredits exhausted. Saving transcript summary for completed scenarios.")
        abort_reason = "credits_exhausted"
    except Exception as e:
        print(f"ERROR: Transcript generation failed: {e}")
        return 1
    else:
        abort_reason = None

    for row in results:
        if row.get("status") == "transcript_ready":
            passed += 1
        else:
            failed += 1

    elapsed = time.time() - start_time
    cost_snapshot = cost_tracker.snapshot()
    actual_total = cost_snapshot["total"]
    summary_path = _write_transcript_run_summary(
        output_dir=output_dir,
        manifest=manifest,
        models=models,
        scenarios=scenarios,
        results=results,
        elapsed_seconds=elapsed,
        cost_snapshot=cost_snapshot,
        abort_reason=abort_reason,
    )

    was_aborted = abort_reason is not None
    state = "Partial" if failed or was_aborted else "Complete"
    print(
        f"\n{state}: {passed} transcripts ready, {failed} errors  "
        f"${actual_total:.3f}"
    )
    print(f"Transcript summary: {summary_path}")
    _print_transcript_next_steps(output_dir, console if RICH_AVAILABLE else None)
    return 0 if passed and not failed and not was_aborted else 1
