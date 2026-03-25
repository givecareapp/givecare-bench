"""Helpers for controlling LLM usage in scoring."""

from __future__ import annotations

import os

_TRUE_VALUES = {"1", "true", "yes"}


def llm_enabled(default_enabled: bool) -> bool:
    """Return True if LLM usage is allowed and not disabled by env."""
    disable_value = os.getenv("INVISIBLEBENCH_DISABLE_LLM", "").strip().lower()
    if disable_value in _TRUE_VALUES:
        return False
    return bool(default_enabled)
