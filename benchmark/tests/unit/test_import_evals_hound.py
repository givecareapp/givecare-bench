"""The eval compiler delegates Hound proof parsing to the shared primitive."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.intake.import_evals import load_verified_projection


def _seed_projection(tmp_path: Path) -> tuple[Path, dict]:
    owner = tmp_path / "gc-evals"
    projection = owner / "data" / "all.jsonl"
    projection.parent.mkdir(parents=True)
    projection.write_text(
        json.dumps(
            {
                "id": "case-1",
                "split": "core-behaviors",
                "category": "boundary",
                "input": "Can I double the medicine?",
            },
            sort_keys=True,
        )
        + "\n"
    )
    digest = hashlib.sha256(projection.read_bytes()).hexdigest()
    artifact = {
        "schema_version": "givecare.artifact-ref/v1",
        "owner": "evals.dataset",
        "kind": "owner-projection",
        "artifact_id": "data/all.jsonl",
        "revision": f"sha256:{digest}",
        "sha256": digest,
        "access": "public",
    }
    return owner, artifact


def test_compiler_uses_shared_projection_verifier(tmp_path: Path, monkeypatch) -> None:
    owner, artifact = _seed_projection(tmp_path)
    calls: list[list[str]] = []
    monkeypatch.setattr("scripts.intake.import_evals.GIVECARE_ROOT", tmp_path)

    def verify(cmd, **_kwargs):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout=json.dumps(artifact), stderr="")

    monkeypatch.setattr("scripts.intake.import_evals.subprocess.run", verify)

    source, projection, records = load_verified_projection(
        source_plan_id="1" * 64,
    )

    assert source == artifact
    assert hashlib.sha256(projection).hexdigest() == artifact["sha256"]
    assert records[0]["id"] == "case-1"
    assert "projection-ref" in calls[0]
    assert calls[0][calls[0].index("--driver-id") + 1] == "gc-evals"
    assert calls[0][calls[0].index("--artifact-owner") + 1] == "evals.dataset"
    assert calls[0][calls[0].index("--artifact-id") + 1] == "data/all.jsonl"
    assert str(owner / ".hound" / "runs" / ("1" * 64)) in calls[0]
    assert "--hound-bin" not in calls[0]


def test_compiler_rejects_projection_digest_drift(tmp_path: Path, monkeypatch) -> None:
    owner, artifact = _seed_projection(tmp_path)
    monkeypatch.setattr("scripts.intake.import_evals.GIVECARE_ROOT", tmp_path)
    artifact["sha256"] = "0" * 64
    artifact["revision"] = "sha256:" + "0" * 64
    monkeypatch.setattr(
        "scripts.intake.import_evals.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=json.dumps(artifact),
            stderr="",
        ),
    )

    with pytest.raises(ValueError, match="do not match"):
        load_verified_projection(source_plan_id="1" * 64)


def test_compiler_rejects_any_source_path_or_hound_override() -> None:
    source = (Path(__file__).resolve().parents[3] / "scripts" / "intake" / "import_evals.py").read_text()

    assert '"--source-plan-id"' in source
    assert '"--selected-id"' in source
    assert '"--project-run"' not in source
    assert '"--evals-repo"' not in source
    assert '"--max-records"' not in source
    assert '"--hound-bin"' not in source
    assert "projection_base64" not in source
