#!/usr/bin/env python3
"""Export an actionable, blind human-adjudication batch from a completed scan.

Only unresolved or explicitly escalated check results are exported. Machine
verdicts, model identities, judge output, and evidence remain in a private
source map; ``batch.json`` contains only the transcript and human rubric the
review UI needs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from invisiblebench.judge import load_transcript  # noqa: E402
from scripts.review_ui.export_batch import (  # noqa: E402
    BANNED_LABEL_KEYS,
    _scenario_cue_index,
    canonical_cue_turn,
    load_check_rubric,
)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def target_reasons(result: dict[str, Any]) -> list[str]:
    """Return the publication reasons that require a human decision."""
    if not result.get("eligible"):
        return []
    reasons: list[str] = []
    if result.get("adjudication_required") is True:
        reasons.append("adjudication_required")
    if result.get("verdict") == "UNCLEAR":
        reasons.append("unresolved_unclear")
    if result.get("verdict") == "FAIL" and not result.get("evidence"):
        reasons.append("fail_without_evidence")
    extra = result.get("extra") or {}
    if isinstance(extra, dict) and extra.get("automated_adjudication"):
        reasons.append("machine_vote_disagreement")
    return reasons


def _opaque_id(scan_sha256: str, model_id: str, scenario_id: str, mode_id: str) -> str:
    payload = "\0".join((scan_sha256, model_id, scenario_id, mode_id)).encode()
    return f"scanreview_{hashlib.sha256(payload).hexdigest()[:24]}"


def _opaque_scenario_id(scan_sha256: str, scenario_id: str) -> str:
    payload = f"{scan_sha256}\0{scenario_id}".encode()
    return f"scenario_{hashlib.sha256(payload).hexdigest()[:16]}"


def _render_transcript(turns: list[dict[str, Any]]) -> str:
    blocks = []
    for turn in turns:
        blocks.append(
            f"[Turn {int(turn.get('turn', 0) or 0)}, "
            f"{str(turn.get('role', '')).upper()}]\n{str(turn.get('content', '')).strip()}"
        )
    return "\n\n".join(blocks)


def _banned_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in BANNED_LABEL_KEYS:
                found.add(str(key))
            found.update(_banned_keys(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_banned_keys(item))
    return found


def build_review_artifacts(
    rows: list[dict[str, Any]],
    *,
    scan_sha256: str,
    transcript_loader: Callable[[Path], list[dict[str, Any]]] = load_transcript,
    rubric_loader: Callable[[str], dict[str, Any]] = load_check_rubric,
    cue_index: dict[str, list[dict[str, Any]]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cue_index = _scenario_cue_index() if cue_index is None else cue_index
    batch: list[dict[str, Any]] = []
    mapping: list[dict[str, Any]] = []
    rubric_cache: dict[str, dict[str, Any]] = {}

    for row in rows:
        model_id = str(row.get("model_id") or "")
        scenario_id = str(row.get("scenario_id") or "")
        transcript_path = Path(str(row.get("transcript_path") or ""))
        turns: list[dict[str, Any]] | None = None
        transcript_window: str | None = None
        for result in row.get("mode_results") or []:
            if not isinstance(result, dict):
                continue
            reasons = target_reasons(result)
            if not reasons:
                continue
            mode_id = str(result.get("mode_id") or "")
            if not all((model_id, scenario_id, mode_id)):
                raise ValueError("review target is missing model_id, scenario_id, or mode_id")
            if turns is None:
                turns = transcript_loader(transcript_path)
                transcript_window = _render_transcript(turns)
            if mode_id not in rubric_cache:
                rubric_cache[mode_id] = rubric_loader(mode_id)
            card_id = _opaque_id(scan_sha256, model_id, scenario_id, mode_id)
            cue_turn = canonical_cue_turn(scenario_id, mode_id, cue_index)
            batch.append(
                {
                    "card_id": card_id,
                    "check_id": mode_id,
                    "scenario_id": _opaque_scenario_id(scan_sha256, scenario_id),
                    "source_tags": ["publication-adjudication"],
                    "window_provenance": "publication-run",
                    "check": rubric_cache[mode_id],
                    "transcript_window": transcript_window,
                    "turns": turns,
                    "cue": {"cue_turn": cue_turn} if cue_turn is not None else None,
                }
            )
            mapping.append(
                {
                    "card_id": card_id,
                    "model_id": model_id,
                    "scenario_id": scenario_id,
                    "mode_id": mode_id,
                    "transcript_path": str(transcript_path),
                    "target_reasons": reasons,
                    "previous_verdict": result.get("verdict"),
                    "previous_rationale_code": result.get("rationale_code"),
                }
            )

    card_ids = [card["card_id"] for card in batch]
    if len(card_ids) != len(set(card_ids)):
        raise ValueError("duplicate review card id")
    leaked = _banned_keys(batch)
    if leaked:
        raise ValueError(f"blind batch contains prohibited machine-label keys: {sorted(leaked)}")
    return batch, {
        "schema": "invisiblebench-scan-review-map/v1",
        "scan_sha256": scan_sha256,
        "target_count": len(mapping),
        "cards": mapping,
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_review_markdown(batch: list[dict[str, Any]]) -> str:
    lines = [
        "# InvisibleBench publication review",
        "",
        f"Review cards: {len(batch)}",
        "",
        "For each card, choose PASS, FAIL, UNCLEAR, or NOT_APPLICABLE. ",
        "Except for NOT_APPLICABLE, include a short rationale with an exact ",
        'assistant excerpt in double quotes so the audit has evidence.',
    ]
    for index, card in enumerate(batch, 1):
        check = card.get("check") or {}
        lines.extend(
            [
                "",
                f"## Card {index}",
                "",
                f"Check: {check.get('name') or card.get('check_id')} "
                f"(`{card.get('check_id')}`)",
                "",
                f"PASS when: {check.get('pass_rule') or ''}",
                "",
                f"FAIL when: {check.get('fail_rule') or ''}",
                "",
                "````text",
                str(card.get("transcript_window") or ""),
                "````",
                "",
                "Verdict: ",
                "",
                "Rationale: ",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a blind scan-adjudication batch")
    parser.add_argument("--scan", required=True, type=Path, help="completed per_run.jsonl")
    parser.add_argument("--out-dir", required=True, type=Path, help="new private review dir")
    args = parser.parse_args()

    if not args.scan.is_file():
        raise FileNotFoundError(args.scan)
    if args.out_dir.exists() and any(args.out_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty review dir: {args.out_dir}")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    scan_sha256 = _sha256(args.scan)
    batch, source_map = build_review_artifacts(
        _load_jsonl(args.scan), scan_sha256=scan_sha256
    )
    batch_path = args.out_dir / "batch.json"
    map_path = args.out_dir / "source_map.json"
    review_path = args.out_dir / "REVIEW.md"
    batch_path.write_text(json.dumps(batch, indent=2, ensure_ascii=False) + "\n")
    source_map.update({"scan_path": str(args.scan.resolve())})
    map_path.write_text(json.dumps(source_map, indent=2) + "\n")
    review_path.write_text(render_review_markdown(batch), encoding="utf-8")
    sums = "\n".join(
        f"{_sha256(path)}  {path.name}" for path in (batch_path, map_path, review_path)
    )
    (args.out_dir / "SHA256SUMS").write_text(sums + "\n")
    print(f"Wrote {len(batch)} blind review cards -> {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
