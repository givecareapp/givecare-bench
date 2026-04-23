"""Progress tracking utilities for scoring runs."""

from __future__ import annotations

import sys
from typing import Any, Callable, Optional

try:
    from tqdm import tqdm  # type: ignore
except ImportError:
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
        self.callback = callback
        self.verbose = verbose
        self.quiet = quiet
        self._tqdm = tqdm
        self.use_tqdm = use_tqdm and (self._tqdm is not None) and not quiet
        self.completed = 0
        self.total = 5  # safety, compliance, regard, coordination, memory
        self._pbar = None

        if self.use_tqdm:
            self._pbar = self._tqdm(
                total=self.total,
                desc="Scoring dimensions",
                unit="dimension",
                leave=True,
                file=sys.stdout,
            )

    def report_dimension(
        self, dimension: str, score: float, details: Optional[dict[str, Any]] = None
    ) -> None:
        self.completed += 1

        if self.callback:
            self.callback(dimension, score)

        if self._pbar is not None:
            self._pbar.update(1)
            if self.verbose and details:
                # tqdm.write avoids corrupting the progress bar line
                if self._tqdm:
                    self._tqdm.write(
                        f"  {dimension.title()}: {score:.2f} - {details}", file=sys.stdout
                    )
        elif not self.quiet:
            output = f"[{self.completed}/{self.total}] {dimension.title()} scoring... {score:.2f}"
            if self.verbose and details:
                output += f" - {details}"
            print(output, file=sys.stdout)

    def close(self) -> None:
        if self._pbar:
            self._pbar.close()
            self._pbar = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
