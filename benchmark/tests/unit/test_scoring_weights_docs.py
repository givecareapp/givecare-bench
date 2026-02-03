"""Ensure doc-reported scoring weights stay in sync with scoring config."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCORING_CONFIG = PROJECT_ROOT / "benchmark" / "configs" / "scoring.yaml"
PACKAGE_SCORING_CONFIG = PROJECT_ROOT / "benchmark" / "invisiblebench" / "scoring.yaml"

EXPECTED_KEYS = {"memory", "consistency", "trauma", "belonging", "compliance", "safety"}


def _load_weights(path: Path) -> dict[str, float]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    weights = data.get("weights", {})
    return weights


def _weights_to_percent(weights: dict[str, float]) -> dict[str, int]:
    return {key: int(round(weights[key] * 100)) for key in EXPECTED_KEYS}


def _label_to_key(label: str) -> str:
    normalized = label.strip().lower()
    if "memory" in normalized:
        return "memory"
    if "consistency" in normalized:
        return "consistency"
    if "trauma" in normalized:
        return "trauma"
    if "belonging" in normalized:
        return "belonging"
    if "compliance" in normalized:
        return "compliance"
    if "safety" in normalized:
        return "safety"
    raise AssertionError(f"Unrecognized dimension label: {label}")


def _parse_root_readme_weights(text: str) -> dict[str, int]:
    header = "### 6 Evaluation Dimensions"
    start = text.find(header)
    assert start != -1, "README.md missing '5 Evaluation Dimensions' section"

    lines = text[start:].splitlines()
    table_lines = []
    for line in lines[1:]:
        if line.startswith(("## ", "### ")) or line.strip() == "---":
            break
        table_lines.append(line)

    pattern = re.compile(r"^\|\s*\*\*(.+?)\*\*\s*\|\s*(\d+)%")
    weights: dict[str, int] = {}
    for line in table_lines:
        match = pattern.match(line)
        if match:
            label, percent = match.group(1), match.group(2)
            weights[_label_to_key(label)] = int(percent)

    return weights


def _parse_dimensions_line(text: str) -> dict[str, int]:
    for line in text.splitlines():
        if line.strip().startswith("**Dimensions**:") and "memory" in line.lower():
            pairs = re.findall(r"([A-Za-z &-]+)\s*\((\d+)%\)", line)
            weights = {_label_to_key(label): int(percent) for label, percent in pairs}
            return weights
    raise AssertionError("benchmark/README.md missing YAML orchestrator dimensions line")


def _parse_yaml_orchestrator_list(text: str) -> dict[str, int]:
    header = "### YAML Orchestrator (6 dimensions)"
    start = text.find(header)
    assert start != -1, "benchmark/README.md missing YAML Orchestrator section"

    lines = text[start:].splitlines()
    weights: dict[str, int] = {}
    pattern = re.compile(r"^\d+\.\s+\*\*(.+?)\*\*\s*\((\d+)%\)")

    for line in lines[1:]:
        if line.startswith(("## ", "### ")) and not line.startswith("### YAML Orchestrator"):
            break
        match = pattern.match(line.strip())
        if match:
            label, percent = match.group(1), match.group(2)
            weights[_label_to_key(label)] = int(percent)

    return weights


def _parse_scripts_dimensions_list(text: str) -> dict[str, int]:
    marker = "Scores each transcript across 6 dimensions:"
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        if marker in line:
            weights: dict[str, int] = {}
            for follow in lines[idx + 1 :]:
                stripped = follow.strip()
                if not stripped.startswith("-"):
                    if weights:
                        break
                    continue
                match = re.match(r"^-\s*(.+?)\s*\((\d+)%\)", stripped)
                if match:
                    label, percent = match.group(1), match.group(2)
                    weights[_label_to_key(label)] = int(percent)
            return weights
    raise AssertionError("benchmark/scripts/README.md missing 5-dimension bullet list")


def _parse_scripts_weights_snippet(text: str) -> dict[str, float]:
    marker = "Edit scoring weights in `benchmark/configs/scoring.yaml`:"
    start = text.find(marker)
    assert start != -1, "benchmark/scripts/README.md missing scoring weights snippet marker"

    fence_start = text.find("```yaml", start)
    assert fence_start != -1, "benchmark/scripts/README.md missing YAML code fence"

    fence_end = text.find("```", fence_start + len("```yaml"))
    assert fence_end != -1, "benchmark/scripts/README.md missing closing YAML code fence"

    snippet = text[fence_start + len("```yaml") : fence_end].strip()
    data = yaml.safe_load(snippet) if snippet else {}
    return data.get("weights", {})


def test_scoring_weights_match_docs() -> None:
    config_weights = _load_weights(SCORING_CONFIG)
    assert set(config_weights.keys()) == EXPECTED_KEYS
    expected_percent = _weights_to_percent(config_weights)

    root_readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    root_weights = _parse_root_readme_weights(root_readme)
    assert root_weights == expected_percent

    benchmark_readme = (PROJECT_ROOT / "benchmark" / "README.md").read_text(encoding="utf-8")
    line_weights = _parse_dimensions_line(benchmark_readme)
    assert line_weights == expected_percent

    list_weights = _parse_yaml_orchestrator_list(benchmark_readme)
    assert list_weights == expected_percent

    scripts_readme = (PROJECT_ROOT / "benchmark" / "scripts" / "README.md").read_text(
        encoding="utf-8"
    )
    bullet_weights = _parse_scripts_dimensions_list(scripts_readme)
    assert bullet_weights == expected_percent

    snippet_weights = _parse_scripts_weights_snippet(scripts_readme)
    assert snippet_weights == config_weights


def test_scoring_config_copy_matches_canonical() -> None:
    config_weights = _load_weights(SCORING_CONFIG)
    package_weights = _load_weights(PACKAGE_SCORING_CONFIG)
    assert package_weights == config_weights
