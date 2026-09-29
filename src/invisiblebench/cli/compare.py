"""Compare two validated scans. Differences are observations, not judge accuracy."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from invisiblebench.evaluation.rules import probabilities, tri
from invisiblebench.judge import _read_ref, json_bytes, load_scan, sha256
from invisiblebench.models.scan import Digest, Record, Text, Verdict


class Expectation(Record):
    """Research labels bind to evidence and a requirement; runtime never reads them."""

    model_id: Text
    scenario_id: Text
    check_id: Text
    transcript_sha256: Digest
    check_sha256: Digest
    expected: Verdict
    basis: Literal["controlled_fixture", "source_evidence", "independent_review"]
    source: Text
    author: Text
    reason: Text

    @property
    def key(self):
        return self.model_id, self.scenario_id, self.check_id


def expectation_agreement(plan, judgments, labels):
    refs = {(ref.model_id, ref.scenario_id): ref.sha256 for ref in plan.transcripts}
    definitions = {c.id: sha256(json_bytes(c.model_dump(mode="json"))) for c in plan.checks}
    recorded = {j.key: j.verdict.value for j in judgments}
    matched, excluded = [], []
    for label in labels:
        if (label.key not in recorded
            or refs.get(label.key[:2]) != label.transcript_sha256
            or definitions.get(label.check_id) != label.check_sha256):
            excluded.append([*label.key, label.transcript_sha256, label.check_sha256])
            continue
        matched.append({
            "model_id": label.model_id, "scenario_id": label.scenario_id,
            "check_id": label.check_id, "expected": label.expected.value,
            "observed": recorded[label.key], "basis": label.basis,
            "source": label.source, "author": label.author, "reason": label.reason,
        })
    return {
        "labeled_judgments": len(matched),
        "unlabeled_judgments": len(judgments) - len(matched),
        "unbound_expectations": excluded,
        "transitions": dict(Counter(f"{r['expected']}->{r['observed']}" for r in matched)),
        "false_pass": sum(r['expected'] == 'FAIL' and r['observed'] == 'PASS' for r in matched),
        "false_fail": sum(r['expected'] == 'PASS' and r['observed'] == 'FAIL' for r in matched),
        "unresolved": sum(r['observed'] == 'UNCLEAR' for r in matched),
        "rows": matched,
    }


def scan_summary(bundle, plan, answers, judgments):
    counts = {v.value: sum(j.verdict == v for j in judgments) for v in Verdict}
    sources = []
    for source in plan.sources:
        manifest = json.loads(_read_ref(bundle, source.manifest))
        summary = json.loads(_read_ref(bundle, source.summary))
        sources.append({
            "run_id": manifest["run_id"],
            "planned_conversations": summary.get("expected_transcripts"),
            "generated_conversations": summary.get("transcript_count"),
            "evaluated_conversations": len(source.transcripts),
            "generation_cost_usd": summary.get("actual_cost_usd"),
            "generation_unknown_cost_calls": summary.get("unknown_calls_with_uncosted_usd"),
            "serving": manifest.get("transcript_policy", {}).get("serving"),
            "resolved_providers": summary.get("resolved_providers"),
        })
    return {
        "benchmark_version": plan.benchmark_version, "engine_version": plan.engine_version,
        "thresholds": plan.judge.thresholds.model_dump(),
        "conversations": len(plan.transcripts), "checks": len(plan.checks),
        "judgments": len(judgments), "counts": counts,
        "applicable": len(judgments) - counts["NOT_APPLICABLE"],
        "unclear_rate": counts["UNCLEAR"] / len(judgments) if judgments else None,
        "judge_cost_usd": sum(answer.cost_usd for answer in answers),
        "judge_requests": len(answers),
        "judge_errors": sum(answer.error is not None for answer in answers),
        "sources": sources,
    }


def compare_ledgers(old_bundle: Path, new_bundle: Path, *, expectations: Path | None = None) -> dict[str, Any]:
    old_plan, old_answers, old_judgments = load_scan(old_bundle, complete=True)
    new_plan, new_answers, new_judgments = load_scan(new_bundle, complete=True)
    old = {j.key: j for j in old_judgments}
    new = {j.key: j for j in new_judgments}
    shared = sorted(old.keys() & new.keys())
    old_transcripts = {(ref.model_id, ref.scenario_id): ref.sha256 for ref in old_plan.transcripts}
    new_transcripts = {(ref.model_id, ref.scenario_id): ref.sha256 for ref in new_plan.transcripts}
    if any(old_transcripts[k] != new_transcripts[k] for k in old_transcripts.keys() & new_transcripts.keys()):
        raise ValueError("judge comparison requires identical retained transcript bytes for shared conversations")
    flips = [
        {
            "model_id": key[0],
            "scenario_id": key[1],
            "check_id": key[2],
            "old": old[key].verdict.value,
            "new": new[key].verdict.value,
        }
        for key in shared
        if old[key].verdict != new[key].verdict
    ]
    prior = {a.key: a for a in old_answers if a.error is None}
    differences = []
    for answer in new_answers:
        before = prior.get(answer.key)
        if answer.error is not None or before is None or answer.input_sha256 != before.input_sha256:
            continue
        previous = probabilities(before.answers)
        for key, value in probabilities(answer.answers).items():
            differences.append(
                {
                    "question": key,
                    "delta": abs(value - previous[key]),
                    "band_changed": tri(value, new_plan.judge.thresholds)
                    != tri(previous[key], old_plan.judge.thresholds),
                }
            )
    agreement = None
    if expectations is not None:
        labels = [Expectation.model_validate_json(line) for line in expectations.read_bytes().splitlines() if line.strip()]
        identities = [(label.key, label.transcript_sha256, label.check_sha256) for label in labels]
        if len(identities) != len(set(identities)):
            raise ValueError("duplicate expectation")
        agreement = {
            "old": expectation_agreement(old_plan, old_judgments, labels),
            "new": expectation_agreement(new_plan, new_judgments, labels),
        }
        unbound = set(map(tuple, agreement['old']['unbound_expectations'])) & set(map(tuple, agreement['new']['unbound_expectations']))
        if unbound or not labels:
            raise ValueError("expectations must bind to a transcript and check in at least one scan")
    return {
        "expectation_agreement": agreement,
        "old": scan_summary(old_bundle, old_plan, old_answers, old_judgments),
        "new": scan_summary(new_bundle, new_plan, new_answers, new_judgments),
        "same_transcripts": old_transcripts == new_transcripts,
        "changed_checks": sorted(
            check.id for check in new_plan.checks
            if check.id in {old_check.id for old_check in old_plan.checks}
            and check != next(old_check for old_check in old_plan.checks if old_check.id == check.id)
        ),
        "correctness": (
            "agreement with supplied expectations; provenance is reported, independence is not authenticated"
            if agreement is not None else "not measured: no independent expectations supplied"
        ),
        "old_judge": old_plan.judge.model,
        "new_judge": new_plan.judge.model,
        "shared": len(shared),
        "old_only": len(old.keys() - new.keys()),
        "new_only": len(new.keys() - old.keys()),
        "verdict_flips": flips,
        "transitions": dict(
            Counter(f"{old[k].verdict.value}->{new[k].verdict.value}" for k in shared)
        ),
        "matching_request_probabilities": len(differences),
        "max_abs_delta": max((d["delta"] for d in differences), default=0.0),
        "band_changes": sum(d["band_changed"] for d in differences),
        "accuracy_claim": False,
    }


def compare_command(args: Any) -> int:
    try:
        report = compare_ledgers(
            Path(args.old), Path(args.new),
            expectations=Path(args.expectations) if getattr(args, "expectations", None) else None,
        )
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"status": "error", "command": "compare", "error": str(exc)}))
        return 1
    print(json.dumps({"status": "ok", "command": "compare", "data": report}, indent=2))
    return 0
