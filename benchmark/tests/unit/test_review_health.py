"""Health states for the review UI's optional active batch."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip(
    "flask",
    reason="scripts/review_ui/app.py's flask dep is script-local (PEP 723), not a project dependency",
)

from scripts.review_ui import app as review_app  # noqa: E402


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
    review_app.BATCH_PATH.write_text(json.dumps([{"card_id": "synthetic"}]), encoding="utf-8")

    response = health_client.get("/health")

    assert response.get_json() == {"cards": 1, "state": "active", "status": "ok"}


@pytest.mark.parametrize("contents", ["{\"cards\": []}", "[1]", "not json"])
def test_health_reports_malformed_batch_as_degraded(
    health_client: Any, contents: str
) -> None:
    review_app.BATCH_PATH.write_text(contents, encoding="utf-8")

    response = health_client.get("/health")

    assert response.get_json() == {"cards": 0, "state": "invalid", "status": "degraded"}
