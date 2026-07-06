"""Completeness gate pin for the gold-card review export.

The reviewer UI (``scripts/review_ui/app.py``) requires a rationale for
FAIL/UNCLEAR verdicts before a card counts as ``is_complete``. The admin export
must honor the same rule: a FAIL/UNCLEAR saved without a rationale is a
half-finished judgment and must never be written into the exported JSONL, only
to be silently treated as a real label downstream. This test drives the actual
Flask routes (``/r/<token>/save`` and ``/admin/<token>/export``) end to end
against a synthetic batch — no real card text, temp REVIEW_DIR, temp sqlite.

``scripts/review_ui/app.py`` is a self-contained ``uv run --script`` app that
declares ``flask`` only in its own PEP 723 inline metadata, not in this
project's ``pyproject.toml`` dependencies — so it is not guaranteed to be
importable in the main dev/test environment. This module skips cleanly (via
``importorskip``) rather than breaking collection for the rest of the suite
when flask isn't installed here.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest

pytest.importorskip("flask", reason="scripts/review_ui/app.py's flask dep is script-local (PEP 723), not a project dependency")

from scripts.review_ui import app as review_app  # noqa: E402

_BATCH: list[dict[str, Any]] = [
    {
        "card_id": "crisis.synthetic__pass",
        "check_id": "crisis.synthetic",
        "transcript_window": "synthetic window: pass case",
        "source_tags": [],
        "scenario_id": "synthetic_scenario_001",
    },
    {
        "card_id": "crisis.synthetic__fail_blank",
        "check_id": "crisis.synthetic",
        "transcript_window": "synthetic window: fail with no rationale",
        "source_tags": [],
        "scenario_id": "synthetic_scenario_002",
    },
    {
        "card_id": "crisis.synthetic__fail_rationale",
        "check_id": "crisis.synthetic",
        "transcript_window": "synthetic window: fail with rationale",
        "source_tags": [],
        "scenario_id": "synthetic_scenario_003",
    },
]

_TOKENS = (
    "token=revtok role=reviewer id=rev1 slot=annotator_1 seed=7\n"
    "token=admintok role=admin id=admin1\n"
)

_REVIEWER_ENTRY = {"role": "reviewer", "id": "rev1", "slot": "annotator_1", "seed": "7"}


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

    with review_app.app.test_client() as c:
        yield c


def _pos_for(card_id: str) -> int:
    order = review_app.reviewer_order(_REVIEWER_ENTRY, _BATCH)
    idx = next(i for i, c in enumerate(_BATCH) if c["card_id"] == card_id)
    return order.index(idx)


def _save(client: Any, card_id: str, verdict: str, rationale: str = "") -> dict[str, Any]:
    resp = client.post(
        "/r/revtok/save",
        json={
            "pos": _pos_for(card_id),
            "verdict": verdict,
            "rationale": rationale,
            "note": "",
            "flagged": False,
        },
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return resp.get_json()


def test_incomplete_fail_excluded_pass_and_rationaled_fail_included(client: Any) -> None:
    _save(client, "crisis.synthetic__pass", "PASS")
    _save(client, "crisis.synthetic__fail_blank", "FAIL", rationale="")
    _save(
        client,
        "crisis.synthetic__fail_rationale",
        "FAIL",
        rationale="Turn 2: assistant ignores the cue.",
    )

    resp = client.get("/admin/admintok/export")
    assert resp.status_code == 200
    records = [json.loads(line) for line in resp.get_data(as_text=True).splitlines() if line]
    by_id = {r["card_id"]: r for r in records}

    # PASS never needs a rationale — it's complete and must be exported.
    assert "crisis.synthetic__pass" in by_id
    assert by_id["crisis.synthetic__pass"]["annotator_1_verdict"] == "PASS"

    # FAIL with a blank rationale is incomplete — must not leak into export.
    assert "crisis.synthetic__fail_blank" not in by_id

    # FAIL with a rationale is complete — must be exported with the rationale.
    assert "crisis.synthetic__fail_rationale" in by_id
    assert by_id["crisis.synthetic__fail_rationale"]["annotator_1_verdict"] == "FAIL"
    assert "ignores the cue" in by_id["crisis.synthetic__fail_rationale"]["annotator_1_note"]


def test_is_complete_predicate_gates_on_rationale() -> None:
    assert review_app.is_complete({"verdict": "PASS", "rationale": ""}) is True
    assert review_app.is_complete({"verdict": "FAIL", "rationale": ""}) is False
    assert review_app.is_complete({"verdict": "FAIL", "rationale": "  "}) is False
    assert review_app.is_complete({"verdict": "FAIL", "rationale": "quote"}) is True
    assert review_app.is_complete({"verdict": "UNCLEAR", "rationale": ""}) is False
    assert review_app.is_complete(None) is False
    assert review_app.is_complete({"verdict": "", "rationale": ""}) is False
