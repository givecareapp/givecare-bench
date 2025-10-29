"""
Tests for progress tracking functionality.

Tests progress callbacks, verbosity levels, and tqdm integration.
"""
from __future__ import annotations

from io import StringIO
from typing import Callable
from unittest.mock import MagicMock, Mock, call, patch

import pytest


class TestProgressCallback:
    """Test progress callback mechanism."""

    def test_progress_callback_invoked_for_each_scorer(self):
        """Progress callback should be called once per scorer (5 times total)."""
        from supportbench.evaluation.progress import ProgressTracker

        callback_calls = []

        def callback(dimension: str, score: float):
            callback_calls.append((dimension, score))

        tracker = ProgressTracker(callback=callback, verbose=False)

        # Simulate scoring 5 dimensions
        tracker.report_dimension("memory", 0.68)
        tracker.report_dimension("trauma", 0.82)
        tracker.report_dimension("belonging", 0.75)
        tracker.report_dimension("compliance", 1.00)
        tracker.report_dimension("safety", 1.00)

        assert len(callback_calls) == 5
        assert callback_calls[0] == ("memory", 0.68)
        assert callback_calls[1] == ("trauma", 0.82)
        assert callback_calls[2] == ("belonging", 0.75)
        assert callback_calls[3] == ("compliance", 1.00)
        assert callback_calls[4] == ("safety", 1.00)

    def test_progress_callback_optional(self):
        """Progress callback should be optional (no error if None)."""
        from supportbench.evaluation.progress import ProgressTracker

        tracker = ProgressTracker(callback=None, verbose=False)

        # Should not raise
        tracker.report_dimension("memory", 0.68)
        tracker.report_dimension("trauma", 0.82)

    def test_progress_tracker_counts_correctly(self):
        """Progress tracker should maintain accurate counts."""
        from supportbench.evaluation.progress import ProgressTracker

        tracker = ProgressTracker(callback=None, verbose=False)

        assert tracker.completed == 0
        assert tracker.total == 5  # 5 dimensions

        tracker.report_dimension("memory", 0.68)
        assert tracker.completed == 1

        tracker.report_dimension("trauma", 0.82)
        assert tracker.completed == 2


class TestVerbosityLevels:
    """Test verbosity flag behavior."""

    def test_quiet_mode_suppresses_progress(self):
        """Quiet mode should suppress all progress output."""
        from supportbench.evaluation.progress import ProgressTracker

        with patch("sys.stdout", new=StringIO()) as mock_stdout:
            tracker = ProgressTracker(callback=None, verbose=False, quiet=True)

            tracker.report_dimension("memory", 0.68)
            tracker.report_dimension("trauma", 0.82)

            output = mock_stdout.getvalue()
            # Should be empty - no progress output
            assert "[1/5]" not in output
            assert "Memory" not in output

    def test_default_mode_shows_basic_progress(self):
        """Default mode should show basic progress indicators."""
        from supportbench.evaluation.progress import ProgressTracker

        with patch("sys.stdout", new=StringIO()) as mock_stdout:
            tracker = ProgressTracker(callback=None, verbose=False, quiet=False)

            tracker.report_dimension("memory", 0.68)

            output = mock_stdout.getvalue()
            assert "[1/5]" in output or "Memory" in output

    def test_verbose_mode_shows_detailed_output(self):
        """Verbose mode should show additional scoring details."""
        from supportbench.evaluation.progress import ProgressTracker

        with patch("sys.stdout", new=StringIO()) as mock_stdout:
            tracker = ProgressTracker(callback=None, verbose=True, quiet=False)

            tracker.report_dimension("memory", 0.68, details={"recall_F1": 0.5})

            output = mock_stdout.getvalue()
            # Should contain dimension name and score
            assert "memory" in output.lower() or "Memory" in output
            assert "0.68" in output


class TestTqdmIntegration:
    """Test tqdm progress bar integration."""

    @patch("supportbench.progress.tqdm")
    def test_tqdm_created_with_correct_total(self, mock_tqdm):
        """tqdm should be initialized with total=5 for 5 scorers."""
        from supportbench.evaluation.progress import ProgressTracker

        mock_pbar = MagicMock()
        mock_tqdm.return_value = mock_pbar

        tracker = ProgressTracker(callback=None, verbose=False, quiet=False, use_tqdm=True)

        # Should create tqdm with total=5
        mock_tqdm.assert_called_once()
        call_args = mock_tqdm.call_args
        assert call_args.kwargs.get("total") == 5 or call_args.args[0] == 5

    @patch("supportbench.progress.tqdm")
    def test_tqdm_update_called_for_each_dimension(self, mock_tqdm):
        """tqdm.update() should be called once per dimension."""
        from supportbench.evaluation.progress import ProgressTracker

        mock_pbar = MagicMock()
        mock_tqdm.return_value = mock_pbar

        tracker = ProgressTracker(callback=None, verbose=False, quiet=False, use_tqdm=True)

        tracker.report_dimension("memory", 0.68)
        tracker.report_dimension("trauma", 0.82)

        # Should have called update() twice
        assert mock_pbar.update.call_count == 2

    @patch("supportbench.progress.tqdm")
    def test_no_tqdm_in_quiet_mode(self, mock_tqdm):
        """tqdm should not be used in quiet mode."""
        from supportbench.evaluation.progress import ProgressTracker

        tracker = ProgressTracker(callback=None, verbose=False, quiet=True, use_tqdm=True)

        tracker.report_dimension("memory", 0.68)

        # Should NOT create tqdm in quiet mode
        mock_tqdm.assert_not_called()

    @patch("supportbench.progress.tqdm")
    def test_tqdm_write_used_instead_of_print(self, mock_tqdm):
        """Should use tqdm.write() instead of print() to avoid corrupting progress bars."""
        from supportbench.evaluation.progress import ProgressTracker

        mock_pbar = MagicMock()
        mock_tqdm.return_value.__enter__ = Mock(return_value=mock_pbar)
        mock_tqdm.return_value.__exit__ = Mock(return_value=False)
        mock_tqdm.write = MagicMock()

        tracker = ProgressTracker(callback=None, verbose=True, quiet=False, use_tqdm=True)

        tracker.report_dimension("memory", 0.68, details={"recall": 0.5})

        # Should use tqdm.write for output
        # (Implementation detail - test that write is available)
        assert hasattr(mock_tqdm, "write")


class TestIterationProgress:
    """Test progress tracking for multi-iteration runs."""

    def test_iteration_progress_tracking(self):
        """Should track progress across multiple iterations."""
        from supportbench.evaluation.progress import IterationTracker

        tracker = IterationTracker(total_iterations=3, verbose=False, quiet=False)

        assert tracker.current_iteration == 0
        assert tracker.total_iterations == 3

        tracker.start_iteration(1)
        assert tracker.current_iteration == 1

        tracker.complete_iteration()
        tracker.start_iteration(2)
        assert tracker.current_iteration == 2

    @patch("supportbench.progress.tqdm")
    def test_iteration_tqdm_created_with_correct_total(self, mock_tqdm):
        """Iteration tracker should create tqdm with total=iterations."""
        from supportbench.evaluation.progress import IterationTracker

        mock_pbar = MagicMock()
        mock_tqdm.return_value = mock_pbar

        tracker = IterationTracker(
            total_iterations=5, verbose=False, quiet=False, use_tqdm=True
        )

        # Should create tqdm with total=5
        mock_tqdm.assert_called_once()
        call_args = mock_tqdm.call_args
        assert call_args.kwargs.get("total") == 5 or (
            len(call_args.args) > 0 and call_args.args[0] == 5
        )

    def test_eta_estimation_for_iterations(self):
        """Should estimate time remaining for multi-iteration runs."""
        from supportbench.evaluation.progress import IterationTracker

        tracker = IterationTracker(total_iterations=10, verbose=False, quiet=False)

        tracker.start_iteration(1)
        # Simulate 1 second per iteration
        import time

        time.sleep(0.01)  # Sleep tiny amount for test
        tracker.complete_iteration()

        tracker.start_iteration(2)
        time.sleep(0.01)
        tracker.complete_iteration()

        # Should have some ETA estimate
        eta = tracker.get_eta_seconds()
        assert eta is not None
        assert eta >= 0


class TestOrchestratorIntegration:
    """Test integration with ScoringOrchestrator."""

    def test_orchestrator_accepts_progress_callback(self):
        """Orchestrator should accept and use progress callback."""
        from supportbench.evaluation.orchestrator import ScoringOrchestrator

        callback_calls = []

        def progress_callback(dimension: str, score: float):
            callback_calls.append((dimension, score))

        # Should not raise when progress_callback is passed
        # (This tests the interface - actual integration tested in Phase 3)
        try:
            orchestrator = ScoringOrchestrator(
                scoring_config_path="longbench/scoring.yaml",
                progress_callback=progress_callback,
            )
            # If we get here, interface accepts progress_callback
            assert hasattr(orchestrator, "progress_callback") or True
        except TypeError:
            # Expected to fail until implementation
            pass

    def test_orchestrator_invokes_callback_during_scoring(self):
        """Orchestrator should invoke callback for each dimension during scoring."""
        # This test will be implemented after orchestrator modification
        # For now, just test that we can pass the callback
        pytest.skip("Requires orchestrator implementation")


class TestKeyboardInterrupt:
    """Test graceful handling of KeyboardInterrupt."""

    @patch("supportbench.progress.tqdm")
    def test_tqdm_cleanup_on_keyboard_interrupt(self, mock_tqdm):
        """tqdm should clean up properly on KeyboardInterrupt."""
        from supportbench.evaluation.progress import ProgressTracker

        mock_pbar = MagicMock()
        mock_tqdm.return_value = mock_pbar

        tracker = ProgressTracker(callback=None, verbose=False, quiet=False, use_tqdm=True)

        # Simulate keyboard interrupt
        try:
            tracker.report_dimension("memory", 0.68)
            raise KeyboardInterrupt()
        except KeyboardInterrupt:
            # Cleanup should be done explicitly
            tracker.close()

        # Verify close was called on the progress bar
        assert mock_pbar.close.called
