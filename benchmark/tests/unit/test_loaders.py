"""
Test suite for data loaders: rules, scenarios, transcripts, and scoring config.

Following TDD methodology - these tests define expected behavior before implementation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RULES_DIR = PROJECT_ROOT / "benchmark" / "configs" / "rules"
SCENARIO_PATH = (
    PROJECT_ROOT
    / "benchmark"
    / "scenarios"
    / "empathy"
    / "burnout"
    / "sandwich_generation_burnout.json"
)
SCORING_PATH = PROJECT_ROOT / "benchmark" / "configs" / "scoring.yaml"
TRANSCRIPT_PATH = PROJECT_ROOT / "benchmark" / "tests" / "fixtures" / "sample_transcript.jsonl"


class TestRuleLoader:
    """Test YAML rule loader with inheritance resolution."""

    def test_load_base_rules(self):
        """Should load base.yaml and return complete rule dictionary."""
        from invisiblebench.evaluation.loaders import RuleLoader

        loader = RuleLoader()
        rules = loader.load(str(RULES_DIR / "base.yaml"))

        # Base rules should have all expected sections
        assert "disclosure" in rules
        assert "forbidden" in rules
        assert "parasocial" in rules
        assert "crisis" in rules

        # Check disclosure section structure
        assert rules["disclosure"]["cadence_turns"] is None
        assert len(rules["disclosure"]["phrases"]) > 0
        # Check for AI mention (handles different quote types)
        assert "AI" in rules["disclosure"]["phrases"][0] and (
            "not a human" in rules["disclosure"]["phrases"][0]
            or "not human" in rules["disclosure"]["phrases"][0]
        )

        # Check forbidden section
        assert "diagnosis_patterns" in rules["forbidden"]
        assert "treatment_plans" in rules["forbidden"]

        # Check crisis section
        assert "cues_indirect" in rules["crisis"]
        assert "required_actions" in rules["crisis"]

    def test_load_rules_with_inheritance(self):
        """Should resolve 'extends: base.yaml' and merge NY-specific overrides."""
        from invisiblebench.evaluation.loaders import RuleLoader

        loader = RuleLoader()
        rules = loader.load(str(RULES_DIR / "ny.yaml"))

        # Should inherit all base rules
        assert "forbidden" in rules
        assert "parasocial" in rules

        # Should have NY-specific overrides
        assert rules["crisis"]["must_detect"] is True
        assert rules["disclosure"]["cadence_turns"] == 5  # NY overrides base (6) to 5

        # Should have notes from NY
        assert "notes" in rules
        assert len(rules["notes"]) > 0

    def test_inheritance_merges_nested_dicts(self):
        """Should deep merge nested dictionaries, not replace them."""
        from invisiblebench.evaluation.loaders import RuleLoader

        loader = RuleLoader()
        rules = loader.load(str(RULES_DIR / "ny.yaml"))

        # NY adds must_detect to crisis, but should keep base crisis fields
        assert "must_detect" in rules["crisis"]
        assert "cues_indirect" in rules["crisis"]  # From base
        assert "required_actions" in rules["crisis"]  # From base

    def test_load_nonexistent_file_raises_error(self):
        """Should raise FileNotFoundError for missing rule files."""
        from invisiblebench.evaluation.loaders import RuleLoader

        loader = RuleLoader()
        with pytest.raises(FileNotFoundError):
            loader.load("/nonexistent/path.yaml")

    def test_circular_inheritance_raises_error(self):
        """Should detect and raise error for circular inheritance."""
        # Create temporary circular reference fixtures
        import tempfile

        from invisiblebench.evaluation.loaders import RuleLoader

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
        import tempfile

        import yaml
        from invisiblebench.evaluation.loaders import RuleLoader

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [unclosed")
            invalid_path = f.name

        try:
            loader = RuleLoader()
            with pytest.raises(yaml.YAMLError):
                loader.load(invalid_path)
        finally:
            Path(invalid_path).unlink()


class TestScenarioLoader:
    """Test scenario YAML loader."""

    def test_load_scenario_basic_structure(self):
        """Should load scenario and return structured dictionary."""
        from invisiblebench.evaluation.loaders import ScenarioLoader

        loader = ScenarioLoader()
        scenario = loader.load(str(SCENARIO_PATH))

        # Required fields (JSON schema uses scenario_id, not id)
        assert scenario["scenario_id"] == "tier2_sandwich_001"
        assert scenario["tier"] == "empathy"
        assert "persona" in scenario
        assert "turns" in scenario
        assert len(scenario["turns"]) > 0

    def test_scenario_turns_structure(self):
        """Should parse turns with correct structure."""
        from invisiblebench.evaluation.loaders import ScenarioLoader

        loader = ScenarioLoader()
        scenario = loader.load(str(SCENARIO_PATH))

        turns = scenario["turns"]

        # Find turn with facts (JSON schema uses user_message, not user)
        turn_2 = [t for t in turns if t["t"] == 2][0]
        # Use 'in' to avoid quote type issues
        assert "Priya" in turn_2["user_message"]
        assert "mother" in turn_2["user_message"]
        assert "facts" in turn_2
        assert "caregiver_name=Priya" in turn_2["facts"]

    def test_scenario_probes_structure(self):
        """Should parse probes with expected fields."""
        from invisiblebench.evaluation.loaders import ScenarioLoader

        loader = ScenarioLoader()
        scenario = loader.load(str(SCENARIO_PATH))

        probes = scenario["probes"]
        assert len(probes) > 0

        # Find recall probe
        recall_probe = [p for p in probes if p["kind"] == "recall"][0]
        assert recall_probe["t"] == 8
        assert "expected" in recall_probe
        assert "Priya" in recall_probe["expected"]

    def test_scenario_compliance_gates(self):
        """Should parse scoring dimensions and autofail triggers."""
        from invisiblebench.evaluation.loaders import ScenarioLoader

        loader = ScenarioLoader()
        scenario = loader.load(str(SCENARIO_PATH))

        # JSON schema has scoring_dimensions instead of compliance_gates
        assert "scoring_dimensions" in scenario
        scoring = scenario["scoring_dimensions"]
        assert "crisis_safety" in scoring or "compliance" in scoring

        # Should have autofail_triggers in turns
        turns = scenario["turns"]
        assert any("autofail_triggers" in turn for turn in turns)

    def test_turn_index_normalization_adds_t(self, tmp_path):
        """Should map turn_number to t for scoring."""
        from invisiblebench.evaluation.loaders import ScenarioLoader

        scenario_path = tmp_path / "scenario.json"
        scenario_path.write_text(
            json.dumps(
                {
                    "scenario_id": "test_turns",
                    "tier": "safety",
                    "title": "Test turn normalization",
                    "persona": {
                        "name": "A",
                        "age": 1,
                        "role": "r",
                        "care_recipient": "c",
                        "care_duration": "d",
                        "context": {},
                    },
                    "turns": [
                        {
                            "turn_number": 1,
                            "user_message": "hi",
                            "expected_behaviors": [],
                            "autofail_triggers": [],
                        },
                    ],
                    "probes": [{"turn_number": 1, "kind": "recall", "expected": ["hi"]}],
                    "risk_triggers": [{"turn_number": 1, "cue": "test", "severity": "medium"}],
                    "scoring_dimensions": {
                        "crisis_safety": 100,
                        "trauma_informed_flow": 100,
                        "belonging_cultural_fitness": 100,
                    },
                }
            )
        )

        loader = ScenarioLoader()
        scenario = loader.load(str(scenario_path))

        assert scenario["turns"][0]["t"] == 1
        assert scenario["probes"][0]["t"] == 1
        assert scenario["risk_triggers"][0]["t"] == 1

    def test_turn_index_lint_flags_mixed_usage(self):
        """Should flag mixed t/turn_number usage."""
        from invisiblebench.utils.turn_index import lint_turn_indices

        scenario = {
            "turns": [{"t": 1}, {"turn_number": 2}],
            "probes": [],
            "risk_triggers": [],
        }

        warnings = lint_turn_indices(scenario)
        assert any("turns uses mixed t and turn_number fields" in w for w in warnings)


class TestTranscriptLoader:
    """Test JSONL transcript loader."""

    def test_load_transcript_basic(self):
        """Should load JSONL transcript into structured format."""
        from invisiblebench.evaluation.loaders import TranscriptLoader

        loader = TranscriptLoader()
        transcript = loader.load(str(TRANSCRIPT_PATH))

        # Should return list of turn dictionaries
        assert isinstance(transcript, list)
        assert len(transcript) > 0

        # Check first turn structure
        assert transcript[0]["turn"] == 1
        assert transcript[0]["role"] == "user"
        assert "content" in transcript[0]

    def test_transcript_alternating_roles(self):
        """Should have alternating user/assistant messages."""
        from invisiblebench.evaluation.loaders import TranscriptLoader

        loader = TranscriptLoader()
        transcript = loader.load(str(TRANSCRIPT_PATH))

        # Should alternate user -> assistant -> user -> assistant
        for i in range(0, len(transcript) - 1, 2):
            assert transcript[i]["role"] == "user"
            assert transcript[i + 1]["role"] == "assistant"

    def test_transcript_preserves_turn_numbers(self):
        """Should preserve turn numbers from JSONL."""
        from invisiblebench.evaluation.loaders import TranscriptLoader

        loader = TranscriptLoader()
        transcript = loader.load(str(TRANSCRIPT_PATH))

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
        import tempfile

        from invisiblebench.evaluation.loaders import TranscriptLoader

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            empty_path = f.name

        try:
            loader = TranscriptLoader()
            transcript = loader.load(empty_path)
            assert transcript == []
        finally:
            Path(empty_path).unlink()

    def test_malformed_json_raises_error(self):
        """Should raise error for malformed JSONL."""
        import tempfile

        from invisiblebench.evaluation.loaders import TranscriptLoader

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
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
        from invisiblebench.evaluation.loaders import ScoringConfigLoader

        loader = ScoringConfigLoader()
        config = loader.load(str(SCORING_PATH))

        # Should have weights section
        assert "weights" in config
        weights = config["weights"]

        # Legacy weights still present for backward compat
        assert weights["safety"] == 0.20
        assert weights["compliance"] == 0.15
        assert weights["memory"] == 0.11

        # Weights should sum to 1.0
        assert abs(sum(weights.values()) - 1.0) < 0.01

        # v2 quality weights
        assert "quality" in config
        assert config["quality"]["regard"] == 0.50
        assert config["quality"]["coordination"] == 0.50

    def test_scoring_config_dimension_details(self):
        """Should load dimension-specific configuration."""
        from invisiblebench.evaluation.loaders import ScoringConfigLoader

        loader = ScoringConfigLoader()
        config = loader.load(str(SCORING_PATH))

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
        from invisiblebench.evaluation.loaders import ScoringConfigLoader

        loader = ScoringConfigLoader()
        config = loader.load(str(SCORING_PATH))

        belonging = config["belonging"]
        assert "pillars" in belonging
        assert isinstance(belonging["pillars"], list)
        assert "recognition" in belonging["pillars"]
        assert "agency" in belonging["pillars"]
        assert "connection" in belonging["pillars"]
