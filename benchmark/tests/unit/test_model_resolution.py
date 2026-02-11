"""Tests for resolve_models() — model selection by name, number, or mixed spec."""

from __future__ import annotations

import pytest

from invisiblebench.cli.runner import resolve_models

# Minimal catalog for testing (mirrors real MODELS_FULL structure)
CATALOG = [
    {"id": "anthropic/claude-opus-4.5", "name": "Claude Opus 4.5", "cost_per_m_input": 5.0, "cost_per_m_output": 25.0},
    {"id": "openai/gpt-5.2-20251211", "name": "GPT-5.2", "cost_per_m_input": 1.75, "cost_per_m_output": 14.0},
    {"id": "google/gemini-3-pro-preview-20251117", "name": "Gemini 3 Pro Preview", "cost_per_m_input": 2.0, "cost_per_m_output": 12.0},
    {"id": "anthropic/claude-sonnet-4.5", "name": "Claude Sonnet 4.5", "cost_per_m_input": 3.0, "cost_per_m_output": 15.0},
    {"id": "x-ai/grok-4", "name": "Grok 4", "cost_per_m_input": 3.0, "cost_per_m_output": 15.0},
    {"id": "openai/gpt-5-mini", "name": "GPT-5 Mini", "cost_per_m_input": 0.25, "cost_per_m_output": 2.0},
    {"id": "deepseek/deepseek-v3.2-20251201", "name": "DeepSeek V3.2", "cost_per_m_input": 0.25, "cost_per_m_output": 0.38},
    {"id": "google/gemini-2.5-flash", "name": "Gemini 2.5 Flash", "cost_per_m_input": 0.3, "cost_per_m_output": 2.5},
]


class TestNumericResolution:
    """Backward-compatible numeric specs."""

    def test_single_number(self):
        assert resolve_models("4", CATALOG) == [3]

    def test_range(self):
        assert resolve_models("1-4", CATALOG) == [0, 1, 2, 3]

    def test_open_ended_range(self):
        assert resolve_models("6-", CATALOG) == [5, 6, 7]

    def test_comma_separated(self):
        assert resolve_models("1,3,5", CATALOG) == [0, 2, 4]

    def test_out_of_range_ignored(self):
        assert resolve_models("99", CATALOG) == []

    def test_single_model_total(self):
        assert resolve_models("1", CATALOG) == [0]


class TestNameResolution:
    """Case-insensitive partial name matching."""

    def test_partial_name(self):
        result = resolve_models("deepseek", CATALOG)
        assert result == [6]

    def test_case_insensitive(self):
        assert resolve_models("DEEPSEEK", CATALOG) == [6]
        assert resolve_models("DeepSeek", CATALOG) == [6]

    def test_matches_multiple(self):
        result = resolve_models("claude", CATALOG)
        assert result == [0, 3]  # Opus 4.5 and Sonnet 4.5

    def test_matches_by_model_id(self):
        result = resolve_models("grok-4", CATALOG)
        assert result == [4]

    def test_version_in_name(self):
        result = resolve_models("gpt-5.2", CATALOG)
        assert result == [1]

    def test_gemini_matches_both(self):
        result = resolve_models("gemini", CATALOG)
        assert result == [2, 7]  # Pro and Flash

    def test_unknown_name_raises(self):
        with pytest.raises(ValueError, match="No model matching 'nonexistent'"):
            resolve_models("nonexistent", CATALOG)

    def test_error_lists_available(self):
        with pytest.raises(ValueError, match="Available models"):
            resolve_models("foobar", CATALOG)


class TestMixedResolution:
    """Mixed numeric + name specs."""

    def test_number_and_name(self):
        result = resolve_models("1,deepseek", CATALOG)
        assert result == [0, 6]

    def test_range_and_name(self):
        result = resolve_models("1-3,grok", CATALOG)
        assert result == [0, 1, 2, 4]

    def test_deduplication(self):
        # "1" and "claude opus" both resolve to index 0 — no duplicate
        result = resolve_models("1,claude opus", CATALOG)
        assert result == [0]  # deduplicated

    def test_whitespace_handling(self):
        result = resolve_models(" 1 , deepseek ", CATALOG)
        assert result == [0, 6]


class TestEdgeCases:
    """Edge cases and error handling."""

    def test_empty_string(self):
        assert resolve_models("", CATALOG) == []

    def test_empty_catalog(self):
        assert resolve_models("1", []) == []

    def test_comma_only(self):
        assert resolve_models(",,,", CATALOG) == []
