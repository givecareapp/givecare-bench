"""Ensure v2 gate+quality docs stay in sync with scoring config.

Diátaxis: reference
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCORING_CONFIG = PROJECT_ROOT / "benchmark" / "configs" / "scoring.yaml"


def _load_config(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _assert_mentions_v2_architecture(doc_text: str, *, doc_name: str) -> None:
    normalized = _normalize_space(doc_text)

    assert "gate + quality" in normalized or "gate+quality" in normalized, (
        f"{doc_name} should mention v2 gate+quality architecture"
    )

    # Gates
    assert "safety" in normalized and "compliance" in normalized, (
        f"{doc_name} should mention safety/compliance gates"
    )

    # Quality dimensions
    assert "regard" in normalized and "coordination" in normalized, (
        f"{doc_name} should mention regard/coordination quality dimensions"
    )


def _extract_yaml_snippet(text: str, marker: str) -> dict:
    start = text.find(marker)
    assert start != -1, f"Missing marker: {marker}"

    fence_start = text.find("```yaml", start)
    assert fence_start != -1, "Missing YAML code fence"

    fence_end = text.find("```", fence_start + len("```yaml"))
    assert fence_end != -1, "Missing closing YAML code fence"

    snippet = text[fence_start + len("```yaml") : fence_end].strip()
    assert snippet, "Empty YAML snippet"
    return yaml.safe_load(snippet)


def test_scoring_config_uses_v2_gate_quality_contract() -> None:
    data = _load_config(SCORING_CONFIG)

    gates = data.get("gates", {})
    quality = data.get("quality", {})

    assert set(gates.keys()) == {"safety", "compliance"}
    assert set(quality.keys()) == {"regard", "coordination"}
    assert abs(float(quality["regard"]) + float(quality["coordination"]) - 1.0) < 1e-9

    assert "weights" in data, "Legacy weights block should exist for backward compatibility"


def test_root_readme_mentions_v2_architecture() -> None:
    text = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    _assert_mentions_v2_architecture(text, doc_name="README.md")


def test_benchmark_readme_mentions_v2_architecture() -> None:
    text = (PROJECT_ROOT / "benchmark" / "README.md").read_text(encoding="utf-8")
    _assert_mentions_v2_architecture(text, doc_name="benchmark/README.md")


def test_scripts_readme_yaml_matches_scoring_config() -> None:
    config = _load_config(SCORING_CONFIG)
    text = (PROJECT_ROOT / "benchmark" / "scripts" / "README.md").read_text(encoding="utf-8")

    snippet = _extract_yaml_snippet(
        text,
        marker="The v2 gate+quality architecture is configured in `benchmark/configs/scoring.yaml`:",
    )

    assert snippet.get("gates") == config.get("gates")
    assert snippet.get("quality") == config.get("quality")
