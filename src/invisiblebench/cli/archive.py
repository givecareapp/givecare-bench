#!/usr/bin/env python3
"""Archive management for InvisibleBench results."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from invisiblebench.cli._console import make_console
from invisiblebench.utils.benchmark_inventory import get_project_root
from invisiblebench.utils.manifest import run_timestamp


def get_run_info(run_path: Path) -> dict[str, Any]:
    """Get info about a run directory."""
    manifest_file = run_path / "run_manifest.json"
    info = {
        "path": run_path,
        "name": run_path.name,
        "date": None,
        "size_mb": sum(f.stat().st_size for f in run_path.rglob("*") if f.is_file())
        / (1024 * 1024),
        "has_results": False,
        "artifact_state": "empty_no_results",
        "models": [],
        "scenarios": 0,
        "manifests": [],
        "jury_card": (
            str(run_path / "jury-card.md") if (run_path / "jury-card.md").is_file() else None
        ),
    }
    if (run_path / "scan_plan.json").exists():
        from invisiblebench.judge import load_questions, load_scan
        from invisiblebench.models.scan import QuestionPlan

        try:
            schema = json.loads((run_path / "scan_plan.json").read_bytes())["schema_version"]
            if schema == QuestionPlan.model_fields["schema_version"].default:
                plan, answers = load_questions(run_path)
                info["scenarios"] = len({task.scenario_id for task in plan.tasks})
                info["has_results"] = sum(a.error is None for a in answers) == len(plan.tasks)
                info["artifact_state"] = (
                    "questions_complete" if info["has_results"] else "questions_incomplete"
                )
            else:
                plan, _answers, records = load_scan(run_path)
                info["models"] = sorted({ref.model_id for ref in plan.transcripts})
                info["scenarios"] = len(plan.transcripts)
                info["has_results"] = len(records) == plan.planned_judgments
                info["artifact_state"] = "judged" if info["has_results"] else "judging_incomplete"
                info["manifests"] = [
                    json.loads((run_path / source.manifest.path).read_bytes())
                    for source in plan.sources
                ]
        except (OSError, ValueError, KeyError) as exc:
            info.update(artifact_state="invalid_scan", error=str(exc))
    elif (run_path / "transcript_run.json").exists():
        try:
            with open(run_path / "transcript_run.json") as f:
                transcript_data = json.load(f)
        except (OSError, json.JSONDecodeError):
            transcript_data = None
        if isinstance(transcript_data, dict):
            info["scenarios"] = int(transcript_data.get("transcript_count") or 0)
            info["models"] = [str(model_id) for model_id in transcript_data.get("model_ids", [])]
            expected = int(transcript_data.get("expected_transcripts") or 0)
            transcript_count = int(transcript_data.get("transcript_count") or 0)
            error_count = int(transcript_data.get("error_count") or 0)
            missing_count = int(transcript_data.get("missing_count") or 0)
            status = transcript_data.get("status")
            info["artifact_state"] = (
                "transcripts_ready"
                if (
                    status == "complete"
                    and error_count == 0
                    and missing_count == 0
                    and (expected == 0 or transcript_count == expected)
                )
                else "transcripts_partial"
            )
        else:
            info["artifact_state"] = "invalid_transcript_run"
    elif manifest_file.exists():
        has_partial_artifacts = any(
            (run_path / name).exists() for name in ("model_results", "transcripts")
        )
        info["artifact_state"] = (
            "incomplete_no_results" if has_partial_artifacts else "aborted_manifest_only"
        )

    if not info["manifests"] and manifest_file.exists():
        try:
            manifest = json.loads(manifest_file.read_bytes())
            if isinstance(manifest, dict):
                info["manifests"] = [manifest]
        except (OSError, ValueError):
            pass
    info["date"] = run_timestamp(run_path, info["manifests"])
    return info


def list_runs(results_dir: Path) -> list[dict[str, Any]]:
    """List all run directories with info."""
    runs = []
    for d in sorted(results_dir.iterdir()) if results_dir.exists() else []:
        if (
            d.is_dir()
            and d.name != "archive"
            and any((d / name).is_file() for name in ("run_manifest.json", "scan_plan.json"))
        ):
            runs.append(get_run_info(d))
    return runs


def archive_runs(
    before_date: datetime | None = None,
    keep_recent: int | None = None,
    dry_run: bool = False,
) -> tuple[list[Path], list[Path]]:
    """
    Archive run directories.

    Returns (archived, kept) lists of paths.
    """
    root = get_project_root()
    results_dir = root / "results"
    archive_dir = results_dir / "archive"

    if not results_dir.exists():
        return [], []

    runs = list_runs(results_dir)

    to_archive = []
    to_keep = []

    if keep_recent is not None:
        sorted_runs = sorted(runs, key=lambda r: r["date"] or datetime.min, reverse=True)
        to_keep = sorted_runs[:keep_recent]
        to_archive = sorted_runs[keep_recent:]
    elif before_date is not None:
        for run in runs:
            if run["date"] and run["date"] < before_date:
                to_archive.append(run)
            else:
                to_keep.append(run)
    else:
        today = datetime.now(UTC).replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0)
        for run in runs:
            if run["date"] and run["date"] < today:
                to_archive.append(run)
            else:
                to_keep.append(run)

    archived_paths = []
    if not dry_run and to_archive:
        archive_dir.mkdir(parents=True, exist_ok=True)
        for run in to_archive:
            if (archive_dir / run["name"]).exists():
                raise FileExistsError(
                    f"archive destination already exists: {archive_dir / run['name']}"
                )
        for run in to_archive:
            src = run["path"]
            dst = archive_dir / run["name"]
            shutil.move(str(src), str(dst))
            archived_paths.append(dst)

    return (
        [r["path"] for r in to_archive] if dry_run else archived_paths,
        [r["path"] for r in to_keep],
    )


def print_archive_report(
    to_archive: list[Path],
    to_keep: list[Path],
    dry_run: bool = False,
    console: Any | None = None,
) -> None:
    """Print archive report."""
    console = console or make_console()
    out = console.print

    action = "Would archive" if dry_run else "Archived"

    out("\n[bold]═══ Archive Report ═══[/bold]\n")

    if to_archive:
        out(f"[yellow]{action} {len(to_archive)} run(s):[/yellow]")
        for p in to_archive:
            out(f"  • {p.name}")
    else:
        out("[green]Nothing to archive[/green]")

    out(f"\n[green]Keeping {len(to_keep)} run(s):[/green]")
    for p in to_keep:
        out(f"  • {p.name}")

    out("")


def run_archive(
    before: str | None = None,
    keep: int | None = None,
    dry_run: bool = False,
) -> int:
    """Run archive command."""
    console = make_console()

    before_date = None
    if before:
        try:
            before_date = datetime.strptime(before, "%Y%m%d")
        except ValueError:
            print(f"Invalid date format: {before}. Use YYYYMMDD.")
            return 1

    try:
        archived, kept = archive_runs(
            before_date=before_date,
            keep_recent=keep,
            dry_run=dry_run,
        )
    except OSError as exc:
        print(f"Cannot archive: {exc}")
        return 1

    print_archive_report(archived, kept, dry_run=dry_run, console=console)

    return 0
