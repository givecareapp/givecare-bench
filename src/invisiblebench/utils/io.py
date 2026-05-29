from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


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
