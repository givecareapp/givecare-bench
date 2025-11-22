"""
Progress tracking utilities for InvisibleBench.

Provides progress bars, callbacks, and ETA estimation for scoring runs.
"""
from __future__ import annotations

import sys
import time
from typing import Any, Callable, Dict, Optional
from importlib import import_module

try:
    # Import through shim so tests can patch `invisiblebench.progress.tqdm`
    from invisiblebench.progress import tqdm  # type: ignore
except Exception:
    tqdm = None  # type: ignore


class ProgressTracker:
    """Tracks progress through dimension scoring."""

    def __init__(
        self,
        callback: Optional[Callable[[str, float], None]] = None,
        verbose: bool = False,
        quiet: bool = False,
        use_tqdm: bool = False,
    ):
        """
        Initialize progress tracker.

        Args:
            callback: Optional callback function(dimension, score)
            verbose: Show detailed output
            quiet: Suppress all progress output
            use_tqdm: Use tqdm progress bars
        """
        self.callback = callback
        self.verbose = verbose
        self.quiet = quiet
        # Resolve tqdm dynamically so test patches to invisiblebench.progress.tqdm take effect
        try:
            shim = import_module("invisiblebench.progress")
            self._tqdm = getattr(shim, "tqdm", None)
        except Exception:
            self._tqdm = None
        self.use_tqdm = use_tqdm and (self._tqdm is not None) and not quiet
        self.completed = 0
        self.total = 5  # 5 dimensions: memory, trauma, belonging, compliance, safety
        self._pbar = None

        # Create tqdm progress bar if enabled
        if self.use_tqdm:
            self._pbar = self._tqdm(
                total=self.total,
                desc="Scoring dimensions",
                unit="dimension",
                leave=True,
                file=sys.stdout,
            )

    def report_dimension(
        self, dimension: str, score: float, details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Report completion of a dimension.

        Args:
            dimension: Dimension name (e.g., "memory", "trauma")
            score: Dimension score (0.0-1.0)
            details: Optional detailed breakdown
        """
        self.completed += 1

        # Invoke callback if provided
        if self.callback:
            self.callback(dimension, score)

        # Update tqdm progress bar
        if self._pbar is not None:
            self._pbar.update(1)
            if self.verbose and details:
                # Use tqdm.write to avoid corrupting progress bar
                if self._tqdm:
                    self._tqdm.write(
                        f"  {dimension.title()}: {score:.2f} - {details}", file=sys.stdout
                    )
        elif not self.quiet:
            # Default mode: simple console output
            output = f"[{self.completed}/{self.total}] {dimension.title()} scoring... {score:.2f}"
            if self.verbose and details:
                output += f" - {details}"
            print(output, file=sys.stdout)

    def close(self) -> None:
        """Clean up resources (close progress bar)."""
        if self._pbar:
            self._pbar.close()
            self._pbar = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures cleanup."""
        self.close()
        return False


class IterationTracker:
    """Tracks progress across multiple iterations."""

    def __init__(
        self,
        total_iterations: int,
        verbose: bool = False,
        quiet: bool = False,
        use_tqdm: bool = True,
    ):
        """
        Initialize iteration tracker.

        Args:
            total_iterations: Total number of iterations to run
            verbose: Show detailed output
            quiet: Suppress all progress output
            use_tqdm: Use tqdm progress bars
        """
        self.total_iterations = total_iterations
        self.current_iteration = 0
        self.verbose = verbose
        self.quiet = quiet
        try:
            shim = import_module("invisiblebench.progress")
            self._tqdm = getattr(shim, "tqdm", None)
        except Exception:
            self._tqdm = None
        self.use_tqdm = use_tqdm and (self._tqdm is not None) and not quiet
        self._pbar = None
        self._start_times = []

        # Create tqdm progress bar if enabled
        if self.use_tqdm:
            self._pbar = self._tqdm(
                total=total_iterations,
                desc="Iterations",
                unit="iteration",
                leave=True,
                file=sys.stdout,
            )

    def start_iteration(self, iteration_num: int) -> None:
        """
        Start a new iteration.

        Args:
            iteration_num: Iteration number (1-indexed)
        """
        self.current_iteration = iteration_num
        self._start_times.append(time.time())

        if not self.quiet and not self.use_tqdm:
            print(
                f"\n=== Iteration {iteration_num}/{self.total_iterations} ===",
                file=sys.stdout,
            )

    def complete_iteration(self) -> None:
        """Mark current iteration as complete."""
        if self._pbar:
            self._pbar.update(1)

    def get_eta_seconds(self) -> Optional[float]:
        """
        Estimate time remaining in seconds.

        Returns:
            Estimated seconds remaining, or None if not enough data
        """
        if len(self._start_times) < 2:
            return None

        # Calculate average time per iteration
        completed = len(self._start_times) - 1  # Don't count current iteration
        if completed == 0:
            return None

        elapsed = time.time() - self._start_times[0]
        avg_per_iteration = elapsed / completed
        remaining_iterations = self.total_iterations - completed

        return avg_per_iteration * remaining_iterations

    def close(self) -> None:
        """Clean up resources."""
        if self._pbar:
            self._pbar.close()
            self._pbar = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures cleanup."""
        self.close()
        return False
