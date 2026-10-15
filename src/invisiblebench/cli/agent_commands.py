"""Agent-friendly subcommand handlers: doctor, runs, get, leaderboard JSON envelopes."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from invisiblebench._agent_cli import DoctorCheck, doctor_runner, emit_json
from invisiblebench.utils.benchmark_inventory import get_project_root
from invisiblebench.utils.io import leaderboard_rows
from invisiblebench.utils.manifest import run_timestamp


def _runs_dir() -> Path:
    """Return the canonical runs directory (results/)."""
    return get_project_root() / "results"


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


def _run_doctor(json_output: bool = False) -> int:
    """Validate env vars + runs dir for the bench CLI."""
    runs_dir = _runs_dir()

    def _openrouter_key() -> bool:
        key = os.getenv("OPENROUTER_API_KEY", "")
        return bool(key) and not key.startswith("your_")

    def _typesafe_key() -> bool:
        return bool(os.getenv("TYPESAFE_API_KEY"))

    def _runs_dir_writable() -> bool:
        try:
            runs_dir.mkdir(parents=True, exist_ok=True)
            probe = runs_dir / ".doctor_probe"
            probe.write_text("ok")
            probe.unlink()
            return True
        except OSError:
            return False

    checks = [
        DoctorCheck(
            name="Target API key (OPENROUTER_API_KEY)",
            check=_openrouter_key,
            hint="set OPENROUTER_API_KEY",
        ),
        DoctorCheck(
            name="Judge API key (TYPESAFE_API_KEY)",
            check=_typesafe_key,
            hint="set TYPESAFE_API_KEY; scans and judge-branched scenarios need it",
        ),
        DoctorCheck(
            name=f"runs_dir exists ({runs_dir})",
            check=lambda: runs_dir.exists() and runs_dir.is_dir(),
            hint="mkdir -p results/",
        ),
        DoctorCheck(
            name="runs_dir writable",
            check=_runs_dir_writable,
            hint="chmod +w on the runs directory",
        ),
    ]

    if not json_output:
        return doctor_runner(checks, exit_on_fail=False)

    results: list[dict[str, Any]] = []
    failures = 0
    for c in checks:
        try:
            ok = bool(c.check())
        except Exception as exc:  # noqa: BLE001 — mirrors doctor_runner's own catch-all
            ok = False
            hint = f"{c.hint or ''} ({exc})".strip()
        else:
            hint = c.hint if not ok else None
        if not ok:
            failures += 1
        results.append({"name": c.name, "passed": ok, "hint": hint})

    emit_json(command="doctor", data={"checks": results, "failures": failures})
    return 1 if failures else 0


def _emit_or_write_json(
    *,
    command: str,
    data: dict[str, Any],
    record_count: int,
    out_path: str | None,
) -> int:
    """Emit envelope on stdout, or write full payload to file and emit a summary.

    When out_path is set, the full `data` dict is written to the path and the
    stdout envelope is `{status, command, data: {path, byte_count, record_count}}`.
    Otherwise the full data is inlined. Both cases write exactly one line to
    stdout so agents can parse predictably.
    """
    if out_path:
        try:
            resolved = Path(out_path).expanduser().resolve()
            resolved.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(data, separators=(",", ":"), default=str)
            resolved.write_text(payload)
        except OSError as exc:
            emit_json(
                status="error",
                command=command,
                error=f"failed to write {out_path}: {exc}",
            )
            return 1
        emit_json(
            command=command,
            data={
                "path": str(resolved),
                "byte_count": len(payload),
                "record_count": record_count,
            },
        )
        return 0
    emit_json(command=command, data=data)
    return 0


def _load_run_metadata(run_id: str) -> dict[str, Any] | None:
    """Resolve a run by id (exact or prefix) and return its metadata."""
    results_dir = _runs_dir()
    if not results_dir.exists():
        return None

    candidates: list[Path] = []
    requested = Path(run_id).expanduser()
    direct = requested if requested.is_absolute() or requested.is_dir() else results_dir / run_id
    if direct.is_dir():
        candidates = [direct]
    else:
        for entry in sorted(results_dir.iterdir()):
            if entry.is_dir() and entry.name != "archive" and entry.name.startswith(run_id):
                candidates.append(entry)
        # also check archive
        archive = results_dir / "archive"
        if archive.exists():
            for entry in sorted(archive.iterdir()):
                if entry.is_dir() and entry.name.startswith(run_id):
                    candidates.append(entry)
    if not candidates:
        return None
    if len(candidates) != 1:
        raise ValueError("run prefix matches multiple runs; use the full run directory name")
    run_path = candidates[0]

    info = get_run_info(run_path)
    return {
        "id": run_path.name,
        "path": str(run_path),
        "date": info["date"].isoformat(timespec="seconds") + "Z" if info.get("date") else None,
        "models": info.get("models", []),
        "scenarios": info.get("scenarios", 0),
        "size_mb": round(info.get("size_mb", 0.0), 2),
        "has_results": info.get("has_results", False),
        "artifact_state": info.get("artifact_state", "unknown"),
        "manifests": info["manifests"],
        "jury_card": info["jury_card"],
    }


def _run_get(run_id: str, *, json_output: bool, out_path: str | None = None) -> int:
    """Handle `bench get <run-id>`."""
    try:
        record = _load_run_metadata(run_id)
    except ValueError as exc:
        if json_output:
            emit_json(status="error", command="get", error=str(exc))
        else:
            print(str(exc), file=sys.stderr)
        return 1
    if record is None:
        if json_output:
            emit_json(status="error", command="get", error=f"run not found: {run_id}")
        else:
            print(f"Run not found: {run_id}", file=sys.stderr)
        return 1
    # get always emits JSON envelope (read-by-id, per cli.md)
    return _emit_or_write_json(
        command="get",
        data=record,
        record_count=1,
        out_path=out_path,
    )


def _run_leaderboard_status_json(out_path: str | None = None) -> int:
    """Emit the leaderboard.json contents as a JSON envelope."""
    from invisiblebench.utils.benchmark_inventory import get_project_root

    lb_path = get_project_root() / "data" / "leaderboard" / "leaderboard.json"
    if not lb_path.exists():
        emit_json(
            status="error",
            command="leaderboard",
            error=f"leaderboard.json not found at {lb_path}",
        )
        return 1
    try:
        data = json.loads(lb_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        emit_json(status="error", command="leaderboard", error=str(exc))
        return 1
    try:
        rows = leaderboard_rows(data) if isinstance(data, dict) else []
    except ValueError:
        rows = []
    record_count = len(rows) if rows else 1
    return _emit_or_write_json(
        command="leaderboard",
        data=data,
        record_count=record_count,
        out_path=out_path,
    )
