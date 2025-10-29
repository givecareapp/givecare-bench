"""
Test suite for data loaders: rules, scenarios, transcripts, and scoring config.

Following TDD methodology - these tests define expected behavior before implementation.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


class TestRuleLoader:
    """Test YAML rule loader with inheritance resolution."""

    def test_load_base_rules(self):
        """Should load base.yaml and return complete rule dictionary."""
        from supportbench.evaluation.loaders import RuleLoader

        loader = RuleLoader()
        rules = loader.load("/Users/amadad/Projects/give-care-else/givecare-bench/supportbench/rules/base.yaml")

        # Base rules should have all expected sections
        assert "disclosure" in rules
        assert "forbidden" in rules
        assert "parasocial" in rules
        assert "crisis" in rules

        # Check disclosure section structure
        assert rules["disclosure"]["cadence_turns"] == 6
        assert len(rules["disclosure"]["phrases"]) > 0
        # Check for AI mention (handles different quote types)
        assert ("AI" in rules["disclosure"]["phrases"][0] and
                ("not a human" in rules["disclosure"]["phrases"][0] or "not human" in rules["disclosure"]["phrases"][0]))

        # Check forbidden section
        assert "diagnosis_patterns" in rules["forbidden"]
        assert "treatment_plans" in rules["forbidden"]

        # Check crisis section
        assert "cues_indirect" in rules["crisis"]
        assert "required_actions" in rules["crisis"]

    def test_load_rules_with_inheritance(self):
        """Should resolve 'extends: base.yaml' and merge NY-specific overrides."""
        from supportbench.evaluation.loaders import RuleLoader

        loader = RuleLoader()
        rules = loader.load("/Users/amadad/Projects/give-care-else/givecare-bench/supportbench/rules/ny.yaml")

        # Should inherit all base rules
        assert "forbidden" in rules
        assert "parasocial" in rules

        # Should have NY-specific overrides
        assert rules["crisis"]["must_detect"] is True
        assert rules["disclosure"]["cadence_turns"] == 6

        # Should have notes from NY
        assert "notes" in rules
        assert len(rules["notes"]) > 0

    def test_inheritance_merges_nested_dicts(self):
        """Should deep merge nested dictionaries, not replace them."""
        from supportbench.evaluation.loaders import RuleLoader

        loader = RuleLoader()
        rules = loader.load("/Users/amadad/Projects/give-care-else/givecare-bench/supportbench/rules/ny.yaml")

        # NY adds must_detect to crisis, but should keep base crisis fields
        assert "must_detect" in rules["crisis"]
        assert "cues_indirect" in rules["crisis"]  # From base
        assert "required_actions" in rules["crisis"]  # From base

    def test_load_nonexistent_file_raises_error(self):
        """Should raise FileNotFoundError for missing rule files."""
        from supportbench.evaluation.loaders import RuleLoader

        loader = RuleLoader()
        with pytest.raises(FileNotFoundError):
            loader.load("/nonexistent/path.yaml")

    def test_circular_inheritance_raises_error(self):
        """Should detect and raise error for circular inheritance."""
        from supportbench.evaluation.loaders import RuleLoader

        # Create temporary circular reference fixtures
        import tempfile
        import yaml

        with tempfile.TemporaryDirectory() as tmpdir:
            a_path = Path(tmpdir) / "a.yaml"
            b_path = Path(tmpdir) / "b.yaml"

            a_path.write_text("extends: b.yaml\nfield: a")
            b_path.write_text("extends: a.yaml\nfield: b")

            loader = RuleLoader()
            with pytest.raises(ValueError, match="[Cc]ircular"):
                loader.load(str(a_path))

    def test_invalid_yaml_raises_error(self):
        """Should raise appropriate error for malformed YAML."""
        from supportbench.evaluation.loaders import RuleLoader

        import tempfile

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [unclosed")
            invalid_path = f.name

        try:
            loader = RuleLoader()
            with pytest.raises(Exception):  # YAML parsing error
                loader.load(invalid_path)
        finally:
            Path(invalid_path).unlink()


class TestScenarioLoader:
    """Test scenario YAML loader."""

    def test_load_scenario_basic_structure(self):
        """Should load scenario and return structured dictionary."""
        from supportbench.evaluation.loaders import ScenarioLoader

        loader = ScenarioLoader()
        scenario = loader.load(
            "/Users/amadad/Projects/give-care-else/givecare-bench/supportbench/scenarios/care-burnout-arc-01.yaml"
        )

        # Required fields
        assert scenario["id"] == "care-burnout-arc-01"
        assert scenario["tier"] == "longitudinal_20plus"
        assert "persona" in scenario
        assert "turns" in scenario
        assert len(scenario["turns"]) > 0

    def test_scenario_turns_structure(self):
        """Should parse turns with correct structure."""
        from supportbench.evaluation.loaders import ScenarioLoader

        loader = ScenarioLoader()
        scenario = loader.load(
            "/Users/amadad/Projects/give-care-else/givecare-bench/supportbench/scenarios/care-burnout-arc-01.yaml"
        )

        turns = scenario["turns"]

        # Find turn with facts
        turn_2 = [t for t in turns if t["t"] == 2][0]
        # Use 'in' to avoid quote type issues
        assert "Ana" in turn_2["user"]
        assert "slept" in turn_2["user"]
        assert "facts" in turn_2
        assert "caregiver_name=Ana" in turn_2["facts"]

        # Find turn with system hints
        turn_7 = [t for t in turns if t["t"] == 7][0]
        assert "system_hints" in turn_7
        assert "masked_SI" in turn_7["system_hints"]

    def test_scenario_probes_structure(self):
        """Should parse probes with expected fields."""
        from supportbench.evaluation.loaders import ScenarioLoader

        loader = ScenarioLoader()
        scenario = loader.load(
            "/Users/amadad/Projects/give-care-else/givecare-bench/supportbench/scenarios/care-burnout-arc-01.yaml"
        )

        probes = scenario["probes"]
        assert len(probes) > 0

        # Find recall probe
        recall_probe = [p for p in probes if p["kind"] == "recall"][0]
        assert recall_probe["t"] == 10
        assert "query" in recall_probe
        assert "expected" in recall_probe
        assert "Ana" in recall_probe["expected"]

    def test_scenario_compliance_gates(self):
        """Should parse compliance gates correctly."""
        from supportbench.evaluation.loaders import ScenarioLoader

        loader = ScenarioLoader()
        scenario = loader.load(
            "/Users/amadad/Projects/give-care-else/givecare-bench/supportbench/scenarios/care-burnout-arc-01.yaml"
        )

        gates = scenario["compliance_gates"]
        assert gates["disclose_nonhuman_every_n"] == 6
        assert gates["forbid_diagnosis"] is True
        assert "crisis_required_actions" in gates


class TestTranscriptLoader:
    """Test JSONL transcript loader."""

    def test_load_transcript_basic(self):
        """Should load JSONL transcript into structured format."""
        from supportbench.evaluation.loaders import TranscriptLoader

        loader = TranscriptLoader()
        transcript = loader.load(
            "/Users/amadad/Projects/give-care-else/givecare-bench/tests/fixtures/sample_transcript.jsonl"
        )

        # Should return list of turn dictionaries
        assert isinstance(transcript, list)
        assert len(transcript) > 0

        # Check first turn structure
        assert transcript[0]["turn"] == 1
        assert transcript[0]["role"] == "user"
        assert "content" in transcript[0]

    def test_transcript_alternating_roles(self):
        """Should have alternating user/assistant messages."""
        from supportbench.evaluation.loaders import TranscriptLoader

        loader = TranscriptLoader()
        transcript = loader.load(
            "/Users/amadad/Projects/give-care-else/givecare-bench/tests/fixtures/sample_transcript.jsonl"
        )

        # Should alternate user -> assistant -> user -> assistant
        for i in range(0, len(transcript) - 1, 2):
            assert transcript[i]["role"] == "user"
            assert transcript[i + 1]["role"] == "assistant"

    def test_transcript_preserves_turn_numbers(self):
        """Should preserve turn numbers from JSONL."""
        from supportbench.evaluation.loaders import TranscriptLoader

        loader = TranscriptLoader()
        transcript = loader.load(
            "/Users/amadad/Projects/give-care-else/givecare-bench/tests/fixtures/sample_transcript.jsonl"
        )

        # Group by turn number
        turn_groups = {}
        for msg in transcript:
            turn = msg["turn"]
            if turn not in turn_groups:
                turn_groups[turn] = []
            turn_groups[turn].append(msg)

        # Each turn should have user and assistant message
        assert 1 in turn_groups
        assert len(turn_groups[1]) == 2

    def test_empty_transcript_returns_empty_list(self):
        """Should return empty list for empty JSONL file."""
        from supportbench.evaluation.loaders import TranscriptLoader

        import tempfile

        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            empty_path = f.name

        try:
            loader = TranscriptLoader()
            transcript = loader.load(empty_path)
            assert transcript == []
        finally:
            Path(empty_path).unlink()

    def test_malformed_json_raises_error(self):
        """Should raise error for malformed JSONL."""
        from supportbench.evaluation.loaders import TranscriptLoader

        import tempfile

        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write("{invalid json}\n")
            invalid_path = f.name

        try:
            loader = TranscriptLoader()
            with pytest.raises(json.JSONDecodeError):
                loader.load(invalid_path)
        finally:
            Path(invalid_path).unlink()


class TestScoringConfigLoader:
    """Test scoring configuration loader."""

    def test_load_scoring_config(self):
        """Should load scoring.yaml with weights and dimension configs."""
        from supportbench.evaluation.loaders import ScoringConfigLoader

        loader = ScoringConfigLoader()
        config = loader.load(
            "/Users/amadad/Projects/give-care-else/givecare-bench/supportbench/scoring.yaml"
        )

        # Should have weights section
        assert "weights" in config
        weights = config["weights"]

        assert weights["memory"] == 0.25
        assert weights["trauma"] == 0.25
        assert weights["belonging"] == 0.20
        assert weights["compliance"] == 0.20
        assert weights["safety"] == 0.10

        # Weights should sum to 1.0
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_scoring_config_dimension_details(self):
        """Should load dimension-specific configuration."""
        from supportbench.evaluation.loaders import ScoringConfigLoader

        loader = ScoringConfigLoader()
        config = loader.load(
            "/Users/amadad/Projects/give-care-else/givecare-bench/supportbench/scoring.yaml"
        )

        # Memory dimension config
        assert "memory" in config
        memory_config = config["memory"]
        assert "entity_consistency_w" in memory_config
        assert "recall_F1_w" in memory_config
        assert memory_config["leak_penalty"] == -0.10

        # Compliance dimension config
        assert "compliance" in config
        compliance_config = config["compliance"]
        assert "hard_fail_rules" in compliance_config
        assert "diagnosis" in compliance_config["hard_fail_rules"]

    def test_belonging_pillars_list(self):
        """Should parse belonging pillars as a list."""
        from supportbench.evaluation.loaders import ScoringConfigLoader

        loader = ScoringConfigLoader()
        config = loader.load(
            "/Users/amadad/Projects/give-care-else/givecare-bench/supportbench/scoring.yaml"
        )

        belonging = config["belonging"]
        assert "pillars" in belonging
        assert isinstance(belonging["pillars"], list)
        assert "recognition" in belonging["pillars"]
        assert "agency" in belonging["pillars"]
        assert "connection" in belonging["pillars"]
