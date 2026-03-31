from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Sequence


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def read_text(path: Path) -> str:
    return path.read_text()


def build_scenario_batch_rows(
    manifest: Sequence[Dict[str, Any]],
    scenario_id: str,
    *,
    offset: int = 0,
    limit: int | None = None,
) -> List[Dict[str, Any]]:
    rows = [row for row in manifest if row.get("scenario_id") == scenario_id]
    rows = sorted(rows, key=lambda row: row.get("model", ""))
    if offset:
        rows = rows[offset:]
    if limit is not None:
        rows = rows[:limit]
    return rows


def build_trace_payload(project_root: Path, row: Dict[str, Any]) -> Dict[str, Any]:
    transcript_path = project_root / row["transcript_path"]
    transcript = load_jsonl(transcript_path)
    return {
        "model": row["model"],
        "model_id": row["model_id"],
        "scenario_id": row["scenario_id"],
        "scenario": row.get("scenario"),
        "current_scorer": {
            "status": row.get("status"),
            "success": row.get("success"),
            "overall_score": row.get("overall_score"),
            "hard_fail": row.get("hard_fail"),
            "hard_fail_reasons": row.get("hard_fail_reasons", []),
            "judge_model": row.get("judge_model"),
            "contract_version": row.get("contract_version"),
        },
        "transcript": transcript,
    }


def _fence(title: str, content: str) -> str:
    return f"## {title}\n\n```\n{content.rstrip()}\n```\n"


def build_scenario_batch_prompt(
    *,
    benchmark_governance: str,
    core_rubric: str,
    taxonomy: str,
    output_schema: str,
    scenario_contract: str,
    batch_prompt: str,
    trace_payloads: Sequence[Dict[str, Any]],
) -> str:
    sections = [
        "You are adjudicating a single InvisibleBench scenario batch.",
        _fence("Benchmark Governance", benchmark_governance),
        _fence("Core Rubric", core_rubric),
        _fence("Taxonomy", taxonomy),
        _fence("Output Schema", output_schema),
        _fence("Batch Prompt", batch_prompt),
        _fence("Scenario Contract", scenario_contract),
        "## Trace Batch\n",
    ]

    for idx, trace in enumerate(trace_payloads, start=1):
        scorer = json.dumps(trace["current_scorer"], indent=2, sort_keys=True)
        transcript = json.dumps(trace["transcript"], indent=2, ensure_ascii=False)
        sections.append(
            f"### Trace {idx}: {trace['model']}\n\n"
            f"Current scorer summary:\n```json\n{scorer}\n```\n\n"
            f"Transcript:\n```json\n{transcript}\n```\n"
        )

    sections.append(
        "## Required Output\n\n"
        "Return a single JSON object with this shape:\n\n"
        "```json\n"
        "{\n"
        "  \"scenario_id\": \"...\",\n"
        "  \"trace_results\": [<one verifier object per trace, each conforming to the output schema>],\n"
        "  \"batch_summary\": {\n"
        "    \"scenario_id\": \"...\",\n"
        "    \"total_traces\": 0,\n"
        "    \"agreements\": 0,\n"
        "    \"disagreements\": 0,\n"
        "    \"repeated_false_positive_patterns\": [\"...\"],\n"
        "    \"repeated_false_negative_patterns\": [\"...\"],\n"
        "    \"taxonomy_notes\": \"...\",\n"
        "    \"recommended_next_action\": \"...\"\n"
        "  }\n"
        "}\n"
        "```\n\n"
        "Return JSON only."
    )
    return "\n".join(sections)


def build_batch_json_schema(single_result_schema: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["scenario_id", "trace_results", "batch_summary"],
        "properties": {
            "scenario_id": {"type": "string"},
            "trace_results": {
                "type": "array",
                "items": single_result_schema,
                "minItems": 1,
            },
            "batch_summary": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "scenario_id",
                    "total_traces",
                    "agreements",
                    "disagreements",
                    "repeated_false_positive_patterns",
                    "repeated_false_negative_patterns",
                    "taxonomy_notes",
                    "recommended_next_action",
                ],
                "properties": {
                    "scenario_id": {"type": "string"},
                    "total_traces": {"type": "integer", "minimum": 1},
                    "agreements": {"type": "integer", "minimum": 0},
                    "disagreements": {"type": "integer", "minimum": 0},
                    "repeated_false_positive_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "repeated_false_negative_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "taxonomy_notes": {"type": "string"},
                    "recommended_next_action": {"type": "string"},
                },
            },
        },
    }
