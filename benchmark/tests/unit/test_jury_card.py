"""A Jury Card reports saved evidence and keeps commentary outside the ledger."""

import hashlib
import json

import pytest

from benchmark.tests.fixtures.current_scan import FixtureJudge, write_source_run
from invisiblebench.judge import load_scan, plan_scan, run_scan
from invisiblebench.jury_card import CARD_FILE, COMMENTARY_MARKER, write_jury_card


@pytest.fixture
def bundle(tmp_path):
    source = write_source_run(tmp_path, roster=[("case", "context")])
    scan = tmp_path / "2026-09-09_00-33-18Z"
    plan = plan_scan([source], scan)
    run_scan(scan, max_cost_usd=plan.estimated_cost_usd, client=FixtureJudge())
    return scan


def test_card_uses_exact_evidence_and_preserves_attributed_commentary(bundle):
    ledger = bundle / "judgments.jsonl"
    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    rows[0].update(
        verdict="FAIL", rationale="A quoted fixture failure.",
        evidence=[{"role": "assistant", "turn": 1, "quote": "I can help."}],
    )
    rows[0]["raw_response"] = json.dumps({k: rows[0][k] for k in ("verdict", "rationale", "evidence")})
    ledger.write_text("".join(json.dumps(row) + "\n" for row in rows))
    saved = ledger.read_bytes()
    path = write_jury_card(bundle)
    assert path == bundle / CARD_FILE
    text = path.read_text()
    assert text.startswith("# Fixture Model 0 — 9 Sep 2026, 00:33:18 UTC\n")
    assert rows[0]["check_id"] in text
    assert "A quoted fixture failure." in text and "I can help." in text
    assert "assistant turn 1" in text
    assert hashlib.sha256(saved).hexdigest() in text
    assert "Safety" in text and "Care" in text and "MODEL-JUDGED" in text
    path.write_text(text.split(COMMENTARY_MARKER)[0] + COMMENTARY_MARKER + "\nReviewer: fixture. Disputed interpretation.\n")
    write_jury_card(bundle)
    assert "Reviewer: fixture. Disputed interpretation." in path.read_text()
    assert ledger.read_bytes() == saved
    assert len([p for p in bundle.iterdir() if p.name.startswith("jury-card")]) == 1


def test_card_refuses_incomplete_or_changed_evidence(bundle):
    path = write_jury_card(bundle)
    saved = path.read_bytes()
    ledger = bundle / "judgments.jsonl"
    ledger.write_bytes(ledger.read_bytes().splitlines(keepends=True)[0])
    with pytest.raises(ValueError, match="incomplete"):
        write_jury_card(bundle)
    assert path.read_bytes() == saved


def test_card_keeps_unclear_visible_and_links_each_model_separately(tmp_path):
    source = write_source_run(tmp_path, model_ids=("fixture/a", "fixture/b"), roster=[("case", "context")])
    scan = tmp_path / "scan"
    plan = plan_scan([source], scan)
    run_scan(scan, max_cost_usd=plan.estimated_cost_usd, client=FixtureJudge())
    rows = [json.loads(line) for line in (scan / "judgments.jsonl").read_text().splitlines()]
    for row in rows:
        if row["model_id"] == "fixture/a":
            row.update(verdict="UNCLEAR", rationale="Unresolved fixture.")
            row["raw_response"] = json.dumps({k: row[k] for k in ("verdict", "rationale", "evidence")})
    (scan / "judgments.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    text = write_jury_card(scan).read_text()
    a, b = text.split("## Fixture Model 1")
    assert "Unresolved fixture." in a and "Unresolved fixture." not in b
    assert "UNCLEAR" in text
    assert load_scan(scan, complete=True)[0] == plan
