from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from invisiblebench.cli import review as review_mod
from invisiblebench.cli import runner as runner_mod


def review_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "review"
    directory.mkdir()
    (directory / "batch.json").write_text(json.dumps([{"card_id": "one"}, {"card_id": "two"}]))
    (directory / "tokens.txt").write_text(
        "role=reviewer id=reviewer-a slot=1 seed=1 token=secret-a\n"
        "role=admin id=admin token=secret-admin\n"
    )
    connection = sqlite3.connect(directory / "reviews.db")
    connection.execute("CREATE TABLE annotations (reviewer_id TEXT, card_id TEXT, verdict TEXT)")
    connection.execute("INSERT INTO annotations VALUES ('reviewer-a', 'one', 'PASS')")
    connection.commit()
    connection.close()
    return directory


def test_review_status_reports_progress_without_token_values(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    directory = review_dir(tmp_path)
    monkeypatch.setattr(review_mod, "_server_live", lambda **_kwargs: False)

    rc = runner_mod.main(["--json", "review", "status", "--dir", str(directory)])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "review.status"
    assert payload["data"] == {
        "review_dir": str(directory.resolve()),
        "batch_path": str((directory / "batch.json").resolve()),
        "batch_cards": 2,
        "reviewers": 1,
        "admin_tokens": 1,
        "annotations": 1,
        "server_live": False,
        "server_url": "http://127.0.0.1:3090",
    }
    assert "secret-a" not in json.dumps(payload)
    assert "secret-admin" not in json.dumps(payload)


def test_review_build_refuses_to_replace_existing_batch_without_yes(tmp_path: Path, capsys) -> None:
    directory = review_dir(tmp_path)

    rc = runner_mod.main(["review", "build", "--out-dir", str(directory)])

    assert rc == 2
    assert "--yes" in capsys.readouterr().err


def test_review_build_uses_existing_blind_exporter(tmp_path: Path, monkeypatch) -> None:
    directory = tmp_path / "new-review"
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(review_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(review_mod, "_repo_root", lambda: tmp_path)
    script = tmp_path / "scripts" / "review_ui" / "export_batch.py"
    script.parent.mkdir(parents=True)
    script.write_text("# test")

    rc = runner_mod.main(["review", "build", "--out-dir", str(directory), "--yes"])

    assert rc == 0
    assert calls == [
        (
            [
                review_mod.sys.executable,
                str(script),
                "--out",
                str(directory / "batch.json"),
            ],
            {"cwd": tmp_path, "check": False},
        )
    ]


def test_review_serve_requires_confirmation_for_non_loopback(tmp_path: Path, capsys) -> None:
    rc = runner_mod.main(
        [
            "review",
            "serve",
            "--dir",
            str(tmp_path),
            "--host",
            "0.0.0.0",
        ]
    )

    assert rc == 2
    assert "--yes" in capsys.readouterr().err
