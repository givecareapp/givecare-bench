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
  uv run python scripts/run_v3_blindspot_scan.py <run_dir>
  uv run python scripts/run_v3_blindspot_scan.py results/run_20260330_130332
  uv run python scripts/run_v3_blindspot_scan.py --all
"""

from __future__ import annotations

import argparse
import collections
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from invisiblebench.api import ModelAPIClient  # noqa: E402
from invisiblebench.evaluation.mode_engine import (  # noqa: E402
    ModeEngine,
    ModeEngineOutput,
    corpus_blindspot_rates,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("v3_scan")


SCENARIOS_ROOT = REPO_ROOT / "benchmark" / "scenarios"


def load_scenario(scenario_id: str) -> Dict[str, Any]:
    """Find a scenario JSON by id across benchmark/scenarios/."""
    for path in SCENARIOS_ROOT.rglob("*.json"):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        if data.get("scenario_id") == scenario_id:
            return data
    # Fallback — legacy id lookup by filename stem
    for path in SCENARIOS_ROOT.rglob("*.json"):
        if path.stem == scenario_id:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    logger.warning("Scenario not found: %s", scenario_id)
    return {"scenario_id": scenario_id, "category": "unknown"}


def load_transcript(path: Path) -> List[Dict[str, Any]]:
    turns: List[Dict[str, Any]] = []
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


def transcripts_for_run(run_dir: Path) -> List[Dict[str, Any]]:
    """Pair each transcript JSONL with its (model, scenario_id) metadata."""
    transcripts_dir = run_dir / "transcripts"
    if not transcripts_dir.is_dir():
        return []

    results_path = run_dir / "all_results.json"
    results_by_key: Dict[str, Dict[str, Any]] = {}
    if results_path.exists():
        with open(results_path, encoding="utf-8") as f:
            for r in json.load(f):
                key = f"{r['model_id']}__{r['scenario_id']}"
                results_by_key[key] = r

    pairs: List[Dict[str, Any]] = []
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
                "legacy_result": matched,
            }
        )
    return pairs


def enrich_scenario_with_inferred_tags(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """Infer failure_mode_tags from legacy scenario fields so v0 modes can fire.

    This is a bridge pass — full scenario tagging is task #17. For now we
    infer from category + risk_triggers + rubric so deterministic modes
    have enough eligibility signal to match existing scenarios.
    """
    def _as_str_tags(items: Any) -> List[str]:
        out: List[str] = []
        if not items:
            return out
        for x in items:
            if isinstance(x, str):
                out.append(x)
            elif isinstance(x, dict):
                # risk_triggers may be dicts with a 'name' or 'type' key
                for k in ("name", "type", "trigger", "id"):
                    if isinstance(x.get(k), str):
                        out.append(x[k])
                        break
        return out

    inferred: List[str] = _as_str_tags(scenario.get("failure_mode_tags"))
    inferred.extend(_as_str_tags(scenario.get("risk_triggers")))
    inferred.extend(_as_str_tags(scenario.get("tags")))

    category = (scenario.get("category") or scenario.get("tier") or "").lower()
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


def scan_run(
    run_dir: Path,
    engine: ModeEngine,
    limit: Optional[int] = None,
    filename_filter: Optional[str] = None,
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

    outputs: List[Dict[str, Any]] = []
    engine_outputs: List[ModeEngineOutput] = []

    for i, pair in enumerate(pairs, 1):
        transcript = load_transcript(pair["transcript_path"])
        if not transcript:
            logger.warning("Empty transcript: %s", pair["transcript_path"].name)
            continue

        scenario = load_scenario(pair["scenario_id"])
        scenario = enrich_scenario_with_inferred_tags(scenario)

        try:
            out = engine.evaluate(transcript=transcript, scenario=scenario)
        except Exception as e:
            logger.exception("Engine crash on %s: %s", pair["scenario_id"], e)
            continue

        record = {
            "model": pair["model"],
            "model_id": pair["model_id"],
            "scenario_id": pair["scenario_id"],
            "category": pair["category"],
            "transcript_path": str(pair["transcript_path"]),
            "legacy_overall": pair["legacy_result"].get("overall_score"),
            "legacy_hard_fail": pair["legacy_result"].get("hard_fail"),
            **out.to_dict(),
        }
        outputs.append(record)
        engine_outputs.append(out)

        if i % 25 == 0:
            logger.info("  scanned %d/%d", i, len(pairs))

    return outputs, engine_outputs


def write_outputs(
    output_dir: Path,
    outputs: List[Dict[str, Any]],
    engine_outputs: List[ModeEngineOutput],
    run_dirs: List[Path],
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

    # Per-model blindspot rates
    by_model: Dict[str, List[ModeEngineOutput]] = collections.defaultdict(list)
    by_model_records: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
    for r, eo in zip(outputs, engine_outputs):
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
    summary_lines: List[str] = []
    summary_lines.append("# V3 Blindspot Scan — Summary\n")
    summary_lines.append(f"- Source run dirs: {', '.join(str(d.name) for d in run_dirs)}")
    summary_lines.append(f"- Transcripts scanned: {len(outputs)}")
    summary_lines.append(
        f"- Models: {', '.join(sorted(by_model.keys()))}\n"
    )
    summary_lines.append("## Overall blindspot rates\n")
    summary_lines.append("| Blindspot | Rate | Failures / Eligible |")
    summary_lines.append("|---|---:|---:|")

    # Recompute with eligibility counts for display
    eligible_counts: Dict[str, Dict[str, int]] = {}
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
        "- Scenario tags inferred from legacy `risk_triggers` + `category` + rubric "
        "heuristics (full tagging pass is task #17)."
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
        "run_dir", nargs="?", help="Path to results/run_<timestamp>/ directory"
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
        "--enable-llm",
        action="store_true",
        help="Wire ModelAPIClient so LLM-primary modes run (costs tokens).",
    )
    ap.add_argument(
        "--llm-model",
        default="google/gemini-2.5-flash-lite",
        help="Judge model for LLM verifiers (default: Gemini flash-lite).",
    )
    args = ap.parse_args()

    api_client = None
    if args.enable_llm:
        try:
            api_client = ModelAPIClient()
            logger.info("LLM verifier enabled with model=%s", args.llm_model)
        except Exception as e:
            logger.error("Failed to initialize ModelAPIClient: %s", e)
            logger.error("LLM modes will short-circuit to UNCLEAR / NOT_APPLICABLE.")
    engine = ModeEngine(llm_api_client=api_client, llm_model=args.llm_model)
    logger.info("Loaded %d modes from failure_modes.yaml", len(engine.modes))
    logger.info("Loaded %d routing entries", len(engine.routing))

    run_dirs: List[Path] = []
    if args.all:
        run_dirs = sorted(
            (REPO_ROOT / "results").glob("run_*"),
            key=lambda p: p.name,
            reverse=True,
        )
    elif args.run_dir:
        run_dirs = [Path(args.run_dir).resolve()]
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

    all_outputs: List[Dict[str, Any]] = []
    all_engine_outputs: List[ModeEngineOutput] = []

    for run_dir in run_dirs:
        outputs, engine_outputs = scan_run(
            run_dir,
            engine,
            limit=args.limit,
            filename_filter=args.filter,
        )
        all_outputs.extend(outputs)
        all_engine_outputs.extend(engine_outputs)

    if not all_outputs:
        logger.error("No transcripts scanned")
        return 3

    output_dir = Path(args.output_root) / time.strftime("%Y%m%d_%H%M%S")
    write_outputs(output_dir, all_outputs, all_engine_outputs, run_dirs)

    print(f"\nScan complete: {output_dir}")
    print(f"See {output_dir}/summary.md for top-line blindspot rates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
