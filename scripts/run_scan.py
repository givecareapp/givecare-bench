#!/usr/bin/env python3
"""Run v3 mode_engine over existing transcripts — deterministic-only.

First runnable v3 benchmark. LLM-dependent modes return UNCLEAR/NOT_APPLICABLE
since no api_client is wired in for this scan (by design, for a clean
deterministic baseline). Regex/lexicon/corpus verifiers produce actionable
signal on the existing transcript corpus.

Output per run:
  - `results/v3_scan/<timestamp>/per_run.jsonl` — one line per (model, scenario)
  - `results/v3_scan/<timestamp>/blindspot_rates.json` — corpus-level rates
  - `results/v3_scan/<timestamp>/summary.md` — human-readable summary

Usage:
  uv run python scripts/run_scan.py <run_dir>
  uv run python scripts/run_scan.py results/run_20260330_130332
  uv run python scripts/run_scan.py results/run_20260330_130332 results/partial_runs/run_20260330_033649_up_to_deepseek
  uv run python scripts/run_scan.py --all
"""

from __future__ import annotations

import argparse
import collections
import concurrent.futures
import json
import logging
import sys
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from invisiblebench.api import ModelAPIClient  # noqa: E402
from invisiblebench.evaluation.mode_engine import (  # noqa: E402
    ModeEngine,
    ModeEngineOutput,
    corpus_blindspot_rates,
)
from invisiblebench.evaluation.verifiers.base import collect_scenario_tags  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("v3_scan")


SCENARIOS_ROOT = REPO_ROOT / "benchmark" / "scenarios"
LLM_REQUIRED_ROUTES = {"hybrid_llm", "llm_primary", "longitudinal_trace"}
MODEL_PRICING = {
    "google/gemini-2.5-flash-lite": (0.10, 0.40),
    "google/gemini-2.5-flash": (0.30, 2.50),
    "gpt-4.1-mini": (0.40, 1.60),
}
SCAN_PROFILES: dict[str, dict[str, Any]] = {
    "smoke": {
        "description": "Fast local scan: deterministic and scenario-rule checks only.",
        "include_routes": {
            "lexicon_only",
            "regex_with_llm_edge",
            "scenario_rule",
            "extract_then_corpus",
        },
        "llm_repetitions": 0,
        "adaptive_repetitions": False,
    },
    "dev": {
        "description": "Cheap development scan: hard gates and boundary checks with one-pass judges.",
        "include_buckets": {"A", "B", "F"},
        "llm_repetitions": 1,
        "adaptive_repetitions": True,
    },
    "full": {
        "description": "All checks with one-pass LLM judges and adaptive metadata.",
        "include_all": True,
        "llm_repetitions": 1,
        "adaptive_repetitions": True,
    },
    "publish": {
        "description": "Publication scan: all checks with configured repetitions.",
        "include_all": True,
        "llm_repetitions": None,
        "adaptive_repetitions": False,
    },
}


def load_scan_profile(name: str) -> dict[str, Any]:
    try:
        profile = deepcopy(SCAN_PROFILES[name])
    except KeyError as exc:
        choices = ", ".join(sorted(SCAN_PROFILES))
        raise ValueError(f"Unknown scan profile {name!r}. Choices: {choices}") from exc
    profile["name"] = name
    profile.setdefault("input_tokens_per_llm_call", 2200)
    profile.setdefault("output_tokens_per_llm_call", 250)
    return profile


def route_requires_llm(routing: dict[str, Any]) -> bool:
    return str(routing.get("route") or "") in LLM_REQUIRED_ROUTES


def _mode_matches_profile(
    mode_id: str,
    mode_config: dict[str, Any],
    routing_config: dict[str, Any],
    profile: dict[str, Any],
) -> bool:
    if mode_id in profile.get("exclude_modes", set()):
        return False
    if mode_id in profile.get("include_modes", set()):
        return True
    if profile.get("include_all"):
        return True
    if profile.get("hard_fail_only") and not mode_config.get("hard_fail"):
        return False
    if profile.get("include_routes") and routing_config.get("route") in profile["include_routes"]:
        return True
    if profile.get("include_buckets") and mode_config.get("primary_bucket") in profile["include_buckets"]:
        return True
    return False


def apply_scan_profile(
    modes: dict[str, dict[str, Any]],
    routing: dict[str, dict[str, Any]],
    profile: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    filtered_modes: dict[str, dict[str, Any]] = {}
    filtered_routing: dict[str, dict[str, Any]] = {}

    for mode_id, mode_config in modes.items():
        routing_config = routing.get(mode_id)
        if routing_config is None:
            continue
        if not _mode_matches_profile(mode_id, mode_config, routing_config, profile):
            continue

        filtered_modes[mode_id] = deepcopy(mode_config)
        routed = deepcopy(routing_config)
        if route_requires_llm(routed) and profile.get("llm_repetitions") is not None:
            routed["repetitions"] = max(int(profile["llm_repetitions"]), 0)
        if route_requires_llm(routed) and profile.get("adaptive_repetitions"):
            routed["adaptive_repetitions"] = True
        filtered_routing[mode_id] = routed

    return filtered_modes, filtered_routing


def _mode_is_eligible(scenario: dict[str, Any], mode_config: dict[str, Any]) -> bool:
    if mode_config.get("scope") == "universal":
        return True

    explicit_modes = scenario.get("eligible_modes")
    if isinstance(explicit_modes, list) and explicit_modes:
        return str(mode_config.get("id")) in {str(mode_id) for mode_id in explicit_modes}

    eligibility = mode_config.get("eligibility") or {}
    required_tags = eligibility.get("scenario_tags_any") or []
    if not required_tags or required_tags == ["any"]:
        return True
    return bool(collect_scenario_tags(scenario).intersection(required_tags))


def _estimate_call_cost(
    model: str,
    *,
    input_tokens: int,
    output_tokens: int,
) -> float | None:
    pricing = MODEL_PRICING.get(model)
    if pricing is None:
        return None
    input_per_m, output_per_m = pricing
    return (input_tokens / 1_000_000) * input_per_m + (output_tokens / 1_000_000) * output_per_m


def build_scan_plan(
    scenarios: list[dict[str, Any]],
    modes: dict[str, dict[str, Any]],
    routing: dict[str, dict[str, Any]],
    profile: dict[str, Any],
    *,
    judge_model: str,
    llm_enabled: bool,
) -> dict[str, Any]:
    by_mode: dict[str, dict[str, Any]] = {}
    eligible_checks = 0
    planned_llm_calls = 0

    for scenario in scenarios:
        scenario_tags = collect_scenario_tags(scenario)
        for mode_id, mode_config in modes.items():
            routing_config = routing.get(mode_id)
            if routing_config is None:
                continue
            suppressed_by = routing_config.get("safety_override_suppressed_by") or []
            if suppressed_by and scenario_tags.intersection(suppressed_by):
                continue
            if not _mode_is_eligible(scenario, mode_config):
                continue

            eligible_checks += 1
            mode_stats = by_mode.setdefault(
                mode_id,
                {
                    "eligible": 0,
                    "planned_llm_calls": 0,
                    "route": routing_config.get("route"),
                    "bucket": mode_config.get("primary_bucket"),
                    "severity": mode_config.get("severity"),
                    "repetitions": routing_config.get("repetitions", 1),
                },
            )
            mode_stats["eligible"] += 1

            if llm_enabled and route_requires_llm(routing_config):
                calls = max(int(routing_config.get("repetitions", 1) or 0), 0)
                mode_stats["planned_llm_calls"] += calls
                planned_llm_calls += calls

    call_cost = _estimate_call_cost(
        judge_model,
        input_tokens=int(profile["input_tokens_per_llm_call"]),
        output_tokens=int(profile["output_tokens_per_llm_call"]),
    )
    estimated_cost = None if call_cost is None else call_cost * planned_llm_calls

    return {
        "profile": profile["name"],
        "llm_enabled": llm_enabled,
        "judge_model": judge_model,
        "transcript_count": len(scenarios),
        "eligible_checks": eligible_checks,
        "planned_llm_calls": planned_llm_calls,
        "estimated_cost_usd": estimated_cost,
        "pricing_known": call_cost is not None,
        "by_mode": dict(sorted(by_mode.items())),
    }


def load_scenario(scenario_id: str) -> dict[str, Any]:
    """Find a scenario JSON by id across benchmark/scenarios/."""
    for path in SCENARIOS_ROOT.rglob("*.json"):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("scenario_id") == scenario_id:
            return data
    logger.warning("Scenario not found: %s", scenario_id)
    return {"scenario_id": scenario_id, "category": "unknown"}


def load_transcript(path: Path) -> list[dict[str, Any]]:
    turns: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                turns.append(json.loads(line))
            except json.JSONDecodeError:
                logger.debug("Bad JSONL line in %s", path)
    return turns


def transcripts_for_run(run_dir: Path) -> list[dict[str, Any]]:
    """Pair each transcript JSONL with its (model, scenario_id) metadata."""
    transcripts_dir = run_dir / "transcripts"
    if not transcripts_dir.is_dir():
        return []

    results_path = run_dir / "all_results.json"
    results_by_key: dict[str, dict[str, Any]] = {}
    if results_path.exists():
        with open(results_path, encoding="utf-8") as f:
            for r in json.load(f):
                key = f"{r['model_id']}__{r['scenario_id']}"
                results_by_key[key] = r

    pairs: list[dict[str, Any]] = []
    for transcript_path in sorted(transcripts_dir.glob("*.jsonl")):
        stem = transcript_path.stem
        # Try to match against results_by_key
        matched = None
        for key, r in results_by_key.items():
            model_id, scenario_id = key.split("__", 1)
            if stem.startswith(model_id.replace("/", "_")) and stem.endswith(
                scenario_id
            ):
                matched = r
                break
        if matched is None:
            # Heuristic parse: last two underscore segments = scenario tail
            logger.debug("No result match for %s; using heuristic", stem)
            matched = {
                "model": "unknown",
                "model_id": "unknown",
                "scenario_id": stem,
                "category": "unknown",
            }
        pairs.append(
            {
                "transcript_path": transcript_path,
                "model": matched.get("model", "unknown"),
                "model_id": matched.get("model_id", "unknown"),
                "scenario_id": matched.get("scenario_id", stem),
                "category": matched.get("category", "unknown"),
            }
        )
    return pairs


def enrich_scenario_with_inferred_tags(scenario: dict[str, Any]) -> dict[str, Any]:
    """Infer failure_mode_tags from scenario fields for mode eligibility matching."""
    if scenario.get("eligible_modes"):
        scenario = dict(scenario)
        scenario["_inferred_tags"] = False
        return scenario

    inferred: list[str] = sorted(collect_scenario_tags(scenario))

    category = (scenario.get("category") or "").lower()
    if category == "safety":
        inferred.append("any")  # regex-primary modes like F1/F2/F3 always apply
    if category in {"empathy", "continuity"}:
        inferred.append("emotional_ask")
        inferred.append("caregiver_burden_disclosure")
    if category == "context":
        inferred.append("cultural_context")

    # Scan rubric / expected_behaviors text for hints
    rubric_text = (
        " ".join(
            x if isinstance(x, str) else json.dumps(x)
            for x in (
                scenario.get("expected_behaviors") or []
            )
        )
        + " "
        + json.dumps(scenario.get("rubric") or {})
        + " "
        + json.dumps(scenario.get("autofail_rubric") or {})
    ).lower()

    scenario_id_text = (scenario.get("scenario_id") or "").lower()
    title_text = (scenario.get("title") or "").lower()
    search_text = rubric_text + " " + scenario_id_text + " " + title_text

    hints = {
        "passive_ideation": ["passive ideation", "wish i", "not wake up", "cssrs", "cssrs_passive", "passive_sms"],
        "direct_ideation": ["suicidal", "kill myself", "end my life", "suicide", "ideation"],
        "masked_crisis": ["indirect", "masked", "bridge", "indirect_bridge", "dual_concern"],
        "caregiver_to_cr_harm_intent": ["shake", "hit him", "hit her", "harm him", "caregiver_violence"],
        "acute_medical_symptom": ["chest pain", "stroke", "overdose", "acute_medical"],
        "self_sacrifice_statement": ["self_sacrifice", "should handle alone", "burnout", "self_neglect"],
        "emotional_disclosure": ["emotional", "distress", "overwhelmed", "breaking down", "burnout", "grief"],
        "caregiver_burden_disclosure": ["burden", "exhaustion", "strain", "overwhelmed"],
        "benefits_question": ["benefit", "medicaid", "nfcsp", "waiver", "fmla", "pfml", "eligibility"],
        "cultural_context": ["asian", "latino", "lgbtq", "cultural", "hispanic", "black", "kinship"],
        "ai_identity_probe": ["identity", "are you real", "are you human", "ai_identity"],
        "emotional_ask": ["emotional", "feelings", "mood", "distress"],
        "practical_ask": ["how do i", "where", "call", "navigate"],
        "caregiver_self_blame": ["self_blame", "failing", "terrible", "failed", "self_diminish"],
    }
    for tag, needles in hints.items():
        if any(n in search_text for n in needles):
            inferred.append(tag)

    scenario = dict(scenario)
    scenario["failure_mode_tags"] = sorted(set(inferred))
    scenario["_inferred_tags"] = True
    return scenario


def _scan_pair(
    pair: dict[str, Any],
    engine: ModeEngine,
    parallel: bool,
    max_workers: int,
) -> tuple[dict[str, Any], ModeEngineOutput] | None:
    transcript = load_transcript(pair["transcript_path"])
    if not transcript:
        logger.warning("Empty transcript: %s", pair["transcript_path"].name)
        return None

    scenario = load_scenario(pair["scenario_id"])
    scenario = enrich_scenario_with_inferred_tags(scenario)

    try:
        out = engine.evaluate(
            transcript=transcript,
            scenario=scenario,
            parallel=parallel,
            max_workers=max_workers,
        )
    except Exception as e:
        logger.exception("Engine crash on %s: %s", pair["scenario_id"], e)
        return None

    record = {
        "model": pair["model"],
        "model_id": pair["model_id"],
        "scenario_id": pair["scenario_id"],
        "category": pair["category"],
        "transcript_path": str(pair["transcript_path"]),
        **out.to_dict(),
    }
    return record, out


def scan_run(
    run_dir: Path,
    engine: ModeEngine,
    limit: int | None = None,
    filename_filter: str | None = None,
    parallel: bool = False,
    max_workers: int = 8,
    transcript_workers: int = 1,
):
    """Run mode_engine over every transcript in a given run directory."""
    pairs = transcripts_for_run(run_dir)
    if filename_filter:
        pairs = [
            p for p in pairs
            if filename_filter.lower() in p["transcript_path"].name.lower()
        ]
    if limit:
        pairs = pairs[:limit]

    logger.info("Scanning %d transcripts in %s", len(pairs), run_dir.name)

    outputs: list[dict[str, Any]] = []
    engine_outputs: list[ModeEngineOutput] = []

    if transcript_workers > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=transcript_workers) as executor:
            futures = [
                executor.submit(_scan_pair, pair, engine, parallel, max_workers)
                for pair in pairs
            ]
            for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
                result = future.result()
                if result is not None:
                    record, out = result
                    outputs.append(record)
                    engine_outputs.append(out)
                if i % 25 == 0:
                    logger.info("  scanned %d/%d", i, len(pairs))
    else:
        for i, pair in enumerate(pairs, 1):
            result = _scan_pair(pair, engine, parallel, max_workers)
            if result is not None:
                record, out = result
                outputs.append(record)
                engine_outputs.append(out)

            if i % 25 == 0:
                logger.info("  scanned %d/%d", i, len(pairs))

    return outputs, engine_outputs


def write_outputs(
    output_dir: Path,
    outputs: list[dict[str, Any]],
    engine_outputs: list[ModeEngineOutput],
    run_dirs: list[Path],
    scan_plan: dict[str, Any] | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    # Per-run JSONL
    per_run_path = output_dir / "per_run.jsonl"
    with open(per_run_path, "w", encoding="utf-8") as f:
        for r in outputs:
            f.write(json.dumps(r, default=str) + "\n")

    # Blindspot rates
    rates = corpus_blindspot_rates(engine_outputs)
    rates_path = output_dir / "blindspot_rates.json"
    with open(rates_path, "w", encoding="utf-8") as f:
        json.dump({"rates": rates, "n_runs": len(engine_outputs)}, f, indent=2)

    if scan_plan is not None:
        with open(output_dir / "scan_plan.json", "w", encoding="utf-8") as f:
            json.dump(scan_plan, f, indent=2)
        with open(output_dir / "cost_report.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "profile": scan_plan.get("profile"),
                    "llm_enabled": scan_plan.get("llm_enabled"),
                    "judge_model": scan_plan.get("judge_model"),
                    "planned_llm_calls": scan_plan.get("planned_llm_calls"),
                    "estimated_cost_usd": scan_plan.get("estimated_cost_usd"),
                    "pricing_known": scan_plan.get("pricing_known"),
                },
                f,
                indent=2,
            )

    # Per-model blindspot rates
    by_model: dict[str, list[ModeEngineOutput]] = collections.defaultdict(list)
    by_model_records: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for r, eo in zip(outputs, engine_outputs, strict=False):
        key = r.get("model") or "unknown"
        by_model[key].append(eo)
        by_model_records[key].append(r)

    per_model_rates = {
        model: {
            "n_runs": len(engine_outputs_for_model),
            "hard_fail_rate": sum(
                1 for eo in engine_outputs_for_model if eo.hard_fail
            )
            / max(len(engine_outputs_for_model), 1),
            "blindspot_rates": corpus_blindspot_rates(engine_outputs_for_model),
        }
        for model, engine_outputs_for_model in by_model.items()
    }
    with open(output_dir / "per_model_rates.json", "w", encoding="utf-8") as f:
        json.dump(per_model_rates, f, indent=2)

    # Human summary
    summary_lines: list[str] = []
    summary_lines.append("# V3 Blindspot Scan — Summary\n")
    summary_lines.append(f"- Source run dirs: {', '.join(str(d.name) for d in run_dirs)}")
    summary_lines.append(f"- Transcripts scanned: {len(outputs)}")
    if scan_plan is not None:
        estimated = scan_plan.get("estimated_cost_usd")
        estimated_text = "unknown" if estimated is None else f"${estimated:.4f}"
        summary_lines.append(f"- Profile: {scan_plan.get('profile')}")
        summary_lines.append(f"- Planned verifier LLM calls: {scan_plan.get('planned_llm_calls')}")
        summary_lines.append(f"- Estimated verifier cost: {estimated_text}")
    summary_lines.append(
        f"- Models: {', '.join(sorted(by_model.keys()))}\n"
    )
    summary_lines.append("## Overall blindspot rates\n")
    summary_lines.append("| Blindspot | Rate | Failures / Eligible |")
    summary_lines.append("|---|---:|---:|")

    # Recompute with eligibility counts for display
    eligible_counts: dict[str, dict[str, int]] = {}
    for eo in engine_outputs:
        for label, val in eo.blindspot_profile.items():
            if val is None:
                continue
            ec = eligible_counts.setdefault(label, {"fail": 0, "eligible": 0})
            ec["eligible"] += 1
            if val:
                ec["fail"] += 1

    sorted_labels = sorted(
        rates.keys(), key=lambda k: (-rates.get(k, 0.0), k)
    )
    for label in sorted_labels:
        ec = eligible_counts.get(label, {"fail": 0, "eligible": 0})
        rate = rates.get(label, 0.0)
        summary_lines.append(
            f"| {label} | {rate:.2%} | {ec['fail']} / {ec['eligible']} |"
        )

    summary_lines.append("\n## Per-model hard-fail rates\n")
    summary_lines.append("| Model | Hard-fail rate | n |")
    summary_lines.append("|---|---:|---:|")
    for model, stats in sorted(
        per_model_rates.items(), key=lambda kv: -kv[1]["hard_fail_rate"]
    ):
        summary_lines.append(
            f"| {model} | {stats['hard_fail_rate']:.2%} | {stats['n_runs']} |"
        )

    summary_lines.append("\n## Notes\n")
    summary_lines.append(
        "- LLM-dependent modes returned NOT_APPLICABLE (no api_client wired in). "
        "Regex/lexicon/corpus modes produced actionable signal."
    )
    summary_lines.append(
        "- Scenario eligibility uses explicit `eligible_modes` when present; tag "
        "inference is the fallback for scenarios without that field."
    )
    summary_lines.append(
        "- Hard-fail rate counts regex-detected B5/B7/B8 and F1-human-identity. "
        "Full A-gate coverage requires LLM verifier calibration."
    )

    with open(output_dir / "summary.md", "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines) + "\n")

    logger.info("Wrote outputs to %s", output_dir)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "run_dirs",
        nargs="*",
        help="Path(s) to results/run_<timestamp>/ directory or other transcript roots",
    )
    ap.add_argument(
        "--all",
        action="store_true",
        help="Scan all run_* directories under results/",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit transcripts scanned (for smoke testing)",
    )
    ap.add_argument(
        "--filter",
        default=None,
        help="Only scan transcripts whose filename contains this substring",
    )
    ap.add_argument(
        "--output-root",
        default=str(REPO_ROOT / "results" / "v3_scan"),
        help="Where to write scan outputs",
    )
    ap.add_argument(
        "--profile",
        default="publish",
        help="Scan profile: smoke, dev, full, or publish (default: publish).",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Write and print the scan plan without evaluating transcripts.",
    )
    ap.add_argument(
        "--enable-llm",
        action="store_true",
        help="Wire ModelAPIClient so LLM-primary modes run (costs tokens).",
    )
    ap.add_argument(
        "--llm-model",
        default="google/gemini-2.5-flash-lite",
        help="Judge model for LLM verifiers (default: Gemini flash-lite).",
    )
    ap.add_argument(
        "--parallel",
        action="store_true",
        help="Run verifier checks concurrently within each transcript (faster, same results).",
    )
    ap.add_argument(
        "--transcript-workers",
        type=int,
        default=1,
        help="Run multiple transcripts concurrently (default: 1).",
    )
    ap.add_argument(
        "--max-workers",
        type=int,
        default=8,
        help="Max concurrent verifier threads when --parallel is set (default: 8).",
    )
    args = ap.parse_args()

    try:
        profile = load_scan_profile(args.profile)
    except ValueError as e:
        logger.error("%s", e)
        return 2

    api_client = None
    if args.enable_llm:
        try:
            api_client = ModelAPIClient()
            logger.info("LLM verifier enabled with model=%s", args.llm_model)
        except (ImportError, ValueError) as e:
            logger.error("Failed to initialize ModelAPIClient: %s", e)
            logger.error("LLM modes will short-circuit to UNCLEAR / NOT_APPLICABLE.")

    engine = ModeEngine(llm_api_client=api_client, llm_model=args.llm_model)
    engine.modes, engine.routing = apply_scan_profile(engine.modes, engine.routing, profile)
    logger.info("Scan profile: %s (%s)", profile["name"], profile["description"])
    logger.info("Loaded %d modes from failure_modes.yaml", len(engine.modes))
    logger.info("Loaded %d routing entries", len(engine.routing))

    run_dirs: list[Path] = []
    if args.all:
        run_dirs = sorted(
            (REPO_ROOT / "results").glob("run_*"),
            key=lambda p: p.name,
            reverse=True,
        )
    elif args.run_dirs:
        run_dirs = [Path(run_dir).resolve() for run_dir in args.run_dirs]
    else:
        # Default: most recent run
        candidates = sorted(
            (REPO_ROOT / "results").glob("run_*"),
            key=lambda p: p.name,
            reverse=True,
        )
        run_dirs = candidates[:1]

    if not run_dirs:
        logger.error("No run_* directories found")
        return 2

    plan_scenarios: list[dict[str, Any]] = []
    for run_dir in run_dirs:
        pairs = transcripts_for_run(run_dir)
        if args.filter:
            pairs = [
                p
                for p in pairs
                if args.filter.lower() in p["transcript_path"].name.lower()
            ]
        if args.limit:
            pairs = pairs[: args.limit]
        for pair in pairs:
            scenario = load_scenario(pair["scenario_id"])
            plan_scenarios.append(enrich_scenario_with_inferred_tags(scenario))

    scan_plan_dict = build_scan_plan(
        plan_scenarios,
        engine.modes,
        engine.routing,
        profile,
        judge_model=args.llm_model,
        llm_enabled=bool(args.enable_llm and api_client is not None),
    )

    if args.dry_run:
        output_dir = Path(args.output_root) / f"plan_{time.strftime('%Y%m%d_%H%M%S')}"
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(output_dir / "scan_plan.json", "w", encoding="utf-8") as f:
            json.dump(scan_plan_dict, f, indent=2)
        with open(output_dir / "cost_report.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "profile": scan_plan_dict["profile"],
                    "llm_enabled": scan_plan_dict["llm_enabled"],
                    "judge_model": scan_plan_dict["judge_model"],
                    "planned_llm_calls": scan_plan_dict["planned_llm_calls"],
                    "estimated_cost_usd": scan_plan_dict["estimated_cost_usd"],
                    "pricing_known": scan_plan_dict["pricing_known"],
                },
                f,
                indent=2,
            )
        estimated = (
            "unknown"
            if scan_plan_dict["estimated_cost_usd"] is None
            else f"${scan_plan_dict['estimated_cost_usd']:.4f}"
        )
        print(f"Scan dry run: {output_dir}")
        print(f"Profile: {scan_plan_dict['profile']}")
        print(f"Transcripts: {scan_plan_dict['transcript_count']}")
        print(f"Eligible checks: {scan_plan_dict['eligible_checks']}")
        print(f"Planned verifier LLM calls: {scan_plan_dict['planned_llm_calls']}")
        print(f"Estimated verifier cost: {estimated}")
        return 0

    all_outputs: list[dict[str, Any]] = []
    all_engine_outputs: list[ModeEngineOutput] = []

    for run_dir in run_dirs:
        outputs, engine_outputs = scan_run(
            run_dir,
            engine,
            limit=args.limit,
            filename_filter=args.filter,
            parallel=getattr(args, "parallel", False),
            max_workers=getattr(args, "max_workers", 8),
            transcript_workers=max(args.transcript_workers, 1),
        )
        all_outputs.extend(outputs)
        all_engine_outputs.extend(engine_outputs)

    if not all_outputs:
        logger.error("No transcripts scanned")
        return 3

    output_dir = Path(args.output_root) / time.strftime("%Y%m%d_%H%M%S")
    write_outputs(output_dir, all_outputs, all_engine_outputs, run_dirs, scan_plan_dict)

    print(f"\nScan complete: {output_dir}")
    print(f"See {output_dir}/summary.md for top-line blindspot rates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
