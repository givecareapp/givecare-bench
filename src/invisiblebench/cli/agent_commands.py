"""Agent-friendly subcommand handlers: doctor, runs, get, leaderboard JSON envelopes."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from invisiblebench._agent_cli import DoctorCheck, doctor_runner, emit_json


def _runs_dir() -> Path:
    """Return the canonical runs directory (results/)."""
    from invisiblebench.cli.archive import get_project_root

    return get_project_root() / "results"


def _run_doctor() -> int:
    """Validate env vars + runs dir for the bench CLI."""
    runs_dir = _runs_dir()

    def _any_llm_key() -> bool:
        return any(
            os.environ.get(k)
            for k in ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")
        )

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
            name="LLM API key (OPENROUTER_API_KEY | OPENAI_API_KEY | ANTHROPIC_API_KEY)",
            check=_any_llm_key,
            hint="set one of OPENROUTER_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY",
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
    return doctor_runner(checks, exit_on_fail=False)


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
    direct = results_dir / run_id
    if direct.is_dir():
        candidates = [direct]
    else:
        for entry in sorted(results_dir.iterdir()):
            if entry.is_dir() and entry.name.startswith(run_id):
                candidates.append(entry)
        # also check archive
        archive = results_dir / "archive"
        if archive.exists():
            for entry in sorted(archive.iterdir()):
                if entry.is_dir() and entry.name.startswith(run_id):
                    candidates.append(entry)
    if not candidates:
        return None
    # pick newest mtime when multiple
    run_path = max(candidates, key=lambda p: p.stat().st_mtime)

    manifest_path = run_path / "run_manifest.json"
    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            manifest = {"_manifest_error": str(exc)}

    from invisiblebench.cli.archive import get_run_info

    info = get_run_info(run_path)
    return {
        "id": run_path.name,
        "path": str(run_path),
        "date": info["date"].strftime("%Y-%m-%d") if info.get("date") else None,
        "models": info.get("models", []),
        "scenarios": info.get("scenarios", 0),
        "size_mb": round(info.get("size_mb", 0.0), 2),
        "has_results": info.get("has_results", False),
        "manifest": manifest,
    }


def _run_get(run_id: str, *, json_output: bool, out_path: str | None = None) -> int:
    """Handle `bench get <run-id>`."""
    record = _load_run_metadata(run_id)
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
    from invisiblebench.cli.leaderboard import _leaderboard_output

    lb_path = _leaderboard_output() / "leaderboard.json"
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
    rows = data.get("overall_leaderboard") if isinstance(data, dict) else None
    record_count = len(rows) if isinstance(rows, list) else 1
    return _emit_or_write_json(
        command="leaderboard",
        data=data,
        record_count=record_count,
        out_path=out_path,
    )


def _read_leaderboard_json() -> tuple[dict[str, Any] | None, str | None]:
    """Return (leaderboard.json contents, error) for envelope payloads."""
    from invisiblebench.cli.leaderboard import _leaderboard_output

    lb_path = _leaderboard_output() / "leaderboard.json"
    if not lb_path.exists():
        return None, f"leaderboard.json not found at {lb_path}"
    try:
        return json.loads(lb_path.read_text()), None
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)


def _run_leaderboard_mutation_json(action: str, results_path: str | None) -> int:
    """Run leaderboard add/rebuild with stdout redirected, then emit JSON envelope.

    Suppresses Rich table output on stdout so the `{status, command, data}`
    envelope is the only line on stdout. Human-facing status messages are
    redirected to stderr. The envelope payload always includes the current
    leaderboard.json (when present) so agents see state on both success and
    failure. A nonzero exit from the underlying call is surfaced as
    `data.exit_code`; status=error is set only if the exit code is nonzero
    or leaderboard.json cannot be read.
    """
    import contextlib

    from invisiblebench.cli.leaderboard import run_leaderboard

    rc: int
    try:
        with contextlib.redirect_stdout(sys.stderr):
            rc = run_leaderboard(
                action=action,
                results_path=results_path,
                verbose=False,
            )
    except (OSError, json.JSONDecodeError, ValueError, RuntimeError) as exc:
        emit_json(status="error", command="leaderboard", error=f"{action}: {exc}")
        return 1

    data, err = _read_leaderboard_json()
    payload: dict[str, Any] = {
        "action": action,
        "exit_code": rc,
        "leaderboard": data,
    }
    if err is not None:
        emit_json(
            status="error",
            command="leaderboard",
            data=payload,
            error=f"{action}: {err}",
        )
        return rc or 1
    if rc != 0:
        emit_json(
            status="error",
            command="leaderboard",
            data=payload,
            error=f"{action} exited {rc}; see stderr for details",
        )
        return rc
    emit_json(command="leaderboard", data=payload)
    return 0
