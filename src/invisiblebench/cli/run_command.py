#!/usr/bin/env python3
"""Generate target-model transcripts and persist run artifacts."""

from __future__ import annotations

import asyncio
import fcntl
import hashlib
import json
import logging
import math
import os
import shlex
import time
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from rich.console import Console

from invisiblebench._agent_cli import confirm_or_abort
from invisiblebench.api.client import (
    CostBudgetExceededError,
    InsufficientCreditsError,
    cost_tracker,
    maximum_reasonable_cost_ceiling,
    register_model_pricing,
)
from invisiblebench.api.typesafe import DEFAULT_JUDGE_MODEL
from invisiblebench.cli._console import make_console
from invisiblebench.cli.display import print_banner
from invisiblebench.cli.transcript import (
    evaluate_scenario_async,
    transcript_policy,
    uses_judge,
)
from invisiblebench.models.config import MODELS_FULL as CONFIG_MODELS_FULL
from invisiblebench.models.config import serving_policy
from invisiblebench.utils.benchmark_inventory import (
    collect_scenario_paths,
    get_private_confidential_dir,
    get_project_root,
    scenario_category_for_path,
)
from invisiblebench.utils.manifest import generate_manifest, write_manifest

logger = logging.getLogger(__name__)


def write_json(path: Path, data: Any) -> Path:
    """Write JSON and create its parent directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
    return path

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


# Map categories to token estimate keys (for cost calculation)
CATEGORY_TOKEN_MAP = {
    "safety": 1,  # 3-5 turns
    "empathy": 2,  # 8-12 turns
    "context": 1,  # 3-5 turns
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
        normalized_pattern == target or normalized_pattern in target
        for target in normalized_targets
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
                raise ValueError(
                    f"No catalog pricing for '{part}'. Add the model and verified prices "
                    "to src/invisiblebench/models/config.py before planning a run."
                )
            if not matched:
                names = [f"  {i+1}. {m['name']}" for i, m in enumerate(all_models)]
                raise ValueError(
                    f"No model matching '{part}'. Available models:\n" + "\n".join(names)
                )
            indices.update(matched)

    return sorted(indices)


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
        # actual_cost_usd is a known-cost total (reported + estimated). Any
        # unknown_calls_with_uncosted_usd are counted above in
        # actual_billable_api_calls but contribute $0 here — they are not
        # priced into the total, not folded in as a false zero.
        "actual_reported_cost_usd": cost_snapshot["reported_total"],
        "actual_estimated_cost_usd": cost_snapshot["estimated_total"],
        "unknown_calls_with_uncosted_usd": cost_snapshot["unknown_calls"],
        "resolved_model_ids": sorted(
            {model_id for result in ready for model_id in result.get("resolved_model_ids") or []}
        ),
        "resolved_providers": sorted(
            {provider for result in ready for provider in result.get("resolved_providers") or []}
        ),
        "transcripts": [
            {
                "model": r.get("model"),
                "model_id": r.get("model_id"),
                "scenario": r.get("scenario"),
                "scenario_id": r.get("scenario_id"),
                "category": r.get("category"),
                "transcript_path": _artifact_transcript_path(r),
                "resolved_model_ids": r.get("resolved_model_ids") or [],
                "resolved_providers": r.get("resolved_providers") or [],
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
                "reason": r.get("error") or r.get("status"),
            }
            for r in errors
        ],
        "next_steps": {"scan_plan": _scan_plan_command(output_dir)},
    }
    path = output_dir / "transcript_run.json"
    write_json(path, summary)
    return path


def _scan_plan_command(output_dir: Path) -> str:
    return shlex.join(
        [
            "uv",
            "run",
            "bench",
            "scan",
            "plan",
            str(output_dir),
            "--llm-model",
            DEFAULT_JUDGE_MODEL,
        ]
    )


def _print_transcript_next_steps(output_dir: Path, console: Console | None = None) -> None:
    command = _scan_plan_command(output_dir)
    if console:
        console.print(f"Next: {command}")
    else:
        print(f"Next: {command}")


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
    console = make_console()

    try:
        scenarios = get_scenarios(
            category_filter=category_filter,
            include_confidential=include_confidential,
        )
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
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
        console.print("[red]No scenarios match the filters[/red]")
        return 1

    pricing = {}
    try:
        for model in models:
            serving_policy(model)
            input_price = float(model["cost_per_m_input"])
            output_price = float(model["cost_per_m_output"])
            register_model_pricing(model["id"], input_price, output_price)
            pricing[model["id"]] = {
                "input_per_million": input_price,
                "output_per_million": output_price,
            }
    except (KeyError, TypeError, ValueError) as exc:
        console.print(f"[red]Invalid model pricing: {exc}[/red]")
        return 2

    scenario_parallel = max(1, scenario_parallel)
    total_cost = sum(estimate_cost(s["category"], m) for m in models for s in scenarios)

    print_banner(console, models, scenarios, total_cost)
    console.print("[cyan]Transcript-only mode: judge/scorer calls are skipped[/cyan]\n")

    if dry_run:
        console.print("[yellow]DRY RUN[/yellow] - No evaluations will be run\n")
        console.print(
            "Conservative budget includes target transcript generation only. "
            f"Use bench scan plan for {DEFAULT_JUDGE_MODEL} judging cost.\n"
        )
        console.print("[bold]Selected models:[/bold]")
        for model in models:
            cost = sum(estimate_cost(s["category"], model) for s in scenarios)
            console.print(f"  {model['name']:<24} [magenta]~${cost:.2f}[/magenta]")
            console.print(f"    Serving: {json.dumps(serving_policy(model), sort_keys=True)}")
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
    if not math.isfinite(max_cost_usd) or max_cost_usd < 0:
        print("ERROR: --max-cost-usd must be finite and non-negative")
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
    if not os.getenv("TYPESAFE_API_KEY") and any(uses_judge(s) for s in scenarios):
        print("ERROR: TYPESAFE_API_KEY not set; judge-branched scenarios need it")
        return 1

    if (output_dir / "scan_plan.json").exists():
        print("ERROR: This run has frozen judging inputs; generation cannot change it.")
        return 2

    confirm_or_abort(
        "proceed with live transcript generation",
        yes=auto_confirm,
        cost_estimate=(f"${total_cost:.2f} conservative plan, ceiling ${max_cost_usd:.2f}"),
    )

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
        scenario_ids=[str(scenario["scenario_id"]) for scenario in scenarios],
        transcript_policy=transcript_policy(api_client, models),
        run_id=run_id,
        harness="llm",
        mode="raw",
        include_confidential=include_confidential,
    )
    manifest["model_pricing"] = pricing
    manifest["artifact_type"] = "transcript_run/v1"
    manifest["stage"] = "transcripts"
    manifest["scoring"] = "deferred_to_run_scan"
    manifest["generation_code_sha256"] = hashlib.sha256(
        b"".join(
            p.relative_to(root).as_posix().encode() + p.read_bytes()
            for p in sorted((root / "src" / "invisiblebench").rglob("*.py"))
        )
    ).hexdigest()
    manifest["lockfile_sha256"] = hashlib.sha256((root / "uv.lock").read_bytes()).hexdigest()
    manifest_path = output_dir / "run_manifest.json"
    try:
        if not manifest_path.exists():
            write_manifest(manifest, output_dir)
        with manifest_path.open("r") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            saved = json.load(lock)
            identity = {"run_id", "run_date", "git_dirty"}
            if {k: v for k, v in saved.items() if k not in identity} != {
                k: v for k, v in manifest.items() if k not in identity
            }:
                raise ValueError("Frozen generation contract changed; use a new run directory")
            from invisiblebench.cli.generation import GenerationJournal
            from invisiblebench.cli.transcript import generation_contract

            # Validate every journal and scenario before any task can spend money.
            contracts = [generation_contract(m, s, api_client) for m in models for s in scenarios]
            journals = [
                GenerationJournal.inspect(p)
                for p in sorted((output_dir / "generation").glob("*.jsonl"))
            ]
            for journal in journals:
                if journal["contract"] not in contracts:
                    raise ValueError("Saved generation inputs differ from the selected run")
            for journal in journals:
                for _, response in journal["completed"].values():
                    if "model" in response:
                        cost_tracker.record(
                            response["model"],
                            response.get("prompt_tokens", 0),
                            response.get("completion_tokens", 0),
                            actual_cost=(response.get("raw") or {}).get("usage", {}).get("cost"),
                        )
            if cost_tracker.snapshot()["unknown_calls"] or not math.isclose(
                cost_tracker.total, sum(j["cost"] for j in journals), abs_tol=1e-12
            ):
                raise ValueError("Saved generation costs cannot be reproduced")
            return _generate_transcripts(
                models, scenarios, api_client, output_dir, saved, parallel, scenario_parallel
            )
    except (ValueError, OSError) as exc:
        print(f"ERROR: Cannot start or resume generation: {exc}")
        return 2


def _generate_transcripts(
    models, scenarios, api_client, output_dir, manifest, parallel, scenario_parallel
):
    run_id = manifest["run_id"]
    console = make_console()
    start_time = time.time()
    passed = 0
    failed = 0

    print(f"Generating transcripts only ({len(models)} model(s), {len(scenarios)} scenario(s))")
    print("Scoring is deferred to bench scan\n")
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
                is_error = result.get("status") == "error"
                status = "ERROR" if is_error else "TRANSCRIPT"
                print(
                    f"[{len(completed)}/{len(tasks)}] {model['name']} - "
                    f"{result.get('scenario', 'unknown')} {status}"
                )
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

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

        tasks = [asyncio.create_task(run_model_with_sem(model)) for model in models]
        try:
            nested = await asyncio.gather(*tasks)
            return [row for model_rows in nested for row in model_rows]
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def execute():
        from invisiblebench.cli.transcript import close_branch_client

        try:
            return await run_transcripts()
        finally:
            try:
                await api_client.aclose()
            finally:
                await close_branch_client()

    try:
        results = asyncio.run(execute())
    except CostBudgetExceededError as exc:
        results = transcript_rows
        print(f"\n{exc}. Saving transcript summary for completed scenarios.")
        abort_reason = "cost_budget_exceeded"
    except InsufficientCreditsError:
        results = transcript_rows
        print("\nCredits exhausted. Saving transcript summary for completed scenarios.")
        abort_reason = "credits_exhausted"
    except Exception as e:
        results = transcript_rows
        print(f"ERROR: Transcript generation stopped; attempts retained: {e}")
        abort_reason = "generation_error"
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
    print(f"\n{state}: {passed} transcripts ready, {failed} errors  " f"${actual_total:.3f}")
    print(f"Transcript summary: {summary_path}")
    _print_transcript_next_steps(output_dir, console)
    return 0 if passed and not failed and not was_aborted else 1
