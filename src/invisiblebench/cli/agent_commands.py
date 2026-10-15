"""Subcommand handlers: doctor, runs, get, and the shared JSON envelope."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from invisiblebench.utils.benchmark_inventory import get_project_root
from invisiblebench.utils.manifest import run_timestamp


def emit_json(command: str, data: Any = None, error: str | None = None) -> None:
    """Write one {status, command, data|error} line to stdout."""
    payload: dict[str, Any] = {"status": "error" if error else "ok", "command": command}
    if data is not None:
        payload["data"] = data
    if error:
        payload["error"] = error
    print(json.dumps(payload, separators=(",", ":"), default=str))


def _runs_dir() -> Path:
    """Return the canonical runs directory (results/)."""
    return get_project_root() / "results"


def get_run_info(run_path: Path, *, verify: bool = True) -> dict[str, Any]:
    """Get info about a run directory. Without verify, a scan is read, not replayed."""
    manifest_file = run_path / "run_manifest.json"
    info = {
        "id": run_path.name,
        "path": str(run_path),
        "date": None,
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
        from invisiblebench.judge import LEDGER_FILE, load_questions, load_scan
        from invisiblebench.models.scan import QuestionPlan, ScanPlan

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
                if verify:
                    plan, _answers, records = load_scan(run_path)
                    judged = len(records)
                else:
                    plan = ScanPlan.model_validate_json((run_path / "scan_plan.json").read_bytes())
                    path = run_path / LEDGER_FILE
                    judged = path.read_bytes().count(b"\n") if path.is_file() else 0
                info["models"] = sorted({ref.model_id for ref in plan.transcripts})
                info["scenarios"] = len(plan.transcripts)
                info["has_results"] = judged == plan.planned_judgments
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
    date = run_timestamp(run_path, info["manifests"])
    info["date"] = date.isoformat(timespec="seconds") + "Z" if date else None
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
            runs.append(get_run_info(d, verify=False))
    return runs


def _run_doctor(json_output: bool = False) -> int:
    """Validate env vars + runs dir for the bench CLI."""
    runs_dir = _runs_dir()

    def runs_dir_writable() -> bool:
        try:
            runs_dir.mkdir(parents=True, exist_ok=True)
            probe = runs_dir / ".doctor_probe"
            probe.write_text("ok")
            probe.unlink()
            return True
        except OSError:
            return False

    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    checks = [
        (
            "Target API key (OPENROUTER_API_KEY)",
            bool(openrouter_key) and not openrouter_key.startswith("your_"),
            "set OPENROUTER_API_KEY",
        ),
        (
            "Judge API key (TYPESAFE_API_KEY)",
            bool(os.getenv("TYPESAFE_API_KEY")),
            "set TYPESAFE_API_KEY; scans and judge-branched scenarios need it",
        ),
        (f"runs_dir exists ({runs_dir})", runs_dir.is_dir(), "mkdir -p results/"),
        ("runs_dir writable", runs_dir_writable(), "chmod +w on the runs directory"),
    ]
    results = [
        {"name": name, "passed": ok, "hint": None if ok else hint} for name, ok, hint in checks
    ]
    failures = sum(not row["passed"] for row in results)
    if json_output:
        emit_json("doctor", {"checks": results, "failures": failures})
    else:
        for row in results:
            line = f"  [{'PASS' if row['passed'] else 'FAIL'}] {row['name']}"
            print(line + (f"  - {row['hint']}" if row["hint"] else ""), file=sys.stderr)
        print(f"\ndoctor: {failures} check(s) failed" if failures else "\ndoctor: all checks passed",
              file=sys.stderr)
    return 1 if failures else 0


def _load_run_metadata(run_id: str) -> dict[str, Any] | None:
    """Resolve a run by id (exact or prefix) and return its metadata."""
    results_dir = _runs_dir()
    if not results_dir.exists():
        return None

    requested = Path(run_id).expanduser()
    direct = requested if requested.is_absolute() or requested.is_dir() else results_dir / run_id
    if direct.is_dir():
        candidates = [direct]
    else:
        candidates = [
            entry
            for parent in (results_dir, results_dir / "archive")
            if parent.is_dir()
            for entry in sorted(parent.iterdir())
            if entry.is_dir() and entry.name != "archive" and entry.name.startswith(run_id)
        ]
    if not candidates:
        return None
    if len(candidates) != 1:
        raise ValueError("run prefix matches multiple runs; use the full run directory name")
    return get_run_info(candidates[0])


def _run_get(run_id: str, *, json_output: bool) -> int:
    """Handle `bench get <run-id>`; always emits the JSON envelope on success."""
    try:
        record = _load_run_metadata(run_id)
        error = None if record is not None else f"run not found: {run_id}"
    except ValueError as exc:
        error = str(exc)
    if error:
        if json_output:
            emit_json("get", error=error)
        else:
            print(error, file=sys.stderr)
        return 1
    emit_json("get", record)
    return 0
