"""Batch hash-freeze pin for the gold-card review server.

``scripts/review_ui/app.py`` resolves a reviewer's per-card position against a
shuffle order computed from ``batch.json`` (see ``reviewer_order``). If
``batch.json`` is swapped mid-session (a re-export overwriting the file a
reviewer already has a live session against), a stale ``pos`` from the client
would resolve against a *different* shuffled order and silently write the
verdict against the wrong card. ``assert_batch_frozen()`` closes this: it
hashes ``batch.json`` on first read this process and pins it, aborting 409 on
any later mismatch — called at the start of ``save`` (before any write) and
``admin_export``.

This module is hermetic: synthetic cards only (no real gold-card text), a temp
``REVIEW_DIR``/``batch.json``/``reviews.db`` per test, and an explicit reset of
the module-global ``_BATCH_SHA`` so state never bleeds across tests or across
this file and the sibling review test modules (all share one imported
``scripts.review_ui.app`` module object within a test run).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest

pytest.importorskip("flask", reason="scripts/review_ui/app.py's flask dep is script-local (PEP 723), not a project dependency")

from werkzeug.exceptions import HTTPException  # noqa: E402

from scripts.review_ui import app as review_app  # noqa: E402

_BATCH: list[dict[str, Any]] = [
    {
        "card_id": "crisis.synthetic__card_1",
        "check_id": "crisis.synthetic",
        "transcript_window": "synthetic window: card 1",
        "source_tags": [],
        "scenario_id": "synthetic_scenario_001",
    },
    {
        "card_id": "crisis.synthetic__card_2",
        "check_id": "crisis.synthetic",
        "transcript_window": "synthetic window: card 2",
        "source_tags": [],
        "scenario_id": "synthetic_scenario_002",
    },
]

_TOKENS = (
    "token=revtok role=reviewer id=rev1 slot=annotator_1 seed=7\n"
    "token=admintok role=admin id=admin1\n"
)


@pytest.fixture
def client(tmp_path, monkeypatch) -> Iterator[Any]:
    review_dir = tmp_path / "review"
    review_dir.mkdir()
    batch_path = review_dir / "batch.json"
    tokens_path = review_dir / "tokens.txt"
    db_path = review_dir / "reviews.db"
    batch_path.write_text(json.dumps(_BATCH), encoding="utf-8")
    tokens_path.write_text(_TOKENS, encoding="utf-8")

    monkeypatch.setattr(review_app, "REVIEW_DIR", review_dir)
    monkeypatch.setattr(review_app, "BATCH_PATH", batch_path)
    monkeypatch.setattr(review_app, "TOKENS_PATH", tokens_path)
    monkeypatch.setattr(review_app, "DB_PATH", db_path)
    # The freeze is a module global — start every test with no prior freeze so
    # this file's tests (and the sibling review test modules run in the same
    # process) never see a hash pinned by an earlier test.
    monkeypatch.setattr(review_app, "_BATCH_SHA", None)

    with review_app.app.test_client() as c:
        yield c


def _swap_batch(batch_path, cards: list[dict[str, Any]]) -> None:
    batch_path.write_text(json.dumps(cards), encoding="utf-8")


def test_assert_batch_frozen_direct(tmp_path, monkeypatch) -> None:
    review_dir = tmp_path / "review"
    review_dir.mkdir()
    batch_path = review_dir / "batch.json"
    batch_path.write_text(json.dumps(_BATCH), encoding="utf-8")

    monkeypatch.setattr(review_app, "BATCH_PATH", batch_path)
    monkeypatch.setattr(review_app, "_BATCH_SHA", None)

    review_app.assert_batch_frozen()  # first read freezes, no error
    assert review_app._BATCH_SHA is not None

    review_app.assert_batch_frozen()  # unchanged bytes: still fine
    frozen = review_app._BATCH_SHA

    _swap_batch(batch_path, list(reversed(_BATCH)))
    with pytest.raises(HTTPException) as exc_info:
        review_app.assert_batch_frozen()
    assert exc_info.value.code == 409
    assert review_app._BATCH_SHA == frozen  # rejection doesn't re-pin the new hash


def test_save_rejects_after_batch_swap(client: Any) -> None:
    body = {"pos": 0, "verdict": "PASS", "rationale": "", "note": "", "flagged": False}

    ok = client.post("/r/revtok/save", json=body)
    assert ok.status_code == 200, ok.get_data(as_text=True)

    _swap_batch(review_app.BATCH_PATH, list(reversed(_BATCH)))

    blocked = client.post("/r/revtok/save", json=body)
    assert blocked.status_code == 409


def test_admin_export_rejects_after_batch_swap(client: Any) -> None:
    first = client.get("/admin/admintok/export")
    assert first.status_code == 200

    extra = [*_BATCH, {
        "card_id": "crisis.synthetic__card_3",
        "check_id": "crisis.synthetic",
        "transcript_window": "synthetic window: card 3",
        "source_tags": [],
        "scenario_id": "synthetic_scenario_003",
    }]
    _swap_batch(review_app.BATCH_PATH, extra)

    blocked = client.get("/admin/admintok/export")
    assert blocked.status_code == 409
