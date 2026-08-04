"""Shared review-batch blindness contract."""

from __future__ import annotations

from typing import Any

# Every field a prior label could hide in. The batch exporters rebuild cards
# from an allowlist and reject this denylist; the review server applies the
# same predicate before calling a batch active.
BANNED_LABEL_KEYS: frozenset[str] = frozenset(
    {
        "verdict",
        "final_gold",
        "final_verdict",
        "gold",
        "gold_verdict",
        "label",
        "human",
        "human_verdict",
        "annotator_1",
        "annotator_2",
        "annotator_1_id",
        "annotator_2_id",
        "annotator_1_verdict",
        "annotator_2_verdict",
        "annotator_1_note",
        "annotator_2_note",
        "adjudicated_verdict",
        "adjudicated_by",
        "adjudication_notes",
        "reps",
        "post_guard",
        "pre_guard",
        "any_fail",
        "guard_fired",
        "rationale_code",
        "rationale",
        "confidence",
        "pass_rule_result",
        "fail_rule_result",
        "score",
        "overall_score",
        "hard_fail_reason",
    }
)


def banned_label_keys(value: Any) -> set[str]:
    """Return forbidden label/answer keys found anywhere in ``value``."""
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in BANNED_LABEL_KEYS:
                found.add(str(key))
            found.update(banned_label_keys(item))
    elif isinstance(value, list):
        for item in value:
            found.update(banned_label_keys(item))
    return found
