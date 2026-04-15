from __future__ import annotations

import json
from pathlib import Path

from invisiblebench.cli import health as health_module


def test_load_leaderboard_prefers_current_output_dir(tmp_path: Path, monkeypatch) -> None:
    leaderboard_dir = tmp_path / "data" / "leaderboard"
    leaderboard_dir.mkdir(parents=True)
    payload = {"metadata": {}, "overall_leaderboard": []}
    (leaderboard_dir / "leaderboard.json").write_text(json.dumps(payload))

    monkeypatch.setattr(health_module, "get_project_root", lambda: tmp_path)

    loaded = health_module.load_leaderboard()

    assert loaded == payload
