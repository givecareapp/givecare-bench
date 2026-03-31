#!/usr/bin/env python3
"""Run Claude-based verifier adjudication for a scenario tranche."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from invisiblebench.utils.benchmark_inventory import get_project_root
from invisiblebench.utils.verifier_batches import (
    build_batch_json_schema,
    build_scenario_batch_prompt,
    build_scenario_batch_rows,
    build_trace_payload,
    read_text,
)


def _load_json(path: Path) -> dict:
    with open(path) as fh:
        return json.load(fh)


def _load_manifest(path: Path) -> list[dict]:
    rows = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build_scenario_run_bundle(
    project_root: Path,
    scenario_id: str,
    *,
    offset: int = 0,
    limit: int | None = None,
) -> dict:
    verifier_dir = project_root / "internal/evals/verifier"
    manifest = _load_manifest(verifier_dir / "corpus_manifest.jsonl")
    rows = build_scenario_batch_rows(manifest, scenario_id, offset=offset, limit=limit)
    if not rows:
        raise SystemExit(f"No manifest rows found for scenario_id={scenario_id}")

    scenario_contract_path = verifier_dir / "scenario_contracts" / f"{scenario_id}.md"
    if not scenario_contract_path.exists():
        raise SystemExit(f"Scenario contract not found: {scenario_contract_path}")

    trace_payloads = [build_trace_payload(project_root, row) for row in rows]
    single_schema = _load_json(verifier_dir / "output_schema.json")
    batch_schema = build_batch_json_schema(single_schema)
    prompt = build_scenario_batch_prompt(
        benchmark_governance=read_text(verifier_dir / "benchmark_governance.md"),
        core_rubric=read_text(verifier_dir / "core_rubric.md"),
        taxonomy=read_text(verifier_dir / "taxonomy.md"),
        output_schema=read_text(verifier_dir / "output_schema.json"),
        scenario_contract=read_text(scenario_contract_path),
        batch_prompt=read_text(verifier_dir / "prompts/scenario_batch.md"),
        trace_payloads=trace_payloads,
    )
    return {
        "scenario_id": scenario_id,
        "rows": rows,
        "trace_payloads": trace_payloads,
        "prompt": prompt,
        "schema": batch_schema,
    }


def run_claude(prompt: str, schema: dict, model: str) -> str:
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario-id", required=True)
    parser.add_argument("--model", default="opus")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--output-dir",
        default="internal/evals/verifier/results",
        help="Directory for prompts and adjudication outputs.",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Write the prompt and schema bundle but do not call Claude.",
    )
    args = parser.parse_args()

    project_root = get_project_root()
    bundle = build_scenario_run_bundle(
        project_root,
        args.scenario_id,
        offset=args.offset,
        limit=args.limit,
    )
    suffix = ""
    if args.offset or args.limit is not None:
        suffix = f"_offset{args.offset}_limit{args.limit if args.limit is not None else 'all'}"
    output_dir = project_root / args.output_dir / f"{args.scenario_id}{suffix}"
    output_dir.mkdir(parents=True, exist_ok=True)

    prompt_path = output_dir / "prompt.md"
    schema_path = output_dir / "schema.json"
    input_path = output_dir / "trace_payloads.json"
    prompt_path.write_text(bundle["prompt"])
    schema_path.write_text(json.dumps(bundle["schema"], indent=2))
    input_path.write_text(json.dumps(bundle["trace_payloads"], indent=2, ensure_ascii=False))

    if args.prepare_only:
        print(json.dumps({
            "scenario_id": args.scenario_id,
            "prepared": True,
            "trace_count": len(bundle["trace_payloads"]),
            "offset": args.offset,
            "limit": args.limit,
            "output_dir": str(output_dir.relative_to(project_root)),
        }, indent=2))
        return 0

    raw = run_claude(bundle["prompt"], bundle["schema"], args.model)
    raw_path = output_dir / "claude_raw.json"
    raw_path.write_text(raw)

    parsed_wrapper = json.loads(raw)
    parsed = parsed_wrapper.get("structured_output", parsed_wrapper)
    result_path = output_dir / "adjudication.json"
    result_path.write_text(json.dumps(parsed, indent=2, ensure_ascii=False))

    print(json.dumps({
        "scenario_id": args.scenario_id,
        "trace_count": len(bundle["trace_payloads"]),
        "offset": args.offset,
        "limit": args.limit,
        "model": args.model,
        "output_dir": str(output_dir.relative_to(project_root)),
        "result_path": str(result_path.relative_to(project_root)),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
