"""`bench explain` — trace a published number back to its evidence.

Walks the chain: leaderboard cell → scan record → per-check verdict
(severity, confidence, rationale, evidence quotes, prompt hash, scorer
version) → transcript path. The scan JSONL referenced by the leaderboard's
``metadata.source_artifact`` is the default source, so any cell in the
published leaderboard is explainable with one command.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from invisiblebench.utils.io import load_jsonl

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LEADERBOARD = REPO_ROOT / "data" / "leaderboard" / "leaderboard.json"


def _resolve_scan_path(args: Any) -> Path | None:
    if getattr(args, "scan", None):
        return Path(args.scan)
    lb_path = Path(getattr(args, "leaderboard", None) or DEFAULT_LEADERBOARD)
    if not lb_path.exists():
        return None
    with open(lb_path, encoding="utf-8") as f:
        metadata = json.load(f).get("metadata", {})
    artifact = metadata.get("source_artifact")
    if not artifact:
        return None
    path = Path(artifact)
    return path if path.is_absolute() else REPO_ROOT / path


def _match_rows(
    rows: list[dict[str, Any]], model: str, scenario_id: str
) -> list[dict[str, Any]]:
    needle_model = model.lower()
    needle_scenario = scenario_id.lower()
    return [
        r
        for r in rows
        if needle_model in str(r.get("model", "")).lower()
        or needle_model in str(r.get("model_id", "")).lower()
        if needle_scenario in str(r.get("scenario_id", "")).lower()
    ]


def _format_evidence(evidence: list[dict[str, Any]] | None, indent: str = "      ") -> list[str]:
    lines: list[str] = []
    for ev in evidence or []:
        turn = ev.get("turn")
        quote = (ev.get("quote") or "").strip()
        rationale = ev.get("rationale")
        lines.append(f'{indent}turn {turn}: "{quote}"')
        if rationale:
            lines.append(f"{indent}  rationale: {rationale}")
    return lines


def _mode_summary(m: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode_id": m.get("mode_id"),
        "verdict": m.get("verdict"),
        "eligible": m.get("eligible"),
        "severity": m.get("severity"),
        "primary_bucket": m.get("primary_bucket"),
        "scorer_type": m.get("scorer_type"),
        "scorer_version": m.get("scorer_version"),
        "confidence": m.get("confidence"),
        "rationale_code": m.get("rationale_code"),
        "prompt_hash": m.get("prompt_hash"),
        "evidence": m.get("evidence") or [],
    }


def explain_command(args: Any) -> int:
    """Explain why a (model, scenario) cell scored the way it did."""
    json_output = bool(getattr(args, "json_output", None))

    scan_path = _resolve_scan_path(args)
    if scan_path is None or not scan_path.exists():
        msg = f"scan artifact not found (looked for {scan_path})"
        if json_output:
            print(json.dumps({"status": "error", "command": "explain", "error": msg}))
        else:
            print(f"error: {msg}")
        return 1

    rows = load_jsonl(scan_path)
    matches = _match_rows(rows, args.model, args.scenario)

    if not matches:
        msg = f"no scan row matches model~'{args.model}' scenario~'{args.scenario}'"
        if json_output:
            print(json.dumps({"status": "error", "command": "explain", "error": msg}))
        else:
            print(f"error: {msg}")
            seen = sorted({str(r.get("model")) for r in rows})
            print("models in scan: " + ", ".join(seen))
        return 1

    check_filter = (getattr(args, "check", None) or "").lower()
    failures_only = bool(getattr(args, "failures", None))

    payload: list[dict[str, Any]] = []
    for row in matches:
        modes = [m for m in row.get("mode_results", []) if m.get("eligible")]
        if check_filter:
            modes = [m for m in modes if check_filter in str(m.get("mode_id", "")).lower()]
        if failures_only:
            modes = [m for m in modes if m.get("verdict") in ("FAIL", "UNCLEAR")]
        payload.append(
            {
                "model": row.get("model"),
                "model_id": row.get("model_id"),
                "scenario_id": row.get("scenario_id"),
                "category": row.get("category"),
                "overall_score": row.get("overall_score"),
                "hard_fail": row.get("hard_fail"),
                "hard_fail_reasons": row.get("hard_fail_reasons") or [],
                "coverage": {
                    "eligible": row.get("eligible_count"),
                    "resolved": row.get("resolved_count"),
                    "unclear": row.get("unclear_count"),
                    "rate": row.get("coverage_rate"),
                },
                "transcript_path": row.get("transcript_path"),
                "scan_artifact": str(scan_path),
                "checks": [_mode_summary(m) for m in modes],
            }
        )

    if json_output:
        print(json.dumps({"status": "ok", "command": "explain", "data": payload}, indent=2))
        return 0

    for item in payload:
        print(f"{item['model']}  ×  {item['scenario_id']}  [{item['category']}]")
        print(f"  overall_score: {item['overall_score']}    hard_fail: {item['hard_fail']}")
        for reason in item["hard_fail_reasons"]:
            print(f"    hard-fail: {reason.get('mode_id')} — {reason.get('reason')}")
        cov = item["coverage"]
        print(
            f"  coverage: {cov['resolved']}/{cov['eligible']} resolved, "
            f"{cov['unclear']} unclear (rate {cov['rate']})"
        )
        print(f"  transcript: {item['transcript_path']}")
        print(f"  scan:       {item['scan_artifact']}")
        shown = item["checks"]
        verdict_order = {"FAIL": 0, "UNCLEAR": 1, "PASS": 2}
        shown.sort(key=lambda m: (verdict_order.get(str(m["verdict"]), 3), str(m["mode_id"])))
        print(f"  checks ({len(shown)} eligible shown):")
        for m in shown:
            conf = m.get("confidence")
            conf_s = f" conf={conf:.2f}" if isinstance(conf, (int, float)) else ""
            print(
                f"    {m['verdict']:<7} {m['mode_id']:<40} [{m['severity']}/{m['primary_bucket']}]"
                f" {m['scorer_type']}:{m.get('scorer_version')}{conf_s}"
            )
            if m.get("rationale_code"):
                print(f"      rationale_code: {m['rationale_code']}")
            if m["verdict"] in ("FAIL", "UNCLEAR") or check_filter:
                for line in _format_evidence(m.get("evidence")):
                    print(line)
                if m.get("prompt_hash"):
                    print(f"      prompt_hash: {m['prompt_hash']}")
        print()
    return 0
