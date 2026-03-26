from __future__ import annotations

import json
from pathlib import Path

import pytest

from invisiblebench.adapters.givecare_live import GiveCareProvider, run_scenario


def test_send_message_raises_when_gc_returns_no_response(monkeypatch) -> None:
    provider = GiveCareProvider.__new__(GiveCareProvider)
    provider.wait_ms = 0
    provider.phone = "+15551234567"
    provider.deployment = "dev"

    outputs = iter([
        "simulate output without a Mira response",
        "still no Mira response here either",
    ])
    monkeypatch.setattr(provider, "_run_gc", lambda _args: next(outputs))

    with pytest.raises(RuntimeError, match="no response"):
        provider.send_message("hello")


def test_run_scenario_fails_closed_on_transport_error(tmp_path: Path) -> None:
    scenario_path = tmp_path / "scenario.json"
    scenario_path.write_text(
        json.dumps(
            {
                "scenario_id": "test_live_error",
                "title": "Live transport error",
                "turns": [
                    {
                        "turn_number": 1,
                        "user_message": "hello",
                    }
                ],
            }
        )
    )

    class StubProvider:
        phone = "+15551234567"

        def reset(self) -> None:
            return None

        def send_message(self, _message: str) -> str:
            raise RuntimeError("gc CLI simulate failed")

    transcripts_dir = tmp_path / "transcripts"
    with pytest.raises(RuntimeError, match="Turn 1"):
        run_scenario(StubProvider(), str(scenario_path), transcripts_dir)

    transcript_path = transcripts_dir / "givecare_test_live_error.jsonl"
    assert transcript_path.exists()

    rows = [json.loads(line) for line in transcript_path.read_text().splitlines()]
    assert rows[-1]["error"] is True
    assert "gc CLI simulate failed" in rows[-1]["content"]
