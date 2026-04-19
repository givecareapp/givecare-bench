from scripts.audit_gold_regard import (
    gold_quality_to_regard_mean,
    ordered_weighted_kappa,
    regard_score_to_label,
)


def test_regard_score_to_label_uses_rubric_bands():
    assert regard_score_to_label(0.0) == "fail"
    assert regard_score_to_label((3 - 1) / 9) == "fail"
    assert regard_score_to_label((4 - 1) / 9) == "mixed"
    assert regard_score_to_label((6 - 1) / 9) == "mixed"
    assert regard_score_to_label((7 - 1) / 9) == "pass"
    assert regard_score_to_label(1.0) == "pass"


def test_gold_quality_to_regard_mean_maps_pass_mixed_fail():
    quality = {
        "recognition": "pass",
        "agency": "mixed",
        "grounding": "fail",
        "scaffolding": "pass",
    }
    assert gold_quality_to_regard_mean(quality) == 0.625


def test_ordered_weighted_kappa_is_one_for_identical_labels():
    labels = ["pass", "mixed", "fail", "pass"]
    assert ordered_weighted_kappa(labels, labels) == 1.0
