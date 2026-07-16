from __future__ import annotations

import json
from pathlib import Path

from scripts.intake.incident_registry import validate_incident, validate_registry


def _incident() -> dict:
    return {
        "schema": "invisiblebench-incident/v1",
        "incident_id": "INC-2026-001",
        "source": {
            "kind": "expert_review",
            "reference": "review:2026-07-16:001",
            "deidentified": True,
        },
        "failure": "The response minimized a caregiver's stated burden.",
        "caregiver_context": "A caregiver described sustained overload.",
        "layer": "care",
        "dimension": "attunement",
        "frequency": {"observations": 2, "window": "2026-Q3"},
        "consequence": "moderate",
        "owner": "benchmark-maintainer",
        "disposition": "candidate",
        "advancement": {
            "contrast_pair": {
                "failure_ref": "private:pair:001:a",
                "comparison_ref": "private:pair:001:b",
            },
            "candidate_route": "llm_primary",
            "discriminating": True,
            "renderable_without_person_text": True,
            "privacy_reviewed": True,
            "rationale": "Repeated and distinguishable from direct advice-first behavior.",
        },
    }


def test_incident_registry_accepts_a_deidentified_recurrent_candidate(tmp_path: Path) -> None:
    path = tmp_path / "incidents.jsonl"
    path.write_text(json.dumps(_incident()) + "\n")

    assert validate_registry(path) == []


def test_candidate_requires_recurrence_or_high_consequence() -> None:
    incident = _incident()
    incident["frequency"]["observations"] = 1

    assert "candidate advancement requires recurrence or high consequence" in validate_incident(
        incident
    )


def test_source_reference_cannot_contain_source_text() -> None:
    incident = _incident()
    incident["source"]["reference"] = "A caregiver said this exact sentence"

    assert "source.reference must be an opaque reference, not source text" in validate_incident(
        incident
    )


def test_registry_rejects_duplicate_incident_ids(tmp_path: Path) -> None:
    path = tmp_path / "incidents.jsonl"
    line = json.dumps(_incident())
    path.write_text(f"{line}\n{line}\n")

    assert "line 2: duplicate incident_id 'INC-2026-001'" in validate_registry(path)
