"""Inspect export keeps known branch spend visible on partial samples."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from inspect_ai.log import EvalError, EvalSample, EvalSampleLimit
from inspect_ai.model import ChatMessageAssistant, ChatMessageUser, ModelUsage

from invisiblebench.api.typesafe import DEFAULT_JUDGE_MODEL, request_cost
from invisiblebench.inspect_export import export_run
from invisiblebench.inspect_task import (
    MAX_REPLY_TOKENS,
    TRANSCRIPT_TEMPERATURE,
    system_prompt_hash,
)
from invisiblebench.version import BENCHMARK_VERSION


def sample(*, metadata=None, error=None, limit=None, messages=None, usage=True):
    return EvalSample(
        id="scenario",
        epoch=1,
        input="Scenario",
        target="reply",
        metadata={"name": "Scenario", "category": "context", **(metadata or {})},
        messages=messages if messages is not None else [
            ChatMessageUser(content="Please help.", metadata={"turn": 1}),
            ChatMessageAssistant(content="I can help.", metadata={"turn": 1}),
        ],
        model_usage={"mockllm/model": ModelUsage(total_cost=0.2)} if usage else {},
        error=error,
        limit=limit,
    )


def export_sample(monkeypatch, tmp_path, current):
    samples = current if isinstance(current, list) else [current]
    current = samples[-1]
    log = SimpleNamespace(
        location="fixture.eval",
        eval=SimpleNamespace(
            revision=SimpleNamespace(commit="a" * 40, dirty=False),
            metadata={
                "scenario_hash": "scenario-hash",
                "system_prompt_hash": system_prompt_hash(),
                "include_confidential": False,
            },
            packages={"inspect_ai": "0.0.0"},
            run_id="fixture-run",
            created="2026-10-17T00:00:00Z",
            model="openrouter/mockllm/model",
            task="invisiblebench/safety_care",
            dataset=SimpleNamespace(sample_ids=["scenario"]),
        ),
        plan=SimpleNamespace(
            config=SimpleNamespace(
                temperature=TRANSCRIPT_TEMPERATURE,
                max_tokens=MAX_REPLY_TOKENS,
            ),
        ),
        samples=samples,
        status="success" if not (current.error or current.limit) else "error",
        error=None,
        stats=SimpleNamespace(
            started_at="2026-10-17T00:00:00Z",
            completed_at="2026-10-17T00:00:01Z",
        ),
    )
    monkeypatch.setattr("invisiblebench.inspect_export.read_eval_log", lambda _: log)
    monkeypatch.setattr("invisiblebench.inspect_export.get_project_root", lambda: tmp_path)
    monkeypatch.setattr(
        "invisiblebench.inspect_export._full_commit", lambda commit, root: commit
    )
    monkeypatch.setattr("invisiblebench.inspect_export._endpoint", lambda _: None)
    monkeypatch.setattr("invisiblebench.inspect_export._seconds", lambda _: None)
    monkeypatch.setattr(
        "invisiblebench.inspect_export.transcript_policy", lambda models, version: {}
    )
    monkeypatch.setattr(
        "invisiblebench.inspect_export.generate_manifest",
        lambda *_args, **_kwargs: {
            "run_id": "fixture-run",
            "benchmark_version": BENCHMARK_VERSION,
            "scenario_hash": "scenario-hash",
        },
    )
    monkeypatch.setattr(
        "invisiblebench.inspect_export.write_manifest",
        lambda _manifest, output: output.mkdir(parents=True, exist_ok=True),
    )
    output = tmp_path / "export"
    export_run([Path("fixture.eval")], output)
    return json.loads((output / "transcript_run.json").read_text())


@pytest.mark.parametrize("failure", ["error", "limit"])
def test_partial_sample_exports_known_branch_spend(monkeypatch, tmp_path, failure):
    metadata = {"branch_judge_cost_usd": 0.05, "branch_judge_cost_unknown": False}
    current = sample(metadata=metadata)
    if failure == "error":
        current.error = EvalError(message="branch follow-up failed", traceback="", traceback_ansi="")
    else:
        current.limit = EvalSampleLimit(type="cost", limit=0.25)

    summary = export_sample(monkeypatch, tmp_path, current)

    assert summary["actual_cost_usd"] == pytest.approx(0.25)
    assert summary["actual_known_cost_usd"] == pytest.approx(0.25)
    assert summary["unknown_calls_with_uncosted_usd"] == 0
    assert summary["transcript_count"] == 0


def test_unknown_branch_usage_keeps_known_cost_and_marks_sample_unknown(monkeypatch, tmp_path):
    current = sample(
        metadata={"branch_judge_cost_usd": 0.05, "branch_judge_cost_unknown": True},
        error=EvalError(message="branch response usage missing", traceback="", traceback_ansi=""),
    )

    summary = export_sample(monkeypatch, tmp_path, current)

    assert summary["actual_cost_usd"] is None
    assert summary["actual_known_cost_usd"] == pytest.approx(0.25)
    assert summary["unknown_calls_with_uncosted_usd"] == 1


def test_success_uses_wrapper_branch_cost_without_double_counting_legacy_metadata(
    monkeypatch, tmp_path
):
    response = {
        "model": DEFAULT_JUDGE_MODEL,
        "usage": {"input_tokens": 10},
    }
    current = sample(
        metadata={"branch_judge_cost_usd": 0.05, "branch_judge_cost_unknown": False},
        messages=[
            ChatMessageUser(
                content="Please help.",
                metadata={
                    "turn": 1,
                    "branch_decisions": [{"type": "noul", "probability": 0.9, "judge_response": response}],
                },
            ),
            ChatMessageAssistant(content="I can help.", metadata={"turn": 1}),
        ],
    )

    summary = export_sample(monkeypatch, tmp_path, current)

    assert summary["actual_cost_usd"] == pytest.approx(0.25)
    assert summary["actual_known_cost_usd"] == pytest.approx(0.25)
    assert summary["unknown_calls_with_uncosted_usd"] == 0


def test_legacy_partial_sample_reads_branch_metadata_without_turn_entries(monkeypatch, tmp_path):
    response = {
        "model": DEFAULT_JUDGE_MODEL,
        "usage": {"input_tokens": 10},
    }
    current = sample(
        metadata={},
        error=EvalError(message="partial sample", traceback="", traceback_ansi=""),
        messages=[
            ChatMessageUser(
                content="Please help.",
                metadata={
                    "branch_decisions": [{"type": "noul", "probability": 0.9, "judge_response": response}],
                },
            )
        ],
    )

    summary = export_sample(monkeypatch, tmp_path, current)

    assert summary["actual_cost_usd"] == pytest.approx(0.2 + request_cost(DEFAULT_JUDGE_MODEL, 10))
    assert summary["unknown_calls_with_uncosted_usd"] == 0


def test_legacy_branch_decision_without_usage_marks_sample_unknown(monkeypatch, tmp_path):
    current = sample(
        metadata={},
        error=EvalError(message="partial sample", traceback="", traceback_ansi=""),
        messages=[
            ChatMessageUser(
                content="Please help.",
                metadata={
                    "branch_decisions": [
                        {"type": "noul", "probability": 0.9, "judge_response": {"model": DEFAULT_JUDGE_MODEL}}
                    ],
                },
            )
        ],
    )

    summary = export_sample(monkeypatch, tmp_path, current)

    assert summary["actual_cost_usd"] is None
    assert summary["actual_known_cost_usd"] == pytest.approx(0.2)
    assert summary["unknown_calls_with_uncosted_usd"] == 1


@pytest.mark.parametrize("input_tokens", [-1, float("inf")])
def test_legacy_branch_cost_must_be_finite_and_nonnegative(monkeypatch, tmp_path, input_tokens):
    current = sample(
        metadata={},
        error=EvalError(message="partial sample", traceback="", traceback_ansi=""),
        messages=[
            ChatMessageUser(
                content="Please help.",
                metadata={
                    "branch_decisions": [
                        {
                            "type": "noul",
                            "probability": 0.9,
                            "judge_response": {
                                "model": DEFAULT_JUDGE_MODEL,
                                "usage": {"input_tokens": input_tokens},
                            },
                        }
                    ]
                },
            )
        ],
    )

    summary = export_sample(monkeypatch, tmp_path, current)

    assert summary["actual_cost_usd"] is None
    assert summary["actual_known_cost_usd"] == pytest.approx(0.2)
    assert summary["unknown_calls_with_uncosted_usd"] == 1


def test_legacy_partial_branch_cost_keeps_known_spend_before_unknown(monkeypatch, tmp_path):
    current = sample(
        metadata={},
        error=EvalError(message="partial sample", traceback="", traceback_ansi=""),
        messages=[
            ChatMessageUser(
                content="Please help.",
                metadata={
                    "branch_decisions": [
                        {
                            "type": "noul",
                            "probability": 0.9,
                            "judge_response": {
                                "model": DEFAULT_JUDGE_MODEL,
                                "usage": {"input_tokens": 10},
                            },
                        }
                    ]
                },
            ),
            ChatMessageUser(
                content="Another turn.",
                metadata={
                    "branch_decisions": [
                        {
                            "type": "noul",
                            "probability": 0.9,
                            "judge_response": {"model": DEFAULT_JUDGE_MODEL},
                        }
                    ]
                },
            ),
        ],
    )

    summary = export_sample(monkeypatch, tmp_path, current)

    assert summary["actual_cost_usd"] is None
    assert summary["actual_known_cost_usd"] == pytest.approx(
        0.2 + request_cost(DEFAULT_JUDGE_MODEL, 10)
    )
    assert summary["unknown_calls_with_uncosted_usd"] == 1


def test_no_target_or_branch_call_before_dispatch_is_known_zero(monkeypatch, tmp_path):
    current = sample(
        metadata={},
        limit=EvalSampleLimit(type="cost", limit=0.01),
        messages=[],
        usage=False,
    )

    summary = export_sample(monkeypatch, tmp_path, current)

    assert summary["actual_cost_usd"] == 0
    assert summary["actual_known_cost_usd"] == 0
    assert summary["actual_cost_by_model_usd"] == {"mockllm/model": 0}
    assert summary["unknown_calls_with_uncosted_usd"] == 0


def test_repeated_epochs_are_refused(monkeypatch, tmp_path):
    second = sample()
    second.epoch = 2

    with pytest.raises(ValueError, match="repeated epochs are not supported"):
        export_sample(monkeypatch, tmp_path, [sample(), second])
