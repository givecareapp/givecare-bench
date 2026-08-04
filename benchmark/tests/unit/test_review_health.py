"""Health states for the review UI's optional active batch."""

from __future__ import annotations

import json
from collections.abc import Iterator
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip(
    "flask",
    reason="scripts/review_ui/app.py's flask dep is script-local (PEP 723), not a project dependency",
)

from scripts.review_ui import app as review_app  # noqa: E402

_VALID_CARD = {
    "card_id": "scanreview_synthetic",
    "check_id": "crisis.synthetic",
    "scenario_id": "scenario_synthetic",
    "source_tags": [],
    "window_provenance": "publication-run",
    "check": {
        "id": "crisis.synthetic",
        "name": "synthetic check",
        "severity": "S5",
        "scope": "trigger",
        "pass_rule": "Assistant routes safely.",
        "fail_rule": "Assistant misses the cue.",
    },
    "transcript_window": "[Turn 1, USER]\nHelp.\n[Turn 1, ASSISTANT]\nI can help.",
    "turns": [
        {"turn": 1, "role": "user", "content": "Help."},
        {"turn": 1, "role": "assistant", "content": "I can help."},
    ],
    "cue": None,
}


@pytest.fixture
def health_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    batch_path = tmp_path / "review" / "batch.json"
    batch_path.parent.mkdir()
    monkeypatch.setattr(review_app, "BATCH_PATH", batch_path)
    with review_app.app.test_client() as client:
        yield client


def test_health_reports_missing_batch_as_healthy_idle(health_client: Any) -> None:
    response = health_client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"cards": 0, "state": "idle", "status": "ok"}


def test_health_reports_empty_batch_as_healthy_idle(health_client: Any) -> None:
    review_app.BATCH_PATH.write_text("[]", encoding="utf-8")

    response = health_client.get("/health")

    assert response.get_json() == {"cards": 0, "state": "idle", "status": "ok"}


def test_health_reports_valid_batch_as_healthy_active(health_client: Any) -> None:
    review_app.BATCH_PATH.write_text(json.dumps([_VALID_CARD]), encoding="utf-8")

    response = health_client.get("/health")

    assert response.get_json() == {"cards": 1, "state": "active", "status": "ok"}


def test_health_rejects_valid_card_with_boolean_turn(health_client: Any) -> None:
    card = deepcopy(_VALID_CARD)
    card["turns"][0]["turn"] = True
    review_app.BATCH_PATH.write_text(json.dumps([card]), encoding="utf-8")

    response = health_client.get("/health")

    assert response.get_json() == {"cards": 0, "state": "invalid", "status": "degraded"}


def test_health_rejects_valid_card_with_boolean_cue_turn(health_client: Any) -> None:
    card = deepcopy(_VALID_CARD)
    card["cue"] = {"cue_turn": True}
    review_app.BATCH_PATH.write_text(json.dumps([card]), encoding="utf-8")

    response = health_client.get("/health")

    assert response.get_json() == {"cards": 0, "state": "invalid", "status": "degraded"}


def test_health_rejects_valid_card_with_verdict(health_client: Any) -> None:
    card = deepcopy(_VALID_CARD)
    card["verdict"] = "PASS"
    review_app.BATCH_PATH.write_text(json.dumps([card]), encoding="utf-8")

    response = health_client.get("/health")

    assert response.get_json() == {"cards": 0, "state": "invalid", "status": "degraded"}


@pytest.mark.parametrize("contents", ["{\"cards\": []}", "[1]", "[{}]", "not json"])
def test_health_reports_malformed_batch_as_degraded(
    health_client: Any, contents: str
) -> None:
    review_app.BATCH_PATH.write_text(contents, encoding="utf-8")

    response = health_client.get("/health")

    assert response.get_json() == {"cards": 0, "state": "invalid", "status": "degraded"}


def test_health_reports_invalid_utf8_batch_as_degraded(health_client: Any) -> None:
    review_app.BATCH_PATH.write_bytes(b"[\xff]")

    response = health_client.get("/health")

    assert response.get_json() == {"cards": 0, "state": "invalid", "status": "degraded"}


def test_health_reports_integer_digit_cap_as_degraded(health_client: Any) -> None:
    review_app.BATCH_PATH.write_text("9" * 5000, encoding="utf-8")

    response = health_client.get("/health")

    assert response.get_json() == {"cards": 0, "state": "invalid", "status": "degraded"}


@pytest.mark.parametrize("forbidden_key", sorted(review_app.BANNED_LABEL_KEYS))
def test_health_rejects_every_exporter_forbidden_key(
    health_client: Any, forbidden_key: str
) -> None:
    card = deepcopy(_VALID_CARD)
    card[forbidden_key] = "forbidden"
    review_app.BATCH_PATH.write_text(json.dumps([card]), encoding="utf-8")

    response = health_client.get("/health")

    assert response.get_json() == {"cards": 0, "state": "invalid", "status": "degraded"}
