from __future__ import annotations

from pathlib import Path


def artifact_reference(path: Path, repo_root: Path) -> str:
    """Return a useful artifact path without publishing a host-specific prefix."""
    resolved = path.resolve()
    try:
        return resolved.relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.name

