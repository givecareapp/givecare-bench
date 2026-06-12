from __future__ import annotations

import json
from pathlib import Path

import pytest

from invisiblebench.adapters.givecare_v2 import (
    GiveCareV2Provider,
    get_category_from_path,
    run_scenario,
)


def test_provider_posts_admin_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    class Response:
        status_code = 200

        @staticmethod
        def json() -> dict[str, object]:
            return {"ok": True, "result": {"replyText": "One next step."}}

        text = ""

    def post(url: str, **kwargs: object) -> Response:
        calls.append({"url": url, **kwargs})
        return Response()

    monkeypatch.setattr("invisiblebench.adapters.givecare_v2.requests.post", post)
    provider = GiveCareV2Provider(site_url="https://sms.example", admin_key="secret")

    reply = provider.run_turn(
        scenario_id="scenario-a",
        user_message="hello",
        previous_messages=[{"role": "assistant", "text": "Hi"}],
    )

    assert reply == "One next step."
    assert calls[0]["url"] == "https://sms.example/api/admin"
    assert calls[0]["json"] == {
        "action": "runBenchmarkTurn",
        "scenarioId": "scenario-a",
        "userMessage": "hello",
        "previousMessages": [{"role": "assistant", "text": "Hi"}],
    }
    assert calls[0]["headers"] == {"Authorization": "Bearer secret"}


def test_get_category_from_path_uses_private_confidential_dir(tmp_path: Path, monkeypatch) -> None:
    confidential_dir = tmp_path / "private_confidential"
    confidential_dir.mkdir()
    scenario_path = confidential_dir / "holdout.json"
    monkeypatch.setenv(
        "INVISIBLEBENCH_PRIVATE_CONFIDENTIAL_SCENARIOS_DIR",
        str(confidential_dir),
    )

    assert get_category_from_path(scenario_path) == "confidential"


def test_run_scenario_writes_transcript_with_history(tmp_path: Path) -> None:
    scenario_path = tmp_path / "scenario.json"
    scenario_path.write_text(
        json.dumps(
            {
                "scenario_id": "test_v2",
                "title": "V2 contract",
                "turns": [
                    {"turn_number": 1, "user_message": "hello"},
                    {"turn_number": 2, "user_message": "thanks"},
                ],
            }
        )
    )

    class StubProvider:
        def __init__(self) -> None:
            self.history_lengths: list[int] = []

        def run_turn(self, *, scenario_id: str, user_message: str, previous_messages):
            assert scenario_id == "test_v2"
            self.history_lengths.append(len(previous_messages))
            return f"reply to {user_message}"

    provider = StubProvider()
    transcript_path, _scenario = run_scenario(provider, str(scenario_path), tmp_path)

    assert transcript_path == tmp_path / "givecare_v2_test_v2.jsonl"
    assert provider.history_lengths == [0, 2]
    rows = [json.loads(line) for line in transcript_path.read_text().splitlines()]
    assert [row["role"] for row in rows] == ["user", "assistant", "user", "assistant"]
    assert rows[-1]["content"] == "reply to thanks"


def test_run_givecare_eval_zero_inline_rows_emits_deprecation_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """When transcripts were generated but inline result rows are 0, the printer
    must NOT print the misleading zero-row summary or BLOCK audit line.  Instead
    it must emit the deprecation hint pointing at the RUN DIR (not transcripts/).
    Return code must be 0.
    """
    from invisiblebench.cli.run_command import run_givecare_eval

    # Stub the scenario list to one fake scenario so we get past the early-exit.
    fake_scenario = tmp_path / "safety" / "scenario_a.json"
    fake_scenario.parent.mkdir(parents=True)
    fake_scenario.write_text(
        json.dumps(
            {
                "scenario_id": "scenario_a",
                "title": "Fake scenario",
                "turns": [{"turn_number": 1, "user_message": "hi"}],
            }
        )
    )

    monkeypatch.setattr(
        "invisiblebench.cli.run_command.get_givecare_scenarios",
        lambda *a, **kw: [fake_scenario],
    )

    # Stub provider: healthcheck passes, run_turn returns a reply so one
    # transcript is written, but no inline result rows are produced (the normal
    # V2-harness path after inline scoring was removed).
    class _StubProvider:
        def healthcheck(self):
            return {"ok": True}

        def run_turn(self, *, scenario_id, user_message, previous_messages):
            return "stub reply"

        def close(self):
            pass

    monkeypatch.setattr(
        "invisiblebench.cli.run_command.GiveCareV2Provider",
        lambda: _StubProvider(),
    )
    # run_givecare_v2_scenario writes a real transcript file and returns the path.
    # We stub it to create a minimal JSONL file and return (path, scenario_data).
    def _stub_run_scenario(provider, scenario_path_str, transcripts_dir, *, verbose=False):
        td = Path(transcripts_dir)
        td.mkdir(parents=True, exist_ok=True)
        t = td / "givecare_v2_scenario_a.jsonl"
        t.write_text(
            json.dumps({"role": "user", "content": "hi"}) + "\n"
            + json.dumps({"role": "assistant", "content": "stub reply"}) + "\n"
        )
        return t, {"scenario_id": "scenario_a", "title": "Fake scenario", "turns": []}

    monkeypatch.setattr(
        "invisiblebench.cli.run_command.run_givecare_v2_scenario",
        _stub_run_scenario,
    )

    rc = run_givecare_eval(
        output_dir=tmp_path / "run_out",
        auto_confirm=True,
        verbose=False,
    )

    captured = capsys.readouterr()
    out = captured.out

    assert rc == 0, f"Expected return code 0, got {rc}"
    # Deprecation hint must be present and point at the run dir (not transcripts/).
    assert "inline V2 scoring is deprecated" in out
    assert "scripts/run_scan.py" in out
    run_dir_str = str(tmp_path / "run_out")
    assert run_dir_str in out
    transcripts_dir_str = str(tmp_path / "run_out" / "transcripts")
    assert transcripts_dir_str not in out, (
        "Hint must point at run dir, not the transcripts/ subdir"
    )
    # The old misleading zero-row block must NOT appear.
    assert "GiveCare V2 Eval Results" not in out
    assert "Scenarios: 0" not in out
    assert "Audit: BLOCK" not in out
