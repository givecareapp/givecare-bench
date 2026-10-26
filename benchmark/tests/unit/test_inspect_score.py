"""Inspect scores retain the rule's uncertainty instead of hiding it in a rate."""

from invisiblebench.models.scan import Judgment, Verdict
from invisiblebench.scorers.core import inspect_score


def test_unclear_score_records_settled_possibilities():
    judgment = Judgment(
        model_id="target/model",
        scenario_id="fixture",
        check_id="attunement.advice-first",
        plan_sha256="0" * 64,
        verdict=Verdict.UNCLEAR,
        rationale="The cue is unresolved.",
        evidence=[],
        answers={},
    )

    score = inspect_score([(judgment, {Verdict.FAIL, Verdict.PASS})])

    assert score.value == {"attunement.advice-first": "UNCLEAR"}
    assert score.metadata["checks"][0]["possible_verdicts"] == ["FAIL", "PASS"]
    assert score.metadata["checks"][0]["plan_sha256"] == "0" * 64
