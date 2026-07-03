"""Scoring sub-package — safety violation rates + care quality distributions.

Public API
----------
contract
    is_gate_failure(verdict, severity, check_hard_fail) -> bool
    can_carry_hard_fail_claim(...) -> bool

safety
    scenario_safety(mode_results, dim_map, ...) -> dict[str, bool]
    model_safety_rates(scenario_safeties, *, scenario_ids=None) -> dict[str, dict]
    severity_breakdown(mode_results, dim_map) -> dict[str, dict[str, int]]
    check_calibration_statuses(checks_dir=None) -> dict[str, str]

care
    scenario_care(mode_results, dim_map) -> dict[str, dict[str, int]]
    model_care_distribution(scenario_cares) -> dict[str, dict]
"""

from __future__ import annotations

from invisiblebench.scoring.care import model_care_distribution, scenario_care
from invisiblebench.scoring.contract import can_carry_hard_fail_claim, is_gate_failure
from invisiblebench.scoring.safety import (
    check_calibration_statuses,
    model_safety_rates,
    scenario_safety,
    severity_breakdown,
)

__all__ = [
    "check_calibration_statuses",
    "can_carry_hard_fail_claim",
    "is_gate_failure",
    "model_care_distribution",
    "model_safety_rates",
    "scenario_care",
    "scenario_safety",
    "severity_breakdown",
]
