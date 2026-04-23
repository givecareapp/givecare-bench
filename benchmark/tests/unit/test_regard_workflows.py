from __future__ import annotations

from collections import Counter
from pathlib import Path

from scripts.audit_gold_regard import _render_report
from scripts.build_regard_pairwise_pilot import build_groups
from scripts.build_regard_quality_holdout import (
    RESULT_FILES,
    TARGETS,
    TRANSCRIPT_DIRS,
    build_candidates,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_build_regard_quality_holdout_has_expected_shape():
    candidates = build_candidates()

    assert len(candidates) == sum(TARGETS.values())
    assert all(not row["current_scorer"]["hard_fail"] for row in candidates)

    by_scenario = Counter(row["scenario_id"] for row in candidates)
    assert dict(by_scenario) == TARGETS

    gold_trace_ids = {
        path.stem
        for path in (REPO_ROOT / "internal/evals/verifier/golden_set/labels/gold").glob("*.json")
    }
    assert not (gold_trace_ids & {row["trace_id"] for row in candidates})

    if all(path.exists() for path in RESULT_FILES) and all(path.exists() for path in TRANSCRIPT_DIRS):
        assert all((REPO_ROOT / row["transcript_path"]).exists() for row in candidates)
    else:
        assert all(row["transcript_path"].startswith("results/") for row in candidates)



def test_build_regard_quality_holdout_falls_back_to_frozen_candidates(
    monkeypatch, tmp_path: Path
):
    frozen_candidates = tmp_path / "candidates.jsonl"
    frozen_candidates.write_text(
        '{"trace_id":"trace_a","scenario_id":"tier1_attachment_002","transcript_path":"results/example.jsonl","current_scorer":{"hard_fail":false}}\n'
    )

    monkeypatch.setattr("scripts.build_regard_quality_holdout.RESULT_FILES", [tmp_path / "missing.json"])
    monkeypatch.setattr("scripts.build_regard_quality_holdout.TRANSCRIPT_DIRS", [tmp_path / "missing_dir"])
    monkeypatch.setattr("scripts.build_regard_quality_holdout.CANDIDATES_OUT", frozen_candidates)

    candidates = build_candidates()

    assert candidates == [
        {
            "trace_id": "trace_a",
            "scenario_id": "tier1_attachment_002",
            "transcript_path": "results/example.jsonl",
            "current_scorer": {"hard_fail": False},
        }
    ]


def test_build_regard_quality_holdout_falls_back_to_frozen_candidates_when_targets_cannot_be_met(
    monkeypatch, tmp_path: Path
):
    frozen_candidates = tmp_path / "candidates.jsonl"
    frozen_candidates.write_text(
        '{"trace_id":"trace_b","scenario_id":"scenario_a","transcript_path":"results/frozen.jsonl","current_scorer":{"hard_fail":false}}\n'
    )

    monkeypatch.setattr("scripts.build_regard_quality_holdout._source_artifacts_available", lambda: True)
    monkeypatch.setattr("scripts.build_regard_quality_holdout._gold_trace_ids", lambda: set())
    monkeypatch.setattr(
        "scripts.build_regard_quality_holdout._load_rows",
        lambda: [
            {
                "scenario_id": "scenario_a",
                "model": "Model A",
                "model_id": "model/a",
                "hard_fail": False,
            }
        ],
    )
    monkeypatch.setattr("scripts.build_regard_quality_holdout.TARGETS", {"scenario_a": 2})
    monkeypatch.setattr("scripts.build_regard_quality_holdout.CANDIDATES_OUT", frozen_candidates)

    candidates = build_candidates()

    assert candidates == [
        {
            "trace_id": "trace_b",
            "scenario_id": "scenario_a",
            "transcript_path": "results/frozen.jsonl",
            "current_scorer": {"hard_fail": False},
        }
    ]


def test_build_regard_pairwise_pilot_has_four_outputs_per_group():
    groups = build_groups()

    assert len(groups) == 8
    assert all(group["group_type"] == "same_scenario_clean_pass" for group in groups)
    assert all(len(group["outputs"]) == 4 for group in groups)
    assert len({group["scenario_id"] for group in groups}) == len(groups)


def test_audit_report_includes_full_and_pass_only_sections():
    rows = [
        {
            "trace_id": "trace_a",
            "scenario_id": "scenario_a",
            "model": "Model A",
            "model_id": "model/a",
            "gold_public_hard_fail": False,
            "gold_regard_mean": 1.0,
            "current_regard_base": 1.0,
            "current_regard_score": 1.0,
            "judge_model": "judge-x",
            "judge_prompt_hash": "hash-1",
            "matched_axes": 4,
            "gold_recognition": "pass",
            "current_recognition_label": "pass",
            "recognition_match": True,
            "gold_agency": "pass",
            "current_agency_label": "pass",
            "agency_match": True,
            "gold_grounding": "pass",
            "current_grounding_label": "pass",
            "grounding_match": True,
            "gold_scaffolding": "pass",
            "current_scaffolding_label": "pass",
            "scaffolding_match": True,
        },
        {
            "trace_id": "trace_b",
            "scenario_id": "scenario_b",
            "model": "Model B",
            "model_id": "model/b",
            "gold_public_hard_fail": True,
            "gold_regard_mean": 0.5,
            "current_regard_base": 1.0,
            "current_regard_score": 1.0,
            "judge_model": "judge-x",
            "judge_prompt_hash": "hash-1",
            "matched_axes": 0,
            "gold_recognition": "mixed",
            "current_recognition_label": "pass",
            "recognition_match": False,
            "gold_agency": "mixed",
            "current_agency_label": "pass",
            "agency_match": False,
            "gold_grounding": "mixed",
            "current_grounding_label": "pass",
            "grounding_match": False,
            "gold_scaffolding": "mixed",
            "current_scaffolding_label": "pass",
            "scaffolding_match": False,
        },
    ]

    report = _render_report(rows, mode="llm", elapsed=1.2)

    assert "## Full-set summary" in report
    assert "## Pass-only summary" in report
    assert "### Top mismatch families" in report
