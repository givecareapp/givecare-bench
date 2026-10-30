import json
import socket
import subprocess
from glob import glob
from pathlib import Path

import pytest
from inspect_ai import Task
from inspect_ai.log import read_eval_log
from inspect_ai.model import ModelCost, ModelInfo, set_model_info
from inspect_ai.solver import solver

import run
from grader import control_samples
from run import main
from task import ROOT, conversation_family

PAID = "openrouter/example"  # no registered price
PAID_PRICED = "openrouter/anthropic/claude-haiku-5.5"  # priced by task.OPENROUTER_PRICES
# Inspect has no call to unregister a price. A name no other test uses keeps this one out of
# every run that uses mockllm/model, so those runs keep reporting no cost.
PRICED = "mockllm/run-priced"
set_model_info(
    PRICED,
    ModelInfo(cost=ModelCost(input=1.0, output=2.0, input_cache_write=1.0, input_cache_read=0.1)),
)


class EvalCalled(Exception):
    pass


def _args(out, *extra, targets=("mockllm/model",), judge="mockllm/model", family="backup_care"):
    args = ["--out", str(out), "--family", family, "--judge", judge]
    for target in targets:
        args += ["--target", target]
    return [*args, *extra]


def _record_git_revision(monkeypatch):
    # Inspect skips git while pytest runs, so a mock log has no native revision. Call this
    # inside the test body: pytest sets the variable again at the start of each phase.
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)


def _forbid_eval(monkeypatch):
    """Any evaluation or network connection fails the test; a request that passes raises."""

    def evaluation(*args, **kwargs):
        raise EvalCalled

    def connection(*args, **kwargs):
        raise AssertionError("A refused request must not touch the network")

    monkeypatch.setattr(run, "inspect_eval", evaluation)
    monkeypatch.setattr(socket.socket, "connect", connection)


def _refused(argv, capsys):
    with pytest.raises(SystemExit) as refused:
        main(argv)
    assert refused.value.code == 2
    return capsys.readouterr().err


def _record(out):
    return json.loads((out / "run.json").read_text())


def test_mock_run_derives_its_record_from_the_saved_logs(tmp_path, monkeypatch, capsys):
    _record_git_revision(monkeypatch)
    monkeypatch.chdir(ROOT)
    out = tmp_path / "run"
    assert main(_args(out, "--purpose", "plumbing check")) == 0

    # Nothing but the logs, their reports, and the one record.
    assert sorted(p.name for p in out.iterdir()) == ["generation", "judge", "reports", "run.json"]
    [generation] = glob(str(out / "generation/backup_care/*.eval"))
    [judged] = glob(str(out / "judge/*.eval"))
    record = _record(out)
    assert record["args"]["purpose"] == "plumbing check"
    assert record["args"]["family"] == ["backup_care"]
    assert record["args"]["max_tokens"] == 2048
    assert record["stop_reason"] is None
    assert [entry["task"] for entry in record["logs"]] == ["conversation_family", "target_judge"]

    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()
    for entry, path in zip(record["logs"], (generation, judged), strict=True):
        saved = read_eval_log(path)
        assert Path(entry["location"]).resolve() == Path(path).resolve()
        assert entry["eval_id"] == saved.eval.eval_id
        assert entry["status"] == saved.status == "success"
        assert entry["family"] == "backup_care" and entry["model"] == "mockllm/model"
        assert entry["samples"] == len(saved.samples) and entry["errors"] == 0
        assert entry["revision"] == {"origin": saved.eval.revision.origin, "commit": head,
                                     "dirty": saved.eval.revision.dirty}
        assert isinstance(entry["revision"]["dirty"], bool)
        assert entry["model_usage"] == {
            name: usage.model_dump(mode="json") for name, usage in saved.stats.model_usage.items()}
        assert entry["model_usage"]["mockllm/model"]["total_cost"] is None
    assert [entry["samples"] for entry in record["logs"]][0] == 3
    # A mock model reports no cost; the record says unknown, not zero.
    assert record["reported_cost_usd"] == 0 and record["unknown_cost_logs"] == 2
    assert read_eval_log(generation, header_only=True).plan.config.max_tokens == 2048

    stem = Path(judged).stem
    assert sorted(p.name for p in (out / "reports").iterdir()) == [f"{stem}.json", f"{stem}.md"]
    report = json.loads((out / "reports" / f"{stem}.json").read_text())
    assert report["kind"] == "target-judging-audit"
    assert report["run"]["eval_id"] == record["logs"][1]["eval_id"]
    # The mock judge answers with non-JSON text, so every verdict is unscored, not a pass.
    assert len(report["trials"]) == record["logs"][1]["samples"]
    assert all(t["verdict"] is None and t["unscored_reason"] for t in report["trials"])
    counts = [c for layer in report["summary"]["by_layer"].values() for c in layer.values()]
    assert sum(c["unscored"] for c in counts) == len(report["trials"])
    assert not any(c["PASS"] or c["FAIL"] or c["UNCLEAR"] or c["NOT_APPLICABLE"] for c in counts)
    text = (out / "reports" / f"{stem}.md").read_text()
    assert "| Unscored |" in text and "No recorded FAIL or UNCLEAR verdicts" in text

    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "GEN backup_care mockllm/model success 3 samples 0 errors"
    assert lines[1].startswith("JUDGE backup_care mockllm/model success ")
    assert lines[-1] == "DONE reported cost $0.0000; 2 of 2 logs report no cost"


def test_controls_flag_judges_the_authored_controls_first_and_reports_them(tmp_path, capsys):
    out = tmp_path / "run"
    assert main(_args(out, "--controls")) == 0
    [control] = glob(str(out / "controls/*.eval"))
    lines = capsys.readouterr().out.splitlines()
    planned = len(control_samples("backup_care"))
    assert lines[0] == f"CTRL backup_care mockllm/model success {planned} samples 0 errors"
    assert lines[1].startswith("GEN backup_care ")
    assert [e["task"] for e in _record(out)["logs"]] == [
        "control_judge", "conversation_family", "target_judge"]
    stem = Path(control).stem
    report = json.loads((out / "reports" / f"{stem}.json").read_text())
    assert report["kind"] == "judge-development-audit"
    assert report["run"]["eval_id"] == read_eval_log(control, header_only=True).eval.eval_id
    assert (out / "reports" / f"{stem}.md").read_text().startswith(
        "# InvisibleBench evaluation report")


def test_dirty_case_file_refuses_before_any_eval(tmp_path, monkeypatch, capsys):
    _forbid_eval(monkeypatch)
    out = tmp_path / "run"
    rubric = ROOT / "cases/backup_care/rubric.json"
    original = rubric.read_bytes()
    try:
        rubric.write_bytes(original + b"\n")
        error = _refused(_args(out), capsys)
    finally:
        rubric.write_bytes(original)
    assert "Commit before judging" in error and "cases/backup_care/rubric.json" in error
    assert not out.exists()


@pytest.mark.parametrize("targets, judge", [((PAID,), "mockllm/model"), (("mockllm/model",), PAID)])
@pytest.mark.parametrize("flags", [[], ["--ceiling-usd", "1"], ["--judge-cost-limit-usd", "0.05"]])
def test_paid_model_without_both_cost_flags_refuses_before_any_eval(
    tmp_path, monkeypatch, capsys, targets, judge, flags
):
    _forbid_eval(monkeypatch)
    out = tmp_path / "run"
    error = _refused(_args(out, *flags, targets=targets, judge=judge), capsys)
    assert "--judge-cost-limit-usd and --ceiling-usd" in error and PAID in error
    assert not out.exists()


def test_priced_paid_model_with_both_cost_flags_passes_the_gate(tmp_path, monkeypatch):
    _forbid_eval(monkeypatch)
    flags = ["--ceiling-usd", "1", "--judge-cost-limit-usd", "0.05"]
    with pytest.raises(EvalCalled):
        main(_args(tmp_path / "run", *flags, targets=(PAID_PRICED,)))


@pytest.mark.parametrize("targets, judge", [((PAID,), "mockllm/model"), ((PAID_PRICED,), PAID)])
def test_unpriced_paid_model_refuses_before_any_eval(tmp_path, monkeypatch, capsys, targets, judge):
    # Inspect aborts an eval whose cost limit needs a price it lacks, and an unpriced target
    # cannot be counted against the ceiling; both are refused before anything is spent.
    _forbid_eval(monkeypatch)
    out = tmp_path / "run"
    flags = ["--ceiling-usd", "1", "--judge-cost-limit-usd", "0.05"]
    error = _refused(_args(out, *flags, targets=targets, judge=judge), capsys)
    assert "No registered price" in error and PAID in error and "OPENROUTER_PRICES" in error
    assert not out.exists()


def test_a_failure_mid_run_still_writes_run_json_then_raises(tmp_path, monkeypatch, capsys):
    calls = []

    def failing(*args, **kwargs):
        calls.append(kwargs.get("log_dir"))
        raise RuntimeError("Deliberate provider outage")

    monkeypatch.setattr(run, "inspect_eval", failing)
    out = tmp_path / "run"
    with pytest.raises(RuntimeError, match="Deliberate provider outage"):
        main(_args(out))
    assert len(calls) == 1
    record = _record(out)
    assert record["stop_reason"].startswith("error: RuntimeError('Deliberate provider outage')")
    assert record["logs"] == [] and record["reported_cost_usd"] == 0.0
    assert "STOPPED error: RuntimeError" in capsys.readouterr().out


def test_non_empty_out_refuses_and_an_empty_one_is_accepted(tmp_path, monkeypatch, capsys):
    _forbid_eval(monkeypatch)
    out = tmp_path / "run"
    out.mkdir()
    (out / "earlier.txt").write_text("an earlier run")
    assert "new or empty" in _refused(_args(out), capsys)
    assert [p.name for p in out.iterdir()] == ["earlier.txt"]
    (out / "earlier.txt").unlink()
    with pytest.raises(EvalCalled):
        main(_args(out))


@pytest.mark.parametrize("kwargs, extra, message", [
    ({"family": "no_such_family"}, [], "Unknown family 'no_such_family'; known families"),
    ({}, ["--target-max-tokens", "mockllm/other=64"], "names models that are not a --target"),
    ({"targets": ()}, [], "Nothing to run"),
    ({}, ["--target-max-tokens", "64"], "expected MODEL=N"),
    ({}, ["--target-max-tokens", "mockllm/model=0"], "must be finite and positive"),
    ({}, ["--epochs", "0"], "must be finite and positive"),
    ({}, ["--ceiling-usd", "nan"], "must be finite and positive"),
])
def test_other_bad_requests_refuse_before_any_eval(
    tmp_path, monkeypatch, capsys, kwargs, extra, message
):
    _forbid_eval(monkeypatch)
    out = tmp_path / "run"
    assert message in _refused(_args(out, *extra, **kwargs), capsys)
    assert not out.exists()


def test_target_max_tokens_reaches_each_targets_generation_plan(tmp_path):
    out = tmp_path / "run"
    argv = _args(out, "--max-tokens", "128", "--target-max-tokens", "mockllm/model=64",
                 targets=("mockllm/model", "mockllm/other"))
    assert main(argv) == 0
    assert _record(out)["args"]["target_max_tokens"] == {"mockllm/model": 64}
    plans = {}
    for path in glob(str(out / "generation/backup_care/*.eval")):
        saved = read_eval_log(path, header_only=True)
        plans[saved.eval.model] = saved.plan.config.max_tokens
    assert plans == {"mockllm/model": 64, "mockllm/other": 128}


def test_ceiling_stops_before_the_next_evaluation_and_records_why(tmp_path, capsys):
    out = tmp_path / "run"
    assert main(_args(out, "--ceiling-usd", "0.001", targets=(PRICED,))) == 1

    record = _record(out)
    [generation] = record["logs"]
    cost = generation["model_usage"][PRICED]["total_cost"]
    assert generation["task"] == "conversation_family" and cost > 0.001
    assert record["reported_cost_usd"] == pytest.approx(cost)
    assert record["unknown_cost_logs"] == 0
    reason = f"reported cost ${cost:.4f} exceeds ceiling $0.0010 before JUDGE backup_care {PRICED}"
    assert record["stop_reason"] == reason
    assert capsys.readouterr().out.splitlines()[-1] == f"STOPPED {reason}; 0 of 1 logs report no cost"
    # The judge never started, so there is no judge log and no report.
    assert sorted(p.name for p in out.iterdir()) == ["generation", "run.json"]


def test_run_under_the_ceiling_completes_and_counts_an_unpriced_log_as_unknown(tmp_path):
    out = tmp_path / "run"
    assert main(_args(out, "--ceiling-usd", "1", targets=(PRICED,))) == 0
    record = _record(out)
    generation, judged = record["logs"]
    assert record["stop_reason"] is None
    assert record["reported_cost_usd"] == pytest.approx(
        generation["model_usage"][PRICED]["total_cost"])
    assert judged["model_usage"]["mockllm/model"]["total_cost"] is None
    assert record["unknown_cost_logs"] == 1


def test_a_log_with_no_judgeable_samples_is_reported_and_skipped(tmp_path, monkeypatch, capsys):
    @solver
    def provider_down():
        async def solve(state, generate):
            raise RuntimeError("Deliberate provider outage before any reply")

        return solve

    def failing_generation(family):
        healthy = conversation_family(family)
        return Task(dataset=healthy.dataset, solver=provider_down(), scorer=None,
                    config=healthy.config, metadata=healthy.metadata)

    monkeypatch.setattr(run, "conversation_family", failing_generation)
    out = tmp_path / "run"
    assert main(_args(out)) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "GEN backup_care mockllm/model success 3 samples 3 errors"
    assert lines[1] == "SKIP backup_care mockllm/model no judgeable samples"
    assert lines[2].startswith("DONE ")
    [generation] = _record(out)["logs"]
    assert generation["samples"] == generation["errors"] == 3
    assert sorted(p.name for p in out.iterdir()) == ["generation", "run.json"]


def test_help_runs_as_a_script_from_a_clone():
    result = subprocess.run(["uv", "run", "--locked", "python", "run.py", "--help"],
                            cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stderr
    assert "--ceiling-usd" in result.stdout
