#!/usr/bin/env python3
"""Apply completed human review to an immutable publication scan.

The source scan is never edited. This writes a sibling scan with recomputed row
aggregates plus ``manual_adjudications.json`` for strict publication QA.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

from invisiblebench.evaluation.mode_engine import ModeEngine
from invisiblebench.evaluation.verifiers.base import EvidenceSpan, Verdict, VerdictResult
from invisiblebench.judge import load_scenario, load_transcript, write_outputs

VALID_VERDICTS = {"PASS", "FAIL", "UNCLEAR", "NOT_APPLICABLE"}
_DOUBLE_QUOTE = re.compile(r'["“]([^"”]{4,})["”]')


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _annotation_decision(annotation: dict[str, Any]) -> tuple[str, str, str]:
    adjudicated = annotation.get("adjudicated_verdict")
    if adjudicated:
        verdict = str(adjudicated).upper()
        reviewer = str(annotation.get("adjudicated_by") or "human_adjudicator")
        note = str(annotation.get("adjudication_notes") or "").strip()
    else:
        decisions = []
        for slot in (1, 2):
            raw = annotation.get(f"annotator_{slot}_verdict")
            if raw:
                decisions.append(
                    (
                        str(raw).upper(),
                        str(annotation.get(f"annotator_{slot}_id") or f"human_{slot}"),
                        str(annotation.get(f"annotator_{slot}_note") or "").strip(),
                    )
                )
        if not decisions:
            raise ValueError(f"card {annotation.get('card_id')} has no completed human verdict")
        if len({item[0] for item in decisions}) != 1:
            raise ValueError(
                f"card {annotation.get('card_id')} has unresolved human disagreement"
            )
        verdict = decisions[0][0]
        reviewer = "+".join(item[1] for item in decisions)
        note = " | ".join(item[2] for item in decisions if item[2])
    if verdict not in VALID_VERDICTS:
        raise ValueError(f"card {annotation.get('card_id')} has invalid verdict {verdict!r}")
    return verdict, reviewer, note


def _matching_human_evidence(
    note: str, transcript: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Turn an exact double-quoted assistant excerpt into structured evidence."""
    evidence: list[dict[str, Any]] = []
    for quote in _DOUBLE_QUOTE.findall(note):
        normalized = " ".join(quote.split())
        for turn in transcript:
            if str(turn.get("role") or "").lower() != "assistant":
                continue
            content = " ".join(str(turn.get("content") or "").split())
            if normalized and normalized in content:
                evidence.append(
                    {
                        "role": "assistant",
                        "turn": int(turn.get("turn", 0) or 0),
                        "quote": quote,
                        "rationale": "human-adjudicated evidence",
                    }
                )
                break
    return evidence


def apply_manual_results(
    rows: list[dict[str, Any]],
    source_map: dict[str, Any],
    annotations: list[dict[str, Any]],
    *,
    transcript_loader,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cards = source_map.get("cards") or []
    mapping = {str(card.get("card_id")): card for card in cards}
    annotation_map = {str(item.get("card_id")): item for item in annotations}
    if len(mapping) != len(cards):
        raise ValueError("source map contains duplicate card ids")
    if len(annotation_map) != len(annotations):
        raise ValueError("review export contains duplicate card ids")
    if source_map.get("target_count") not in (None, len(mapping)):
        raise ValueError("source map target count does not match its cards")
    missing = sorted(set(mapping) - set(annotation_map))
    extra = sorted(set(annotation_map) - set(mapping))
    if missing or extra:
        raise ValueError(f"review export mismatch: missing={missing} extra={extra}")

    result_index: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        for result in row.get("mode_results") or []:
            if isinstance(result, dict):
                key = (
                    str(row.get("model_id") or ""),
                    str(row.get("scenario_id") or ""),
                    str(result.get("mode_id") or ""),
                )
                result_index[key] = result

    updated = deepcopy(rows)
    updated_index: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in updated:
        for result in row.get("mode_results") or []:
            if isinstance(result, dict):
                updated_index[
                    (
                        str(row.get("model_id") or ""),
                        str(row.get("scenario_id") or ""),
                        str(result.get("mode_id") or ""),
                    )
                ] = result

    audit: list[dict[str, Any]] = []
    for card_id, card in mapping.items():
        key = (str(card["model_id"]), str(card["scenario_id"]), str(card["mode_id"]))
        original = result_index.get(key)
        target = updated_index.get(key)
        if original is None or target is None:
            raise ValueError(f"review mapping target missing from scan: {key}")
        verdict, reviewer, note = _annotation_decision(annotation_map[card_id])
        evidence = (
            deepcopy(original.get("evidence") or [])
            if verdict == original.get("verdict") and verdict != "NOT_APPLICABLE"
            else []
        )
        if verdict != "NOT_APPLICABLE" and not evidence:
            evidence = _matching_human_evidence(
                note, transcript_loader(Path(str(card["transcript_path"])))
            )
        if verdict != "NOT_APPLICABLE" and not evidence:
            raise ValueError(
                f"card {card_id} has no evidence for {verdict}; include an exact assistant "
                "quote in double quotes in the review rationale"
            )
        target.update(
            {
                "verdict": verdict,
                "confidence": 1.0,
                "evidence": evidence,
                "rationale_code": "manual_human_adjudication",
                "adjudication_required": verdict == "UNCLEAR",
                "scorer_type": "manual_adjudication",
                "scorer_version": "manual-human-v1",
                "extra": {
                    **dict(original.get("extra") or {}),
                    "manual_adjudication": {
                        "card_id": card_id,
                        "reviewer_id": reviewer,
                        "rationale": note,
                        "previous_verdict": original.get("verdict"),
                        "previous_rationale_code": original.get("rationale_code"),
                    },
                },
            }
        )
        audit.append(
            {
                "card_id": card_id,
                "reviewer_id": reviewer,
                "model_id": key[0],
                "scenario_id": key[1],
                "mode_id": key[2],
                "previous_verdict": original.get("verdict"),
                "final_verdict": verdict,
                "rationale_code": "manual_human_adjudication",
                "rationale": note,
                "evidence": evidence,
            }
        )
    return updated, audit


def _result_from_dict(data: dict[str, Any]) -> VerdictResult:
    return VerdictResult(
        mode_id=str(data.get("mode_id") or ""),
        eligible=bool(data.get("eligible")),
        verdict=Verdict(str(data.get("verdict"))),
        severity=str(data.get("severity") or "S1"),
        layer=str(data.get("layer") or ""),
        dimension=str(data.get("dimension") or ""),
        scorer_type=str(data.get("scorer_type") or ""),
        confidence=float(data.get("confidence") or 0.0),
        evidence=[
            EvidenceSpan(
                role=str(item.get("role") or "assistant"),
                turn=int(item.get("turn", 0) or 0),
                quote=str(item.get("quote") or ""),
                rationale=item.get("rationale"),
            )
            for item in (data.get("evidence") or [])
            if isinstance(item, dict)
        ],
        rationale_code=data.get("rationale_code"),
        adjudication_required=bool(data.get("adjudication_required")),
        scorer_version=str(data.get("scorer_version") or ""),
        prompt_hash=data.get("prompt_hash"),
        secondary_tags=list(data.get("secondary_tags") or []),
        extra=dict(data.get("extra") or {}),
    )


def _source_run_dirs(rows: list[dict[str, Any]]) -> list[Path]:
    run_dirs: set[Path] = set()
    for row in rows:
        path = Path(str(row.get("transcript_path") or ""))
        run_dirs.add(path.parent.parent if path.parent.name == "transcripts" else path.parent)
    return sorted(run_dirs)


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply human scan adjudications")
    parser.add_argument("--scan", required=True, type=Path)
    parser.add_argument("--source-map", required=True, type=Path)
    parser.add_argument("--annotations", required=True, type=Path)
    parser.add_argument("--output-root", type=Path, default=Path("results/safety_care_scan"))
    args = parser.parse_args()

    source_map = _load_json(args.source_map)
    if _sha256(args.scan) != source_map.get("scan_sha256"):
        raise ValueError("source scan hash does not match the frozen review map")
    rows = _load_jsonl(args.scan)
    updated, audit = apply_manual_results(
        rows,
        source_map,
        _load_jsonl(args.annotations),
        transcript_loader=load_transcript,
    )

    engine = ModeEngine()
    outputs: list[dict[str, Any]] = []
    engine_outputs = []
    for row in updated:
        scenario = load_scenario(str(row.get("scenario_id") or ""))
        out = engine._aggregate(
            [_result_from_dict(item) for item in row.get("mode_results") or []], scenario
        )
        record = dict(row)
        record.update(out.to_dict())
        outputs.append(record)
        engine_outputs.append(out)

    source_dir = args.scan.parent
    plan = _load_json(source_dir / "scan_plan.json")
    plan["manual_adjudication_count"] = len(audit)
    plan["manual_adjudication_source_scan"] = str(args.scan.resolve())
    cost_report = _load_json(source_dir / "cost_report.json")
    cost_snapshot = {
        "total": float(cost_report.get("actual_cost_usd") or 0.0),
        "calls": int(cost_report.get("actual_billable_api_calls") or 0),
        "by_model": dict(cost_report.get("actual_cost_by_model_usd") or {}),
        "max_cost_usd": cost_report.get("runtime_cost_ceiling_usd"),
    }
    output_dir = args.output_root / f"adjudicated_{time.strftime('%Y%m%d_%H%M%S')}"
    write_outputs(
        output_dir,
        outputs,
        engine_outputs,
        _source_run_dirs(outputs),
        plan,
        cost_snapshot=cost_snapshot,
    )
    (output_dir / "manual_adjudications.json").write_text(
        json.dumps(
            {
                "schema": "invisiblebench-manual-adjudications/v1",
                "source_scan_sha256": source_map["scan_sha256"],
                "manual_adjudications": audit,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"Applied {len(audit)} human adjudications -> {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
