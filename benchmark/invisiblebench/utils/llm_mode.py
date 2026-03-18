"""Helpers for controlling LLM usage in scoring."""

from __future__ import annotations

import os

_TRUE_VALUES = {"1", "true", "yes"}


def llm_enabled(default_enabled: bool) -> bool:
    """Return True if judge/scorer LLM usage is allowed and not disabled by env."""
    disable_judge_value = os.getenv("INVISIBLEBENCH_DISABLE_JUDGE_LLM", "").strip().lower()
    if disable_judge_value in _TRUE_VALUES:
        return False

    disable_value = os.getenv("INVISIBLEBENCH_DISABLE_LLM", "").strip().lower()
    if disable_value in _TRUE_VALUES:
        return False
    return bool(default_enabled)
