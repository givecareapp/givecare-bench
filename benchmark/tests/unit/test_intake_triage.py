"""Triage suggests; it never decides, and it never touches `incidents.jsonl`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.intake.triage import run_triage


class FakeTriageClient:
    """Scripted answers keyed by incident_id; records every call for inspection."""

    def __init__(
        self,
        *,
        triage_answers: dict[str, dict[str, Any]],
        duplicate_probabilities: dict[str, list[float]],
    ) -> None:
        self.triage_answers = triage_answers
        self.duplicate_probabilities = duplicate_probabilities
        self.calls: list[dict[str, Any]] = []

    def ask_typed(self, *, model: str, state: Any, questions: dict[str, Any]) -> dict[str, Any]:
        self.calls.append({"model": model, "state": state, "questions": questions})
        if "check" in questions:
            incident_id = state["incident_id"]
            scripted = self.triage_answers[incident_id]
            return {
                "model": "fake-judge",
                "input_tokens": 100,
                "answers": {
                    "check": {
                        "type": "choice",
                        "choice": scripted["check"],
                        "probabilities": {scripted["check"]: scripted["check_confidence"]},
                        "confidence": scripted["check_confidence"],
                    },
                    "fits_any": {"type": "noul", "noul": scripted["fits_any"]},
                    "severity": {
                        "type": "score",
                        "score": scripted["severity"],
                        "probabilities": {},
                        "confidence": scripted["severity_confidence"],
                    },
                    "route": {
                        "type": "choice",
                        "choice": scripted["route"],
                        "probabilities": {scripted["route"]: scripted["route_confidence"]},
                        "confidence": scripted["route_confidence"],
                    },
                },
            }
        # A duplicate-detection request: one noul per existing candidate.
        incident_id = state["new"]["incident_id"]
        probabilities = self.duplicate_probabilities.get(incident_id, [])
        answers = {
            key: {"type": "noul", "noul": probabilities[int(key.split("_")[1])]}
            for key in questions
        }
        return {"model": "fake-judge", "input_tokens": 20, "answers": answers}


def _incident(incident_id: str, disposition: str) -> dict[str, Any]:
    return {
        "schema": "invisiblebench-incident/v1",
        "incident_id": incident_id,
        "source": {"kind": "expert_review", "reference": f"review:{incident_id}", "deidentified": True},
        "failure": "The response minimized a caregiver's stated burden.",
        "caregiver_context": "A caregiver described sustained overload.",
        "layer": "care",
        "dimension": "attunement",
        "frequency": {"observations": 1, "window": "2026-Q3"},
        "consequence": "moderate",
        "owner": "benchmark-maintainer",
        "disposition": disposition,
    }


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n")


def test_triage_rows_have_the_full_suggestion_shape(tmp_path: Path) -> None:
    incidents_path = tmp_path / "incidents.jsonl"
    existing = _incident("INC-existing", "candidate")
    confident = _incident("INC-confident", "triage")
    _write_jsonl(incidents_path, [existing, confident])

    client = FakeTriageClient(
        triage_answers={
            "INC-confident": {
                "check": "crisis.fixture-cue",
                "check_confidence": 0.9,
                "fits_any": 0.8,
                "severity": 3.0,
                "severity_confidence": 0.75,
                "route": "llm_primary",
                "route_confidence": 0.85,
            }
        },
        duplicate_probabilities={"INC-confident": [0.9]},
    )

    rows, summary = run_triage(client, incidents_path=incidents_path)

    assert len(rows) == 1
    row = rows[0]
    assert set(row) == {
        "incident_id",
        "suggested_check",
        "check_confidence",
        "fits_any",
        "severity_score",
        "severity_confidence",
        "suggested_route",
        "duplicates",
        "model",
        "input_tokens",
    }
    assert row["incident_id"] == "INC-confident"
    assert row["suggested_check"] == "crisis.fixture-cue"
    assert row["check_confidence"] == 0.9
    assert row["fits_any"] is True
    assert row["severity_score"] == 3.0
    assert row["suggested_route"] == "llm_primary"
    assert row["model"] == "fake-judge"
    assert row["input_tokens"] == 120  # 100 for the triage request + 20 for the duplicate check
    assert "Triaged 1 of 2" in summary


def test_low_confidence_choices_are_gated_to_review(tmp_path: Path) -> None:
    incidents_path = tmp_path / "incidents.jsonl"
    unsure = _incident("INC-unsure", "observed")
    _write_jsonl(incidents_path, [unsure])

    client = FakeTriageClient(
        triage_answers={
            "INC-unsure": {
                "check": "attunement.fixture-required",
                "check_confidence": 0.4,  # below the 0.6 floor
                "fits_any": 0.5,
                "severity": 1.0,
                "severity_confidence": 0.5,
                "route": "llm_primary",
                "route_confidence": 0.55,  # below the 0.6 floor
            }
        },
        duplicate_probabilities={},
    )

    rows, summary = run_triage(client, incidents_path=incidents_path)

    row = rows[0]
    assert row["suggested_check"] == "review"
    assert row["check_confidence"] == 0.4  # the raw confidence is still reported
    assert row["suggested_route"] == "review"
    assert row["duplicates"] == []
    assert "Flagged for human review (low confidence): 1" in summary


def test_duplicates_are_flagged_only_above_the_probability_floor(tmp_path: Path) -> None:
    incidents_path = tmp_path / "incidents.jsonl"
    existing_a = _incident("INC-existing-a", "candidate")
    existing_b = _incident("INC-existing-b", "accepted")
    new = _incident("INC-new", "triage")
    _write_jsonl(incidents_path, [existing_a, existing_b, new])

    client = FakeTriageClient(
        triage_answers={
            "INC-new": {
                "check": "identity.fixture-prohibition",
                "check_confidence": 0.7,
                "fits_any": 0.9,
                "severity": 2.0,
                "severity_confidence": 0.8,
                "route": "deterministic",
                "route_confidence": 0.7,
            }
        },
        duplicate_probabilities={"INC-new": [0.9, 0.5]},  # only the first clears 0.65
    )

    rows, _summary = run_triage(client, incidents_path=incidents_path)

    assert rows[0]["duplicates"] == [{"incident_id": "INC-existing-a", "probability": 0.9}]


def test_triage_never_writes_to_the_incidents_file(tmp_path: Path) -> None:
    incidents_path = tmp_path / "incidents.jsonl"
    record = _incident("INC-readonly", "triage")
    _write_jsonl(incidents_path, [record])
    original_bytes = incidents_path.read_bytes()

    client = FakeTriageClient(
        triage_answers={
            "INC-readonly": {
                "check": "crisis.fixture-cue",
                "check_confidence": 0.9,
                "fits_any": 0.9,
                "severity": 4.0,
                "severity_confidence": 0.9,
                "route": "llm_primary",
                "route_confidence": 0.9,
            }
        },
        duplicate_probabilities={},
    )

    run_triage(client, incidents_path=incidents_path)

    assert incidents_path.read_bytes() == original_bytes


def test_triage_skips_records_that_are_not_observed_or_triage(tmp_path: Path) -> None:
    incidents_path = tmp_path / "incidents.jsonl"
    rejected = _incident("INC-rejected", "rejected")
    _write_jsonl(incidents_path, [rejected])

    client = FakeTriageClient(triage_answers={}, duplicate_probabilities={})

    rows, summary = run_triage(client, incidents_path=incidents_path)

    assert rows == []
    assert client.calls == []
    assert "Triaged 0 of 1" in summary
