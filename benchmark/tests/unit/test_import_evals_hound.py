"""The Evals compiler consumes only the fixed local materialization."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.intake.import_evals import load_verified_projection


def _source(content: bytes) -> dict[str, str]:
    digest = hashlib.sha256(content).hexdigest()
    return {
        "schema_version": "givecare.artifact-ref/v1",
        "owner": "evals.dataset",
        "kind": "owner-projection",
        "artifact_id": "data/all.jsonl",
        "revision": f"sha256:{digest}",
        "sha256": digest,
        "access": "public",
    }


def test_compiler_reads_the_local_evals_materialization(monkeypatch) -> None:
    content = (json.dumps({"id": "case-1", "input": "Help"}) + "\n").encode()
    monkeypatch.setattr(
        "scripts.sync_evals_projection.load_materialized_source",
        lambda: ("a" * 64, _source(content), content),
    )

    source, projection, records = load_verified_projection()

    assert source == _source(content)
    assert projection == content
    assert records == [{"id": "case-1", "input": "Help"}]


def test_compiler_rejects_invalid_local_projection(monkeypatch) -> None:
    from scripts.sync_evals_projection import ProjectionSyncError

    monkeypatch.setattr(
        "scripts.sync_evals_projection.load_materialized_source",
        lambda: (_ for _ in ()).throw(ProjectionSyncError("local proof failed")),
    )
    with pytest.raises(ValueError, match="local proof failed"):
        load_verified_projection()


def test_compiler_has_no_foreign_run_or_repository_argument() -> None:
    source = (Path(__file__).resolve().parents[3] / "scripts" / "intake" / "import_evals.py").read_text()
    for retired in ("--source-plan-id", "--project-run", "--evals-repo", "--hound-bin", "gc-evals/.hound"):
        assert retired not in source
