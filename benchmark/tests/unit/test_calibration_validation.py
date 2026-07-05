"""Claim-ready validation harness: loading, IAA, bootstrap CIs, N/A, any-FAIL.

Fixtures are synthesized neutral text — never copied from the real (contaminated)
gold cards. They exercise the schema and the metrics, not any scenario content.
"""

from __future__ import annotations

import json
from pathlib import Path

from invisiblebench.evaluation.calibration import (
    ATTRIBUTIONS,
    CalibrationHarness,
    CardRun,
    Interval,
    bootstrap_ci,
    compute_attribution_metrics,
    compute_iaa,
    fail_recall,
    load_gold_cards,
    parse_transcript_window,
)
from invisiblebench.evaluation.verifiers.base import Verdict

P = Verdict.PASS
F = Verdict.FAIL
U = Verdict.UNCLEAR
NA = Verdict.NOT_APPLICABLE

# A neutral two-turn window in the on-disk render format. No scenario content.
_WINDOW = "[Turn 1, USER]\nplaceholder user text\n[Turn 2, ASSISTANT]\nplaceholder assistant text"


def _run(human: Verdict, reps: list[Verdict], post: Verdict | None = None, **kw) -> CardRun:
    return CardRun(
        card_id="c",
        mode_id="crisis.passive-ideation",
        human=human,
        reps=reps,
        post_guard=post if post is not None else (reps[0] if reps else U),
        **kw,
    )


# --------------------------------------------------------------------------- #
# Current-schema loading
# --------------------------------------------------------------------------- #
def test_loads_current_schema_transcript_window_and_verdict(tmp_path: Path) -> None:
    card = {
        "card_id": "x1",
        "mode_id": "crisis.passive-ideation",
        "scenario_id": "scn_1",
        "cue_turn": 2,
        "transcript_window": _WINDOW,
        "verdict": "FAIL",
        "author": "human_a",
    }
    (tmp_path / "crisis.passive-ideation.jsonl").write_text(json.dumps(card) + "\n")

    cards = load_gold_cards("crisis.passive-ideation", tmp_path)

    assert len(cards) == 1
    c = cards[0]
    assert c.card_id == "x1"
    assert c.verdict is F and c.final_verdict is F
    assert c.cue_turn == 2
    # transcript_window string was parsed into ordered turn dicts.
    assert [t["role"] for t in c.transcript] == ["user", "assistant"]
    assert c.transcript[0]["turn"] == 1
    assert not c.has_dual_annotation


def test_parse_transcript_window_roundtrips_roles_and_turns() -> None:
    ts = parse_transcript_window(_WINDOW)
    assert ts == [
        {"turn": 1, "role": "user", "content": "placeholder user text"},
        {"turn": 2, "role": "assistant", "content": "placeholder assistant text"},
    ]


def test_missing_gold_file_returns_empty(tmp_path: Path) -> None:
    assert load_gold_cards("does.not-exist", tmp_path) == []


# --------------------------------------------------------------------------- #
# Dual-annotator loading + IAA
# --------------------------------------------------------------------------- #
def test_loads_dual_annotator_schema_and_adjudicated_final(tmp_path: Path) -> None:
    card = {
        "card_id": "d1",
        "mode_id": "crisis.passive-ideation",
        "transcript_window": _WINDOW,
        "annotator_1_id": "human_a",
        "annotator_1_verdict": "FAIL",
        "annotator_2_id": "human_b",
        "annotator_2_verdict": "UNCLEAR",
        "adjudicated_verdict": "FAIL",
        "verdict": "FAIL",
    }
    (tmp_path / "crisis.passive-ideation.jsonl").write_text(json.dumps(card) + "\n")

    c = load_gold_cards("crisis.passive-ideation", tmp_path)[0]

    assert c.has_dual_annotation
    assert c.annotator_1 is F and c.annotator_2 is U
    # Final label used for metrics prefers the adjudicated label.
    assert c.adjudicated_verdict is F and c.final_verdict is F


def test_iaa_is_none_without_two_annotators() -> None:
    assert compute_iaa([]) is None


def test_iaa_kappa_and_ci_computed_from_two_humans() -> None:
    # 8 agree (4 FAIL, 4 PASS), 2 disagree -> κ defined and < 1, CI present.
    pairs = [(F, F)] * 4 + [(P, P)] * 4 + [(F, P), (P, F)]
    iaa = compute_iaa(pairs, seed=7, n_resamples=200)
    assert iaa is not None
    assert iaa.n_pairs == 10
    assert iaa.kappa is not None and 0.0 < iaa.kappa < 1.0
    assert iaa.kappa_ci.lo is not None and iaa.kappa_ci.hi is not None
    assert iaa.kappa_ci.lo <= iaa.kappa <= iaa.kappa_ci.hi


# --------------------------------------------------------------------------- #
# Bootstrap CI: shape + determinism
# --------------------------------------------------------------------------- #
def test_bootstrap_ci_is_deterministic_for_a_fixed_seed() -> None:
    pairs = [(F, F)] * 6 + [(F, P)] * 2 + [(P, P)] * 8
    a = bootstrap_ci(pairs, fail_recall, seed=123, n_resamples=300)
    b = bootstrap_ci(pairs, fail_recall, seed=123, n_resamples=300)
    assert (a.point, a.lo, a.hi, a.n_valid) == (b.point, b.lo, b.hi, b.n_valid)


def test_bootstrap_ci_shape_and_bounds() -> None:
    pairs = [(F, F)] * 6 + [(F, P)] * 2 + [(P, P)] * 8
    ci = bootstrap_ci(pairs, fail_recall, seed=1, n_resamples=500)
    assert isinstance(ci, Interval)
    assert ci.point is not None
    assert ci.lo is not None and ci.hi is not None
    assert ci.lo <= ci.point <= ci.hi
    assert 0.0 <= ci.lo <= ci.hi <= 1.0
    assert ci.n_valid > 0 and ci.n_resamples == 500


def test_bootstrap_ci_undefined_statistic_yields_none_interval() -> None:
    # No gold FAILs anywhere -> fail_recall is None on every resample.
    pairs = [(P, P)] * 10
    ci = bootstrap_ci(pairs, fail_recall, seed=1, n_resamples=100)
    assert ci.point is None and ci.lo is None and ci.hi is None
    assert ci.n_valid == 0


def test_point_estimate_is_seed_independent() -> None:
    # The point estimate is the statistic on the observed data — not resampled —
    # so it must not move with the bootstrap seed (only the interval resamples).
    pairs = [(F, F)] * 6 + [(F, P)] * 2 + [(P, P)] * 8
    a = bootstrap_ci(pairs, fail_recall, seed=1, n_resamples=300)
    b = bootstrap_ci(pairs, fail_recall, seed=2, n_resamples=300)
    assert a.point == b.point == fail_recall(pairs)


# --------------------------------------------------------------------------- #
# N/A as its own category (never folded into UNCLEAR)
# --------------------------------------------------------------------------- #
def test_na_reported_separately_from_unclear() -> None:
    pairs = [(F, F), (F, U), (F, NA), (P, P), (P, NA)]
    m = compute_attribution_metrics(pairs, "post_guard", seed=1, n_resamples=100)
    assert m.unclear_rate == 1 / 5
    assert m.na_rate == 2 / 5
    # N/A appears as its own column in the confusion matrix, not merged.
    assert m.confusion["FAIL"].get("NOT_APPLICABLE") == 1
    assert m.confusion["PASS"].get("NOT_APPLICABLE") == 1
    assert m.confusion["FAIL"].get("UNCLEAR") == 1
    # Verifier N/A / UNCLEAR are abstentions: only the resolved FAIL->FAIL is TP,
    # so recall base is the one resolved gold FAIL.
    assert m.recall == 1.0


def test_na_not_collapsed_into_unclear_rate() -> None:
    pairs = [(P, NA)] * 3 + [(P, U)] * 1
    m = compute_attribution_metrics(pairs, "post_guard", seed=1, n_resamples=50)
    assert m.na_rate == 3 / 4
    assert m.unclear_rate == 1 / 4


# --------------------------------------------------------------------------- #
# any-FAIL vs majority attribution
# --------------------------------------------------------------------------- #
def test_any_fail_recovers_minority_rep_detection_that_majority_hides() -> None:
    # One gold FAIL card; reps FAIL,PASS,PASS -> majority PASS hides the detect.
    runs = [_run(F, [F, P, P], post=P)]
    harness = CalibrationHarness()
    report = harness.build_report(runs, mode_id="crisis.passive-ideation", n_resamples=50)

    post = report.attributions["post_guard"]
    pre = report.attributions["pre_guard"]
    any_fail = report.attributions["any_fail"]

    # Majority-based attributions miss it (recall 0); any_fail catches it (recall 1).
    assert post.recall == 0.0
    assert pre.recall == 0.0
    assert any_fail.recall == 1.0
    assert set(report.attributions) == set(ATTRIBUTIONS)


def test_card_run_attribution_verdicts_derive_from_reps() -> None:
    run = _run(F, [F, P, P], post=P)
    assert run.post_guard is P  # recorded production verdict
    assert run.pre_guard() is P  # majority of reps
    assert run.any_fail() is F  # any rep failed
    run_maj = _run(F, [F, F, P], post=F)
    assert run_maj.pre_guard() is F
    assert run_maj.any_fail() is F


def test_from_record_replays_recorded_verdicts_without_api() -> None:
    rec = {
        "card_id": "r1",
        "mode_id": "crisis.passive-ideation",
        "human": "FAIL",
        "reps": ["FAIL", "PASS", "PASS"],
        "post_guard": "PASS",
        "guard_fired": False,
    }
    run = CardRun.from_record(rec)
    assert run.human is F
    assert run.reps == [F, P, P]
    assert run.post_guard is P
    assert run.any_fail() is F


def test_guard_fired_counted_in_report() -> None:
    runs = [
        _run(F, [F, F, F], post=U, guard_fired=True),
        _run(P, [P, P, P], post=P, guard_fired=False),
    ]
    report = CalibrationHarness().build_report(
        runs, mode_id="crisis.passive-ideation", n_resamples=50
    )
    assert report.guard_fired == 1
    assert report.gold_distribution == {"FAIL": 1, "PASS": 1}
