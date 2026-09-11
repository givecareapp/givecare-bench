"""Contrast-delta reporting over the judgment ledger."""

import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[3] / "scripts" / "contrast_delta.py"
spec = importlib.util.spec_from_file_location("contrast_delta", MODULE_PATH)
contrast_delta = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contrast_delta)


METADATA = {
    "anchor_one": {"contrast_group": "pressure_probe", "contrast_variable": "anchor"},
    "variant_one": {"contrast_group": "pressure_probe", "contrast_variable": "pressure_removed"},
    "orphan_one": {"contrast_group": "lonely_probe", "contrast_variable": "cue_removed"},
}


def test_reports_only_differing_checks():
    verdicts = {
        ("model/a", "anchor_one"): {"scope.prescribing": "FAIL", "crisis.direct-ideation": "PASS"},
        ("model/a", "variant_one"): {"scope.prescribing": "PASS", "crisis.direct-ideation": "PASS"},
    }
    groups = contrast_delta.group_deltas(verdicts, METADATA)
    comparison = groups["pressure_probe"]["comparisons"][0]
    assert groups["pressure_probe"]["anchor"] == "anchor_one"
    assert comparison["compared_checks"] == 2
    assert comparison["differing_checks"] == 1
    assert comparison["differences"] == [
        {"check_id": "scope.prescribing", "anchor": "FAIL", "variant": "PASS"}
    ]


def test_compares_within_one_model_only():
    verdicts = {
        ("model/a", "anchor_one"): {"scope.prescribing": "FAIL"},
        ("model/b", "variant_one"): {"scope.prescribing": "PASS"},
    }
    groups = contrast_delta.group_deltas(verdicts, METADATA)
    assert groups["pressure_probe"]["anchor"] is None
    assert groups["pressure_probe"]["comparisons"] == []


def test_unpaired_checks_are_skipped():
    verdicts = {
        ("model/a", "anchor_one"): {"scope.prescribing": "FAIL"},
        ("model/a", "variant_one"): {"scope.prescribing": "FAIL", "identity.feelings-claim": "PASS"},
    }
    comparison = contrast_delta.group_deltas(verdicts, METADATA)["pressure_probe"]["comparisons"][0]
    assert comparison["compared_checks"] == 1
    assert comparison["differing_checks"] == 0


def test_variant_without_anchor_reports_missing_anchor():
    verdicts = {("model/a", "orphan_one"): {"scope.prescribing": "PASS"}}
    groups = contrast_delta.group_deltas(verdicts, METADATA)
    assert groups["lonely_probe"] == {"anchor": None, "comparisons": []}


def test_corpus_groups_each_declare_one_anchor():
    metadata = contrast_delta.contrast_metadata()
    assert metadata, "the corpus declares at least one contrast group"
    anchors = {}
    for scenario_id, entry in metadata.items():
        if entry["contrast_variable"] == contrast_delta.ANCHOR:
            group = entry["contrast_group"]
            assert group not in anchors, f"{group} declares more than one anchor"
            anchors[group] = scenario_id
    missing = {entry["contrast_group"] for entry in metadata.values()} - set(anchors)
    assert not missing, f"contrast groups without an anchor: {sorted(missing)}"


def test_render_names_a_group_without_an_anchor():
    report = {"bundle": "x", "groups": {"lonely_probe": {"anchor": None, "comparisons": []}}}
    assert "MISSING" in contrast_delta.render(report)


@pytest.mark.parametrize("report", [{"bundle": "x", "groups": {}}])
def test_render_handles_an_empty_report(report):
    assert "no contrast-grouped scenarios" in contrast_delta.render(report)
