"""Rescore existing transcripts without re-running model conversations.

Usage:
    uv run bench rescore results/run_20260213_232236/
    uv run bench rescore results/run_20260213_232236/ --update-leaderboard
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

from invisiblebench.models.results import is_result_success
from invisiblebench.utils.benchmark_inventory import (
    collect_scenario_paths,
    get_private_confidential_dir,
    get_project_root,
)
from invisiblebench.utils.verifier_corpus import TRANSCRIPT_PREFIX_ALIASES

logger = logging.getLogger(__name__)


def _build_scenario_index(scenarios_dir: Path) -> dict[str, Path]:
    """Build scenario_id → scenario_path mapping from available scenario JSON files."""
    index: dict[str, Path] = {}
    project_root = get_project_root()
    include_confidential = get_private_confidential_dir(project_root) is not None
    del scenarios_dir
    for f in collect_scenario_paths(project_root, include_confidential=include_confidential):
        with open(f) as fh:
            data = json.load(fh)
        sid = data.get("scenario_id", f.stem)
        index[sid] = f
    return index


def _transcript_key_candidates(model_id: str, scenario_id: str) -> list[str]:
    base = model_id.replace("/", "_")
    prefixes = [base, *TRANSCRIPT_PREFIX_ALIASES.get(base, ())]
    return [f"{prefix}_{scenario_id}.jsonl" for prefix in prefixes]


def _load_old_results_for_run(run_path: Path, project_root: Path) -> tuple[list[dict[str, Any]], bool]:
    """Load prior per-scenario results for a run.

    Returns `(rows, had_existing_all_results)`.
    Falls back to synthesizing rows from `results/leaderboard_ready/*.json`
    when the run only has frozen transcripts.
    """
    results_file = run_path / "all_results.json"
    if results_file.exists():
        with open(results_file) as f:
            return json.load(f), True

    leaderboard_dir = project_root / "results" / "leaderboard_ready"
    transcript_names = {path.name for path in (run_path / "transcripts").glob("*.jsonl")}
    synthesized: list[dict[str, Any]] = []

    if not leaderboard_dir.exists():
        raise FileNotFoundError(
            f"No all_results.json in {run_path} and no leaderboard_ready directory at {leaderboard_dir}"
        )

    for leaderboard_file in sorted(leaderboard_dir.glob("*.json")):
        with open(leaderboard_file) as fh:
            doc = json.load(fh)
        model = doc.get("model", doc.get("model_name", "unknown"))
        model_id = doc.get("model_id", model)
        provider = doc.get("provider")

        for scenario in doc.get("scenarios", []):
            if not any(
                key in transcript_names
                for key in _transcript_key_candidates(model_id, scenario["scenario_id"])
            ):
                continue
            synthesized.append(
                {
                    "model": model,
                    "model_id": model_id,
                    "provider": provider,
                    "scenario": scenario.get("scenario"),
                    "scenario_id": scenario.get("scenario_id"),
                    "category": scenario.get("category", "unknown"),
                    "overall_score": scenario.get("overall_score", 0.0),
                    "dimension_scores": scenario.get("dimension_scores", {}),
                    "status": scenario.get("status", "error"),
                    "hard_fail": scenario.get("hard_fail", False),
                    "hard_fail_reasons": scenario.get("hard_fail_reasons", []),
                    "failure_categories": scenario.get("failure_categories", {}),
                    "gates": scenario.get("gates", {}),
                    "success": scenario.get("success"),
                    "cost": scenario.get("cost", 0.0),
                    "run_id": scenario.get("run_id"),
                    "judge_model": scenario.get("judge_model"),
                    "judge_prompt_hash": scenario.get("judge_prompt_hash"),
                    "judge_temp": scenario.get("judge_temp"),
                    "contract_version": scenario.get("contract_version", "2.1.0"),
                    "detail_json": scenario.get("detail_json"),
                    "detail_html": scenario.get("detail_html"),
                }
            )

    if not synthesized:
        raise FileNotFoundError(
            f"No all_results.json in {run_path} and could not synthesize prior rows from leaderboard_ready"
        )

    return synthesized, False


def run_rescore(
    run_dir: str,
    update_leaderboard: bool = False,
    parallel: Optional[int] = None,
) -> int:
    """Rescore all transcripts in a run directory."""
    from invisiblebench.evaluation.orchestrator import ScoringOrchestrator

    run_path = Path(run_dir).resolve()
    transcripts_dir = run_path / "transcripts"

    if not transcripts_dir.exists():
        print(f"Error: No transcripts/ directory in {run_path}")
        return 1

    # Find project root and scenario index
    # Walk up from this file to find benchmark/scenarios
    project_root = get_project_root()
    scenarios_dir = project_root / "benchmark" / "scenarios"
    rules_path = project_root / "benchmark" / "configs" / "rules" / "base.yaml"

    if not scenarios_dir.exists():
        print(f"Error: Scenarios directory not found at {scenarios_dir}")
        return 1

    scenario_index = _build_scenario_index(scenarios_dir)
    print(f"Indexed {len(scenario_index)} scenarios")

    results_file = run_path / "all_results.json"
    try:
        old_results, had_existing_all_results = _load_old_results_for_run(run_path, project_root)
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        return 1

    old_by_key: dict[str, dict[str, Any]] = {}
    for r in old_results:
        model_part = r["model_id"].replace("/", "_")
        key = f"{model_part}_{r['scenario_id']}.jsonl"
        old_by_key[key] = r

    transcript_files = sorted(transcripts_dir.glob("*.jsonl"))
    print(f"Found {len(transcript_files)} transcripts to rescore")

    if not transcript_files:
        print("Nothing to rescore.")
        return 0

    # Back up old results (or the synthesized pre-rescore baseline)
    backup_path = run_path / "all_results.pre_rescore.json"
    with open(backup_path, "w") as f:
        json.dump(old_results, f, indent=2)
    if had_existing_all_results:
        print(f"Backed up old results to {backup_path.name}")
    else:
        print(f"Wrote synthesized pre-rescore baseline to {backup_path.name}")

    scoring_config = project_root / "benchmark" / "configs" / "scoring.yaml"
    orchestrator = ScoringOrchestrator(
        scoring_config_path=str(scoring_config),
        enable_state_persistence=False,
        enable_llm=True,
    )
    new_results: list[dict[str, Any]] = []
    errors = 0
    start_time = time.time()

    for i, transcript_path in enumerate(transcript_files, 1):
        fname = transcript_path.name
        old = old_by_key.get(fname)

        if not old:
            print(f"  [{i}/{len(transcript_files)}] SKIP {fname} (no matching result)")
            continue

        scenario_id = old["scenario_id"]
        scenario_path = scenario_index.get(scenario_id)

        if not scenario_path:
            print(f"  [{i}/{len(transcript_files)}] SKIP {fname} (scenario {scenario_id} not found)")
            new_results.append(old)
            errors += 1
            continue

        try:
            result = orchestrator.score(
                transcript_path=str(transcript_path),
                scenario_path=str(scenario_path),
                rules_path=str(rules_path),
                model_name=old["model"],
                run_id=old.get("run_id"),
            )

            score = result.get("overall_score", 0.0)
            hard_fail = result.get("hard_fail", False)

            summary = {
                "model": old["model"],
                "model_id": old["model_id"],
                "scenario": old["scenario"],
                "scenario_id": scenario_id,
                "category": old["category"],
                "overall_score": score,
                "hard_fail": hard_fail,
                "hard_fail_reasons": result.get("hard_fail_reasons", []),
                "failure_categories": result.get("failure_categories", {}),
                "gates": result.get("gates", {}),
                "dimensions": result.get("dimensions", {}),
                "dimension_scores": {
                    k: v.get("score") if isinstance(v, dict) else v
                    for k, v in result.get("dimension_scores", {}).items()
                },
                "cost": old.get("cost", 0.0),  # preserve original cost
                "status": "pass" if not hard_fail else "fail",
                "run_id": result.get("run_id"),
                "judge_model": result.get("judge_model"),
                "judge_prompt_hash": result.get("judge_prompt_hash"),
                "judge_temp": result.get("judge_temp"),
                "contract_version": result.get("contract_version", "2.1.0"),
                "success": _compute_success(score, hard_fail, result.get("gates", {})),
                "rescored": True,
            }
            new_results.append(summary)

            old_score = old.get("overall_score", 0.0)
            delta = score - old_score
            delta_str = f" ({delta:+.3f})" if abs(delta) > 0.001 else ""
            status = "PASS" if not hard_fail else "FAIL"
            print(f"  [{i}/{len(transcript_files)}] {status} {old['model'][:20]:20s} {scenario_id:40s} {score:.3f}{delta_str}")

        except Exception as e:
            print(f"  [{i}/{len(transcript_files)}] ERROR {fname}: {e}")
            new_results.append(old)
            errors += 1

    elapsed = time.time() - start_time

    # Write new results
    with open(results_file, "w") as f:
        json.dump(new_results, f, indent=2)

    # Summary
    old_fails = sum(1 for r in old_results if r.get("hard_fail"))
    new_fails = sum(1 for r in new_results if r.get("hard_fail"))
    old_avg = sum(r.get("overall_score", 0) for r in old_results) / len(old_results) if old_results else 0
    new_avg = sum(r.get("overall_score", 0) for r in new_results) / len(new_results) if new_results else 0

    print(f"\n{'='*60}")
    print(f"Rescored {len(new_results)} results in {elapsed:.1f}s ({errors} errors)")
    print(f"Hard fails: {old_fails} → {new_fails} ({new_fails - old_fails:+d})")
    print(f"Avg score:  {old_avg:.3f} → {new_avg:.3f} ({new_avg - old_avg:+.3f})")
    print(f"Results written to {results_file}")

    if update_leaderboard:
        try:
            from invisiblebench.cli.leaderboard import add_results

            add_results(results_file)
            print("Leaderboard updated: data/leaderboard/leaderboard.json")
        except Exception as e:
            print(f"Warning: Could not update leaderboard: {e}")

    return 0


def _compute_success(
    score: float, hard_fail: bool, gates: dict[str, Any]
) -> bool:
    """Determine if this result is a 'success' for leaderboard purposes."""
    return is_result_success(
        {
            "overall_score": score,
            "hard_fail": hard_fail,
            "gates": gates,
        }
    )
