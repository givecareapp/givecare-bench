"""Run audit helpers for benchmark results.

A run audit classifies benchmark-run failure modes and decides whether a run is
valid and publishable without requiring manual inspection.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from invisiblebench.failure_taxonomy import (
    classify_reliability_issue,
    compute_quality_summary,
    compute_reliability_summary,
)
from invisiblebench.run_artifacts import detect_transcripts_dir, load_result_rows

STATUS_PASS = "PASS"
STATUS_WARN = "WARN"
STATUS_BLOCK = "BLOCK"

CHECK_ORDER = [
    "run_integrity",
    "comparability",
    "state_isolation",
    "provider_health",
    "transcript_integrity",
    "judge_health",
    "scoring_integrity",
    "target_config",
    "model_behavior",
    "statistical_stability",
    "publication_eligibility",
]

CRITICAL_CHECKS = [
    "run_integrity",
    "comparability",
    "state_isolation",
    "transcript_integrity",
    "judge_health",
    "scoring_integrity",
    "target_config",
]

OWNER_BY_CHECK = {
    "run_integrity": "benchmark",
    "comparability": "benchmark",
    "state_isolation": "harness",
    "provider_health": "provider",
    "transcript_integrity": "harness",
    "judge_health": "judge",
    "scoring_integrity": "scoring",
    "target_config": "target-config",
    "model_behavior": "model",
    "statistical_stability": "benchmark",
    "publication_eligibility": "benchmark",
}


def _check(status: str, summary: str, details: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return {"status": status, "summary": summary, "details": details or {}}


def _infer_run_dir(source: Path) -> Optional[Path]:
    if source.is_dir():
        if (source / "run_manifest.json").exists():
            return source
        if source.name == "model_results" and (source.parent / "run_manifest.json").exists():
            return source.parent
        return source

    parent = source.parent
    if parent.name == "model_results":
        return parent.parent
    return parent


def find_existing_audit_file(source: Path) -> Optional[Path]:
    """Return existing run_audit.json for a source if present."""
    run_dir = _infer_run_dir(source)
    if run_dir is None:
        return None
    audit_path = run_dir / "run_audit.json"
    return audit_path if audit_path.exists() else None


def _load_manifest(source: Path) -> Dict[str, Any]:
    run_dir = _infer_run_dir(source)
    if run_dir is None:
        return {}
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        with open(manifest_path) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _result_key(row: Dict[str, Any]) -> Tuple[str, str]:
    return (
        str(row.get("model") or row.get("model_id") or "unknown"),
        str(row.get("scenario_id") or row.get("scenario") or "unknown"),
    )


def _iter_transcript_files(transcripts_dir: Optional[Path]) -> Iterable[Path]:
    if transcripts_dir is None or not transcripts_dir.exists():
        return []
    return sorted(transcripts_dir.rglob("*.jsonl"))


def _audit_run_integrity(
    rows: List[Dict[str, Any]],
    manifest: Dict[str, Any],
    expected_scenario_count: Optional[int],
) -> Dict[str, Any]:
    if not rows:
        return _check(STATUS_BLOCK, "No result rows found", {"row_count": 0})

    by_model: Dict[str, int] = {}
    for row in rows:
        model = str(row.get("model") or row.get("model_id") or "unknown")
        by_model[model] = by_model.get(model, 0) + 1

    details = {
        "row_count": len(rows),
        "model_count": len(by_model),
        "scenario_counts_by_model": by_model,
        "manifest_present": bool(manifest),
    }

    if not manifest:
        return _check(STATUS_BLOCK, "Missing run manifest", details)

    counts = set(by_model.values())
    if len(counts) > 1:
        return _check(STATUS_BLOCK, "Inconsistent scenario counts across models", details)

    if expected_scenario_count is not None and counts != {expected_scenario_count}:
        details["expected_scenario_count"] = expected_scenario_count
        return _check(STATUS_BLOCK, "Scenario count does not match expected run shape", details)

    return _check(STATUS_PASS, "Run shape is internally consistent", details)


def _audit_comparability(
    rows: List[Dict[str, Any]],
    manifest: Dict[str, Any],
    harness: Optional[str],
    mode: Optional[str],
    previous_manifest: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    contract_versions = sorted({str(r.get("contract_version")) for r in rows if r.get("contract_version")})
    judge_prompt_hashes = sorted({str(r.get("judge_prompt_hash")) for r in rows if r.get("judge_prompt_hash")})
    details: Dict[str, Any] = {
        "contract_versions": contract_versions,
        "judge_prompt_hashes": judge_prompt_hashes,
        "manifest_harness": manifest.get("harness"),
        "manifest_mode": manifest.get("mode"),
    }

    if len(contract_versions) > 1:
        return _check(STATUS_BLOCK, "Multiple scoring contract versions detected", details)
    if len(judge_prompt_hashes) > 1:
        return _check(STATUS_BLOCK, "Multiple judge prompt hashes detected", details)
    if harness and manifest.get("harness") and manifest.get("harness") != harness:
        return _check(STATUS_BLOCK, "Manifest harness does not match requested harness", details)
    if mode and manifest.get("mode") and manifest.get("mode") != mode:
        return _check(STATUS_BLOCK, "Manifest mode does not match requested mode", details)

    if previous_manifest:
        drift = {}
        for key in (
            "scenario_hash",
            "scoring_config_hash",
            "contract_version",
            "harness",
            "mode",
        ):
            if manifest.get(key) != previous_manifest.get(key):
                drift[key] = {
                    "current": manifest.get(key),
                    "previous": previous_manifest.get(key),
                }
        if drift:
            details["drift"] = drift
            return _check(STATUS_BLOCK, "Run is not comparable to previous reference", details)

    return _check(STATUS_PASS, "Run is comparable under current contract/config", details)


def _audit_state_isolation(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    seen = set()
    duplicates = []
    run_ids = sorted({str(r.get("run_id")) for r in rows if r.get("run_id")})
    for row in rows:
        key = _result_key(row)
        if key in seen:
            duplicates.append({"model": key[0], "scenario_id": key[1]})
        seen.add(key)

    details = {"duplicate_rows": duplicates, "run_ids": run_ids}
    if duplicates:
        return _check(STATUS_BLOCK, "Duplicate model/scenario rows detected", details)
    if len(run_ids) > 1:
        return _check(STATUS_WARN, "Multiple run_ids detected within one result set", details)
    return _check(STATUS_PASS, "No obvious cross-scenario state contamination detected", details)


def _audit_provider_health(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary = compute_reliability_summary(rows)
    error_rate = summary["error_rate"]
    if summary["error"] == 0:
        return _check(STATUS_PASS, "No provider/runtime errors detected", summary)
    if error_rate >= 0.05:
        return _check(STATUS_BLOCK, "Provider/runtime error rate is too high", summary)
    return _check(STATUS_WARN, "Provider/runtime errors detected", summary)


def _audit_transcript_integrity(rows: List[Dict[str, Any]], transcripts_dir: Optional[Path]) -> Dict[str, Any]:
    if transcripts_dir is None or not transcripts_dir.exists():
        return _check(STATUS_WARN, "No transcripts directory found", {"transcripts_dir": None})

    transcript_files = list(_iter_transcript_files(transcripts_dir))
    malformed = []
    empty_assistant_turns = 0
    parsed_line_count = 0
    for path in transcript_files:
        try:
            for raw_line in path.read_text().splitlines():
                if not raw_line.strip():
                    continue
                parsed_line_count += 1
                row = json.loads(raw_line)
                if row.get("role") == "assistant" and not str(row.get("content", "")).strip():
                    empty_assistant_turns += 1
        except Exception as e:
            malformed.append({"path": str(path), "error": str(e)})

    details = {
        "transcripts_dir": str(transcripts_dir),
        "transcript_file_count": len(transcript_files),
        "parsed_line_count": parsed_line_count,
        "empty_assistant_turns": empty_assistant_turns,
        "malformed_files": malformed,
    }
    if malformed:
        return _check(STATUS_BLOCK, "Malformed transcript files detected", details)
    if len(transcript_files) < len(rows):
        return _check(STATUS_BLOCK, "Fewer transcripts than scored results", details)
    if empty_assistant_turns > 0:
        return _check(STATUS_WARN, "Transcripts contain empty assistant turns", details)
    return _check(STATUS_PASS, "Transcript files appear structurally valid", details)


def _audit_judge_health(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    judge_models = sorted({str(r.get("judge_model")) for r in rows if r.get("judge_model")})
    prompt_hashes = sorted({str(r.get("judge_prompt_hash")) for r in rows if r.get("judge_prompt_hash")})
    scoring_error_count = sum(
        1 for r in rows if classify_reliability_issue(r) == "scoring"
    )
    details = {
        "judge_models": judge_models,
        "judge_prompt_hashes": prompt_hashes,
        "scoring_error_count": scoring_error_count,
    }
    if scoring_error_count > 0:
        return _check(STATUS_BLOCK, "Scoring/judge failures detected", details)
    if len(judge_models) > 1:
        return _check(STATUS_BLOCK, "Multiple judge models detected in one run", details)
    if len(prompt_hashes) > 1:
        return _check(STATUS_BLOCK, "Multiple judge prompt hashes detected in one run", details)
    if not judge_models:
        return _check(STATUS_WARN, "Judge metadata missing from results", details)
    return _check(STATUS_PASS, "Judge metadata is consistent", details)


def _audit_scoring_integrity(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    invalid_rows = []
    for idx, row in enumerate(rows):
        score = row.get("overall_score")
        status = row.get("status")
        if not isinstance(score, (int, float)) or float(score) < 0 or float(score) > 1:
            invalid_rows.append({"row": idx, "reason": "invalid_score"})
        if status not in {"pass", "fail", "error"}:
            invalid_rows.append({"row": idx, "reason": "invalid_status"})
        for key in ("model", "scenario", "scenario_id"):
            if not row.get(key):
                invalid_rows.append({"row": idx, "reason": f"missing_{key}"})

    details = {"invalid_rows": invalid_rows, "row_count": len(rows)}
    if invalid_rows:
        return _check(STATUS_BLOCK, "Scoring output schema is inconsistent", details)
    return _check(STATUS_PASS, "Scoring output is structurally valid", details)


def _audit_target_config(
    rows: List[Dict[str, Any]],
    manifest: Dict[str, Any],
    harness: Optional[str],
    mode: Optional[str],
) -> Dict[str, Any]:
    providers = sorted({str(r.get("provider")) for r in rows if r.get("provider")})
    model_ids = sorted({str(r.get("model_id")) for r in rows if r.get("model_id")})
    details = {
        "providers": providers,
        "model_ids": model_ids,
        "manifest_harness": manifest.get("harness"),
        "manifest_mode": manifest.get("mode"),
    }
    if not manifest.get("harness") or not manifest.get("mode"):
        return _check(STATUS_WARN, "Manifest is missing harness/mode metadata", details)
    if harness and manifest.get("harness") != harness:
        return _check(STATUS_BLOCK, "Harness metadata mismatch", details)
    if mode and manifest.get("mode") != mode:
        return _check(STATUS_BLOCK, "Mode metadata mismatch", details)
    return _check(STATUS_PASS, "Target configuration metadata is present", details)


def _audit_model_behavior(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    from invisiblebench.stats.analysis import compute_failure_buckets

    quality = compute_quality_summary(rows)
    failure_buckets = compute_failure_buckets(rows)
    details = {"quality_summary": quality, "failure_buckets": failure_buckets}
    rate = quality["pass_rate"]
    status = STATUS_PASS if rate >= 0.8 else STATUS_WARN if rate >= 0.6 else STATUS_BLOCK
    summary = f"Behavioral pass rate: {rate * 100:.1f}%"
    return _check(status, summary, details)


def _audit_statistical_stability(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    run_stats = [r.get("run_stats") for r in rows if isinstance(r.get("run_stats"), dict)]
    if not run_stats:
        return _check(STATUS_PASS, "Single-run benchmark; no stability estimate available", {})

    max_std = max(float(rs.get("std", 0.0)) for rs in run_stats)
    max_range = max(float(rs.get("max", 0.0)) - float(rs.get("min", 0.0)) for rs in run_stats)
    details = {
        "multi_run_scenarios": len(run_stats),
        "max_std": max_std,
        "max_range": max_range,
    }
    if max_std >= 0.2 or max_range >= 0.5:
        return _check(STATUS_WARN, "High scenario variance detected across repeated runs", details)
    return _check(STATUS_PASS, "Repeated-run variance is within expected range", details)


def _derive_gate(checks: Dict[str, Dict[str, Any]]) -> Tuple[bool, bool, str, str]:
    critical_statuses = [checks[name]["status"] for name in CRITICAL_CHECKS]
    if STATUS_BLOCK in critical_statuses:
        summary_status = STATUS_BLOCK
        run_valid = False
    elif STATUS_WARN in critical_statuses:
        summary_status = STATUS_WARN
        run_valid = True
    else:
        behavior_status = checks["model_behavior"]["status"]
        summary_status = behavior_status if behavior_status in {STATUS_WARN, STATUS_BLOCK} else STATUS_PASS
        run_valid = True

    publishable = True
    for name in [
        "run_integrity",
        "comparability",
        "state_isolation",
        "judge_health",
        "scoring_integrity",
        "target_config",
    ]:
        if checks[name]["status"] != STATUS_PASS:
            publishable = False
            break
    if checks["provider_health"]["status"] == STATUS_BLOCK:
        publishable = False
    if checks["transcript_integrity"]["status"] == STATUS_BLOCK:
        publishable = False

    primary_owner = "benchmark"
    for name in CHECK_ORDER:
        if name == "publication_eligibility":
            continue
        if checks[name]["status"] in {STATUS_BLOCK, STATUS_WARN}:
            primary_owner = OWNER_BY_CHECK[name]
            break

    return run_valid, publishable, summary_status, primary_owner


def audit_results_source(
    source: str | Path,
    *,
    expected_scenario_count: Optional[int] = None,
    harness: Optional[str] = None,
    mode: Optional[str] = None,
    previous_source: str | Path | None = None,
) -> Dict[str, Any]:
    """Audit a benchmark run/results source and classify failure modes."""
    source_path = Path(source)
    rows = load_result_rows(source_path)
    manifest = _load_manifest(source_path)
    previous_manifest = _load_manifest(Path(previous_source)) if previous_source else None
    transcripts_dir = detect_transcripts_dir(source_path)

    checks = {
        "run_integrity": _audit_run_integrity(rows, manifest, expected_scenario_count),
        "comparability": _audit_comparability(rows, manifest, harness, mode, previous_manifest),
        "state_isolation": _audit_state_isolation(rows),
        "provider_health": _audit_provider_health(rows),
        "transcript_integrity": _audit_transcript_integrity(rows, transcripts_dir),
        "judge_health": _audit_judge_health(rows),
        "scoring_integrity": _audit_scoring_integrity(rows),
        "target_config": _audit_target_config(rows, manifest, harness, mode),
        "model_behavior": _audit_model_behavior(rows),
        "statistical_stability": _audit_statistical_stability(rows),
    }

    run_valid, publishable, summary_status, primary_owner = _derive_gate(checks)
    publication_summary = (
        "Run is eligible for publication" if publishable else "Run should not be published/promoted"
    )
    checks["publication_eligibility"] = _check(
        STATUS_PASS if publishable else STATUS_BLOCK,
        publication_summary,
        {"run_valid": run_valid, "publishable": publishable},
    )

    return {
        "source": str(source_path),
        "run_valid": run_valid,
        "publishable": publishable,
        "summary_status": summary_status,
        "primary_owner": primary_owner,
        "checks": checks,
    }


def render_audit_markdown(audit: Dict[str, Any]) -> str:
    """Render a human-readable markdown summary for a run audit."""
    lines = [
        "# Run Audit",
        "",
        f"- **Source:** `{audit.get('source', '')}`",
        f"- **Run valid:** {'YES' if audit.get('run_valid') else 'NO'}",
        f"- **Publishable:** {'YES' if audit.get('publishable') else 'NO'}",
        f"- **Summary status:** {audit.get('summary_status', STATUS_WARN)}",
        f"- **Primary owner:** {audit.get('primary_owner', 'benchmark')}",
        "",
    ]

    for name in CHECK_ORDER:
        check = audit["checks"].get(name)
        if not check:
            continue
        title = name.replace("_", " ").title()
        lines.append(f"## {title}")
        lines.append("")
        lines.append(f"- **Status:** {check['status']}")
        lines.append(f"- **Summary:** {check['summary']}")
        details = check.get("details") or {}
        if details:
            lines.append("- **Details:**")
            for key, value in details.items():
                lines.append(f"  - `{key}`: `{value}`")
        lines.append("")

    return "\n".join(lines)
