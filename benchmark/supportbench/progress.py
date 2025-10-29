"""Top-level progress shims for test patching.

Provides a `tqdm` attribute so tests can patch
`supportbench.progress.tqdm` without importing the real dependency.
"""

from supportbench.utils.progress import tqdm as tqdm  # type: ignore

__all__ = ["tqdm"]

