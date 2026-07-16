#!/usr/bin/env python3
"""Validate the private incident-to-check registry without reading transcripts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from invisiblebench.evaluation.check_registry import (  # noqa: E402
    CARE_DIMENSIONS,
    SAFETY_DIMENSIONS,
)

SCHEMA = "invisiblebench-incident/v1"
DISPOSITIONS = {"observed", "triage", "candidate", "accepted", "rejected"}
CONSEQUENCES = {"low", "moderate", "high", "critical"}
CANDIDATE_ROUTES = {
    "deterministic",
    "regex_with_llm_edge",
    "llm_primary",
    "longitudinal_trace",
}
OPAQUE_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")


def _nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_incident(record: object) -> list[str]:
    """Return validation errors for one de-identified registry record."""
    if not isinstance(record, dict):
        return ["record must be an object"]

    errors: list[str] = []
    required_strings = (
        "incident_id",
        "failure",
        "caregiver_context",
        "layer",
        "dimension",
        "consequence",
        "owner",
        "disposition",
    )
    if record.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA!r}")
    errors.extend(
        f"{field} must be a non-empty string"
        for field in required_strings
        if not _nonempty_string(record.get(field))
    )

    layer = record.get("layer")
    dimension = record.get("dimension")
    valid_dimensions = SAFETY_DIMENSIONS if layer == "safety" else CARE_DIMENSIONS
    if layer not in {"safety", "care"}:
        errors.append("layer must be 'safety' or 'care'")
    elif dimension not in valid_dimensions:
        errors.append(f"dimension {dimension!r} is invalid for layer {layer!r}")
    if record.get("consequence") not in CONSEQUENCES:
        errors.append(f"consequence must be one of {sorted(CONSEQUENCES)}")
    if record.get("disposition") not in DISPOSITIONS:
        errors.append(f"disposition must be one of {sorted(DISPOSITIONS)}")

    source = record.get("source")
    if not isinstance(source, dict):
        errors.append("source must be an object")
    else:
        if not _nonempty_string(source.get("kind")):
            errors.append("source.kind must be a non-empty string")
        if not isinstance(source.get("reference"), str) or not OPAQUE_REFERENCE.fullmatch(
            source["reference"]
        ):
            errors.append("source.reference must be an opaque reference, not source text")
        if source.get("deidentified") is not True:
            errors.append("source.deidentified must be true")

    frequency = record.get("frequency")
    if not isinstance(frequency, dict):
        errors.append("frequency must be an object")
        observations = 0
    else:
        observations = frequency.get("observations")
        if isinstance(observations, bool) or not isinstance(observations, int) or observations < 1:
            errors.append("frequency.observations must be a positive integer")
            observations = 0
        if not _nonempty_string(frequency.get("window")):
            errors.append("frequency.window must be a non-empty string")

    if record.get("disposition") in {"candidate", "accepted"}:
        advancement = record.get("advancement")
        if not isinstance(advancement, dict):
            errors.append("candidate or accepted incidents require advancement")
        else:
            contrast = advancement.get("contrast_pair")
            if not isinstance(contrast, dict) or not all(
                _nonempty_string(contrast.get(field))
                for field in ("failure_ref", "comparison_ref")
            ):
                errors.append("advancement.contrast_pair requires two artifact references")
            if advancement.get("candidate_route") not in CANDIDATE_ROUTES:
                errors.append(
                    f"advancement.candidate_route must be one of {sorted(CANDIDATE_ROUTES)}"
                )
            for field in ("discriminating", "renderable_without_person_text", "privacy_reviewed"):
                if advancement.get(field) is not True:
                    errors.append(f"advancement.{field} must be true")
            if not _nonempty_string(advancement.get("rationale")):
                errors.append("advancement.rationale must be a non-empty string")
        if observations < 2 and record.get("consequence") not in {"high", "critical"}:
            errors.append("candidate advancement requires recurrence or high consequence")

    return errors


def validate_registry(path: Path) -> list[str]:
    """Return line-addressed errors for a JSONL registry."""
    errors: list[str] = []
    incident_ids: set[str] = set()
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_number}: invalid JSON: {exc.msg}")
            continue
        for error in validate_incident(record):
            errors.append(f"line {line_number}: {error}")
        if isinstance(record, dict) and _nonempty_string(record.get("incident_id")):
            incident_id = str(record["incident_id"])
            if incident_id in incident_ids:
                errors.append(f"line {line_number}: duplicate incident_id {incident_id!r}")
            incident_ids.add(incident_id)
    if not incident_ids and not errors:
        errors.append("registry has no incidents")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "registry",
        nargs="?",
        type=Path,
        default=REPO_ROOT / "intake" / "incidents.jsonl",
    )
    args = parser.parse_args(argv)
    try:
        errors = validate_registry(args.registry)
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if errors:
        print("Incident registry validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"Incident registry valid: {args.registry}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
