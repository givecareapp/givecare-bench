"""Unit tests for rationale_code sourcing fix in LLM verifier.

Exercises the two-step sourcing expression introduced to replace the
first-repetition bug:
  1. Prefer a rationale_code from a repetition whose verdict matches the
     aggregated verdict_str (the majority winner).
  2. Fall back to any rationale_code when no matching-verdict repetition
     has one.

Tests operate directly on a synthetic parsed_results list to avoid
depending on consistency.py (parallel agent) or a live judge client.
"""

from __future__ import annotations


def _source_rationale_code(
    parsed_results: list[dict],
    verdict_str: str,
) -> str | None:
    """Mirror of the sourcing expression in llm_verifier.verify()."""
    rationale_code = next(
        (
            r.get("rationale_code")
            for r in parsed_results
            if r.get("verdict") == verdict_str and r.get("rationale_code")
        ),
        None,
    )
    if rationale_code is None:
        rationale_code = next(
            (r.get("rationale_code") for r in parsed_results if r.get("rationale_code")),
            None,
        )
    return rationale_code


def test_rationale_code_comes_from_majority_verdict_not_first_repetition() -> None:
    """[PASS, FAIL, FAIL] → majority is FAIL; rationale_code must come from a FAIL repetition."""
    parsed_results = [
        {"verdict": "PASS", "rationale_code": "p_recognized"},
        {"verdict": "FAIL", "rationale_code": "f_real"},
        {"verdict": "FAIL", "rationale_code": "f_real2"},
    ]
    verdict_str = "FAIL"  # majority verdict from _aggregate_repetitions

    rationale_code = _source_rationale_code(parsed_results, verdict_str)

    assert rationale_code in {"f_real", "f_real2"}, (
        f"Expected a FAIL repetition rationale code, got {rationale_code!r}"
    )
    assert rationale_code != "p_recognized", (
        "rationale_code must NOT come from the minority PASS repetition"
    )


def test_rationale_code_fallback_when_no_matching_verdict_has_code() -> None:
    """When matching-verdict repetitions lack rationale_code, fall back to any."""
    parsed_results = [
        {"verdict": "PASS", "rationale_code": "p_recognized"},
        {"verdict": "FAIL", "rationale_code": None},
        {"verdict": "FAIL"},
    ]
    verdict_str = "FAIL"

    rationale_code = _source_rationale_code(parsed_results, verdict_str)

    # fallback: PASS repetition has the only non-None code
    assert rationale_code == "p_recognized"


def test_rationale_code_none_when_all_codes_absent() -> None:
    """Returns None when no repetition carries a rationale_code."""
    parsed_results = [
        {"verdict": "FAIL"},
        {"verdict": "FAIL"},
    ]
    verdict_str = "FAIL"

    rationale_code = _source_rationale_code(parsed_results, verdict_str)

    assert rationale_code is None


def test_rationale_code_single_repetition_pass() -> None:
    """Single PASS repetition → rationale_code from that repetition."""
    parsed_results = [{"verdict": "PASS", "rationale_code": "criteria_met"}]
    verdict_str = "PASS"

    rationale_code = _source_rationale_code(parsed_results, verdict_str)

    assert rationale_code == "criteria_met"


def test_rationale_code_skips_empty_string() -> None:
    """Empty string rationale_code is falsy and must be skipped."""
    parsed_results = [
        {"verdict": "FAIL", "rationale_code": ""},
        {"verdict": "FAIL", "rationale_code": "f_real"},
    ]
    verdict_str = "FAIL"

    rationale_code = _source_rationale_code(parsed_results, verdict_str)

    assert rationale_code == "f_real"
