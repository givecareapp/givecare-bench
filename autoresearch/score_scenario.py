#!/usr/bin/env python3
"""Score one scenario with 3 probe models using existing transcripts.

Usage:
    python autoresearch/score_scenario.py SCENARIO_ID
    python autoresearch/score_scenario.py tier2_impossible_constraint_001
    python autoresearch/score_scenario.py --all-targets   # Score all 16 target scenarios
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "benchmark"))

# Import constants directly (avoid module import issues)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from constants import PROBE_MODELS, SPREAD_THRESHOLD_COMMIT

# Use newer run with complete (full-length) transcripts for all scenarios
TRANSCRIPT_DIR = PROJECT_ROOT / "results" / "run_20260312_025324" / "transcripts"

# Override probe models to match available transcripts in the newer run
# (Original probe models from constants.py don't all exist in this run)
PROBE_MODELS_OVERRIDE = [
    "anthropic/claude-opus-4.6",       # Best performer (replaces opus-4.5)
    "google/gemini-3.1-pro-preview",   # Different vendor, mid-range
    "openai/gpt-5-mini",              # Same as original probe
]
SCENARIO_DIR = PROJECT_ROOT / "benchmark" / "scenarios"
RULES_PATH = PROJECT_ROOT / "benchmark" / "configs" / "rules" / "base.yaml"
SCORING_CONFIG = PROJECT_ROOT / "benchmark" / "configs" / "scoring.yaml"

# 16 target scenarios (spread < 0.20, excluding 4 resistant)
TARGET_SCENARIOS = [
    "tier2_impossible_constraint_001",
    "tier1_false_refusal_med_001",
    "tier1_false_refusal_grief_001",
    "tier1_gray_cultural_001",
    "tier3_longitudinal_003_cultural_rituals",
    "tier1_crisis_dual_concern_001",
    "tier3_crisis_return_001",
    "tier1_boundaries_therapy_001",
    "tier2_belonging_001_identity_mismatch",
    "tier1_gray_humor_001",
    "tier2_no_right_answer_001",
    "tier1_gray_compassion_sms_001",
    "tier2_cultural_004",
    "tier1_false_refusal_eol_001",
    "tier2_burnout_financial_substance_001",
    "tier1_gray_venting_001",
]


def find_scenario_path(scenario_id: str) -> Optional[Path]:
    """Find scenario JSON file by scenario_id."""
    for f in SCENARIO_DIR.rglob("*.json"):
        if f.parts[-2] == "archive" or "confidential" in str(f):
            continue
        try:
            data = json.loads(f.read_text())
            if data.get("scenario_id") == scenario_id:
                return f
        except (json.JSONDecodeError, OSError):
            continue
    return None


def score_scenario(scenario_id: str, verbose: bool = True) -> Dict[str, Any]:
    """Score one scenario with 3 probe models. Returns dict with scores and spread."""
    from invisiblebench.evaluation.orchestrator import ScoringOrchestrator

    scenario_path = find_scenario_path(scenario_id)
    if not scenario_path:
        print(f"  ERROR: Scenario {scenario_id} not found", file=sys.stderr)
        return {"error": f"Scenario {scenario_id} not found"}

    orchestrator = ScoringOrchestrator(
        scoring_config_path=str(SCORING_CONFIG),
        enable_state_persistence=False,
        enable_llm=True,
    )

    scores: List[float] = []
    model_scores: Dict[str, float] = {}
    hard_fails: List[str] = []

    for model_id in PROBE_MODELS_OVERRIDE:
        model_key = model_id.replace("/", "_")
        transcript = TRANSCRIPT_DIR / f"{model_key}_{scenario_id}.jsonl"
        if not transcript.exists():
            if verbose:
                print(f"  SKIP {model_id} (no transcript)", file=sys.stderr)
            continue

        try:
            result = orchestrator.score(
                transcript_path=str(transcript),
                scenario_path=str(scenario_path),
                rules_path=str(RULES_PATH),
                model_name=model_id.split("/")[-1],
            )
            score = result.get("overall_score", 0.0)
            is_hard_fail = result.get("hard_fail", False)
            scores.append(score)
            model_scores[model_id] = score

            if is_hard_fail:
                hard_fails.append(model_id)

            status = "FAIL" if is_hard_fail else "PASS"
            if verbose:
                print(f"  {model_id:40s} {score:.3f} [{status}]", file=sys.stderr)

        except Exception as e:
            if verbose:
                print(f"  ERROR {model_id}: {e}", file=sys.stderr)

    if len(scores) < 2:
        return {"error": "Too few scores", "scores": model_scores}

    spread = max(scores) - min(scores)
    mean = sum(scores) / len(scores)

    if verbose:
        verdict = "GOOD" if spread >= SPREAD_THRESHOLD_COMMIT else "LOW"
        print(f"  Spread: {spread:.3f} [{verdict}]  Mean: {mean:.3f}", file=sys.stderr)

    return {
        "scenario_id": scenario_id,
        "spread": spread,
        "mean": mean,
        "scores": model_scores,
        "hard_fails": hard_fails,
        "n_models": len(scores),
    }


def score_all_targets(verbose: bool = True) -> List[Dict[str, Any]]:
    """Score all 16 target scenarios."""
    results = []
    for i, sid in enumerate(TARGET_SCENARIOS, 1):
        if verbose:
            print(f"\n[{i}/{len(TARGET_SCENARIOS)}] {sid}", file=sys.stderr)
        result = score_scenario(sid, verbose=verbose)
        results.append(result)
    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: python score_scenario.py SCENARIO_ID|--all-targets", file=sys.stderr)
        sys.exit(1)

    start = time.time()

    if sys.argv[1] == "--all-targets":
        results = score_all_targets()
        elapsed = time.time() - start

        print(f"\n{'='*70}")
        print(f"{'Scenario':<50} {'Spread':>7} {'Mean':>7} {'Verdict':>8}")
        print(f"{'-'*70}")

        good = 0
        for r in sorted(results, key=lambda x: x.get("spread", 0)):
            if "error" in r:
                print(f"  {r.get('scenario_id', '?'):<48} ERROR: {r['error']}")
                continue
            spread = r["spread"]
            mean = r["mean"]
            verdict = "GOOD" if spread >= SPREAD_THRESHOLD_COMMIT else "LOW"
            if spread >= SPREAD_THRESHOLD_COMMIT:
                good += 1
            print(f"  {r['scenario_id']:<48} {spread:>7.3f} {mean:>7.3f} {verdict:>8}")

        print(f"\n{good}/{len(results)} scenarios at target spread (>= {SPREAD_THRESHOLD_COMMIT})")
        print(f"Elapsed: {elapsed:.1f}s")

        # Output JSON for programmatic use
        json.dump(results, open("/tmp/autoresearch-baseline.json", "w"), indent=2)
        print(f"Results saved to /tmp/autoresearch-baseline.json")

    else:
        result = score_scenario(sys.argv[1])
        print(json.dumps(result, indent=2))

    elapsed = time.time() - start
    print(f"\nElapsed: {elapsed:.1f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
