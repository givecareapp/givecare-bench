from __future__ import annotations

import json
from pathlib import Path

from invisiblebench.utils.verifier_batches import (
    build_batch_json_schema,
    build_scenario_batch_prompt,
    build_scenario_batch_rows,
    build_trace_payload,
)


def test_build_scenario_batch_rows_filters_and_sorts() -> None:
    manifest = [
        {"scenario_id": "s1", "model": "B"},
        {"scenario_id": "s2", "model": "A"},
        {"scenario_id": "s1", "model": "A"},
    ]
    rows = build_scenario_batch_rows(manifest, "s1")
    assert [row["model"] for row in rows] == ["A", "B"]


def test_build_trace_payload_reads_transcript(tmp_path: Path) -> None:
    transcript_path = tmp_path / "results" / "transcripts" / "m_s1.jsonl"
    transcript_path.parent.mkdir(parents=True)
    transcript_path.write_text(
        json.dumps({"turn": 1, "role": "user", "content": "Hi"}) + "\n"
        + json.dumps({"turn": 1, "role": "assistant", "content": "Hello"}) + "\n"
    )

    row = {
        "model": "Model A",
        "model_id": "provider/model-a",
        "scenario_id": "s1",
        "scenario": "Scenario 1",
        "transcript_path": "results/transcripts/m_s1.jsonl",
        "status": "fail",
        "success": False,
        "overall_score": 0.0,
        "hard_fail": True,
        "hard_fail_reasons": ["false_scope"],
        "judge_model": "judge",
        "contract_version": "2.1.0",
    }
    payload = build_trace_payload(tmp_path, row)
    assert payload["model"] == "Model A"
    assert payload["current_scorer"]["hard_fail"] is True
    assert len(payload["transcript"]) == 2


def test_build_scenario_batch_prompt_includes_trace_sections() -> None:
    prompt = build_scenario_batch_prompt(
        benchmark_governance="governance",
        core_rubric="rubric",
        taxonomy="taxonomy",
        output_schema="schema",
        scenario_contract="contract",
        batch_prompt="batch rules",
        trace_payloads=[
            {
                "model": "Model A",
                "current_scorer": {"status": "fail"},
                "transcript": [{"turn": 1, "role": "assistant", "content": "Hi"}],
            }
        ],
    )
    assert "Benchmark Governance" in prompt
    assert "Trace 1: Model A" in prompt
    assert "Current scorer summary" in prompt
    assert "Required Output" in prompt


def test_build_batch_json_schema_wraps_single_schema() -> None:
    single = {
        "type": "object",
        "properties": {"scenario_id": {"type": "string"}},
        "required": ["scenario_id"],
    }
    schema = build_batch_json_schema(single)
    assert schema["properties"]["trace_results"]["items"] == single
    assert "batch_summary" in schema["properties"]
