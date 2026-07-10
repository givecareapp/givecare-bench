"""Regression coverage for the frozen-rescore behavior gate."""

from scripts.rescore_diff import compare_row


def test_hybrid_edge_verdict_is_not_treated_as_offline_reproducible() -> None:
    stored = {
        "mode_results": [
            {
                "mode_id": "identity.body-claim",
                "eligible": True,
                "verdict": "FAIL",
                "scorer_type": "regex",
            }
        ]
    }
    rescored = [
        {
            "mode_id": "identity.body-claim",
            "eligible": True,
            "verdict": "UNCLEAR",
            "scorer_type": "regex_with_llm_edge",
        }
    ]

    assert compare_row(stored, rescored) == []


def test_hybrid_edge_eligibility_drift_still_fails() -> None:
    stored = {
        "mode_results": [
            {
                "mode_id": "identity.body-claim",
                "eligible": True,
                "verdict": "FAIL",
                "scorer_type": "regex",
            }
        ]
    }
    rescored = [
        {
            "mode_id": "identity.body-claim",
            "eligible": False,
            "verdict": "NOT_APPLICABLE",
            "scorer_type": "regex_with_llm_edge",
        }
    ]

    assert compare_row(stored, rescored) == [
        {
            "mode_id": "identity.body-claim",
            "field": "eligible",
            "old": True,
            "new": False,
        }
    ]
