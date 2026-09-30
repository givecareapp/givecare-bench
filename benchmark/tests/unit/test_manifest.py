"""Manifests bind run identity, source bytes, and the owning checkout."""

import json
import subprocess
import sys
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from invisiblebench.utils import manifest as manifests
from invisiblebench.utils.benchmark_inventory import get_project_root
from invisiblebench.version import BENCHMARK_VERSION


@pytest.fixture
def project_root():
    return get_project_root()


def test_manifest_captures_run_identity_and_generation_policy(project_root):
    policy = {"system_prompt_hash": "abc123", "temperature": 0.7}
    manifest = manifests.generate_manifest(
        project_root,
        model_ids=["provider/model"],
        scenario_ids=["s2", "s1", "s1"],
        transcript_policy=policy,
        run_id="fixture-run",
    )
    assert manifest["schema"] == "invisiblebench-run-manifest/v3"
    assert manifest["run_id"] == "fixture-run"
    assert manifest["model_ids"] == ["provider/model"]
    assert manifest["scenario_ids"] == ["s1", "s2"]
    assert manifest["transcript_policy"] == policy
    assert manifest["benchmark_version"] == manifest["code_version"] == BENCHMARK_VERSION
    assert manifest["python_version"] == sys.version
    assert datetime.fromisoformat(manifest["run_date"]).tzinfo == UTC
    assert manifest["scenario_hash"] == manifests.scenario_corpus_hash(project_root)


@pytest.mark.parametrize("failure", ["sha", "status", "exception", "malformed"])
def test_git_inspection_failure_stays_unknown(project_root, monkeypatch, failure):
    seen = []

    def inspect(args, **kwargs):
        seen.append(kwargs.get("cwd"))
        if failure == "exception":
            raise OSError("git unavailable")
        sha_call = "rev-parse" in args
        failed = (failure == "sha" and sha_call) or (failure == "status" and not sha_call)
        value = "unknown" if failure == "malformed" else "a" * 40
        return SimpleNamespace(returncode=int(failed), stdout=value if sha_call else "")

    monkeypatch.setattr(manifests.subprocess, "run", inspect)
    manifest = manifests.generate_manifest(project_root, model_ids=[])
    assert manifest["git_sha"] is manifest["git_dirty"] is None
    assert seen and all(root == project_root for root in seen)


def test_git_state_reads_the_selected_checkout_and_reports_dirty_files(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "core.hooksPath=/dev/null",
            "commit",
            "--allow-empty",
            "-qm",
            "Fixture",
        ],
        cwd=tmp_path,
        check=True,
    )
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert manifests._git_state(tmp_path) == (commit, False)
    (tmp_path / "untracked").write_text("changed")
    assert manifests._git_state(tmp_path) == (commit, True)


def test_scenario_hash_binds_contents_and_paths_without_binding_checkout_location(tmp_path):
    files = [("nested/b.json", '{"id":"b"}'), ("a.json", '{"id":"a"}')]
    first, second = tmp_path / "first", tmp_path / "second"
    for root, entries in [(first, files), (second, reversed(files))]:
        for name, text in entries:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
    saved = manifests._scenario_hash(first)
    assert manifests._scenario_hash(second) == saved
    source = first / "a.json"
    source.write_text('{"id":"changed"}')
    assert manifests._scenario_hash(first) != saved
    source.write_text('{"id":"a"}')
    source.rename(first / "renamed.json")
    assert manifests._scenario_hash(first) != saved


def test_default_run_identity_is_unique_and_roundtrips(tmp_path, project_root):
    manifest = manifests.generate_manifest(project_root, model_ids=["test-model"])
    another = manifests.generate_manifest(project_root, model_ids=["test-model"])
    assert manifest["run_id"] and another["run_id"]
    assert manifest["run_id"] != another["run_id"]
    path = manifests.write_manifest(manifest, tmp_path / "nested/run")
    assert path.name == "run_manifest.json"
    assert json.loads(path.read_text()) == manifest
