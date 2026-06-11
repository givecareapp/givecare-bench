"""Regression pins for the calibration→claims link.

VISION.md: "uncalibrated scores are caveats, not claims." The QA gate makes
that structural rather than cultural:

1. Every claim-carrying check (hard_fail or S5/S4_GATE severity) must declare
   a machine-readable `calibration:` block in its checks/<ID>.yaml.
2. A published hard_fail_reason from a check without calibration evidence
   (status validated or provisional) is a QA error unconditionally.

Evidence statuses are declarations with provenance (docs/verifier-validation.md):
`validated` = per-mode Tier 1 gold (κ vs human), `provisional` = layer-level or
card-level human evidence only, `unvalidated` = no human evidence — cannot
carry hard-fail claims.
"""

from __future__ import annotations

import yaml

from invisiblebench.evaluation.check_registry import load_checks
from invisiblebench.evaluation.scoring_contract import scoring_config_path
from invisiblebench.evaluation.verifiers.base import GATE_SEVERITIES
from scripts.qa_leaderboard import CLAIM_SEVERITIES, calibration_errors


def test_gate_severities_agree_with_scoring_yaml() -> None:
    """base.py owns GATE_SEVERITIES in code; scoring.yaml `gates:` states the
    same rule declaratively. They must never drift apart."""
    config = yaml.safe_load(scoring_config_path().read_text())
    for gate_name, gate in (config.get("gates") or {}).items():
        declared = set(gate.get("hard_fail_on_severity") or [])
        assert declared == set(GATE_SEVERITIES), (gate_name, declared)


def test_every_claim_carrying_check_declares_calibration() -> None:
    modes, _routing = load_checks()
    errors = calibration_errors([], modes)
    assert errors == [], errors

    claim_checks = [
        check_id
        for check_id, mode in modes.items()
        if mode.get("hard_fail") or mode.get("severity") in CLAIM_SEVERITIES
    ]
    assert claim_checks, "taxonomy has no claim-carrying checks?"
    for check_id in claim_checks:
        status = (modes[check_id].get("calibration") or {}).get("status")
        assert status in {"validated", "provisional"}, (check_id, status)


def test_hard_fail_from_uncalibrated_check_is_a_qa_error() -> None:
    modes = {
        "IB-X1": {"severity": "S5", "hard_fail": True},  # no calibration block
    }
    rows = [
        {
            "model": "M",
            "scenario_id": "s1",
            "hard_fail": True,
            "hard_fail_reasons": [{"mode_id": "IB-X1", "bucket": "A", "severity": "S5"}],
        }
    ]
    errors = calibration_errors(rows, modes)
    assert any("claim_check_missing_calibration" in e for e in errors)
    assert any("hard_fail_from_uncalibrated_check" in e for e in errors)


def test_unvalidated_status_cannot_carry_claims() -> None:
    modes = {
        "IB-X1": {
            "severity": "S5",
            "hard_fail": True,
            "calibration": {"status": "unvalidated"},
        },
    }
    rows = [{"hard_fail_reasons": [{"mode_id": "IB-X1"}]}]
    errors = calibration_errors(rows, modes)
    # The block exists (inventory passes) but the status cannot carry a claim.
    assert not any("claim_check_missing_calibration" in e for e in errors)
    assert any("hard_fail_from_uncalibrated_check" in e for e in errors)


def test_calibrated_statuses_carry_claims() -> None:
    modes = {
        "IB-X1": {
            "severity": "S5",
            "hard_fail": True,
            "calibration": {"status": "provisional", "basis": "layer gold"},
        },
        "IB-X2": {
            "severity": "S5",
            "hard_fail": True,
            "calibration": {"status": "validated", "human_kappa": 1.0, "n": 40},
        },
    }
    rows = [{"hard_fail_reasons": [{"mode_id": "IB-X1"}, {"mode_id": "IB-X2"}]}]
    assert calibration_errors(rows, modes) == []
