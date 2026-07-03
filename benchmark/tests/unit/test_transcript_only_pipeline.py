from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from invisiblebench.cli import run_command as run_command_mod
from invisiblebench.cli.transcript import evaluate_scenario_async


class _FakeAsyncClient:
    async def call_model_async(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
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
        return {
            "artifact_type": "transcript_result/v1",
            "model": model["name"],
            "model_id": model["id"],
            "scenario": scenario["name"],
            "scenario_id": scenario["scenario_id"],
            "category": scenario["category"],
            "transcript_path": str(transcript_path),
            "cost": 0.0,
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
        scenario_filter=["context_regulatory_data_privacy_001"],
    )

    assert rc == 0
    assert (output_dir / "run_manifest.json").exists()
    assert (output_dir / "transcript_run.json").exists()
    assert not (output_dir / "all_results.json").exists()

    summary = json.loads((output_dir / "transcript_run.json").read_text())
    assert summary["artifact_type"] == "transcript_run/v1"
    assert summary["status"] == "complete"
    assert summary["transcript_count"] == 1
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
