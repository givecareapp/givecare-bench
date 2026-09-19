"""A Jury Card reports saved evidence and keeps commentary outside the ledger."""

import hashlib

import pytest

from benchmark.tests.fixtures.current_scan import FixtureJudge, ScriptedJudge, write_source_run
from invisiblebench.judge import ANSWERS_FILE, LEDGER_FILE, load_scan, plan_scan, run_scan
from invisiblebench.jury_card import CARD_FILE, COMMENTARY_MARKER, write_jury_card


def judged(tmp_path, scan_name, client, **source):
    source_run = write_source_run(tmp_path, roster=[("case", "context")], **source)
    scan = tmp_path / scan_name
    plan = plan_scan([source_run], scan)
    run_scan(scan, max_cost_usd=plan.estimated_cost_usd, client=client)
    return scan


@pytest.fixture
def bundle(tmp_path):
    return judged(tmp_path, "2026-09-09_00-33-18Z", FixtureJudge())


def test_card_uses_exact_evidence_and_preserves_attributed_commentary(tmp_path):
    # A confident yes on the prohibition question fails the first assistant turn.
    bundle = judged(
        tmp_path, "2026-09-09_00-33-18Z", ScriptedJudge({"claim": 0.95}),
    )
    saved = (bundle / ANSWERS_FILE).read_bytes()
    path = write_jury_card(bundle)
    assert path == bundle / CARD_FILE
    text = path.read_text()
    assert text.startswith("# Fixture Model 0 — 9 Sep 2026, 00:33:18 UTC\n")
    assert "identity.fixture-prohibition" in text
    assert "I can help." in text and "assistant turn 1" in text
    assert "claim 0.95 (yes)" in text
    assert hashlib.sha256(saved).hexdigest() in text
    assert hashlib.sha256((bundle / LEDGER_FILE).read_bytes()).hexdigest() in text
    assert "Judge thresholds" in text
    assert "Safety" in text and "Care" in text and "MODEL-JUDGED" in text
    path.write_text(
        text.split(COMMENTARY_MARKER)[0]
        + COMMENTARY_MARKER
        + "\nReviewer: fixture. Disputed interpretation.\n"
    )
    write_jury_card(bundle)
    assert "Reviewer: fixture. Disputed interpretation." in path.read_text()
    assert (bundle / ANSWERS_FILE).read_bytes() == saved
    assert len([p for p in bundle.iterdir() if p.name.startswith("jury-card")]) == 1


def test_card_refuses_incomplete_or_changed_evidence(bundle):
    path = write_jury_card(bundle)
    saved = path.read_bytes()
    answers = bundle / ANSWERS_FILE
    answers.write_bytes(answers.read_bytes().splitlines(keepends=True)[0])
    with pytest.raises(ValueError, match="stored judgments differ"):
        write_jury_card(bundle)
    (bundle / LEDGER_FILE).unlink()
    with pytest.raises(ValueError, match="incomplete"):
        write_jury_card(bundle)
    assert path.read_bytes() == saved


def test_card_keeps_unclear_visible_and_links_each_model_separately(tmp_path):
    bundle = judged(
        tmp_path,
        "scan",
        ScriptedJudge({"claim": 0.5}),
        model_ids=("fixture/a", "fixture/b"),
    )
    plan, answers, judgments = load_scan(bundle, complete=True)
    text = write_jury_card(bundle).read_text()
    a, b = text.split("## Fixture Model 1")
    assert "UNCLEAR" in a and "UNCLEAR" in b
    assert "The rule is unresolved at assistant turn(s) 1, 2." in text
    assert f"Completed judge requests: {len(answers)}" in text
    assert f"derived judgments: {len(judgments)}" in text
    assert plan.planned_judgments == len(judgments)
