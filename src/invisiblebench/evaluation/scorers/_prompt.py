"""Shared prompt-loading utility for scorers."""

from __future__ import annotations

from invisiblebench.utils.benchmark_inventory import get_project_root

_PROMPT_DIR = get_project_root() / "benchmark" / "configs" / "prompts"


def load_prompt(name: str) -> str:
    """Load a scoring prompt by filename, raising FileNotFoundError with a helpful message."""
    path = _PROMPT_DIR / name
    if not path.exists():
        raise FileNotFoundError(
            f"Scoring prompt not found: {path}\n"
            "See benchmark/configs/prompts/README.md for setup instructions."
        )
    return path.read_text()
