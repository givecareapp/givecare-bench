from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

CURRENT_BOARD_LEADERBOARD_DIR = Path("results/leaderboard_ready")
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


def _model_prefix_candidates(model_id: str) -> List[str]:
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
) -> Optional[Path]:
    prefixes = _model_prefix_candidates(model_id)
    roots = [project_root / transcript_dir for transcript_dir in transcript_dirs]

    for prefix in prefixes:
        for root in roots:
            candidate = root / f"{prefix}_{scenario_id}.jsonl"
            if candidate.exists():
                return candidate

    return None


def _resolve_detail_path(project_root: Path, raw_path: Optional[str]) -> Optional[Path]:
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


def _iter_leaderboard_documents(leaderboard_dir: Path) -> Iterable[Tuple[Path, Dict[str, Any]]]:
    for path in sorted(leaderboard_dir.glob("*.json")):
        with open(path) as fh:
            yield path, json.load(fh)


def build_verifier_corpus_manifest(
    project_root: Path,
    *,
    leaderboard_dir: Path = CURRENT_BOARD_LEADERBOARD_DIR,
    transcript_dirs: Sequence[Path] = CURRENT_BOARD_TRANSCRIPT_DIRS,
) -> List[Dict[str, Any]]:
    """Build a manifest over the current 15-model leaderboard corpus.

    The manifest unifies leaderboard rows, transcript locations, and resolved detail
    artifact paths without copying any raw result files.
    """

    manifest: List[Dict[str, Any]] = []
    leaderboard_root = project_root / leaderboard_dir

    for leaderboard_file, doc in _iter_leaderboard_documents(leaderboard_root):
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
                "category": scenario.get("category", scenario.get("tier", "unknown")),
                "tier": scenario.get("tier", scenario.get("category", "unknown")),
                "overall_score": scenario.get("overall_score", 0.0),
                "status": scenario.get("status", "error"),
                "success": scenario.get("success"),
                "hard_fail": scenario.get("hard_fail", False),
                "hard_fail_reasons": scenario.get("hard_fail_reasons", []),
                "judge_model": scenario.get("judge_model"),
                "contract_version": scenario.get("contract_version"),
                "leaderboard_file": _relative_to_project(leaderboard_file, project_root),
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


def build_verifier_corpus_summary(manifest: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    by_model: Dict[str, Dict[str, Any]] = {}
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


def write_verifier_corpus_manifest(
    project_root: Path,
    output_path: Path,
    *,
    leaderboard_dir: Path = CURRENT_BOARD_LEADERBOARD_DIR,
    transcript_dirs: Sequence[Path] = CURRENT_BOARD_TRANSCRIPT_DIRS,
) -> List[Dict[str, Any]]:
    manifest = build_verifier_corpus_manifest(
        project_root,
        leaderboard_dir=leaderboard_dir,
        transcript_dirs=transcript_dirs,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as fh:
        for row in manifest:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    return manifest


def write_verifier_corpus_summary(summary: Dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
