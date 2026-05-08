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
