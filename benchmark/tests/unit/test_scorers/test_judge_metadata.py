"""Tests for v2.1 judge metadata wiring through the scoring pipeline."""

from __future__ import annotations

import hashlib

import pytest
from invisiblebench.api.client import compute_prompt_hash
from invisiblebench.evaluation.scorers import coordination, memory

# ---------------------------------------------------------------------------
# compute_prompt_hash
# ---------------------------------------------------------------------------

class TestComputePromptHash:
    def test_deterministic(self) -> None:
        """Same prompt text produces the same hash."""
        prompt = "Evaluate this conversation for regard."
        h1 = compute_prompt_hash(prompt)
        h2 = compute_prompt_hash(prompt)
        assert h1 == h2

    def test_returns_hex_string(self) -> None:
        h = compute_prompt_hash("test prompt")
        assert isinstance(h, str)
        assert len(h) == 64  # SHA256 hex digest
        int(h, 16)  # Should not raise

    def test_strips_whitespace(self) -> None:
        """Leading/trailing whitespace is normalized."""
        h1 = compute_prompt_hash("  hello  ")
        h2 = compute_prompt_hash("hello")
        assert h1 == h2

    def test_different_prompts_different_hashes(self) -> None:
        h1 = compute_prompt_hash("prompt A")
        h2 = compute_prompt_hash("prompt B")
        assert h1 != h2

    def test_matches_manual_sha256(self) -> None:
        text = "test"
        expected = hashlib.sha256(text.encode("utf-8")).hexdigest()
        assert compute_prompt_hash(text) == expected


# ---------------------------------------------------------------------------
# Coordination scorer returns deterministic judge metadata
# ---------------------------------------------------------------------------

class TestCoordinationJudgeMeta:
    def test_returns_deterministic_judge_model(self) -> None:
        transcript = [
            {"turn": 1, "role": "user", "content": "Help me."},
            {"turn": 1, "role": "assistant", "content": "I can help."},
        ]
        result = coordination.score(transcript, {})
        assert result["judge_model"] == "deterministic"
        assert result["judge_temp"] is None
        assert result["judge_prompt_hash"] is None


# ---------------------------------------------------------------------------
# Memory scorer returns deterministic judge metadata
# ---------------------------------------------------------------------------

class TestMemoryJudgeMeta:
    def test_returns_deterministic_judge_model(self) -> None:
        transcript = [
            {"turn": 1, "role": "user", "content": "My name is Ana."},
            {"turn": 1, "role": "assistant", "content": "Nice to meet you, Ana."},
        ]
        result = memory.score(transcript, {"turns": []})
        assert result["judge_model"] == "deterministic"
        assert result["judge_temp"] is None
        assert result["judge_prompt_hash"] is None


# ---------------------------------------------------------------------------
# Regard scorer returns deterministic metadata when LLM disabled
# ---------------------------------------------------------------------------

class TestRegardJudgeMetaOffline:
    def test_deterministic_fallback(self) -> None:
        from invisiblebench.evaluation.scorers import regard

        transcript = [
            {"turn": 1, "role": "user", "content": "I'm exhausted."},
            {"turn": 1, "role": "assistant", "content": "That sounds really hard."},
        ]
        result = regard.score(transcript, {}, allow_llm=False)
        assert result["judge_model"] == "deterministic"
        assert result["judge_temp"] is None
        assert result["judge_prompt_hash"] is None


# ---------------------------------------------------------------------------
# Orchestrator populates judge metadata in results
# ---------------------------------------------------------------------------

class TestOrchestratorJudgeMeta:
    """Test that score() output includes v2.1 judge metadata fields."""

    @pytest.fixture()
    def orchestrator(self):
        """Create a minimal orchestrator with LLM disabled."""
        from pathlib import Path

        from invisiblebench.evaluation.orchestrator import ScoringOrchestrator

        scoring_config = Path("benchmark/configs/scoring.yaml")
        if not scoring_config.exists():
            pytest.skip("scoring.yaml not found")

        return ScoringOrchestrator(
            scoring_config_path=str(scoring_config),
            enable_state_persistence=False,
            enable_llm=False,
        )

    @pytest.fixture()
    def simple_scenario(self, tmp_path):
        """Create transcript + use a real scenario for testing."""
        import json
        from pathlib import Path

        scenario_path = Path("benchmark/scenarios/empathy/burnout/compassion_fatigue_expression.json")
        if not scenario_path.exists():
            pytest.skip("Scenario file not found")

        # Read the scenario to build a matching transcript
        scenario_data = json.loads(scenario_path.read_text())
        turns = scenario_data.get("turns", [])

        import jsonlines

        transcript_path = tmp_path / "transcript.jsonl"
        with jsonlines.open(str(transcript_path), mode="w") as writer:
            for turn in turns:
                t_num = turn.get("turn_number", 1)
                user_msg = turn.get("user_message", "I'm tired.")
                writer.write({"turn": t_num, "role": "user", "content": user_msg})
                writer.write({"turn": t_num, "role": "assistant", "content": "That sounds hard. I hear you."})

        rules_path = Path("benchmark/configs/rules/base.yaml")
        if not rules_path.exists():
            pytest.skip("base.yaml not found")

        return str(transcript_path), str(scenario_path), str(rules_path)

    def test_score_includes_run_id(self, orchestrator, simple_scenario):
        transcript_path, scenario_path, rules_path = simple_scenario
        result = orchestrator.score(
            transcript_path=transcript_path,
            scenario_path=scenario_path,
            rules_path=rules_path,
            model_name="test-model",
            run_id="test-run-123",
        )
        assert result["run_id"] == "test-run-123"

    def test_score_includes_contract_version(self, orchestrator, simple_scenario):
        transcript_path, scenario_path, rules_path = simple_scenario
        result = orchestrator.score(
            transcript_path=transcript_path,
            scenario_path=scenario_path,
            rules_path=rules_path,
            model_name="test-model",
        )
        assert result["contract_version"] == "2.1.0"

    def test_score_includes_judge_model(self, orchestrator, simple_scenario):
        transcript_path, scenario_path, rules_path = simple_scenario
        result = orchestrator.score(
            transcript_path=transcript_path,
            scenario_path=scenario_path,
            rules_path=rules_path,
            model_name="test-model",
        )
        # With LLM disabled, should be "deterministic"
        assert result["judge_model"] == "deterministic"

    def test_score_run_id_none_by_default(self, orchestrator, simple_scenario):
        transcript_path, scenario_path, rules_path = simple_scenario
        result = orchestrator.score(
            transcript_path=transcript_path,
            scenario_path=scenario_path,
            rules_path=rules_path,
            model_name="test-model",
        )
        assert result["run_id"] is None
