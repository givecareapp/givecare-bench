"""CLI contracts: machine-readable output, artifact state, consent, and cost limits."""

import json
from pathlib import Path

import pytest

from invisiblebench import _agent_cli
from invisiblebench.cli import agent_commands, archive, runner
from invisiblebench.cli.run_command import run_benchmark


@pytest.fixture
def model():
    return {
        "id": "test/model",
        "name": "Test Model",
        "cost_per_m_input": 1.0,
        "cost_per_m_output": 1.0,
    }


@pytest.fixture
def noninteractive(monkeypatch):
    monkeypatch.setattr(_agent_cli, "is_tty", lambda: False)


@pytest.fixture
def runs(tmp_path, monkeypatch):
    directory = tmp_path / "results"
    for name in ["2026-01-01_00-00-00Z", "2026-01-02_00-00-00Z"]:
        run = directory / name
        run.mkdir(parents=True)
        (run / "run_manifest.json").write_text(json.dumps({"run_id": name}))
    monkeypatch.setattr(agent_commands, "_runs_dir", lambda: directory)
    return directory


@pytest.mark.parametrize("relative_path", ["runs.json", "nested/deeper/runs.json"])
def test_runs_export_writes_full_payload_and_one_summary(runs, tmp_path, capsys, relative_path):
    output = tmp_path / relative_path
    assert runner.main(["--json", "runs", "--out", str(output)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    envelope = json.loads(lines[0])
    assert (envelope["status"], envelope["command"]) == ("ok", "runs")
    assert envelope["data"]["path"] == str(output.resolve())
    assert envelope["data"]["record_count"] == 2
    assert envelope["data"]["byte_count"] == len(output.read_bytes())
    payload = json.loads(output.read_text())
    assert payload["total"] == len(payload["runs"]) == 2
    assert {row["id"] for row in payload["runs"]} == {path.name for path in runs.iterdir()}


@pytest.mark.parametrize(
    ("summary", "state", "scenarios"),
    [
        (None, "aborted_manifest_only", 0),
        (
            {"expected_transcripts": 1, "missing_count": 0, "status": "complete"},
            "transcripts_ready",
            1,
        ),
        (
            {"expected_transcripts": 2, "missing_count": 1, "status": "partial"},
            "transcripts_partial",
            1,
        ),
    ],
)
def test_runs_reports_artifact_state(tmp_path, monkeypatch, capsys, summary, state, scenarios):
    run = tmp_path / "2026-07-02_01-01-01Z"
    run.mkdir()
    (run / "run_manifest.json").write_text(json.dumps({"run_id": run.name}))
    if summary is not None:
        (run / "transcript_run.json").write_text(
            json.dumps(
                {
                    "artifact_type": "transcript_run/v1",
                    "model_ids": ["test/model"],
                    "transcript_count": 1,
                    "error_count": 0,
                    **summary,
                }
            )
        )
    monkeypatch.setattr(agent_commands, "_runs_dir", lambda: tmp_path)
    assert runner.main(["--json", "runs"]) == 0
    [record] = json.loads(capsys.readouterr().out)["data"]["runs"]
    assert record["id"] == run.name
    assert record["has_results"] is False
    assert (record["artifact_state"], record["scenarios"]) == (state, scenarios)


def test_runs_export_reports_filesystem_failure(runs, tmp_path, monkeypatch, capsys):
    def refuse_write(*args, **kwargs):
        raise PermissionError("read-only filesystem")

    monkeypatch.setattr(Path, "mkdir", refuse_write)
    assert runner.main(["--json", "runs", "--out", str(tmp_path / "out.json")]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    envelope = json.loads(lines[0])
    assert (envelope["status"], envelope["command"]) == ("error", "runs")
    assert "failed to write" in envelope["error"]


def test_benchmark_dry_run_creates_no_artifacts(tmp_path, model):
    output = tmp_path / "run"
    assert (
        run_benchmark(
            models=[model],
            output_dir=output,
            dry_run=True,
            auto_confirm=False,
            scenario_filter=["context_regulatory_data_privacy_001"],
        )
        == 0
    )
    assert not output.exists()


@pytest.mark.parametrize(("interactive", "exit_code"), [(False, 2), (True, 130)])
def test_benchmark_refuses_without_consent(
    tmp_path, monkeypatch, capsys, model, interactive, exit_code
):
    output = tmp_path / "run"
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(_agent_cli, "is_tty", lambda: interactive)
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    with pytest.raises(SystemExit) as exc:
        run_benchmark(
            models=[model],
            output_dir=output,
            dry_run=False,
            auto_confirm=False,
            max_cost_usd=1,
            scenario_filter=["context_regulatory_data_privacy_001"],
        )
    assert exc.value.code == exit_code
    if not interactive:
        assert "--yes" in capsys.readouterr().err
    assert not output.exists()


def test_benchmark_yes_never_prompts(tmp_path, monkeypatch, capsys, model, noninteractive):
    output = tmp_path / "run"
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    def refuse_prompt(prompt):
        pytest.fail("--yes prompted for consent")

    monkeypatch.setattr("builtins.input", refuse_prompt)
    assert (
        run_benchmark(
            models=[model],
            output_dir=output,
            dry_run=False,
            auto_confirm=True,
            max_cost_usd=1,
            scenario_filter=["context_regulatory_data_privacy_001"],
        )
        == 1
    )
    # The suite disables real target calls; consent must pass before client refusal.
    assert "Failed to initialize API client" in capsys.readouterr().out
    assert not output.exists()


@pytest.mark.parametrize(
    ("ceiling", "error"),
    [
        (None, "--max-cost-usd"),
        (0, "exceeds --max-cost-usd"),
        (1_000_000, "not a meaningful guardrail"),
    ],
)
def test_benchmark_rejects_unsafe_cost_ceiling(
    tmp_path, monkeypatch, capsys, model, ceiling, error
):
    output = tmp_path / "run"
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    assert (
        run_benchmark(
            models=[model],
            output_dir=output,
            dry_run=False,
            auto_confirm=True,
            max_cost_usd=ceiling,
            scenario_filter=["context_regulatory_data_privacy_001"],
        )
        == 2
    )
    assert error in capsys.readouterr().out
    assert not output.exists()


def test_full_and_selected_models_cannot_start_together(monkeypatch, capsys):
    from invisiblebench.cli import run_command

    def refuse_run(**kwargs):
        pytest.fail("conflicting model selection started a run")

    monkeypatch.setattr(run_command, "run_benchmark", refuse_run)
    assert runner.main(["--full", "-m", "openai/gpt-6-sol", "--dry-run"]) == 1
    assert "--full runs the whole roster" in capsys.readouterr().err


@pytest.mark.parametrize("arguments", [[], ["--before", "20200101", "--keep", "5", "--dry-run"]])
def test_archive_requires_one_selection_rule(capsys, arguments):
    assert runner.main(["archive", *arguments]) == 2
    assert "pass one of" in capsys.readouterr().err


@pytest.mark.parametrize(
    "arguments", [["--yes", "archive", "--keep", "5"], ["archive", "--keep", "5", "--yes"]]
)
def test_archive_accepts_explicit_consent(tmp_path, monkeypatch, noninteractive, arguments):
    monkeypatch.setattr(archive, "get_project_root", lambda: tmp_path)
    (tmp_path / "results").mkdir()
    assert runner.main(arguments) == 0


def test_archive_refuses_without_consent(tmp_path, monkeypatch, noninteractive):
    monkeypatch.setattr(archive, "get_project_root", lambda: tmp_path)
    (tmp_path / "results").mkdir()
    with pytest.raises(SystemExit) as exc:
        runner.main(["archive", "--keep", "5"])
    assert exc.value.code == 2


@pytest.mark.parametrize(
    ("keys", "missing"),
    [
        ({"OPENROUTER_API_KEY": "test-key", "TYPESAFE_API_KEY": "test-key"}, None),
        ({"OPENAI_API_KEY": "test-key", "TYPESAFE_API_KEY": "test-key"}, "Target"),
        ({"ANTHROPIC_API_KEY": "test-key", "TYPESAFE_API_KEY": "test-key"}, "Target"),
        ({"TYPESAFE_API_KEY": "test-key"}, "Target"),
        ({"OPENROUTER_API_KEY": "test-key"}, "Judge"),
    ],
)
def test_doctor_reports_required_keys(tmp_path, monkeypatch, capsys, keys, missing):
    for name in ["OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "TYPESAFE_API_KEY"]:
        monkeypatch.delenv(name, raising=False)
    for name, value in keys.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(agent_commands, "_runs_dir", lambda: tmp_path)
    assert runner.main(["--json", "doctor"]) == int(missing is not None)
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    envelope = json.loads(lines[0])
    assert (envelope["status"], envelope["command"]) == ("ok", "doctor")
    failed = [check for check in envelope["data"]["checks"] if not check["passed"]]
    assert envelope["data"]["failures"] == len(failed) == int(missing is not None)
    if missing:
        assert failed[0]["name"].startswith(missing)
    assert not (tmp_path / ".doctor_probe").exists()


@pytest.mark.parametrize("historical", [False, True])
def test_health_reports_missing_or_historical_results(tmp_path, monkeypatch, capsys, historical):
    from invisiblebench.cli import health

    if historical:
        directory = tmp_path / "data/leaderboard"
        directory.mkdir(parents=True)
        (directory / "leaderboard.json").write_text(
            json.dumps(
                {
                    "schema": "safety-care/v1",
                    "models": [{"model": "test-model"}],
                }
            )
        )
    monkeypatch.setattr(health, "get_project_root", lambda: tmp_path)
    assert runner.main(["--json", "health"]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    envelope = json.loads(lines[0])
    assert (envelope["status"], envelope["command"]) == ("ok", "health")
    assert envelope["data"]["current"] is False
    assert envelope["data"]["model_count"] == 0
    assert envelope["data"]["errors"]
    if historical:
        assert "historical" in envelope["data"]["errors"][0]


@pytest.mark.parametrize("export", [False, True])
def test_leaderboard_read_never_prompts(tmp_path, monkeypatch, capsys, noninteractive, export):
    payload = {"schema": "safety-care/v1", "models": []}
    (tmp_path / "data/leaderboard").mkdir(parents=True)
    (tmp_path / "data/leaderboard/leaderboard.json").write_text(json.dumps(payload))
    monkeypatch.setattr(
        "invisiblebench.utils.benchmark_inventory.get_project_root", lambda: tmp_path
    )

    def refuse_prompt(prompt):
        pytest.fail("read command prompted for consent")

    monkeypatch.setattr("builtins.input", refuse_prompt)
    output = tmp_path / "out.json"
    arguments = (
        ["leaderboard", "status", "--out", str(output)]
        if export
        else ["--json", "leaderboard", "status"]
    )
    assert runner.main(arguments) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    envelope = json.loads(lines[0])
    assert (envelope["status"], envelope["command"]) == ("ok", "leaderboard")
    if export:
        assert envelope["data"]["path"] == str(output.resolve())
        assert json.loads(output.read_text()) == payload
    else:
        assert envelope["data"] == payload


def test_judge_branched_generation_requires_a_judge_key(tmp_path, monkeypatch, capsys, model):
    output = tmp_path / "run"
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    assert (
        run_benchmark(
            models=[model],
            output_dir=output,
            dry_run=False,
            auto_confirm=True,
            max_cost_usd=1,
            scenario_filter=["tier1_crisis_cssrs_passive_001"],
        )
        == 1
    )
    assert "TYPESAFE_API_KEY" in capsys.readouterr().out
    assert not output.exists()
