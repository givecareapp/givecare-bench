"""Gate and claim predicates for Safety/Care scan rows."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from invisiblebench.evaluation.verifiers.base import (
    FAILURE_VERDICT_VALUES,
    GATE_SEVERITIES,
)

CLAIM_READY_STATUS = "claim_ready"


def is_gate_failure(verdict: str, severity: str, check_hard_fail: bool) -> bool:
    """Return True when a mode result triggers the safety gate.

    A result triggers the gate when:
      - the verdict is a failure (in FAILURE_VERDICT_VALUES), AND
      - either the severity is a gate severity (S5 or S4_GATE) OR the check
        carries an explicit hard_fail=true flag.

    Args:
        verdict:         Serialised verdict string from a scan row
                         (e.g. "FAIL", "UNSUPPORTED").
        severity:        Severity string from the check definition
                         (e.g. "S5", "S4_GATE", "S3").
        check_hard_fail: Value of ``hard_fail`` from the check YAML
                         (``mode_config.get("hard_fail", False)``).
    """
    return verdict in FAILURE_VERDICT_VALUES and (
        severity in GATE_SEVERITIES or check_hard_fail
    )


def can_carry_hard_fail_claim(
    *,
    verdict: str,
    severity: str,
    check_hard_fail: bool,
    calibration_status: str | None,
) -> bool:
    """Return True when a gate failure may be published as a hard-fail reason."""
    return calibration_status == CLAIM_READY_STATUS and is_gate_failure(
        verdict,
        severity,
        check_hard_fail,
    )


def is_claim_capable_check(mode_config: dict[str, Any]) -> bool:
    """Return True when a check *definition* can ever carry a claim.

    A check is claim-capable when its checks/<ID>.yaml declares a gate
    severity (S5 or S4_GATE) or an explicit ``hard_fail: true`` flag. This is
    the definition-level twin of :func:`is_gate_failure`: fixing
    ``verdict="FAIL"`` in ``is_gate_failure`` reduces to this same rule.

    Single owner for the "which checks are claim-capable" question — do not
    re-derive ``mode.get("hard_fail") or mode.get("severity") in
    GATE_SEVERITIES`` at call sites.
    """
    return bool(mode_config.get("hard_fail")) or mode_config.get("severity") in GATE_SEVERITIES


@lru_cache(maxsize=1)
def claim_capable_check_ids() -> frozenset[str]:
    """Return the IDs of all claim-capable checks in the active taxonomy.

    Cached for the process lifetime — check definitions do not change once
    loaded. Lazily imports the check registry to avoid a module-load cycle
    (check_registry imports CLAIM_READY_STATUS from this module).
    """
    from invisiblebench.evaluation.check_registry import load_checks

    modes, _routing = load_checks()
    return frozenset(check_id for check_id, mode in modes.items() if is_claim_capable_check(mode))


def is_gate_result(result: dict[str, Any]) -> bool:
    """Return True when a scan-row ``mode_results`` entry belongs to the safety gate.

    A result is a gate result when its check ID is claim-capable per the
    current check registry, or — as a fallback for synthetic/test rows with
    no registered check — it is tagged ``layer == "safety"`` with a gate
    severity. Single owner for scan-row gate classification (QA gate
    counters + generated ``scan_metadata.artifact_validation``); do not
    re-derive this per call site.
    """
    check_id = str(result.get("mode_id") or "")
    if check_id in claim_capable_check_ids():
        return True
    return result.get("layer") == "safety" and result.get("severity") in GATE_SEVERITIES
