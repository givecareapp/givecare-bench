"""Dimension metrics describe one defined estimate and the check set behind it."""

import pytest
from inspect_ai.scorer import SampleScore

from invisiblebench.metrics.dimensions import dimension_observation
from invisiblebench.models.scan import EvidenceSpan, Judgment, Verdict
from invisiblebench.scorers.core import inspect_score


def _scores(cells):
    """cells: (epoch, scenario number, check_id, verdict)."""
    out = []
    for epoch, number, check_id, verdict in cells:
        judgment = Judgment(
            model_id="target/model", scenario_id=f"s{number}", check_id=check_id,
            plan_sha256="0" * 64, verdict=Verdict(verdict), rationale="fixture",
            evidence=[EvidenceSpan(role="assistant", turn=1, quote="q")]
            if verdict == "FAIL" else [],
            answers={},
        )
        score = inspect_score([(judgment, {Verdict(verdict)} if verdict != "UNCLEAR"
                                else {Verdict.PASS, Verdict.FAIL})])
        score.metadata["epoch"] = epoch
        out.append(SampleScore(sample_id=f"s{number}", score=score))
    return out


def test_mismatched_epoch_denominators_give_no_standard_error():
    cells = [(1, n, "crisis.a", "FAIL") for n in range(5)]
    cells += [(2, 0, "crisis.a", "PASS")] + [(2, n, "crisis.a", "NOT_APPLICABLE") for n in range(1, 5)]
    result = dimension_observation(layer="safety", dimension="crisis")(_scores(cells))
    assert result["rate_low"] == pytest.approx(5 / 6)
    assert result["epoch_standard_error"] is None
    assert result["epoch_settled_sets_match"] == 0
    assert (result["epoch_1_applicable"], result["epoch_1_settled"], result["epoch_1_unclear"]) == (5, 5, 0)
    assert (result["epoch_2_applicable"], result["epoch_2_settled"], result["epoch_2_unclear"]) == (1, 1, 0)


def test_unclear_in_one_epoch_changes_settled_set_and_is_counted():
    cells = [(1, n, "attunement.a", "PASS") for n in range(5)]
    cells += [(2, n, "attunement.a", "PASS") for n in range(4)] + [(2, 4, "attunement.a", "UNCLEAR")]
    result = dimension_observation(layer="care", dimension="attunement")(_scores(cells))
    assert result["epoch_standard_error"] is None
    assert result["epoch_2_unclear"] == 1
    assert result["epoch_2_applicable"] == 5
    assert result["epoch_2_settled"] == 4


def test_matching_settled_sets_give_standard_error():
    cells = [(1, n, "crisis.a", "FAIL") for n in range(5)]
    cells += [(2, n, "crisis.a", "PASS") for n in range(5)]
    result = dimension_observation(layer="safety", dimension="crisis")(_scores(cells))
    assert result["epoch_settled_sets_match"] == 1
    assert result["epoch_standard_error"] == pytest.approx(0.5)


def test_check_set_is_listed_with_settled_denominators():
    run_b = [(1, n, "crisis.x", "PASS") for n in range(5)]
    run_b += [(1, n, "crisis.y", "FAIL") for n in range(4)] + [(1, 4, "crisis.y", "UNCLEAR")]
    result = dimension_observation(layer="safety", dimension="crisis")(_scores(run_b))
    assert result["included_settled:crisis.x"] == 5
    assert result["excluded_settled:crisis.y"] == 4
    assert "included_settled:crisis.y" not in result
    assert result["included_checks"] == 1
    assert result["rate_low"] == 0  # only x contributes; compare runs on the common set

    run_a = [(1, n, "crisis.x", "PASS") for n in range(5)]
    run_a += [(1, n, "crisis.y", "FAIL") for n in range(5)]
    result = dimension_observation(layer="safety", dimension="crisis")(_scores(run_a))
    assert result["included_settled:crisis.y"] == 5
    assert result["rate_low"] == 0.5
