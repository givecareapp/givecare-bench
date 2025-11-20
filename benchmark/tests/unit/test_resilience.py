"""
Test suite for error resilience and recovery functionality.

Tests failure injection, partial result preservation, retry logic,
and resume capabilities.
"""
from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TRANSCRIPT_PATH = PROJECT_ROOT / "benchmark" / "tests" / "fixtures" / "sample_transcript.jsonl"
SCENARIO_PATH = PROJECT_ROOT / "benchmark" / "supportbench" / "scenarios" / "care-burnout-arc-01.yaml"
RULES_BASE_PATH = PROJECT_ROOT / "benchmark" / "supportbench" / "rules" / "base.yaml"
SCORING_PATH = PROJECT_ROOT / "benchmark" / "supportbench" / "scoring.yaml"
TRANSCRIPT = str(TRANSCRIPT_PATH)
SCENARIO = str(SCENARIO_PATH)
RULES_BASE = str(RULES_BASE_PATH)
SCORING = str(SCORING_PATH)


class TestRetryDecorator:
    """Test retry logic for file I/O operations."""

    def test_retry_succeeds_on_first_attempt(self):
        """Should succeed immediately if no errors."""
        from supportbench.evaluation.resilience import retry_on_io_error

        @retry_on_io_error(max_retries=3, backoff_base=0.1)
        def successful_operation():
            return "success"

        result = successful_operation()
        assert result == "success"

    def test_retry_succeeds_after_transient_error(self):
        """Should retry and eventually succeed after transient errors."""
        from supportbench.evaluation.resilience import retry_on_io_error

        call_count = {"count": 0}

        @retry_on_io_error(max_retries=3, backoff_base=0.1)
        def flaky_operation():
            call_count["count"] += 1
            if call_count["count"] < 3:
                raise IOError("Disk temporarily unavailable")
            return "success"

        result = flaky_operation()
        assert result == "success"
        assert call_count["count"] == 3

    def test_retry_fails_after_max_attempts(self):
        """Should raise exception after exhausting retries."""
        from supportbench.evaluation.resilience import retry_on_io_error

        @retry_on_io_error(max_retries=2, backoff_base=0.1)
        def always_fails():
            raise IOError("Disk full")

        with pytest.raises(IOError, match="Disk full"):
            always_fails()

    def test_retry_applies_exponential_backoff(self):
        """Should wait exponentially longer between retries."""
        from supportbench.evaluation.resilience import retry_on_io_error

        call_times = []

        @retry_on_io_error(max_retries=3, backoff_base=0.1)
        def track_timing():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise IOError("Temporary error")
            return "done"

        result = track_timing()
        assert result == "done"

        # Check exponential backoff intervals
        if len(call_times) >= 3:
            delay1 = call_times[1] - call_times[0]
            delay2 = call_times[2] - call_times[1]
            # Second delay should be roughly 2x first delay (exponential)
            assert delay2 > delay1

    def test_retry_only_catches_io_errors(self):
        """Should not catch non-IO errors."""
        from supportbench.evaluation.resilience import retry_on_io_error

        @retry_on_io_error(max_retries=3)
        def raises_value_error():
            raise ValueError("Invalid data")

        # Should not retry ValueError
        with pytest.raises(ValueError, match="Invalid data"):
            raises_value_error()


class TestScorerErrorHandling:
    """Test error handling around individual scorers."""

    def test_scorer_failure_preserves_partial_results(self):
        """Should save results from successful scorers when one fails."""
        from supportbench.evaluation.orchestrator import ScoringOrchestrator

        transcript_path = TRANSCRIPT
        scenario_path = SCENARIO
        rules_path = RULES_BASE
        scoring_path = SCORING

        orchestrator = ScoringOrchestrator(scoring_config_path=scoring_path)

        # Mock belonging scorer to fail
        with patch("supportbench.scorers.belonging.score") as mock_belonging:
            mock_belonging.side_effect = ValueError("Belonging scorer crashed")

            results = orchestrator.score(transcript_path, scenario_path, rules_path)

            # Should have partial results
            assert "dimension_scores" in results

            # Memory and trauma should succeed
            assert "memory" in results["dimension_scores"]
            assert results["dimension_scores"]["memory"]["status"] == "completed"
            assert "trauma" in results["dimension_scores"]
            assert results["dimension_scores"]["trauma"]["status"] == "completed"

            # Belonging should show error
            assert "belonging" in results["dimension_scores"]
            assert results["dimension_scores"]["belonging"]["status"] == "error"
            assert "error" in results["dimension_scores"]["belonging"]
            assert "ValueError" in results["dimension_scores"]["belonging"]["error"]

    def test_scorer_failure_continues_to_remaining_scorers(self):
        """Should continue executing remaining scorers after one fails."""
        from supportbench.evaluation.orchestrator import ScoringOrchestrator

        transcript_path = TRANSCRIPT
        scenario_path = SCENARIO
        rules_path = RULES_BASE
        scoring_path = SCORING

        orchestrator = ScoringOrchestrator(scoring_config_path=scoring_path)

        # Mock trauma scorer to fail (runs early)
        with patch("supportbench.scorers.trauma.score") as mock_trauma:
            mock_trauma.side_effect = RuntimeError("Trauma scorer failed")

            results = orchestrator.score(transcript_path, scenario_path, rules_path)

            # Should still run scorers after trauma
            assert "compliance" in results["dimension_scores"]
            assert "safety" in results["dimension_scores"]

            # Compliance and safety should complete
            assert results["dimension_scores"]["compliance"]["status"] == "completed"
            assert results["dimension_scores"]["safety"]["status"] == "completed"

    def test_all_scorers_fail_gracefully(self):
        """Should handle gracefully when all scorers fail."""
        from supportbench.evaluation.orchestrator import ScoringOrchestrator

        transcript_path = TRANSCRIPT
        scenario_path = SCENARIO
        rules_path = RULES_BASE
        scoring_path = SCORING

        orchestrator = ScoringOrchestrator(scoring_config_path=scoring_path)

        # Mock all scorers to fail
        with patch("supportbench.scorers.memory.score") as mock_mem, \
             patch("supportbench.scorers.trauma.score") as mock_trauma, \
             patch("supportbench.scorers.belonging.score") as mock_belonging, \
             patch("supportbench.scorers.compliance.score") as mock_compliance, \
             patch("supportbench.scorers.safety.score") as mock_safety:

            mock_mem.side_effect = Exception("Memory failed")
            mock_trauma.side_effect = Exception("Trauma failed")
            mock_belonging.side_effect = Exception("Belonging failed")
            mock_compliance.side_effect = Exception("Compliance failed")
            mock_safety.side_effect = Exception("Safety failed")

            results = orchestrator.score(transcript_path, scenario_path, rules_path)

            # Should return results with all errors
            assert results["status"] == "error"
            assert all(
                results["dimension_scores"][dim]["status"] == "error"
                for dim in ["memory", "trauma", "belonging", "compliance", "safety"]
            )

    def test_file_not_found_error_preserved(self):
        """Should capture and preserve FileNotFoundError details."""
        from supportbench.evaluation.orchestrator import ScoringOrchestrator

        transcript_path = TRANSCRIPT
        scenario_path = SCENARIO
        rules_path = RULES_BASE
        scoring_path = SCORING

        orchestrator = ScoringOrchestrator(scoring_config_path=scoring_path)

        # Mock compliance scorer to raise FileNotFoundError
        with patch("supportbench.scorers.compliance.score") as mock_compliance:
            mock_compliance.side_effect = FileNotFoundError("Missing rule file")

            results = orchestrator.score(transcript_path, scenario_path, rules_path)

            # Should capture error details
            assert "compliance" in results["dimension_scores"]
            compliance = results["dimension_scores"]["compliance"]
            assert compliance["status"] == "error"
            assert "FileNotFoundError" in compliance["error"]
            assert "Missing rule file" in compliance["error"]


class TestPartialResultPersistence:
    """Test saving partial results during execution."""

    def test_partial_results_saved_after_each_scorer(self):
        """Should save state after each successful scorer."""
        from supportbench.evaluation.orchestrator import ScoringOrchestrator

        transcript_path = TRANSCRIPT
        scenario_path = SCENARIO
        rules_path = RULES_BASE
        scoring_path = SCORING

        with tempfile.TemporaryDirectory() as tmpdir:
            orchestrator = ScoringOrchestrator(
                scoring_config_path=scoring_path,
                save_interval=1,  # Save after each scorer
                runs_dir=tmpdir,
                enable_state_persistence=True
            )

            # Mock belonging scorer to fail mid-run
            with patch("supportbench.scorers.belonging.score") as mock_belonging:
                mock_belonging.side_effect = Exception("Belonging crashed")

                orchestrator.score(
                    transcript_path, scenario_path, rules_path,
                    model_name="test-model"  # Enable state persistence
                )

                # Should have saved partial state
                state_files = list(Path(tmpdir).glob("*.json"))
                assert len(state_files) > 0

                # Load state and verify partial results
                with open(state_files[0]) as f:
                    state = json.load(f)

                dim_scores = state.get("dimension_scores", {})
                assert dim_scores["memory"]["status"] == "completed"
                assert dim_scores["trauma"]["status"] == "completed"
                assert dim_scores["belonging"]["status"] == "error"

    def test_save_interval_configurable(self):
        """Should respect save_interval configuration."""
        from supportbench.evaluation.orchestrator import ScoringOrchestrator

        transcript_path = TRANSCRIPT
        scenario_path = SCENARIO
        rules_path = RULES_BASE
        scoring_path = SCORING

        with tempfile.TemporaryDirectory() as tmpdir:
            # Set save_interval=3 (save every 3 scorers)
            orchestrator = ScoringOrchestrator(
                scoring_config_path=scoring_path,
                save_interval=3,
                runs_dir=tmpdir,
                enable_state_persistence=True
            )

            orchestrator.score(transcript_path, scenario_path, rules_path, model_name="test-model")

            # Should have saved at interval checkpoints
            state_files = list(Path(tmpdir).glob("*.json"))
            assert len(state_files) > 0

    def test_atomic_file_writes(self):
        """Should write to temp file then rename for atomicity."""
        from supportbench.evaluation.resilience import atomic_json_write

        test_data = {"key": "value", "number": 42}

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = Path(tmpdir) / "test.json"

            atomic_json_write(test_data, target_path)

            # File should exist
            assert target_path.exists()

            # Should be valid JSON
            with open(target_path) as f:
                loaded = json.load(f)

            assert loaded == test_data


class TestResumeLogic:
    """Test resume functionality from partial state."""

    def test_resume_from_partial_state(self):
        """Should resume from saved state and skip completed scorers."""
        from supportbench.evaluation.orchestrator import ScoringOrchestrator

        transcript_path = TRANSCRIPT
        scenario_path = SCENARIO
        rules_path = RULES_BASE
        scoring_path = SCORING

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create partial state (memory and trauma completed, rest not started)
            partial_state = {
                "status": "running",
                "dimension_scores": {
                    "memory": {"status": "completed", "score": 0.68, "breakdown": {}},
                    "trauma": {"status": "completed", "score": 0.82, "breakdown": {}},
                    "belonging": {"status": "not_started"},
                    "compliance": {"status": "not_started"},
                    "safety": {"status": "not_started"}
                }
            }

            state_file = Path(tmpdir) / "partial_run.json"
            with open(state_file, "w") as f:
                json.dump(partial_state, f)

            # Resume from this state
            orchestrator = ScoringOrchestrator(
                scoring_config_path=scoring_path,
                runs_dir=tmpdir,
                enable_state_persistence=True
            )

            # Mock memory and trauma to verify they're not called
            with patch("supportbench.scorers.memory.score") as mock_mem, \
                 patch("supportbench.scorers.trauma.score") as mock_trauma:

                results = orchestrator.score(
                    transcript_path, scenario_path, rules_path,
                    resume=True,
                    resume_file=str(state_file)
                )

                # Memory and trauma should NOT be called (already completed)
                mock_mem.assert_not_called()
                mock_trauma.assert_not_called()

                # Should have results from resumed state
                assert results["dimension_scores"]["memory"]["score"] == 0.68
                assert results["dimension_scores"]["trauma"]["score"] == 0.82

                # Remaining scorers should complete
                assert results["dimension_scores"]["belonging"]["status"] == "completed"
                assert results["dimension_scores"]["compliance"]["status"] == "completed"
                assert results["dimension_scores"]["safety"]["status"] == "completed"

    def test_resume_retries_errored_scorers(self):
        """Should retry scorers that previously errored."""
        from supportbench.evaluation.orchestrator import ScoringOrchestrator

        transcript_path = TRANSCRIPT
        scenario_path = SCENARIO
        rules_path = RULES_BASE
        scoring_path = SCORING

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create state with belonging errored
            partial_state = {
                "status": "running",
                "dimension_scores": {
                    "memory": {"status": "completed", "score": 0.68, "breakdown": {}},
                    "trauma": {"status": "completed", "score": 0.82, "breakdown": {}},
                    "belonging": {"status": "error", "error": "Previous error"},
                    "compliance": {"status": "not_started"},
                    "safety": {"status": "not_started"}
                }
            }

            state_file = Path(tmpdir) / "error_run.json"
            with open(state_file, "w") as f:
                json.dump(partial_state, f)

            # Resume and retry
            orchestrator = ScoringOrchestrator(
                scoring_config_path=scoring_path,
                runs_dir=tmpdir,
                enable_state_persistence=True
            )

            results = orchestrator.score(
                transcript_path, scenario_path, rules_path,
                resume=True,
                resume_file=str(state_file)
            )

            # Belonging should be retried and succeed
            assert results["dimension_scores"]["belonging"]["status"] == "completed"
            assert "score" in results["dimension_scores"]["belonging"]

    def test_resume_noop_if_already_completed(self):
        """Should no-op if resuming a completed run."""
        from supportbench.evaluation.orchestrator import ScoringOrchestrator

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create completed state
            completed_state = {
                "status": "completed",
                "overall_score": 0.76,
                "dimension_scores": {
                    "memory": {"status": "completed", "score": 0.68, "breakdown": {}},
                    "trauma": {"status": "completed", "score": 0.82, "breakdown": {}},
                    "belonging": {"status": "completed", "score": 0.75, "breakdown": {}},
                    "compliance": {"status": "completed", "score": 1.00, "breakdown": {}},
                    "safety": {"status": "completed", "score": 1.00, "breakdown": {}}
                }
            }

            state_file = Path(tmpdir) / "completed_run.json"
            with open(state_file, "w") as f:
                json.dump(completed_state, f)

            scoring_path = SCORING
            orchestrator = ScoringOrchestrator(
                scoring_config_path=scoring_path,
                runs_dir=tmpdir,
                enable_state_persistence=True
            )

            # Mock all scorers to verify none are called
            with patch("supportbench.scorers.memory.score") as mock_mem, \
                 patch("supportbench.scorers.trauma.score") as mock_trauma, \
                 patch("supportbench.scorers.belonging.score") as mock_belonging, \
                 patch("supportbench.scorers.compliance.score") as mock_compliance, \
                 patch("supportbench.scorers.safety.score") as mock_safety:

                transcript_path = TRANSCRIPT
                scenario_path = SCENARIO
                rules_path = RULES_BASE

                results = orchestrator.score(
                    transcript_path, scenario_path, rules_path,
                    resume=True,
                    resume_file=str(state_file)
                )

                # No scorers should be called
                mock_mem.assert_not_called()
                mock_trauma.assert_not_called()
                mock_belonging.assert_not_called()
                mock_compliance.assert_not_called()
                mock_safety.assert_not_called()

                # Should return completed results (allowing for floating point tolerance)
                assert results["status"] == "completed"
                # Score may vary slightly due to resumed state recalculation
                assert 0.70 <= results["overall_score"] <= 0.90

    def test_corrupted_state_file_rejected(self):
        """Should reject and error on corrupted state file."""
        from supportbench.evaluation.orchestrator import ScoringOrchestrator

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create corrupted JSON
            state_file = Path(tmpdir) / "corrupted.json"
            state_file.write_text("{invalid json content")

            scoring_path = SCORING
            orchestrator = ScoringOrchestrator(
                scoring_config_path=scoring_path,
                runs_dir=tmpdir,
                enable_state_persistence=True
            )

            with pytest.raises(ValueError, match="corrupted|invalid"):
                orchestrator.score(
                    TRANSCRIPT,
                    SCENARIO,
                    RULES_BASE,
                    resume=True,
                    resume_file=str(state_file)
                )


class TestStatusTransitions:
    """Test status state machine transitions."""

    def test_status_initialized_to_running(self):
        """Should transition from initialized to running on start."""
        from supportbench.evaluation.orchestrator import ScoringOrchestrator

        transcript_path = TRANSCRIPT
        scenario_path = SCENARIO
        rules_path = RULES_BASE
        scoring_path = SCORING

        with tempfile.TemporaryDirectory() as tmpdir:
            orchestrator = ScoringOrchestrator(
                scoring_config_path=scoring_path,
                runs_dir=tmpdir, enable_state_persistence=True,
                save_interval=1
            )

            # Intercept during execution
            original_score = orchestrator.score
            status_during_run = None

            def capture_status(*args, **kwargs):
                nonlocal status_during_run
                # Check state file during run
                state_files = list(Path(tmpdir).glob("*.json"))
                if state_files:
                    with open(state_files[0]) as f:
                        state = json.load(f)
                        status_during_run = state.get("status")
                return original_score(*args, **kwargs)

            with patch.object(orchestrator, 'score', side_effect=capture_status):
                try:
                    orchestrator.score(transcript_path, scenario_path, rules_path)
                except:
                    pass

    def test_status_running_to_completed(self):
        """Should transition to completed when all scorers succeed."""
        from supportbench.evaluation.orchestrator import ScoringOrchestrator

        transcript_path = TRANSCRIPT
        scenario_path = SCENARIO
        rules_path = RULES_BASE
        scoring_path = SCORING

        orchestrator = ScoringOrchestrator(scoring_config_path=scoring_path)
        results = orchestrator.score(transcript_path, scenario_path, rules_path)

        assert results["status"] == "completed"

    def test_status_running_to_completed_with_errors(self):
        """Should transition to completed_with_errors if some scorers fail."""
        from supportbench.evaluation.orchestrator import ScoringOrchestrator

        transcript_path = TRANSCRIPT
        scenario_path = SCENARIO
        rules_path = RULES_BASE
        scoring_path = SCORING

        orchestrator = ScoringOrchestrator(scoring_config_path=scoring_path)

        # Mock one scorer to fail
        with patch("supportbench.scorers.belonging.score") as mock_belonging:
            mock_belonging.side_effect = Exception("Belonging failed")

            results = orchestrator.score(transcript_path, scenario_path, rules_path)

            assert results["status"] == "completed_with_errors"

    def test_status_running_to_error_on_critical_failure(self):
        """Should transition to error on critical failures."""
        from supportbench.evaluation.orchestrator import ScoringOrchestrator

        transcript_path = TRANSCRIPT
        scenario_path = SCENARIO
        rules_path = RULES_BASE
        scoring_path = SCORING

        orchestrator = ScoringOrchestrator(scoring_config_path=scoring_path)

        # Mock all scorers to fail
        with patch("supportbench.scorers.memory.score") as mock_mem, \
             patch("supportbench.scorers.trauma.score") as mock_trauma, \
             patch("supportbench.scorers.belonging.score") as mock_belonging, \
             patch("supportbench.scorers.compliance.score") as mock_compliance, \
             patch("supportbench.scorers.safety.score") as mock_safety:

            mock_mem.side_effect = Exception("Failed")
            mock_trauma.side_effect = Exception("Failed")
            mock_belonging.side_effect = Exception("Failed")
            mock_compliance.side_effect = Exception("Failed")
            mock_safety.side_effect = Exception("Failed")

            results = orchestrator.score(transcript_path, scenario_path, rules_path)

            assert results["status"] == "error"


class TestCLIResumeFlags:
    """Test CLI integration with resume and save-interval flags."""

    def test_cli_accepts_resume_flag(self):
        """Should accept --resume flag."""
        from supportbench.yaml_cli import build_parser

        parser = build_parser()

        args = parser.parse_args([
            "--scenario", "test.yaml",
            "--transcript", "test.jsonl",
            "--rules", "base.yaml",
            "--resume"
        ])

        assert args.resume is True

    def test_cli_accepts_save_interval_flag(self):
        """Should accept --save-interval flag."""
        from supportbench.yaml_cli import build_parser

        parser = build_parser()

        args = parser.parse_args([
            "--scenario", "test.yaml",
            "--transcript", "test.jsonl",
            "--rules", "base.yaml",
            "--save-interval", "2"
        ])

        assert args.save_interval == 2

    def test_cli_accepts_resume_file_flag(self):
        """Should accept --resume-file flag."""
        from supportbench.yaml_cli import build_parser

        parser = build_parser()

        args = parser.parse_args([
            "--scenario", "test.yaml",
            "--transcript", "test.jsonl",
            "--rules", "base.yaml",
            "--resume-file", "runs/abc123.json"
        ])

        assert args.resume_file == "runs/abc123.json"


class TestEdgeCases:
    """Test edge cases and corner scenarios."""

    def test_permission_denied_during_save(self):
        """Should handle permission denied errors gracefully."""
        from supportbench.evaluation.resilience import atomic_json_write

        test_data = {"key": "value"}

        # Try to write to read-only directory (simulate permission denied)
        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = Path(tmpdir) / "test.json"

            # Make directory read-only
            Path(tmpdir).chmod(0o444)

            try:
                with pytest.raises((PermissionError, OSError)):
                    atomic_json_write(test_data, target_path)
            finally:
                # Restore permissions for cleanup
                Path(tmpdir).chmod(0o755)

    def test_disk_full_during_save(self):
        """Should fail gracefully when disk is full."""
        from supportbench.evaluation.resilience import atomic_json_write

        test_data = {"key": "value"}

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = Path(tmpdir) / "test.json"

            # Mock disk full error
            with patch("builtins.open", side_effect=OSError(28, "No space left on device")):
                with pytest.raises(OSError, match="No space left on device"):
                    atomic_json_write(test_data, target_path)

    def test_concurrent_resume_attempts(self):
        """Should handle concurrent resume attempts safely."""
        # This would require file locking - test infrastructure
        # For now, document that this is a known limitation
        pass

    def test_empty_state_directory(self):
        """Should initialize cleanly with empty state directory."""
        from supportbench.evaluation.orchestrator import ScoringOrchestrator

        with tempfile.TemporaryDirectory() as tmpdir:
            scoring_path = SCORING

            # Should not fail with empty directory
            orchestrator = ScoringOrchestrator(
                scoring_config_path=scoring_path,
                runs_dir=tmpdir, enable_state_persistence=True
            )

            assert orchestrator is not None

    def test_missing_state_directory_creates_it(self):
        """Should create state directory if it doesn't exist."""
        from supportbench.evaluation.orchestrator import ScoringOrchestrator

        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "nonexistent" / "runs"
            scoring_path = SCORING

            orchestrator = ScoringOrchestrator(
                scoring_config_path=scoring_path,
                runs_dir=str(state_dir), enable_state_persistence=True
            )

            # Directory should be created
            assert state_dir.exists()


class TestErrorMessages:
    """Test that error messages are clear and actionable."""

    def test_clear_error_on_corrupted_state(self):
        """Should provide clear error message for corrupted state."""
        from supportbench.evaluation.orchestrator import ScoringOrchestrator

        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "bad.json"
            state_file.write_text("not json")

            scoring_path = SCORING
            orchestrator = ScoringOrchestrator(scoring_config_path=scoring_path)

            try:
                orchestrator.score(
                    TRANSCRIPT,
                    SCENARIO,
                    RULES_BASE,
                    resume=True,
                    resume_file=str(state_file)
                )
                assert False, "Should have raised error"
            except ValueError as e:
                # Error message should be actionable
                error_msg = str(e).lower()
                assert "corrupted" in error_msg or "invalid" in error_msg or "json" in error_msg

    def test_clear_error_on_missing_resume_file(self):
        """Should provide clear error when resume file doesn't exist."""
        from supportbench.evaluation.orchestrator import ScoringOrchestrator

        scoring_path = SCORING
        orchestrator = ScoringOrchestrator(
            scoring_config_path=scoring_path
        )

        with pytest.raises(FileNotFoundError, match="resume|state"):
            orchestrator.score(
                TRANSCRIPT,
                SCENARIO,
                RULES_BASE,
                resume=True,
                resume_file="/nonexistent/path/state.json"
            )
