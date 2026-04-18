#!/usr/bin/env python3
"""Run a repeated, decomposed verifier over the golden set.

For each golden-set candidate:
  1. Build a rule-decomposed single-trace verifier prompt.
  2. Run the prompt N times with Claude.
  3. Aggregate the repeated verifier passes into one public-schema label.
  4. Write aggregated labels to labels/<label_name>/.
  5. Optionally score them against a reference label folder such as annotator_a.

This is a verifier-style dev harness, not authoritative gold generation.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from golden_set_kappa import _load_candidates, _load_labels, build_report

from invisiblebench.utils.golden_verifier import (
    aggregate_verifier_passes,
    build_validation_summary,
    build_verifier_pass_schema,
    build_verifier_prompt,
    load_jsonl,
    parse_claude_json,
    read_text,
)

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = ROOT / "internal/evals/verifier/golden_set"
VERIFIER_DIR = ROOT / "internal/evals/verifier"
CANDIDATES_PATH = GOLDEN_DIR / "candidates.jsonl"

SCENARIO_FILE_INDEX: dict[str, Path] | None = None


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())



def _scenario_index() -> dict[str, Path]:
    global SCENARIO_FILE_INDEX
    if SCENARIO_FILE_INDEX is not None:
        return SCENARIO_FILE_INDEX
    idx: dict[str, Path] = {}
    for path in (ROOT / "benchmark/scenarios").rglob("*.json"):
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        scenario_id = data.get("scenario_id") or data.get("id")
        if isinstance(scenario_id, str):
            idx[scenario_id] = path
    SCENARIO_FILE_INDEX = idx
    return idx



def _load_contract(scenario_id: str) -> tuple[str, str]:
    contract_path = VERIFIER_DIR / "scenario_contracts" / f"{scenario_id}.md"
    if contract_path.exists():
        return contract_path.read_text(), str(contract_path.relative_to(ROOT))

    raw_path = _scenario_index().get(scenario_id)
    if raw_path is None:
        raise SystemExit(f"No scenario contract or raw scenario file found for {scenario_id}")
    raw = json.loads(raw_path.read_text())
    keep_keys = [
        "scenario_id",
        "category",
        "title",
        "description",
        "gray_zone",
        "ambiguity_type",
        "persona",
        "turns",
        "probes",
        "risk_triggers",
        "scoring_dimensions",
        "calibration_notes",
    ]
    trimmed = {key: raw[key] for key in keep_keys if key in raw}
    rel = raw_path.relative_to(ROOT)
    text = (
        f"# Raw scenario contract fallback\n\nSource: `{rel}`\n\n"
        f"```json\n{json.dumps(trimmed, indent=2, ensure_ascii=False)}\n```\n"
    )
    return text, str(rel)



def _run_claude(prompt: str, schema: dict[str, Any], model: str) -> str:
    cmd = [
        "claude",
        "-p",
        "--model",
        model,
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(schema),
        "--tools",
        "",
    ]
    proc = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout



def _validate_pass(pass_output: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {
        "scenario_id",
        "model",
        "model_id",
        "rule_checks",
        "quality",
        "soft_issues",
        "evidence",
        "agreement_with_current_scorer",
        "disagreement_labels",
        "summary",
    }
    missing = required - set(pass_output)
    if missing:
        errors.append(f"missing keys: {sorted(missing)}")
    if not pass_output.get("evidence"):
        errors.append("evidence must have at least one entry")
    return errors



def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")



def _select_candidates(candidates: list[dict[str, Any]], trace_ids: list[str] | None, limit: int | None) -> list[dict[str, Any]]:
    if trace_ids:
        wanted = set(trace_ids)
        candidates = [candidate for candidate in candidates if candidate["trace_id"] in wanted]
    if limit is not None:
        candidates = candidates[:limit]
    return candidates



def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--label-name", default="ai_verifier_v1")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--trace-id", action="append", dest="trace_ids")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--score-against", default="annotator_a")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()

    if args.repeat < 1:
        raise SystemExit("--repeat must be >= 1")

    candidates = _load_candidates()
    selected = _select_candidates(candidates, args.trace_ids, args.limit)
    if not selected:
        raise SystemExit("No candidates selected")

    schema = build_verifier_pass_schema()
    label_dir = GOLDEN_DIR / "labels" / args.label_name
    runs_dir = label_dir / "_passes"
    prompt_dir = label_dir / "_prompts"
    label_dir.mkdir(parents=True, exist_ok=True)

    prepared = 0
    completed = 0
    failures: list[tuple[str, str]] = []

    for index, candidate in enumerate(selected, start=1):
        trace_id = candidate["trace_id"]
        final_path = label_dir / f"{trace_id}.json"
        if final_path.exists() and not args.overwrite:
            print(f"[{index}/{len(selected)}] {trace_id} (skip existing)")
            continue

        transcript = load_jsonl(ROOT / candidate["transcript_path"])
        contract_text, contract_src = _load_contract(candidate["scenario_id"])
        pass_outputs: list[dict[str, Any]] = []
        print(f"[{index}/{len(selected)}] {trace_id}")

        for repeat_index in range(1, args.repeat + 1):
            prompt = build_verifier_prompt(
                benchmark_governance=read_text(VERIFIER_DIR / "benchmark_governance.md"),
                core_rubric=read_text(VERIFIER_DIR / "core_rubric.md"),
                taxonomy=read_text(VERIFIER_DIR / "taxonomy.md"),
                output_schema=read_text(VERIFIER_DIR / "output_schema.json"),
                verifier_prompt=read_text(VERIFIER_DIR / "prompts/decomposed_single_trace.md"),
                scenario_contract=contract_text,
                candidate=candidate,
                transcript=transcript,
                repeat_index=repeat_index,
                repeat_total=args.repeat,
            )
            prompt_path = prompt_dir / trace_id / f"pass_{repeat_index}.md"
            prompt_path.parent.mkdir(parents=True, exist_ok=True)
            prompt_path.write_text(prompt)
            prepared += 1

            if args.prepare_only:
                continue

            try:
                raw = _run_claude(prompt, schema, args.model)
            except subprocess.CalledProcessError as exc:
                failures.append((trace_id, f"claude rc={exc.returncode}: {exc.stderr[:200]}"))
                break

            raw_path = runs_dir / trace_id / f"pass_{repeat_index}_raw.json"
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_text(raw)
            try:
                parsed = parse_claude_json(raw)
            except Exception as exc:
                failures.append((trace_id, f"json parse: {exc}"))
                break

            errors = _validate_pass(parsed)
            if errors:
                failures.append((trace_id, "; ".join(errors)))
                break

            notes = parsed.setdefault("summary", {}).get("notes", "").strip()
            parsed["summary"]["notes"] = (
                f"AI-VERIFIER PASS DRAFT ({args.label_name}; pass {repeat_index}/{args.repeat}; contract={contract_src})."
                + (f" {notes}" if notes else "")
            )
            parsed_path = runs_dir / trace_id / f"pass_{repeat_index}.json"
            _write_json(parsed_path, parsed)
            pass_outputs.append(parsed)

        if args.prepare_only:
            continue

        if len(pass_outputs) != args.repeat:
            continue

        aggregated = aggregate_verifier_passes(pass_outputs, label_name=args.label_name)
        _write_json(final_path, aggregated)
        completed += 1

    if args.prepare_only:
        print(json.dumps({
            "prepared_prompts": prepared,
            "selected_candidates": len(selected),
            "repeat": args.repeat,
            "label_name": args.label_name,
        }, indent=2))
        return 0

    if failures:
        print(f"\n{len(failures)} failures:")
        for trace_id, message in failures[:20]:
            print(f"- {trace_id}: {message}")
        if completed == 0:
            return 1

    if args.score_against:
        predictions = _load_labels(label_dir)
        reference_dir = GOLDEN_DIR / "labels" / args.score_against
        references = _load_labels(reference_dir)

        validation_summary = build_validation_summary(
            label_name=args.label_name,
            predictions=predictions,
            references=references,
        )
        validation_path = GOLDEN_DIR / f"{args.label_name}_vs_{args.score_against}.md"
        validation_path.write_text(validation_summary)

        kappa_report, _ = build_report(candidates, references, predictions, args.score_against, args.label_name)
        kappa_path = GOLDEN_DIR / f"{args.score_against}_vs_{args.label_name}_kappa.md"
        kappa_path.write_text(kappa_report + "\n")

        print(json.dumps({
            "completed": completed,
            "selected_candidates": len(selected),
            "repeat": args.repeat,
            "label_dir": str(label_dir.relative_to(ROOT)),
            "validation_path": str(validation_path.relative_to(ROOT)),
            "kappa_path": str(kappa_path.relative_to(ROOT)),
            "failures": len(failures),
        }, indent=2))
    else:
        print(json.dumps({
            "completed": completed,
            "selected_candidates": len(selected),
            "repeat": args.repeat,
            "label_dir": str(label_dir.relative_to(ROOT)),
            "failures": len(failures),
        }, indent=2))

    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
