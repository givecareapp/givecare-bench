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
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _build_scenario_index(scenarios_dir: Path) -> Dict[str, Path]:
    """Build scenario_id → scenario_path mapping from all scenario JSON files."""
    index: Dict[str, Path] = {}
    categories = ["safety", "empathy", "context", "continuity", "confidential"]
    for cat in categories:
        cat_dir = scenarios_dir / cat
        if not cat_dir.exists():
            continue
        for f in cat_dir.rglob("*.json"):
            with open(f) as fh:
                data = json.load(fh)
            sid = data.get("scenario_id", f.stem)
            index[sid] = f
    return index


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
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    scenarios_dir = project_root / "benchmark" / "scenarios"
    rules_path = project_root / "benchmark" / "configs" / "rules" / "base.yaml"

    if not scenarios_dir.exists():
        print(f"Error: Scenarios directory not found at {scenarios_dir}")
        return 1

    scenario_index = _build_scenario_index(scenarios_dir)
    print(f"Indexed {len(scenario_index)} scenarios")

    # Load existing results to get model/scenario metadata
    results_file = run_path / "all_results.json"
    if not results_file.exists():
        print(f"Error: No all_results.json in {run_path}")
        return 1

    with open(results_file) as f:
        old_results: List[Dict[str, Any]] = json.load(f)

    # Build transcript filename → old result mapping
    old_by_key: Dict[str, Dict[str, Any]] = {}
    for r in old_results:
        model_part = r["model_id"].replace("/", "_")
        key = f"{model_part}_{r['scenario_id']}.jsonl"
        old_by_key[key] = r

    # Collect transcript files
    transcript_files = sorted(transcripts_dir.glob("*.jsonl"))
    print(f"Found {len(transcript_files)} transcripts to rescore")

    if not transcript_files:
        print("Nothing to rescore.")
        return 0

    # Back up old results
    backup_path = run_path / "all_results.pre_rescore.json"
    with open(backup_path, "w") as f:
        json.dump(old_results, f, indent=2)
    print(f"Backed up old results to {backup_path.name}")

    scoring_config = project_root / "benchmark" / "configs" / "scoring.yaml"
    orchestrator = ScoringOrchestrator(
        scoring_config_path=str(scoring_config),
        enable_state_persistence=False,
        enable_llm=True,
    )
    new_results: List[Dict[str, Any]] = []
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
                "contract_version": result.get("contract_version", "2.0.0"),
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
            print("Leaderboard updated: benchmark/website/data/leaderboard.json")
        except Exception as e:
            print(f"Warning: Could not update leaderboard: {e}")

    return 0


def _compute_success(
    score: float, hard_fail: bool, gates: Dict[str, Any]
) -> bool:
    """Determine if this result is a 'success' for leaderboard purposes."""
    if hard_fail:
        return False
    if score < 0.5:
        return False
    for gate_info in gates.values():
        if isinstance(gate_info, dict) and not gate_info.get("passed", True):
            return False
    return True
