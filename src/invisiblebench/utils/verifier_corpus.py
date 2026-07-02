from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Sequence

from invisiblebench.models.results import (
    PUBLIC_SCORE_MODEL,
    RAW_RESULT_SURFACE,
    RAW_SCORE_MODEL,
)

CURRENT_BOARD_RAW_MODEL_RESULTS_DIR = Path("results/raw_model_results")
CURRENT_BOARD_TRANSCRIPT_DIRS = (
    Path("results/run_20260330_130332/transcripts"),
    Path("results/partial_runs/run_20260330_033649_up_to_deepseek/transcripts"),
)
DETAIL_PATH_REWRITES = {
    "results/run_20260330_033649/": "results/partial_runs/run_20260330_033649_up_to_deepseek/",
}
TRANSCRIPT_PREFIX_ALIASES = {
    "google_gemini-3.1-pro": ("google_gemini-3.1-pro-preview",),
}


def _relative_to_project(path: Path, project_root: Path) -> str:
    return str(path.relative_to(project_root))


def _model_prefix_candidates(model_id: str) -> list[str]:
    base = model_id.replace("/", "_")
    candidates = [base]
    candidates.extend(TRANSCRIPT_PREFIX_ALIASES.get(base, ()))
    return candidates


def _resolve_transcript_path(
    *,
    project_root: Path,
    transcript_dirs: Sequence[Path],
    model_id: str,
    scenario_id: str,
) -> Path | None:
    prefixes = _model_prefix_candidates(model_id)
    roots = [project_root / transcript_dir for transcript_dir in transcript_dirs]

    for prefix in prefixes:
        for root in roots:
            candidate = root / f"{prefix}_{scenario_id}.jsonl"
            if candidate.exists():
                return candidate

    return None


def _resolve_detail_path(project_root: Path, raw_path: str | None) -> Path | None:
    if not raw_path:
        return None

    direct = project_root / raw_path
    if direct.exists():
        return direct

    for old_prefix, new_prefix in DETAIL_PATH_REWRITES.items():
        if raw_path.startswith(old_prefix):
            rewritten = project_root / raw_path.replace(old_prefix, new_prefix, 1)
            if rewritten.exists():
                return rewritten

    return None


def _iter_raw_model_documents(raw_results_dir: Path) -> Iterable[tuple[Path, dict[str, Any]]]:
    for path in sorted(raw_results_dir.glob("*.json")):
        with open(path) as fh:
            yield path, json.load(fh)


def build_verifier_corpus_manifest(
    project_root: Path,
    *,
    raw_results_dir: Path = CURRENT_BOARD_RAW_MODEL_RESULTS_DIR,
    transcript_dirs: Sequence[Path] = CURRENT_BOARD_TRANSCRIPT_DIRS,
) -> list[dict[str, Any]]:
    """Build a manifest over raw/internal per-model result documents.

    The manifest unifies raw model-result rows, transcript locations, and
    resolved detail artifact paths without copying any raw result files.
    """

    manifest: list[dict[str, Any]] = []
    raw_results_root = project_root / raw_results_dir

    for raw_results_file, doc in _iter_raw_model_documents(raw_results_root):
        model = doc.get("model", doc.get("model_name", "unknown"))
        model_id = doc.get("model_id", model)
        provider = doc.get("provider")

        for scenario in doc.get("scenarios", []):
            transcript_path = _resolve_transcript_path(
                project_root=project_root,
                transcript_dirs=transcript_dirs,
                model_id=model_id,
                scenario_id=scenario["scenario_id"],
            )
            detail_json_raw = scenario.get("detail_json")
            detail_html_raw = scenario.get("detail_html")
            detail_json_path = _resolve_detail_path(project_root, detail_json_raw)
            detail_html_path = _resolve_detail_path(project_root, detail_html_raw)

            entry = {
                "model": model,
                "model_id": model_id,
                "provider": provider,
                "scenario": scenario.get("scenario"),
                "scenario_id": scenario.get("scenario_id"),
                "category": scenario.get("category", "unknown"),
                "result_surface": scenario.get("result_surface", RAW_RESULT_SURFACE),
                "score_model": scenario.get("score_model", RAW_SCORE_MODEL),
                "public_score_model": scenario.get("public_score_model", PUBLIC_SCORE_MODEL),
                "overall_score": scenario.get("overall_score", 0.0),
                "status": scenario.get("status", "error"),
                "success": scenario.get("success"),
                "hard_fail": scenario.get("hard_fail", False),
                "hard_fail_reasons": scenario.get("hard_fail_reasons", []),
                "judge_model": scenario.get("judge_model"),
                "contract_version": scenario.get("contract_version"),
                "raw_results_file": _relative_to_project(raw_results_file, project_root),
                "transcript_path": (
                    _relative_to_project(transcript_path, project_root)
                    if transcript_path is not None
                    else None
                ),
                "transcript_found": transcript_path is not None,
                "transcript_source_run": transcript_path.parent.parent.name if transcript_path else None,
                "detail_json": detail_json_raw,
                "detail_json_resolved": (
                    _relative_to_project(detail_json_path, project_root)
                    if detail_json_path is not None
                    else None
                ),
                "detail_json_exists": detail_json_path is not None,
                "detail_html": detail_html_raw,
                "detail_html_resolved": (
                    _relative_to_project(detail_html_path, project_root)
                    if detail_html_path is not None
                    else None
                ),
                "detail_html_exists": detail_html_path is not None,
            }
            manifest.append(entry)

    return manifest


def build_verifier_corpus_summary(manifest: Sequence[dict[str, Any]]) -> dict[str, Any]:
    by_model: dict[str, dict[str, Any]] = {}
    for row in manifest:
        stats = by_model.setdefault(
            row["model"],
            {
                "traces": 0,
                "transcripts_found": 0,
                "error_rows": 0,
                "hard_fails": 0,
                "detail_json_found": 0,
                "detail_html_found": 0,
                "source_runs": set(),
            },
        )
        stats["traces"] += 1
        stats["transcripts_found"] += int(bool(row["transcript_found"]))
        stats["error_rows"] += int(row.get("status") == "error")
        stats["hard_fails"] += int(bool(row.get("hard_fail")))
        stats["detail_json_found"] += int(bool(row.get("detail_json_exists")))
        stats["detail_html_found"] += int(bool(row.get("detail_html_exists")))
        if row.get("transcript_source_run"):
            stats["source_runs"].add(row["transcript_source_run"])

    model_rows = []
    for model, stats in sorted(by_model.items()):
        model_rows.append(
            {
                "model": model,
                "traces": stats["traces"],
                "transcripts_found": stats["transcripts_found"],
                "error_rows": stats["error_rows"],
                "hard_fails": stats["hard_fails"],
                "detail_json_found": stats["detail_json_found"],
                "detail_html_found": stats["detail_html_found"],
                "source_runs": sorted(stats["source_runs"]),
            }
        )

    return {
        "traces": len(manifest),
        "models": len(by_model),
        "transcripts_found": sum(int(bool(row.get("transcript_found"))) for row in manifest),
        "detail_json_found": sum(int(bool(row.get("detail_json_exists"))) for row in manifest),
        "detail_html_found": sum(int(bool(row.get("detail_html_exists"))) for row in manifest),
        "error_rows": sum(int(row.get("status") == "error") for row in manifest),
        "hard_fails": sum(int(bool(row.get("hard_fail"))) for row in manifest),
        "models_by_name": model_rows,
    }
