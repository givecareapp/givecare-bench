"""Blindness pin for the gold-card review export.

Task #16 requires reviewers to grade cold: the exported batch must carry the
check rubric and the transcript, and NONE of the prior labels (verdict,
annotator fields, judge outputs, adjudication notes). This test feeds
``build_card`` a synthetic source record that is *saturated* with every banned
field and asserts none of them survive into the exported card — recursively.

Synthetic fixture only: no real gold-card text appears here (the real cards are
contamination-sensitive and live under gitignored ``internal/``).
"""

from __future__ import annotations

from typing import Any

from scripts.review_ui.export_batch import BANNED_LABEL_KEYS, build_card, parse_turns

_WINDOW = "[Turn 1, USER]\nsynthetic user line\n[Turn 1, ASSISTANT]\nsynthetic reply\n"

# A source card poisoned with every label field a leak could ride on.
_POISONED_SOURCE = {
    "card_id": "crisis.synthetic__card_1",
    "mode_id": "crisis.synthetic",
    "transcript_window": _WINDOW,
    "verdict": "FAIL",
    "final_gold": "FAIL",
    "human": "FAIL",
    "annotator_1_verdict": "FAIL",
    "annotator_2_verdict": "UNCLEAR",
    "annotator_1_id": "human_a",
    "adjudicated_verdict": "FAIL",
    "adjudication_notes": "leak me",
    "reps": ["FAIL", "PASS"],
    "post_guard": "FAIL",
    "guard_fired": True,
    "rationale_code": "missed_cue",
    "confidence": 0.9,
    "_recovered_from": {"model": "synthetic-model", "scenario": "synthetic_scenario_001"},
}

_RUBRIC = {
    "id": "crisis.synthetic",
    "name": "synthetic_failure_mode",
    "severity": "S5",
    "scope": "trigger",
    "hard_fail": True,
    "pass_rule": "Assistant routes to support.",
    "fail_rule": "Assistant ignores the cue.",
}


def _keys_recursive(obj: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(obj, dict):
        for key, value in obj.items():
            keys.add(key)
            keys |= _keys_recursive(value)
    elif isinstance(obj, list):
        for item in obj:
            keys |= _keys_recursive(item)
    return keys


def _values_recursive(obj: Any) -> list[Any]:
    out: list[Any] = []
    if isinstance(obj, dict):
        for value in obj.values():
            out.extend(_values_recursive(value))
    elif isinstance(obj, list):
        for item in obj:
            out.extend(_values_recursive(item))
    else:
        out.append(obj)
    return out


def _build() -> dict[str, Any]:
    return build_card(
        card_id="crisis.synthetic__card_1",
        source_tags=["relabel-flagged"],
        recardable={"crisis.synthetic__card_1": _POISONED_SOURCE},
        gold_joined={},
        rubric_cache={"crisis.synthetic": _RUBRIC},
    )


def test_export_strips_every_banned_label_field() -> None:
    card = _build()
    leaked = _keys_recursive(card) & BANNED_LABEL_KEYS
    assert not leaked, f"banned label fields leaked into export: {sorted(leaked)}"


def test_export_carries_rubric_and_transcript() -> None:
    card = _build()
    assert card["card_id"] == "crisis.synthetic__card_1"
    assert card["check_id"] == "crisis.synthetic"
    assert card["check"]["pass_rule"] == "Assistant routes to support."
    assert card["check"]["fail_rule"] == "Assistant ignores the cue."
    assert card["transcript_window"] == _WINDOW
    assert [t["role"] for t in card["turns"]] == ["user", "assistant"]
    # Scenario id is recovered provenance, not a label.
    assert card["scenario_id"] == "synthetic_scenario_001"


def test_export_does_not_leak_verdict_values() -> None:
    card = _build()
    # The poisoned source labels were all FAIL/UNCLEAR; the rubric legitimately
    # contains no verdict tokens, so no bare verdict string should appear.
    values = [v for v in _values_recursive(card) if isinstance(v, str)]
    assert "missed_cue" not in values  # rationale_code must not survive
    assert "leak me" not in values  # adjudication note must not survive


def test_parse_turns_roundtrips_roles() -> None:
    turns = parse_turns(_WINDOW)
    assert turns == [
        {"turn": 1, "role": "user", "content": "synthetic user line"},
        {"turn": 1, "role": "assistant", "content": "synthetic reply"},
    ]
