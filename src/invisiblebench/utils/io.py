from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load a JSONL file. Parse errors report the offending line number."""
    rows: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as fh:
        for line_number, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSONL: {exc}") from exc
    return rows


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON file that must contain an object at the top level."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected JSON object")
    return data


def read_text(path: Path) -> str:
    return path.read_text()


# The canonical key for the per-model row list in a leaderboard artifact.
# The web-bench projection re-keys the same rows under "models"; both are
# accepted so callers never have to guess which surface they hold.
_LEADERBOARD_ROW_KEYS = ("overall_leaderboard", "models")


def leaderboard_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the per-model rows from a leaderboard artifact.

    Accepts either the canonical ``overall_leaderboard`` key (source artifact)
    or the projected ``models`` key (web-bench payload). Raises ``ValueError``
    with a clear message if neither key holds a list — never a bare ``KeyError``
    on a malformed or unexpected file.
    """
    if not isinstance(data, dict):
        raise ValueError(
            f"Leaderboard artifact is not a JSON object (got {type(data).__name__})"
        )
    for key in _LEADERBOARD_ROW_KEYS:
        rows = data.get(key)
        if isinstance(rows, list):
            return rows
    raise ValueError(
        "Leaderboard artifact missing a row list under any of "
        f"{_LEADERBOARD_ROW_KEYS}; got keys {sorted(data)}"
    )
