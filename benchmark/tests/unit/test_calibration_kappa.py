"""Cohen's kappa degenerate-case contract for the calibration harness.

Regression guard for the `pe == 1.0 -> return 1.0` bug: a one-class gold
(all-PASS or all-FAIL) against a constant verifier collapses to p_e == 1, where
Cohen's kappa is 0/0 (undefined). The single `cohens_kappa` implementation must
report that as `None`, not fabricate a perfect kappa of 1.0 from a set with zero
discriminating signal.

`cohens_kappa` is now the sole owner of the statistic (the gitignored
`internal/scripts/run_golden_verifier.py` is a thin CLI wrapper that imports it,
so there is no second copy to drift).
"""

from __future__ import annotations

from invisiblebench.evaluation.calibration import cohens_kappa
from invisiblebench.evaluation.verifiers.base import Verdict

P = Verdict.PASS
F = Verdict.FAIL
U = Verdict.UNCLEAR
NA = Verdict.NOT_APPLICABLE


def _kappa(pairs: list[tuple[Verdict, Verdict]]) -> float | None:
    return cohens_kappa(pairs)


def test_all_pass_gold_and_verifier_is_degenerate_not_perfect() -> None:
    # Both raters constant on the single PASS class: κ is undefined (0/0).
    assert _kappa([(P, P)] * 8) is None


def test_all_fail_gold_and_verifier_is_degenerate_not_perfect() -> None:
    assert _kappa([(F, F)] * 12) is None


def test_one_class_gold_survives_after_unclear_rows_excluded() -> None:
    # UNCLEAR rows drop out of the κ binary; the residue is all-PASS -> degenerate.
    # (This is the shape that made the prior run print κ=1.000 despite 2/9
    # PASS->UNCLEAR disagreements, e.g. scope.ai-disclosure.)
    assert _kappa([(P, P), (P, P), (P, P), (P, U), (P, U)]) is None


def test_not_applicable_rows_also_drop_out_of_kappa_binary() -> None:
    # N/A is neither pass nor fail; like UNCLEAR it leaves the binary collapse.
    # Residue here is all-PASS -> degenerate -> None (not a fabricated 1.0).
    assert _kappa([(P, P), (P, P), (P, NA), (NA, P)]) is None


def test_real_perfect_agreement_on_two_class_set_is_still_one() -> None:
    # Legitimate κ=1.0 (a two-class gold both raters get exactly right) must NOT
    # be masked by the degenerate guard — it comes through the formula, not the
    # p_e == 1 branch.
    assert _kappa([(F, F), (F, F), (P, P), (P, P)]) == 1.0


def test_total_disagreement_gives_zero_not_one() -> None:
    # All-FAIL gold, all-PASS verifier (recall=0): p_e != 1, κ == 0.
    assert _kappa([(F, P)] * 6) == 0.0


def test_partial_agreement_is_between_zero_and_one() -> None:
    # 3/4 agree on a two-class set: κ strictly between 0 and 1.
    k = _kappa([(F, F), (F, F), (P, P), (P, F)])
    assert k is not None and 0.0 < k < 1.0


def test_empty_returns_none() -> None:
    assert _kappa([]) is None
