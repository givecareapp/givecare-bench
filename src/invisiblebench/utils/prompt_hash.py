"""Stable prompt-template hashes for run and publication provenance."""

from __future__ import annotations

import hashlib


def prompt_hash(text: str) -> str:
    """Return the full SHA256 digest of trimmed prompt text."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def prompt_template_hash(*parts: str) -> str:
    """Hash non-empty trimmed template parts joined by one blank line."""
    normalized = "\n\n".join(part.strip() for part in parts if part and part.strip())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
