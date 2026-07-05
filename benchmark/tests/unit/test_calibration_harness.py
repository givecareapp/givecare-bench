"""Calibration report output contract.

The report emits a *development band* and a hard `not_claim_ready` status — it
never emits a validation-tier or otherwise promotes a check. Promotion stays out
of band (check-YAML review).
"""

from __future__ import annotations

from invisiblebench.evaluation.calibration import CalibrationHarness, CardRun
from invisiblebench.evaluation.verifiers.base import Verdict

P = Verdict.PASS
F = Verdict.FAIL


def _run(human: Verdict, verdict: Verdict) -> CardRun:
    return CardRun(
        card_id="c",
        mode_id="crisis.passive-ideation",
        human=human,
        reps=[verdict, verdict, verdict],
        post_guard=verdict,
    )


def test_report_emits_development_band_not_validation_tier() -> None:
    harness = CalibrationHarness()
    # A two-class set the verifier gets exactly right: strong development band.
    runs = [_run(F, F) for _ in range(20)] + [_run(P, P) for _ in range(20)]
    report = harness.build_report(runs, mode_id="crisis.passive-ideation", n_resamples=200)

    payload = report.to_dict()

    assert payload["development_band"] == "strong_development_evidence"
    assert payload["claim_status"] == "not_claim_ready"
    assert "validation_tier" not in payload


def test_report_claim_status_is_hard_not_claim_ready_even_when_bar_met() -> None:
    harness = CalibrationHarness()
    # 100 cards, 40 gold FAILs all caught, 60 gold PASS all correct: this clears
    # every numeric bar criterion, yet claim_status must still refuse promotion.
    runs = [_run(F, F) for _ in range(40)] + [_run(P, P) for _ in range(60)]
    report = harness.build_report(runs, mode_id="crisis.passive-ideation", n_resamples=200)

    bar = report.bar_check()
    assert bar["n_ge_80"] and bar["gold_fails_ge_30"]
    assert bar["recall_ge_0.85"] and bar["precision_ge_0.80"] and bar["kappa_ge_0.65"]
    # IAA absent (single-annotator) so the *bar* is not fully met...
    assert bar["iaa_kappa_ge_0.65"] is False
    # ...but regardless of the numbers, promotion never happens here.
    assert report.claim_status() == "not_claim_ready"
