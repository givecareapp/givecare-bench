"""Flask test-client coverage for the Hound approval queue's write actions.

B-18: approve, decline, note, and auto-advance had zero automated coverage —
the only proof was production use. This module drives the actual routes
(``/q/<token>``, ``/q/<token>/plan/<repo>/<stem>``, and the decide POST) end
to end against synthetic Hound plans in a temp ``GIVECARE_ROOT``, mocking the
``hound`` subprocess calls (``_plan_status`` for status, ``subprocess.run``
for ``hound approve``) rather than shelling out to the real binary.

It also pins the B-08, B-15, B-16, and B-17 fixes alongside the coverage they
motivated: an unprobeable plan renders as an error row instead of vanishing
and decide re-checks status before acting; a decide-form note attaches to the
decisions ledger under the verb that actually happened; decline is guarded
against a race/OS-error 500; and a cross-site decide POST is rejected the
same way ``/r/<token>/save`` already is.

``scripts/review_ui/app.py`` is a self-contained ``uv run --script`` app that
declares ``flask`` only in its own PEP 723 inline metadata, not in this
project's ``pyproject.toml`` dependencies — this module skips cleanly via
``importorskip`` rather than breaking collection when flask isn't installed
in the main dev/test environment (run with ``uv run --with flask pytest ...``
to exercise it).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

pytest.importorskip(
    "flask", reason="scripts/review_ui/app.py's flask dep is script-local (PEP 723), not a project dependency"
)

from scripts.review_ui import app as review_app  # noqa: E402

REPO = "gc-fake"

_TOKENS = (
    "token=admintok role=admin id=admin1\n"
    "token=revtok role=reviewer id=rev1 slot=annotator_1 seed=1\n"
)


def _write_plan(givecare_root: Path, stem: str, **overrides: Any) -> Path:
    plan: dict[str, Any] = {
        "gate": "human",
        "plan_id": f"plan-{stem}",
        "operation": "corpus.project",
        "effect": "write",
        "as_of": "2026-08-01",
        "driver_id": "test-driver",
        "write_scope_sha256": "deadbeef" * 4,
        "write_scopes": ["benchmark/scenarios/**"],
        "proposal": {"data": {"records": {}}},
    }
    plan.update(overrides)
    plans_dir = givecare_root / REPO / ".hound" / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    path = plans_dir / f"{stem}.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path


@pytest.fixture
def queue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[SimpleNamespace]:
    givecare_root = tmp_path / "givecare"
    (givecare_root / REPO / ".hound" / "plans").mkdir(parents=True)
    review_dir = tmp_path / "review"
    review_dir.mkdir()
    tokens_path = review_dir / "tokens.txt"
    tokens_path.write_text(_TOKENS, encoding="utf-8")
    batch_path = review_dir / "batch.json"
    decisions_path = givecare_root / ".agents" / "decisions.jsonl"

    monkeypatch.setattr(review_app, "REVIEW_DIR", review_dir)
    monkeypatch.setattr(review_app, "TOKENS_PATH", tokens_path)
    monkeypatch.setattr(review_app, "BATCH_PATH", batch_path)
    monkeypatch.setattr(review_app, "GIVECARE_ROOT", givecare_root)
    monkeypatch.setattr(review_app, "DECISIONS_PATH", decisions_path)
    monkeypatch.setattr(review_app, "_discover_hound_repos", lambda: (REPO,))

    with review_app.app.test_client() as client:
        yield SimpleNamespace(
            client=client, root=givecare_root, decisions_path=decisions_path
        )


def _decisions(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


# --------------------------------------------------------------------------- #
# B-08: queue rendering + decide status re-check
# --------------------------------------------------------------------------- #
def test_queue_renders_pending_plan(queue: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_plan(queue.root, "alpha")
    monkeypatch.setattr(review_app, "_plan_status", lambda repo, path: "pending")

    resp = queue.client.get("/q/admintok")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "alpha" in body
    assert "Nothing needs you." not in body


def test_queue_renders_error_row_for_unprobeable_status(
    queue: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_plan(queue.root, "beta")
    monkeypatch.setattr(review_app, "_plan_status", lambda repo, path: "")

    resp = queue.client.get("/q/admintok")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # B-08: an unprobeable plan must still render — "Nothing needs you" would
    # be a false negative — as a visible error row, not silently dropped.
    assert "beta" in body
    assert "status unavailable" in body.lower()


def test_decide_refuses_a_plan_hound_cannot_judge(
    queue: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_plan(queue.root, "gamma")
    monkeypatch.setattr(review_app, "_plan_status", lambda repo, path: "")

    resp = queue.client.post(
        f"/q/admintok/plan/{REPO}/gamma/decide", data={"decision": "approve", "note": ""}
    )

    assert resp.status_code == 409
    assert "status unavailable" in resp.get_data(as_text=True).lower()
    approvals_dir = queue.root / REPO / ".hound" / "approvals"
    assert not approvals_dir.exists() or not any(approvals_dir.iterdir())


@pytest.mark.parametrize("stale_status", ["stale", "executed"])
def test_decide_refuses_a_stale_or_executed_plan(
    queue: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, stale_status: str
) -> None:
    _write_plan(queue.root, "delta")
    monkeypatch.setattr(review_app, "_plan_status", lambda repo, path: stale_status)

    resp = queue.client.post(
        f"/q/admintok/plan/{REPO}/delta/decide", data={"decision": "decline", "note": ""}
    )

    assert resp.status_code == 409
    assert "no longer decidable" in resp.get_data(as_text=True).lower()
    plan_path = queue.root / REPO / ".hound" / "plans" / "delta.json"
    assert plan_path.is_file()  # untouched — decline never ran


# --------------------------------------------------------------------------- #
# Approve: writes the artifact, honors already-approved 409
# --------------------------------------------------------------------------- #
def test_approve_writes_artifact_and_honors_already_approved_409(
    queue: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_plan(queue.root, "epsilon")
    monkeypatch.setattr(review_app, "_plan_status", lambda repo, path: "pending")

    def fake_run(command: list[str], **kwargs: Any) -> SimpleNamespace:
        out_path = Path(command[command.index("--output") + 1])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps({"plan_id": "plan-epsilon", "reviewer": "admin1 (via review UI)"})
        )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(review_app.subprocess, "run", fake_run)

    resp = queue.client.post(
        f"/q/admintok/plan/{REPO}/epsilon/decide",
        data={"decision": "approve", "note": ""},
    )
    assert resp.status_code == 302
    approval_path = queue.root / REPO / ".hound" / "approvals" / "epsilon.approval.json"
    assert approval_path.is_file()

    # A second approve on the same plan is caught before hound runs again.
    again = queue.client.post(
        f"/q/admintok/plan/{REPO}/epsilon/decide",
        data={"decision": "approve", "note": ""},
    )
    assert again.status_code == 409
    assert "already approved" in again.get_data(as_text=True).lower()


# --------------------------------------------------------------------------- #
# B-16: decline idempotency / guarded rename
# --------------------------------------------------------------------------- #
def test_decline_moves_plan_to_declined_dir(
    queue: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_plan(queue.root, "zeta")
    monkeypatch.setattr(review_app, "_plan_status", lambda repo, path: "pending")

    resp = queue.client.post(
        f"/q/admintok/plan/{REPO}/zeta/decide", data={"decision": "decline", "note": ""}
    )

    assert resp.status_code == 302
    declined = queue.root / REPO / ".hound" / "plans" / "declined" / "zeta.json"
    assert declined.is_file()
    assert not (queue.root / REPO / ".hound" / "plans" / "zeta.json").exists()


def test_decline_already_moved_plan_is_a_friendly_409_not_a_traceback(
    queue: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_plan(queue.root, "eta")
    monkeypatch.setattr(review_app, "_plan_status", lambda repo, path: "pending")

    # Simulate the true race: another request's rename already won between
    # this request's load_plan() read and its own rename() call.
    def raise_not_found(self: Path, target: Path) -> None:
        raise FileNotFoundError(self)

    monkeypatch.setattr(Path, "rename", raise_not_found)

    resp = queue.client.post(
        f"/q/admintok/plan/{REPO}/eta/decide", data={"decision": "decline", "note": ""}
    )

    assert resp.status_code == 409
    body = resp.get_data(as_text=True)
    assert "already declined" in body.lower()
    assert "Traceback" not in body


def test_decline_os_error_is_a_clean_500_not_a_traceback(
    queue: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_plan(queue.root, "theta")
    monkeypatch.setattr(review_app, "_plan_status", lambda repo, path: "pending")

    def raise_os_error(self: Path, target: Path) -> None:
        raise OSError("cross-device link")

    monkeypatch.setattr(Path, "rename", raise_os_error)

    resp = queue.client.post(
        f"/q/admintok/plan/{REPO}/theta/decide", data={"decision": "decline", "note": ""}
    )

    assert resp.status_code == 500
    body = resp.get_data(as_text=True)
    assert "Decline failed" in body
    assert "Traceback" not in body


# --------------------------------------------------------------------------- #
# B-15: decide-form note persists (approve/decline), same as the
# always-available Activity-panel note (decision=note).
# --------------------------------------------------------------------------- #
def test_decide_form_note_persists_on_approve(
    queue: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_plan(queue.root, "iota")
    monkeypatch.setattr(review_app, "_plan_status", lambda repo, path: "pending")

    def fake_run(command: list[str], **kwargs: Any) -> SimpleNamespace:
        out_path = Path(command[command.index("--output") + 1])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("{}")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(review_app.subprocess, "run", fake_run)

    resp = queue.client.post(
        f"/q/admintok/plan/{REPO}/iota/decide",
        data={"decision": "approve", "note": "Looks right, ship it."},
    )
    assert resp.status_code == 302

    rows = _decisions(queue.decisions_path)
    assert len(rows) == 1
    assert rows[0]["verb"] == "approve"
    assert rows[0]["note"] == "Looks right, ship it."
    assert rows[0]["key"] == f"hound:{REPO}/iota"
    assert rows[0]["by"] == "admin1"


def test_decide_form_note_persists_on_decline(
    queue: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_plan(queue.root, "kappa")
    monkeypatch.setattr(review_app, "_plan_status", lambda repo, path: "pending")

    resp = queue.client.post(
        f"/q/admintok/plan/{REPO}/kappa/decide",
        data={"decision": "decline", "note": "Wrong scope."},
    )
    assert resp.status_code == 302

    rows = _decisions(queue.decisions_path)
    assert len(rows) == 1
    assert rows[0]["verb"] == "decline"
    assert rows[0]["note"] == "Wrong scope."


def test_decide_form_empty_note_writes_nothing_extra(
    queue: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_plan(queue.root, "lambda_")
    monkeypatch.setattr(review_app, "_plan_status", lambda repo, path: "pending")

    resp = queue.client.post(
        f"/q/admintok/plan/{REPO}/lambda_/decide", data={"decision": "decline", "note": ""}
    )
    assert resp.status_code == 302
    assert _decisions(queue.decisions_path) == []


def test_activity_panel_note_persists_and_stays_on_the_item(
    queue: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_plan(queue.root, "mu")
    monkeypatch.setattr(review_app, "_plan_status", lambda repo, path: "pending")

    resp = queue.client.post(
        f"/q/admintok/plan/{REPO}/mu/decide", data={"decision": "note", "note": "Watching this one."}
    )

    # Note never advances — it redirects back to the same item, not the queue.
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith(f"/q/admintok/plan/{REPO}/mu?msg=note:mu")
    rows = _decisions(queue.decisions_path)
    assert len(rows) == 1
    assert rows[0]["verb"] == "note"
    assert rows[0]["status"] == "noted"
    assert rows[0]["note"] == "Watching this one."
    # The plan itself was untouched by a note.
    assert (queue.root / REPO / ".hound" / "plans" / "mu.json").is_file()


# --------------------------------------------------------------------------- #
# B-17: origin / Sec-Fetch-Site rejection on decide
# --------------------------------------------------------------------------- #
def test_decide_rejects_mismatched_origin(
    queue: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_plan(queue.root, "nu")
    monkeypatch.setattr(review_app, "_plan_status", lambda repo, path: "pending")

    resp = queue.client.post(
        f"/q/admintok/plan/{REPO}/nu/decide",
        data={"decision": "decline", "note": ""},
        headers={"Origin": "https://evil.example"},
    )

    assert resp.status_code == 403
    # Untouched — the rejected request never reached decision logic.
    assert (queue.root / REPO / ".hound" / "plans" / "nu.json").is_file()


def test_decide_rejects_mismatched_sec_fetch_site(
    queue: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_plan(queue.root, "xi")
    monkeypatch.setattr(review_app, "_plan_status", lambda repo, path: "pending")

    resp = queue.client.post(
        f"/q/admintok/plan/{REPO}/xi/decide",
        data={"decision": "decline", "note": ""},
        headers={"Sec-Fetch-Site": "cross-site"},
    )

    assert resp.status_code == 403


def test_decide_allows_absent_origin_headers(
    queue: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_plan(queue.root, "omicron")
    monkeypatch.setattr(review_app, "_plan_status", lambda repo, path: "pending")

    resp = queue.client.post(
        f"/q/admintok/plan/{REPO}/omicron/decide", data={"decision": "decline", "note": ""}
    )

    assert resp.status_code == 302


# --------------------------------------------------------------------------- #
# Role and reference guards (already covered lightly elsewhere, pinned here
# alongside the rest of the decide-route surface per B-18).
# --------------------------------------------------------------------------- #
def test_reviewer_token_is_404_on_the_admin_queue(queue: SimpleNamespace) -> None:
    resp = queue.client.get("/q/revtok")
    assert resp.status_code == 404


def test_unknown_repo_404s_before_any_hound_call(
    queue: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    called = False

    def fail_if_called(repo: str, path: Path) -> str:
        nonlocal called
        called = True
        return "pending"

    monkeypatch.setattr(review_app, "_plan_status", fail_if_called)

    resp = queue.client.post(
        "/q/admintok/plan/not-a-real-repo/whatever/decide",
        data={"decision": "decline", "note": ""},
    )

    assert resp.status_code == 404
    assert not called
