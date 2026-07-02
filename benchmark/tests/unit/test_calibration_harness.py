"""Calibration harness output contract."""

from __future__ import annotations

from invisiblebench.evaluation.calibration import CalibrationMetrics


def test_calibration_metrics_emit_development_band_not_validation_tier() -> None:
    metrics = CalibrationMetrics(
        mode_id="crisis.passive-ideation",
        n_examples=40,
        accuracy=0.9,
        precision=0.9,
        recall=0.9,
        false_negative_rate=0.1,
        false_positive_rate=0.1,
        unclear_rate=0.0,
        inter_run_stability=1.0,
        human_verifier_kappa=0.8,
    )

    payload = metrics.to_dict()

    assert payload["development_band"] == "strong_development_evidence"
    assert payload["claim_status"] == "not_claim_ready"
    assert "validation_tier" not in payload
