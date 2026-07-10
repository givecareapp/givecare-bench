"""Regression pins for the calibration→claims link.

VISION.md: "uncalibrated scores are caveats, not claims." The QA gate makes
that structural rather than cultural:

1. Every claim-capable check (hard_fail or S5/S4_GATE severity) must declare
   a machine-readable `calibration:` block in its
   checks/<layer>/<dimension>/<ID>.yaml.
2. A published hard_fail_reason from a check that is not `claim_ready` is a QA
   error unconditionally.

Evidence statuses are declarations with provenance (docs/verifier-validation.md):
`claim_ready` = independent human-labeled natural-case calibration clears the
bar; `not_claim_ready` = everything else, including development evidence.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from invisiblebench.evaluation.check_registry import load_checks
from invisiblebench.evaluation.scoring_contract import scoring_config_path
from invisiblebench.evaluation.verifiers.base import GATE_SEVERITIES
from invisiblebench.scoring.contract import is_claim_capable_check
from scripts.qa_leaderboard import calibration_errors


def test_gate_severities_agree_with_scoring_yaml() -> None:
    """base.py owns GATE_SEVERITIES in code; scoring.yaml `gates:` states the
    same rule declaratively. They must never drift apart."""
    config = yaml.safe_load(scoring_config_path().read_text())
    for gate_name, gate in (config.get("gates") or {}).items():
        declared = set(gate.get("hard_fail_on_severity") or [])
        assert declared == set(GATE_SEVERITIES), (gate_name, declared)


def test_every_claim_capable_check_declares_calibration() -> None:
    modes, _routing = load_checks()
    errors = calibration_errors([], modes)
    assert errors == [], errors

    claim_checks = [
        check_id
        for check_id, mode in modes.items()
        if is_claim_capable_check(mode)
    ]
    assert claim_checks, "taxonomy has no claim-capable checks?"
    for check_id in claim_checks:
        status = (modes[check_id].get("calibration") or {}).get("status")
        assert status in {"claim_ready", "not_claim_ready"}, (check_id, status)


def test_check_loader_rejects_retired_calibration_status(tmp_path: Path) -> None:
    check_file = tmp_path / "retired.yaml"
    check_file.write_text(
        """
id: retired
name: Retired status
severity: S5
scope: scenario
calibration:
  status: validated
routing:
  scorer: regex
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported calibration.status"):
        load_checks(tmp_path)


def test_claim_ready_requires_claim_grade_natural_independent_evidence(tmp_path: Path) -> None:
    check_dir = tmp_path / "safety" / "crisis"
    check_dir.mkdir(parents=True)
    (check_dir / "crisis.test.yaml").write_text(
        """
id: crisis.test
severity: S5
hard_fail: true
routing:
  route: llm_primary
calibration:
  status: claim_ready
  evidence:
    claim_grade: false
    independent_human_labels: false
    natural_cases: false
""".strip()
    )

    with pytest.raises(ValueError, match="claim_ready requires"):
        load_checks(tmp_path)


def test_hard_fail_from_uncalibrated_check_is_a_qa_error() -> None:
    modes = {
        "crisis.test-check": {"severity": "S5", "hard_fail": True},  # no calibration block
    }
    rows = [
        {
            "model": "M",
            "scenario_id": "s1",
            "hard_fail": True,
            "hard_fail_reasons": [
                {
                    "mode_id": "crisis.test-check",
                    "layer": "safety",
                    "dimension": "crisis",
                    "severity": "S5",
                }
            ],
        }
    ]
    errors = calibration_errors(rows, modes)
    assert any("claim_check_missing_calibration" in e for e in errors)
    assert any("hard_fail_from_uncalibrated_check" in e for e in errors)


def test_not_claim_ready_status_cannot_carry_claims() -> None:
    modes = {
        "crisis.test-check": {
            "severity": "S5",
            "hard_fail": True,
            "calibration": {"status": "not_claim_ready"},
        },
    }
    rows = [{"hard_fail_reasons": [{"mode_id": "crisis.test-check"}]}]
    errors = calibration_errors(rows, modes)
    # The block exists (inventory passes) but the status cannot carry a claim.
    assert not any("claim_check_missing_calibration" in e for e in errors)
    assert any("hard_fail_from_uncalibrated_check" in e for e in errors)


def test_calibrated_statuses_carry_claims() -> None:
    modes = {
        "crisis.test-check": {
            "severity": "S5",
            "hard_fail": True,
            "calibration": {"status": "claim_ready", "basis": "human-labeled gold"},
        },
        "scope.test-check": {
            "severity": "S5",
            "hard_fail": True,
            "calibration": {"status": "claim_ready", "human_kappa": 1.0, "n": 40},
        },
    }
    rows = [
        {
            "hard_fail_reasons": [
                {"mode_id": "crisis.test-check"},
                {"mode_id": "scope.test-check"},
            ]
        }
    ]
    assert calibration_errors(rows, modes) == []
