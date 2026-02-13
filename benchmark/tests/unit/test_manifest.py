"""Tests for run reproducibility manifest."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from invisiblebench.utils.manifest import (
    _scenario_hash,
    generate_manifest,
    write_manifest,
)


@pytest.fixture
def project_root() -> Path:
    """Return the actual project root."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    pytest.skip("Could not find project root")


class TestGenerateManifest:
    def test_all_required_fields(self, project_root: Path):
        manifest = generate_manifest(project_root, model_ids=["model-a", "model-b"])
        required = {
            "run_id",
            "git_sha",
            "git_dirty",
            "scenario_hash",
            "scoring_config_hash",
            "scorer_prompt_hashes",
            "model_ids",
            "run_date",
            "contract_version",
            "python_version",
            "benchmark_version",
        }
        assert required == set(manifest.keys())

    def test_git_sha_format(self, project_root: Path):
        manifest = generate_manifest(project_root, model_ids=[])
        sha = manifest["git_sha"]
        # Either a valid 40-char hex string or 'unknown' (if not in git repo)
        assert sha == "unknown" or re.fullmatch(r"[0-9a-f]{40}", sha)

    def test_git_dirty_is_bool(self, project_root: Path):
        manifest = generate_manifest(project_root, model_ids=[])
        assert isinstance(manifest["git_dirty"], bool)

    def test_model_ids_preserved(self, project_root: Path):
        ids = ["openai/gpt-5.2", "anthropic/claude-opus-4.5"]
        manifest = generate_manifest(project_root, model_ids=ids)
        assert manifest["model_ids"] == ids

    def test_custom_run_id(self, project_root: Path):
        manifest = generate_manifest(project_root, model_ids=[], run_id="test-uuid-1234")
        assert manifest["run_id"] == "test-uuid-1234"

    def test_contract_version_from_config(self, project_root: Path):
        manifest = generate_manifest(project_root, model_ids=[])
        # Should read contract_version from scoring.yaml (not "unknown")
        assert manifest["contract_version"] != "unknown"
        assert re.match(r"\d+\.\d+\.\d+", manifest["contract_version"])

    def test_benchmark_version_from_pyproject(self, project_root: Path):
        manifest = generate_manifest(project_root, model_ids=[])
        assert manifest["benchmark_version"] != "unknown"
        # Should look like a semver
        assert re.match(r"\d+\.\d+\.\d+", manifest["benchmark_version"])

    def test_run_date_is_iso(self, project_root: Path):
        manifest = generate_manifest(project_root, model_ids=[])
        # Should be parseable ISO 8601
        from datetime import datetime

        datetime.fromisoformat(manifest["run_date"])

    def test_scorer_prompt_hashes_empty_dict(self, project_root: Path):
        manifest = generate_manifest(project_root, model_ids=[])
        assert manifest["scorer_prompt_hashes"] == {}


class TestScenarioHash:
    def test_deterministic(self, project_root: Path):
        scenarios_dir = project_root / "benchmark" / "scenarios"
        h1 = _scenario_hash(scenarios_dir)
        h2 = _scenario_hash(scenarios_dir)
        assert h1 == h2

    def test_is_hex_string(self, project_root: Path):
        scenarios_dir = project_root / "benchmark" / "scenarios"
        h = _scenario_hash(scenarios_dir)
        assert re.fullmatch(r"[0-9a-f]{64}", h)


class TestWriteManifest:
    def test_writes_valid_json(self, tmp_path: Path, project_root: Path):
        manifest = generate_manifest(project_root, model_ids=["test-model"])
        path = write_manifest(manifest, tmp_path)

        assert path.name == "run_manifest.json"
        assert path.exists()

        loaded = json.loads(path.read_text())
        assert loaded == manifest

    def test_creates_output_dir(self, tmp_path: Path, project_root: Path):
        nested = tmp_path / "a" / "b" / "c"
        manifest = generate_manifest(project_root, model_ids=[])
        write_manifest(manifest, nested)
        assert (nested / "run_manifest.json").exists()
