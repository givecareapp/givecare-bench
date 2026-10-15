"""CLI contracts: machine-readable output, artifact state, consent, and cost limits."""

import json
from pathlib import Path

import pytest

from invisiblebench.cli import agent_commands, runner


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
def test_leaderboard_read_never_prompts(tmp_path, monkeypatch, capsys, export):
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


