from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from invisiblebench.cli import run_command as run_command_mod
from invisiblebench.cli.transcript import evaluate_scenario_async


class _FakeAsyncClient:
    def __init__(self) -> None:
        self.calls: list[list[dict[str, str]]] = []

    async def call_model_async(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        self.calls.append([dict(message) for message in messages])
        return {
            "response": "I can help with that.",
            "finish_reason": "stop",
            "tokens": 8,
            "prompt_tokens": 4,
            "completion_tokens": 4,
            "model": model,
            "raw": {},
        }


def _write_scenario(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "scenario_id": "context_unit_test_001",
                "category": "context",
                "title": "Unit Test Scenario",
                "turns": [
                    {
                        "turn_number": 1,
                        "user_message": "Can you help me understand my options?",
                    }
                ],
            }
        )
    )


def test_evaluate_scenario_async_transcript_only_skips_judge(tmp_path: Path) -> None:
    scenario_path = tmp_path / "scenario.json"
    _write_scenario(scenario_path)

    row = asyncio.run(
        evaluate_scenario_async(
            model={"id": "test/model", "name": "Test Model"},
            scenario={
                "path": str(scenario_path),
                "name": "Unit Test Scenario",
                "category": "context",
            },
            api_client=_FakeAsyncClient(),  # type: ignore[arg-type]
            output_dir=tmp_path / "run",
            semaphore=asyncio.Semaphore(1),
            run_id="run-id",
        )
    )

    assert row["status"] == "transcript_ready"
    assert row["run_id"] == "run-id"
    assert Path(row["transcript_path"]).exists()


def test_multisession_transcript_preserves_session_semantics(tmp_path: Path) -> None:
    scenario_path = tmp_path / "multisession.json"
    scenario_path.write_text(
        json.dumps(
            {
                "scenario_id": "continuity_unit_test_001",
                "category": "continuity",
                "sessions": [
                    {
                        "session_number": 1,
                        "time_elapsed": "Day 0",
                        "session_context": "Initial conversation.",
                        "turns": [{"turn_number": 1, "user_message": "My name is Jamie."}],
                    },
                    {
                        "session_number": 2,
                        "time_elapsed": "3 months later",
                        "session_context": "Jamie returns after the appeal.",
                        "turns": [{"turn_number": 2, "user_message": "I'm back."}],
                    },
                ],
            }
        )
    )
    client = _FakeAsyncClient()

    row = asyncio.run(
        evaluate_scenario_async(
            model={"id": "test/model", "name": "Test Model"},
            scenario={
                "path": str(scenario_path),
                "name": "Multi-session Scenario",
                "category": "continuity",
            },
            api_client=client,  # type: ignore[arg-type]
            output_dir=tmp_path / "run",
            semaphore=asyncio.Semaphore(1),
        )
    )

    transcript = [
        json.loads(line)
        for line in Path(row["transcript_path"]).read_text().splitlines()
    ]
    assert {entry["session_number"] for entry in transcript} == {1, 2}
    assert transcript[-1]["time_elapsed"] == "3 months later"
    assert "3 months later" in client.calls[-1][0]["content"]
    assert "Jamie returns after the appeal" in client.calls[-1][0]["content"]


def test_run_benchmark_transcript_only_writes_stage_artifact(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "run"
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(run_command_mod, "RICH_AVAILABLE", False)

    class FakeModelAPIClient:
        pass

    monkeypatch.setattr(
        "invisiblebench.api.client.ModelAPIClient",
        FakeModelAPIClient,
    )

    async def fake_evaluate_scenario_async(
        model: dict[str, Any],
        scenario: dict[str, Any],
        api_client: Any,
        output_dir: Path,
        semaphore: asyncio.Semaphore,
        **kwargs: Any,
    ) -> dict[str, Any]:
        assert "score_transcript" not in kwargs
        transcript_dir = output_dir / "transcripts"
        transcript_dir.mkdir(parents=True, exist_ok=True)
        transcript_path = transcript_dir / f"{model['id'].replace('/', '_')}_scenario.jsonl"
        transcript_path.write_text('{"role":"assistant","content":"ok"}\n')
        run_command_mod.cost_tracker.record(
            model["id"],
            prompt_tokens=100,
            completion_tokens=50,
            actual_cost=0.012345,
        )
        return {
            "artifact_type": "transcript_result/v1",
            "model": model["name"],
            "model_id": model["id"],
            "scenario": scenario["name"],
            "scenario_id": scenario["scenario_id"],
            "category": scenario["category"],
            "transcript_path": str(transcript_path),
            "cost": 0.012345,
            "status": "transcript_ready",
            "success": True,
            "run_id": kwargs["run_id"],
        }

    monkeypatch.setattr(
        run_command_mod,
        "evaluate_scenario_async",
        fake_evaluate_scenario_async,
    )

    rc = run_command_mod.run_benchmark(
        models=[
            {
                "id": "test/model",
                "name": "Test Model",
                "cost_per_m_input": 1.0,
                "cost_per_m_output": 1.0,
            }
        ],
        output_dir=output_dir,
        dry_run=False,
        auto_confirm=True,
        max_cost_usd=1.0,
        scenario_filter=["context_regulatory_data_privacy_001"],
    )

    assert rc == 0
    assert (output_dir / "run_manifest.json").exists()
    assert (output_dir / "transcript_run.json").exists()
    assert not (output_dir / "all_results.json").exists()

    manifest = json.loads((output_dir / "run_manifest.json").read_text())
    assert manifest["schema"] == "invisiblebench-run-manifest/v2"
    assert manifest["scenario_ids"] == ["context_regulatory_data_privacy_001"]
    assert manifest["transcript_policy"]["system_prompt_hash"]
    assert manifest["transcript_policy"]["temperature"] == 0.7
    assert manifest["transcript_policy"]["max_reply_tokens"] == 4000
    assert manifest["transcript_policy"]["tools"] == "none"

    summary = json.loads((output_dir / "transcript_run.json").read_text())
    assert summary["artifact_type"] == "transcript_run/v1"
    assert summary["status"] == "complete"
    assert "resolved_model_ids" in summary
    assert "resolved_providers" in summary
    assert summary["transcript_count"] == 1
    assert summary["actual_cost_usd"] == 0.012345
    assert summary["actual_billable_api_calls"] == 1
    assert summary["actual_cost_by_model_usd"] == {"test/model": 0.012345}
    assert "run_scan.py --profile dev" in summary["next_steps"]["dev_scan"]
    assert "--llm-model openai/gpt-5-mini" in summary["next_steps"]["dev_scan"]


def test_runner_main_defaults_to_transcript_only(monkeypatch, tmp_path: Path) -> None:
    observed: dict[str, Any] = {}

    def fake_run_benchmark(**kwargs: Any) -> int:
        observed.update(kwargs)
        return 0

    monkeypatch.setattr("invisiblebench.cli.runner.run_benchmark", fake_run_benchmark)

    from invisiblebench.cli import runner as runner_mod

    rc = runner_mod.main(
        [
            "-m",
            "1",
            "--dry-run",
            "--output",
            str(tmp_path / "run"),
        ]
    )

    assert rc == 0
    assert "transcripts_only" not in observed
