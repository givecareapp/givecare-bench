"""Delivery artifact contract tests.

These projections are consumed by other repos, so they must stay in lockstep
with the authoritative check YAMLs instead of preserving stale generated state.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from delivery.contrast_analysis import CONTRAST_ANALYSIS_SCHEMA, analyze
from delivery.export_taxonomy_snapshot import build_snapshot
from invisiblebench.evaluation.check_registry import load_checks
from invisiblebench.evaluation.verifiers.base import GATE_SEVERITIES
from invisiblebench.models.results import PUBLIC_SCORE_MODEL, RAW_RESULT_SURFACE, RAW_SCORE_MODEL

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_checked_in_taxonomy_snapshot_matches_generated_checks() -> None:
    checked_in = (REPO_ROOT / "delivery" / "taxonomy-snapshot.yaml").read_text()

    assert checked_in == build_snapshot()


def test_taxonomy_snapshot_has_exactly_current_check_ids() -> None:
    modes, _routing = load_checks()
    snapshot = yaml.safe_load((REPO_ROOT / "delivery" / "taxonomy-snapshot.yaml").read_text())
    snapshot_ids = {entry["id"] for entry in snapshot["modes"]}

    assert snapshot_ids == set(modes)


def test_taxonomy_snapshot_uses_safety_care_contract_fields() -> None:
    snapshot = yaml.safe_load((REPO_ROOT / "delivery" / "taxonomy-snapshot.yaml").read_text())
    entries = snapshot["modes"]

    assert entries
    for entry in entries:
        assert set(entry) == {
            "id",
            "name",
            "layer",
            "dimension",
            "severity",
            "scope",
            "claim_status",
        }
        assert entry["layer"] in {"safety", "care"}
        assert entry["claim_status"] in {"claim_ready", "not_claim_ready"}
        assert "primary_bucket" not in entry
        assert "hard_fail" not in entry


def test_check_yaml_has_no_retired_source_fields() -> None:
    """Source checks belong to Safety/Care; retired bucket/code fields stay archived."""
    offenders: list[str] = []
    retired_fields = {"primary_bucket", "legacy_bucket", "legacy_id"}
    for check_path in sorted((REPO_ROOT / "checks").rglob("*.yaml")):
        if check_path.name.startswith("_"):
            continue
        data = yaml.safe_load(check_path.read_text()) or {}
        rel = str(check_path.relative_to(REPO_ROOT))
        present = sorted(retired_fields.intersection(data))
        if present:
            offenders.append(f"{rel}: {present}")

    assert offenders == []


@pytest.mark.parametrize("retired_field", ["primary_bucket", "legacy_bucket", "legacy_id"])
def test_check_loader_rejects_bucket_source_fields(
    tmp_path: Path, retired_field: str
) -> None:
    check_path = tmp_path / "retired-source.yaml"
    check_path.write_text(
        f"""
id: retired-source
name: Retired source shape
{retired_field}: A
severity: S5
scope: scenario
routing:
  scorer: regex
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=retired_field):
        load_checks(tmp_path)


def test_load_checks_exposes_safety_care_identity_without_bucket_aliases() -> None:
    modes, _routing = load_checks()

    assert modes
    for check_id, mode in modes.items():
        assert mode["id"] == check_id
        assert mode["layer"] in {"safety", "care"}
        assert isinstance(mode["dimension"], str)
        assert "legacy_bucket" not in mode
        assert "primary_bucket" not in mode
        assert "legacy_id" not in mode


def test_checks_meta_matches_current_taxonomy_counts() -> None:
    modes, _routing = load_checks()
    meta = yaml.safe_load((REPO_ROOT / "checks" / "_meta.yaml").read_text())
    metadata = meta["checks_header"]["metadata"]

    claim_capable = [
        mode
        for mode in modes.values()
        if mode.get("hard_fail") or mode.get("severity") in GATE_SEVERITIES
    ]

    assert metadata["total_modes"] == len(modes)
    assert metadata["active_modes"] == len(modes)
    assert metadata["gate_modes"] == len(claim_capable)
    assert metadata["quality_modes"] == len(modes) - len(claim_capable)


def test_slug_map_check_file_paths_exist() -> None:
    slug_map = json.loads((REPO_ROOT / "delivery" / "slug-map.json").read_text())
    missing = [
        entry
        for entry in slug_map
        if str(entry.get("file") or "").startswith("checks/")
        and not (REPO_ROOT / entry["file"]).is_file()
    ]

    assert missing == []


def test_slug_map_has_exactly_current_check_slugs() -> None:
    modes, _routing = load_checks()
    slug_map = json.loads((REPO_ROOT / "delivery" / "slug-map.json").read_text())
    slugs = {entry["slug"] for entry in slug_map}

    assert slugs == set(modes)


def test_slug_map_has_no_retired_code_fields() -> None:
    slug_map = json.loads((REPO_ROOT / "delivery" / "slug-map.json").read_text())

    assert all("legacy_id" not in entry for entry in slug_map)


def test_contrast_analysis_labels_raw_internal_fields() -> None:
    groups = {
        "anchor": {"contrast_group": "crisis-passive", "contrast_variable": "anchor"},
        "variant": {"contrast_group": "crisis-passive", "contrast_variable": "religious_frame"},
    }
    findings = analyze(
        [
            {"model": "model-a", "scenario_id": "anchor", "overall_score": 0.9, "hard_fail": False},
            {"model": "model-a", "scenario_id": "variant", "overall_score": 0.5, "hard_fail": True},
        ],
        groups,
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding["schema"] == CONTRAST_ANALYSIS_SCHEMA
    assert finding["analysis_surface"] == RAW_RESULT_SURFACE
    assert finding["score_model"] == RAW_SCORE_MODEL
    assert finding["public_score_model"] == PUBLIC_SCORE_MODEL
    assert finding["anchor_raw_overall_score"] == 0.9
    assert finding["variant_raw_overall_score"] == 0.5
    assert finding["anchor_raw_hard_fail"] is False
    assert finding["variant_raw_hard_fail"] is True
    assert "RAW_SCORE_DRIFT: 0.40 gap between anchor and religious frame" in finding["flags"]

    assert "anchor_score" not in finding
    assert "variant_score" not in finding
    assert "anchor_hard_fail" not in finding
    assert "variant_hard_fail" not in finding
