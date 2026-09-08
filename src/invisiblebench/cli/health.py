"""Read-only status for the current aggregate projection."""

from __future__ import annotations

import hashlib
import json
import tarfile
from pathlib import Path
from typing import Any

from invisiblebench._agent_cli import emit_json
from invisiblebench.scoring.projection import SCHEMA_VERSION
from invisiblebench.utils.benchmark_inventory import get_project_root
from invisiblebench.version import BENCHMARK_VERSION


def load_leaderboard() -> dict[str, Any]:
    return json.loads((get_project_root() / "data/leaderboard/leaderboard.json").read_text())


def analyze_leaderboard(data: dict[str, Any]) -> dict[str, Any]:
    metadata = data.get("scan_metadata") or {}
    if data.get("schema") != SCHEMA_VERSION or metadata.get("benchmark_version") != BENCHMARK_VERSION:
        return {"current": False, "schema": data.get("schema"), "model_count": 0,
                "errors": ["The retained leaderboard is historical. No current benchmark result is published."]}
    models = data.get("models")
    errors = []
    if not isinstance(models, list) or not models:
        errors.append("The current leaderboard has no model observations.")
    if data.get("provenance_status") == "historical-unverified":
        errors.append("The leaderboard does not have verified source records.")
    return {"current": True, "schema": SCHEMA_VERSION,
            "model_count": len(models) if isinstance(models, list) else 0, "errors": errors}


def append_local_web_release_health(analysis: dict[str, Any], *, root: Path | None = None) -> None:
    root = root or get_project_root()
    target = root / "data/releases/web-bench-release.tar.gz"
    try:
        with tarfile.open(target, "r:gz") as archive:
            manifest_file = archive.extractfile("release-manifest.json")
            if manifest_file is None:
                raise ValueError("Release manifest is missing")
            manifest = json.load(manifest_file)
            if manifest.get("schema_version") != "gc-bench.web-benchmark-release/v2":
                raise ValueError("Release archive uses a retired contract")
            if manifest.get("release_version") != f"v{BENCHMARK_VERSION}":
                raise ValueError("Release archive uses another benchmark version")
            members = manifest.get("members")
            if not isinstance(members, list) or len(members) != 1 or members[0].get("path") != "leaderboard.json":
                raise ValueError("Release member list is invalid")
            if set(archive.getnames()) != {"release-manifest.json", "leaderboard.json"}:
                raise ValueError("Release contains unexpected members")
            data = archive.extractfile("leaderboard.json").read()
            if hashlib.sha256(data).hexdigest() != members[0].get("sha256"):
                raise ValueError("Release member hash differs")
            if data != (root / "data/leaderboard/leaderboard.json").read_bytes():
                raise ValueError("Release differs from the committed projection")
    except (OSError, ValueError, KeyError, AttributeError, tarfile.TarError) as exc:
        analysis["errors"].append(str(exc))


def run_health(verbose: bool = False, json_output: bool = False) -> int:
    del verbose
    try:
        analysis = analyze_leaderboard(load_leaderboard())
    except (OSError, ValueError) as exc:
        analysis = {"current": False, "model_count": 0, "errors": [str(exc)]}
    if analysis["current"]:
        append_local_web_release_health(analysis)
    if json_output:
        emit_json(command="health", data=analysis)
    else:
        print(f"Current benchmark projection: {analysis['current']}")
        print(f"Models: {analysis['model_count']}")
        for error in analysis["errors"]:
            print(error)
    return 1 if analysis["errors"] else 0
