from __future__ import annotations

from pathlib import Path

from scripts.review_ui.export_scan_adjudication import (
    _banned_keys,
    build_review_artifacts,
    render_review_markdown,
    target_reasons,
)


def _result(**overrides):
    result = {
        "mode_id": "crisis.passive-ideation",
        "eligible": True,
        "verdict": "PASS",
        "adjudication_required": False,
        "evidence": [],
        "rationale_code": "machine_code",
        "extra": {},
    }
    result.update(overrides)
    return result


def test_target_reasons_are_bounded_to_unresolved_or_escalated_results() -> None:
    assert target_reasons(_result()) == []
    assert target_reasons(_result(eligible=False, verdict="UNCLEAR")) == []
    assert target_reasons(_result(verdict="UNCLEAR")) == ["unresolved_unclear"]
    assert target_reasons(_result(verdict="FAIL")) == ["fail_without_evidence"]
    assert target_reasons(
        _result(adjudication_required=True, extra={"automated_adjudication": {"resolved": True}})
    ) == ["adjudication_required", "machine_vote_disagreement"]


def test_blind_batch_excludes_model_and_machine_judgment() -> None:
    rows = [
        {
            "model_id": "provider/secret-model",
            "scenario_id": "safety_secret_scenario",
            "transcript_path": "/private/transcript.jsonl",
            "mode_results": [
                _result(
                    verdict="FAIL",
                    adjudication_required=True,
                    evidence=[{"role": "assistant", "turn": 1, "quote": "bad"}],
                )
            ],
        }
    ]

    def transcript_loader(_path: Path):
        return [
            {"turn": 1, "role": "user", "content": "Help."},
            {"turn": 1, "role": "assistant", "content": "I am here."},
        ]

    batch, source_map = build_review_artifacts(
        rows,
        scan_sha256="a" * 64,
        transcript_loader=transcript_loader,
        rubric_loader=lambda mode_id: {
            "id": mode_id,
            "name": "Passive ideation",
            "severity": "S5",
            "pass_rule": "Routes safely.",
            "fail_rule": "Misses the cue.",
        },
        cue_index={},
    )

    assert len(batch) == 1
    assert not _banned_keys(batch)
    serialized = str(batch)
    assert "provider/secret-model" not in serialized
    assert "safety_secret_scenario" not in serialized
    assert "machine_code" not in serialized
    assert source_map["cards"][0]["model_id"] == "provider/secret-model"
    assert source_map["cards"][0]["previous_verdict"] == "FAIL"
    review = render_review_markdown(batch)
    assert "Card 1" in review
    assert "provider/secret-model" not in review
    assert "safety_secret_scenario" not in review
