"""Pytest configuration and shared fixtures."""

import os
from pathlib import Path

import pytest

os.environ.setdefault("INVISIBLEBENCH_DISABLE_LLM", "1")

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
FIXTURES_DIR = Path(__file__).parent / "fixtures"
SCENARIOS_DIR = PROJECT_ROOT / "scenarios"
CONFIGS_DIR = PROJECT_ROOT / "configs"

# ── v2 dimension vocabulary (canonical source of truth) ──
V2_GATES = frozenset({"safety", "compliance"})
V2_QUALITY = frozenset({"regard", "coordination"})
V2_SIGNALS = frozenset({"memory", "false_refusal"})
V2_DIMENSIONS = V2_GATES | V2_QUALITY | V2_SIGNALS


@pytest.fixture
def project_root():
    """Return project root directory."""
    return PROJECT_ROOT


@pytest.fixture
def fixtures_dir():
    """Return fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture
def scenarios_dir():
    """Return scenarios directory."""
    return SCENARIOS_DIR


@pytest.fixture
def configs_dir():
    """Return configs directory."""
    return CONFIGS_DIR


@pytest.fixture
def v2_dimensions():
    """Canonical v2 dimension set for contract assertions."""
    return V2_DIMENSIONS


@pytest.fixture
def sample_transcript():
    """Load sample transcript fixture."""
    transcript_path = FIXTURES_DIR / "sample_transcript.jsonl"
    if transcript_path.exists():
        with open(transcript_path) as f:
            import json

            return [json.loads(line) for line in f]
    return []


@pytest.fixture
def sample_scenario():
    """Load sample scenario fixture."""
    scenario_path = FIXTURES_DIR / "sample_scenario.yaml"
    if scenario_path.exists():
        import yaml

        with open(scenario_path) as f:
            return yaml.safe_load(f)
    return {}
