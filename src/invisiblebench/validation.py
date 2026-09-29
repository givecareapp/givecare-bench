"""Read frozen research expectations; they never enter runtime verdict composition."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from invisiblebench.judge import _conversations, _read_ref, json_bytes, sha256
from invisiblebench.models.scan import (
    Digest,
    Judgment,
    MemoryContext,
    Record,
    ScanPlan,
    Text,
    Verdict,
)


class Expectation(Record):
    model_id: Text
    scenario_id: Text
    check_id: Text
    transcript_sha256: Digest
    evidence_context_sha256: Digest
    check_sha256: Digest
    expected: Verdict
    basis: Literal["controlled_fixture", "source_evidence", "independent_review"]
    source: Text
    author: Text
    reason: Text

    @property
    def key(self) -> tuple[str, str, str]:
        return self.model_id, self.scenario_id, self.check_id


def evidence_context_hash(transcript_sha256: str, memory: MemoryContext) -> str:
    return sha256(
        json_bytes(
            {
                "transcript_sha256": transcript_sha256,
                "memory": memory.model_dump(mode="json"),
            }
        )
    )


def evidence_context_hashes(bundle: Path, plan: ScanPlan) -> dict[tuple[str, str], str]:
    conversations = _conversations(bundle, plan)
    return {
        (ref.model_id, ref.scenario_id): evidence_context_hash(
            ref.sha256, conversations[ref.model_id, ref.scenario_id][1]
        )
        for ref in plan.transcripts
    }


def validate_expectations(labels: list[Expectation]) -> list[Expectation]:
    identities = [
        (label.key, label.transcript_sha256, label.evidence_context_sha256, label.check_sha256)
        for label in labels
    ]
    if len(identities) != len(set(identities)):
        raise ValueError("duplicate expectation")
    return labels


def load_expectations(path: Path) -> list[Expectation]:
    return validate_expectations(
        [
            Expectation.model_validate_json(line)
            for line in path.read_bytes().splitlines()
            if line.strip()
        ]
    )


def frozen_expectations(bundle: Path, plan: ScanPlan) -> list[Expectation]:
    """Optional research rows travel in the already hash-bound source summaries."""
    labels = []
    for source in plan.sources:
        summary = json.loads(_read_ref(bundle, source.summary))
        if "research_expectations" not in summary:
            continue
        rows = summary["research_expectations"]
        if not isinstance(rows, list) or not rows:
            raise ValueError("research_expectations must be a non-empty list")
        selected = {(ref.model_id, ref.scenario_id) for ref in source.transcripts}
        labels.extend(
            label for row in rows if (label := Expectation.model_validate(row)).key[:2] in selected
        )
    return validate_expectations(labels)


def expectation_agreement(
    plan: ScanPlan,
    judgments: list[Judgment],
    labels: list[Expectation],
    contexts: dict[tuple[str, str], str],
) -> dict[str, Any]:
    refs = {(ref.model_id, ref.scenario_id): ref.sha256 for ref in plan.transcripts}
    definitions = {c.id: sha256(json_bytes(c.model_dump(mode="json"))) for c in plan.checks}
    recorded = {j.key: j.verdict.value for j in judgments}
    matched, excluded = [], []
    for label in labels:
        if (
            label.key not in recorded
            or refs.get(label.key[:2]) != label.transcript_sha256
            or contexts.get(label.key[:2]) != label.evidence_context_sha256
            or definitions.get(label.check_id) != label.check_sha256
        ):
            excluded.append(
                [
                    *label.key,
                    label.transcript_sha256,
                    label.evidence_context_sha256,
                    label.check_sha256,
                ]
            )
            continue
        matched.append(
            {
                "model_id": label.model_id,
                "scenario_id": label.scenario_id,
                "check_id": label.check_id,
                "expected": label.expected.value,
                "observed": recorded[label.key],
                "basis": label.basis,
                "source": label.source,
                "author": label.author,
                "reason": label.reason,
            }
        )
    return {
        "labeled_judgments": len(matched),
        "labeled_checks": sorted({row["check_id"] for row in matched}),
        "unlabeled_judgments": len(judgments) - len(matched),
        "mismatches": sum(row["expected"] != row["observed"] for row in matched),
        "unbound_expectations": excluded,
        "transitions": dict(Counter(f"{r['expected']}->{r['observed']}" for r in matched)),
        "false_pass": sum(r["expected"] == "FAIL" and r["observed"] == "PASS" for r in matched),
        "false_fail": sum(r["expected"] == "PASS" and r["observed"] == "FAIL" for r in matched),
        "unresolved": sum(r["observed"] == "UNCLEAR" for r in matched),
        "rows": matched,
    }


def validation_agreement(
    bundle: Path, plan: ScanPlan, judgments: list[Judgment]
) -> dict[str, Any] | None:
    labels = frozen_expectations(bundle, plan)
    if not labels:
        return None
    report = expectation_agreement(plan, judgments, labels, evidence_context_hashes(bundle, plan))
    if report["unbound_expectations"] or not report["labeled_judgments"]:
        raise ValueError("frozen expectations must bind to transcript, evidence context, and check")
    return report
