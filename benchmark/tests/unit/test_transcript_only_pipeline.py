from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from invisiblebench.api.client import CostBudgetExceededError
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


def test_evaluate_scenario_async_propagates_cost_ceiling(tmp_path: Path) -> None:
    scenario_path = tmp_path / "scenario.json"
    _write_scenario(scenario_path)

    class BudgetExceededClient:
        async def call_model_async(self, **_kwargs: Any) -> dict[str, Any]:
            raise CostBudgetExceededError("test ceiling")

    with pytest.raises(CostBudgetExceededError, match="test ceiling"):
        asyncio.run(
            evaluate_scenario_async(
                model={"id": "test/model", "name": "Test Model"},
                scenario={
                    "path": str(scenario_path),
                    "name": "Unit Test Scenario",
                    "category": "context",
                },
                api_client=BudgetExceededClient(),  # type: ignore[arg-type]
                output_dir=tmp_path / "run",
                semaphore=asyncio.Semaphore(1),
            )
        )


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

    class FakeModelAPIClient(_FakeAsyncClient):
        async def call_model_async(self, **kwargs):
            response = await super().call_model_async(**kwargs)
            run_command_mod.cost_tracker.record(kwargs["model"], 100, 50, actual_cost=0.012345)
            return response

    client = FakeModelAPIClient()
    monkeypatch.setattr("invisiblebench.api.client.ModelAPIClient", lambda: client)

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
    assert manifest["schema"] == "invisiblebench-run-manifest/v3"
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
    assert summary["actual_cost_usd"] == pytest.approx(len(client.calls) * 0.012345)
    assert summary["actual_billable_api_calls"] == len(client.calls)
    assert summary["actual_cost_by_model_usd"] == {"test/model": pytest.approx(len(client.calls) * 0.012345)}
    assert "run_scan.py plan" in summary["next_steps"]["scan_plan"]
    assert "--output" in summary["next_steps"]["scan_plan"]

    from benchmark.tests.fixtures.current_scan import FixtureJudge
    from invisiblebench.judge import load_scan, plan_scan, run_scan

    bundle = tmp_path / "scan"
    plan = plan_scan([output_dir], bundle)
    run_scan(bundle, max_cost_usd=plan.estimated_cost_usd, client=FixtureJudge())
    assert len(load_scan(bundle, complete=True)[1]) == len(plan.checks)


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
