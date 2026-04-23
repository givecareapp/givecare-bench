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
def scenarios_dir():
    return SCENARIOS_DIR


@pytest.fixture
def configs_dir():
    return CONFIGS_DIR


