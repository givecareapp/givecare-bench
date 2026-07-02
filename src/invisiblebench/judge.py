"""JUDGE verb — score transcripts against the check taxonomy.

The single entry point for judging: given run directories of transcripts,
evaluate every (transcript, check) pair through the ModeEngine and emit
scan artifacts (per_run.jsonl, blindspot rates, summary). The thin CLI
wrapper lives in scripts/run_scan.py; this module owns the logic so other
callers (rescore_diff, future verbs) share one implementation.

Scan profiles control cost: `smoke` is deterministic-only; `dev`/`full`/
`publish` wire LLM verifiers with increasing repetitions.
"""

from __future__ import annotations

import collections
import concurrent.futures
import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any

from invisiblebench.evaluation.mode_engine import (
    ModeEngine,
    ModeEngineOutput,
    corpus_blindspot_rates,
)
from invisiblebench.evaluation.verifiers.base import (
    collect_scenario_tags,
    mode_is_eligible,
)
from invisiblebench.models.results import (
    PUBLIC_SCORE_MODEL,
    RAW_RESULT_SURFACE,
    RAW_SCORE_MODEL,
)

logger = logging.getLogger("safety_care_scan")

REPO_ROOT = Path(__file__).resolve().parents[2]

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
        "include_dimensions": {"crisis", "scope", "identity"},
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
    included_layers = profile.get("include_layers")
    if included_layers and mode_config.get("layer") in included_layers:
        return True
    included_dimensions = profile.get("include_dimensions")
    if included_dimensions and mode_config.get("dimension") in included_dimensions:
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
            if not mode_is_eligible(scenario, mode_config):
                continue

            eligible_checks += 1
            mode_stats = by_mode.setdefault(
                mode_id,
                {
                    "eligible": 0,
                    "planned_llm_calls": 0,
                    "route": routing_config.get("route"),
                    "layer": mode_config.get("layer"),
                    "dimension": mode_config.get("dimension"),
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


_SCENARIO_METADATA_CACHE: dict[str, dict[str, Any]] | None = None


def _scenario_metadata_by_id() -> dict[str, dict[str, Any]]:
    global _SCENARIO_METADATA_CACHE
    if _SCENARIO_METADATA_CACHE is not None:
        return _SCENARIO_METADATA_CACHE

    scenarios: dict[str, dict[str, Any]] = {}
    for path in SCENARIOS_ROOT.rglob("*.json"):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        scenario_id = data.get("scenario_id")
        if isinstance(scenario_id, str) and scenario_id:
            scenarios[scenario_id] = data

    _SCENARIO_METADATA_CACHE = scenarios
    return scenarios


def _model_metadata_from_transcript_prefix(prefix: str) -> dict[str, str]:
    try:
        from invisiblebench.models.config import MODELS_FULL
    except ImportError:
        MODELS_FULL = []

    for model in MODELS_FULL:
        model_id = getattr(model, "id", "")
        if model_id.replace("/", "_") == prefix:
            return {"model_id": model_id, "model": getattr(model, "name", model_id)}

    if "_" in prefix:
        model_id = prefix.replace("_", "/", 1)
    else:
        model_id = prefix
    return {"model_id": model_id or "unknown", "model": model_id or "unknown"}


def _infer_transcript_metadata_from_stem(stem: str) -> dict[str, Any] | None:
    scenarios = _scenario_metadata_by_id()
    for scenario_id in sorted(scenarios, key=len, reverse=True):
        suffix = f"_{scenario_id}"
        if not stem.endswith(suffix):
            continue
        model_prefix = stem[: -len(suffix)]
        if not model_prefix:
            continue
        model_metadata = _model_metadata_from_transcript_prefix(model_prefix)
        scenario = scenarios[scenario_id]
        return {
            **model_metadata,
            "scenario_id": scenario_id,
            "category": scenario.get("category", "unknown"),
        }
    return None


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
            logger.debug("No result match for %s; inferring from scenario inventory", stem)
            matched = _infer_transcript_metadata_from_stem(stem)
        if matched is None:
            logger.warning("Could not infer scenario metadata for transcript %s", stem)
            matched = {"model": "unknown", "model_id": "unknown", "scenario_id": stem, "category": "unknown"}
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
            "result_surface": RAW_RESULT_SURFACE,
            "score_model": RAW_SCORE_MODEL,
            "public_score_model": PUBLIC_SCORE_MODEL,
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
    summary_lines.append("# Safety/Care Scan — Summary\n")
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

    summary_lines.append("\n## Per-model raw/internal hard-fail compatibility rates\n")
    summary_lines.append("| Model | Raw/internal hard-fail rate | n |")
    summary_lines.append("|---|---:|---:|")
    for model, stats in sorted(
        per_model_rates.items(), key=lambda kv: -kv[1]["hard_fail_rate"]
    ):
        summary_lines.append(
            f"| {model} | {stats['hard_fail_rate']:.2%} | {stats['n_runs']} |"
        )

    summary_lines.append("\n## Notes\n")
    if scan_plan is not None and scan_plan.get("llm_enabled"):
        summary_lines.append(
            "- LLM-dependent modes ran for routes included in the selected scan profile. "
            "Routes outside the selected profile were excluded from this scan."
        )
    else:
        summary_lines.append(
            "- LLM-dependent modes returned NOT_APPLICABLE (no api_client wired in). "
            "Regex/lexicon/corpus modes produced actionable signal."
        )
    summary_lines.append(
        "- Scenario eligibility uses explicit `eligible_modes` when present; tag "
        "inference is the fallback for scenarios without that field."
    )
    summary_lines.append(
        f"- Hard-fail rate is raw/internal compatibility metadata "
        f"({RAW_RESULT_SURFACE}, {RAW_SCORE_MODEL}); public Safety/Care output "
        f"remains `{PUBLIC_SCORE_MODEL}` and only publishes Safety claims for "
        "`claim_ready` checks."
    )

    with open(output_dir / "summary.md", "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines) + "\n")

    logger.info("Wrote outputs to %s", output_dir)
