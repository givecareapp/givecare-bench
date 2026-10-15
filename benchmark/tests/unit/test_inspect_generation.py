"""Generation runs through Inspect; the export is byte-compatible with the judge's input."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from inspect_ai import eval as inspect_eval
from inspect_ai.log import EvalRevision, read_eval_log, write_eval_log
from inspect_ai.model import (
    ModelCost,
    ModelInfo,
    ModelOutput,
    get_model,
    get_model_info,
    set_model_cost,
    set_model_info,
)

from benchmark.tests.fixtures.current_scan import FixtureJudge, judge_response
from invisiblebench import inspect_task
from invisiblebench.cli import runner
from invisiblebench.inspect_export import export_run
from invisiblebench.inspect_task import safety_care, serving_policy
from invisiblebench.judge import (
    _conversations,
    _public_scenarios,
    _transcript,
    plan_scan,
    verify_execution,
)
from invisiblebench.models.config import MODELS_FULL

PROVIDER = serving_policy({})["provider"]
NOUL = "tier1_crisis_cssrs_passive_001"
KEYWORD = "tier1_crisis_cssrs_passive_001__religious_frame"


def reply(text: str, stop: str = "stop") -> ModelOutput:
    output = ModelOutput.from_content(model="mockllm/model", content=text)
    output.choices[0].stop_reason = stop  # type: ignore[assignment]
    return output


def generate(tmp_path: Path, outputs, *, scenario=NOUL, provider=PROVIDER, **options):
    model = get_model("mockllm/model", custom_outputs=outputs, provider=provider)
    [log] = inspect_eval(
        safety_care(scenario=scenario),
        model=model,
        log_dir=str(tmp_path / "inspect"),
        display="none",
        **options,
    )
    assert log.status == "success", log.error
    return stamp(Path(log.location))


def stamp(path: Path, commit: str | None = None, dirty: bool = False) -> Path:
    """Inspect records no git revision under pytest; stamp one the way it would."""
    log = read_eval_log(str(path))
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    log.eval.revision = EvalRevision(type="git", origin="x", commit=commit or head, dirty=dirty)
    write_eval_log(log, str(path))
    return path


def transcripts(run: Path) -> dict[str, list[dict]]:
    return {
        path.name: [json.loads(line) for line in path.read_text().splitlines()]
        for path in sorted((run / "transcripts").glob("*.jsonl"))
    }


@pytest.fixture
def fake_judge(monkeypatch):
    class Judge(FixtureJudge):
        closed = False

        def ask(self, *, model, state, questions):
            return judge_response(model, dict.fromkeys(questions, 0.9), 5)

        def close(self):
            Judge.closed = True

    monkeypatch.setattr(inspect_task, "_judge_client", Judge)
    return Judge


def test_branched_scenarios_export_a_bundle_the_judge_accepts(tmp_path, fake_judge):
    counter = iter(range(1, 1000))
    log = generate(
        tmp_path,
        lambda *_: reply(f"Reply {next(counter)}. Please consider a therapist."),
        scenario="cssrs_passive_ideation",
    )
    run = export_run([log], tmp_path / "run")
    summary = json.loads((run / "transcript_run.json").read_text())
    manifest = json.loads((run / "run_manifest.json").read_text())
    count = len(transcripts(run))
    assert count >= 2
    assert (summary["status"], summary["transcript_count"], summary["error_count"]) == (
        "complete",
        count,
        0,
    )
    assert manifest["schema"] == "invisiblebench-run-manifest/v3"
    assert (manifest["harness"], manifest["mode"]) == ("llm", "raw")
    assert manifest["model_ids"] == ["mockllm/model"]
    assert manifest["transcript_policy"]["backend"] == "inspect_ai/openrouter"
    assert fake_judge.closed

    scenarios = _public_scenarios()
    for name, entries in transcripts(run).items():
        scenario_id = name.removesuffix(".jsonl").split("_", 1)[1]
        verify_execution(_transcript(("\n".join(map(json.dumps, entries))).encode()), scenarios[scenario_id], "mockllm/model")
    noul = transcripts(run)[f"mockllm%2Fmodel_{NOUL}.jsonl"]
    branched = next(e for e in noul if e["role"] == "user" and e.get("branch_id"))
    assert branched["branch_id"] == "missed_passive_ideation"
    assert branched["branch_decisions"][0]["judge_response"]["usage"]["input_tokens"] == 5
    keyword = transcripts(run)[f"mockllm%2Fmodel_{KEYWORD}.jsonl"]
    assert [e["turn"] for e in keyword if e["role"] == "assistant"] == [1, 2, 3, 4, 5]

    plan = plan_scan([run], tmp_path / "scan")
    assert len(plan.transcripts) == len(_conversations(tmp_path / "scan", plan)) == count


def test_truncation_and_empty_replies_are_recorded(tmp_path):
    script = iter(
        [
            reply("Cut off", "max_tokens"),
            reply("   "),
            reply(""),
            reply("Finally a reply."),
        ]
    )
    log = generate(tmp_path, lambda *_: next(script, reply("Steady reply.")), scenario=KEYWORD)
    run = export_run([log], tmp_path / "run")
    entries = next(iter(transcripts(run).values()))
    first, second = [e for e in entries if e["role"] == "assistant"][:2]
    assert first["truncated"] is True and "empty_response_attempts" not in first
    assert second["content"] == "Finally a reply."
    assert second["empty_response_attempts"] == 3 and "truncated" not in second


def test_three_empty_replies_leave_the_sample_failed(tmp_path):
    model = get_model("mockllm/model", custom_outputs=lambda *_: reply(""), provider=PROVIDER)
    [log] = inspect_eval(
        safety_care(scenario=KEYWORD), model=model, log_dir=str(tmp_path / "inspect"), display="none"
    )
    assert log.status == "error"
    run = export_run([stamp(Path(log.location))], tmp_path / "run")
    summary = json.loads((run / "transcript_run.json").read_text())
    assert summary["status"] == "partial"
    assert summary["transcript_count"] == 0 and summary["error_count"] == 1
    assert "empty responses" in summary["errors"][0]["reason"]


def test_export_takes_git_state_from_the_log_revision(tmp_path):
    log_path = generate(tmp_path, lambda *_: reply("Support."), scenario=KEYWORD)
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    # Inspect logs an abbreviated commit and a dirty flag; the manifest keeps both facts.
    stamp(log_path, head[:7], dirty=True)
    manifest = json.loads((export_run([log_path], tmp_path / "run") / "run_manifest.json").read_text())
    assert (manifest["git_sha"], manifest["git_dirty"]) == (head, True)
    assert manifest["run_date"] == read_eval_log(str(log_path)).eval.created

    log = read_eval_log(str(log_path))
    log.eval.revision = None
    write_eval_log(log, str(log_path))
    with pytest.raises(ValueError, match="git revision"):
        export_run([log_path], tmp_path / "other")
    stamp(log_path, "f" * 40)
    with pytest.raises(ValueError, match="not in this checkout"):
        export_run([log_path], tmp_path / "other")


def test_export_refuses_logs_without_the_roster_serving_policy(tmp_path):
    log_path = generate(tmp_path, lambda *_: reply("Support."), scenario=KEYWORD, provider=None)
    with pytest.raises(ValueError, match="allow_fallbacks"):
        export_run([log_path], tmp_path / "run")


def test_export_records_pinned_provider_and_priced_cost(tmp_path):
    set_model_info("mockllm/model", ModelInfo())
    set_model_cost(
        "mockllm/model",
        ModelCost(input=1.0, output=2.0, input_cache_write=1.0, input_cache_read=1.0),
    )
    pinned = {"allow_fallbacks": False, "require_parameters": True, "only": ["acme"]}
    log_path = generate(tmp_path, lambda *_: reply("Support."), scenario=KEYWORD, provider=pinned)
    run = export_run([log_path], tmp_path / "run")
    manifest = json.loads((run / "run_manifest.json").read_text())
    assert manifest["transcript_policy"]["serving"]["mockllm/model"] == serving_policy(
        {"endpoint": "acme"}
    )
    summary = json.loads((run / "transcript_run.json").read_text())
    assert summary["actual_cost_usd"] == pytest.approx(summary["actual_known_cost_usd"])
    assert summary["actual_cost_usd"] > 0 and summary["unknown_calls_with_uncosted_usd"] == 0


def test_unpriced_generation_is_unknown_not_zero(tmp_path):
    set_model_info("mockllm/model", ModelInfo())  # no cost configured
    from inspect_ai.model import _model_info

    _model_info._custom_models["mockllm/model"] = ModelInfo()
    log_path = generate(tmp_path, lambda *_: reply("Support."), scenario=KEYWORD)
    summary = json.loads((export_run([log_path], tmp_path / "run") / "transcript_run.json").read_text())
    assert summary["actual_cost_usd"] is None
    assert summary["unknown_calls_with_uncosted_usd"] == 1


def test_export_command_writes_a_run_and_hints_the_scan(tmp_path, capsys):
    log_path = generate(tmp_path, lambda *_: reply("Support."), scenario=KEYWORD)
    output = tmp_path / "run"
    assert runner.main(["export", str(log_path), "--output", str(output)]) == 0
    assert "bench scan plan" in capsys.readouterr().out
    assert runner.main(["export", str(log_path), "--output", str(output)]) == 1


def test_every_roster_model_is_priced_for_inspect():
    inspect_task.register_roster_prices()
    for model in MODELS_FULL:
        cost = get_model_info(f"openrouter/{model.id}").cost
        assert (cost.input, cost.output) == (model.cost_per_m_input, model.cost_per_m_output)


def test_multisession_system_prompt_and_metadata(tmp_path):
    seen: list[str] = []

    def record(input, *_):
        seen.append(input[0].text)
        return reply("Support.")

    scenario = next(
        s for s in inspect_task.get_scenarios(category=["continuity"]) if _sessions(s["path"])
    )
    log_path = generate(tmp_path, record, scenario=scenario["scenario_id"])
    entries = next(iter(transcripts(export_run([log_path], tmp_path / "run")).values()))
    assert {e["session_number"] for e in entries} >= {1, 2}
    assert any("Current scripted session: Session 2" in prompt for prompt in seen)
    assert seen[0].startswith(inspect_task.SYSTEM_PROMPT)


def _sessions(path: str) -> bool:
    return len(json.loads(Path(path).read_text()).get("sessions") or []) > 1


def test_scenario_selection_filters_and_confidential(tmp_path, monkeypatch):
    private = tmp_path / "private_confidential"
    private.mkdir()
    (private / "holdout.json").write_text(json.dumps({"scenario_id": "conf_holdout_001", "turns": []}))
    monkeypatch.setenv("INVISIBLEBENCH_PRIVATE_CONFIDENTIAL_SCENARIOS_DIR", str(private))
    held = inspect_task.get_scenarios(include_confidential=True)
    assert any(s["category"] == "confidential" and s["scenario_id"] == "conf_holdout_001" for s in held)
    assert not any(s["category"] == "confidential" for s in inspect_task.get_scenarios())

    scenario = {
        "path": "benchmark/scenarios/context/regulatory/data_privacy_inquiry.json",
        "name": "Data Privacy Inquiry",
        "scenario_id": "context_regulatory_data_privacy_001",
    }
    match = inspect_task._scenario_matches_filter
    assert match(scenario, "data_privacy") and match(scenario, "dataprivacy")
    assert match(scenario, "privacy inquiry") and not match(scenario, "scope_honesty")
    assert [s["category"] for s in inspect_task.get_scenarios(category=["safety"])] == [
        "safety"
    ] * len(inspect_task.get_scenarios(category=["safety"]))
    with pytest.raises(ValueError, match="No scenarios"):
        safety_care(scenario="no-such-scenario")
