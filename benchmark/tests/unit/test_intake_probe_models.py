"""Fixture-backed preflight: the intake probe's PROBE_MODELS roster must
resolve against the live models catalog.

Before this test, a model rename/retirement in
src/invisiblebench/models/config.py only surfaced when the weekly
bench-intake-probe timer burned all 25 staged candidates with an opaque
"bench exited with code 1" (see CLAUDE.md's 2026-07-05 repair note — a0882fb
renamed "Claude Opus 4.7" to "Claude Opus 4.8" and PROBE_MODELS' hardcoded
default went stale for three consecutive weekly runs before anyone noticed).
This test resolves the SAME default roster string the script falls back to
(parsed straight out of scripts/intake/overnight-promote.sh, so there's one
source of truth, not a second hardcoded copy that itself could drift) against
MODELS_FULL, so the next rename fails here — in CI-local `pytest
benchmark/tests -q` — instead of in the weekly timer.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from invisiblebench.cli.runner import resolve_models
from invisiblebench.models.config import MODELS_FULL

REPO_ROOT = Path(__file__).resolve().parents[3]
OVERNIGHT_PROMOTE_SCRIPT = REPO_ROOT / "scripts" / "intake" / "overnight-promote.sh"


def _catalog() -> list[dict[str, Any]]:
    return [m.model_dump() for m in MODELS_FULL]


def _default_probe_models() -> list[str]:
    """Parse the PROBE_MODELS default straight out of the script."""
    text = OVERNIGHT_PROMOTE_SCRIPT.read_text()
    match = re.search(r'PROBE_MODELS="\$\{PROBE_MODELS:-([^}]+)\}"', text)
    assert match, "could not find a PROBE_MODELS default in overnight-promote.sh"
    return [name.strip() for name in match.group(1).split(",")]


def test_overnight_promote_script_exists() -> None:
    assert OVERNIGHT_PROMOTE_SCRIPT.is_file(), (
        "scripts/intake/overnight-promote.sh not found — if it moved again, "
        "update OVERNIGHT_PROMOTE_SCRIPT here and the systemd unit ExecStart."
    )


def test_probe_models_default_resolves_against_catalog() -> None:
    """Every name in the PROBE_MODELS default must match exactly one model in
    the live catalog. A rename/retirement makes this assertion fail."""
    probe_models = _default_probe_models()
    assert probe_models, "PROBE_MODELS default parsed empty"

    for name in probe_models:
        matched = resolve_models(name, _catalog())
        assert matched, (
            f"PROBE_MODELS name {name!r} does not resolve against "
            "src/invisiblebench/models/config.py — the intake probe roster "
            "has drifted from the current model catalog (this is exactly "
            "the 2026-06/07 silent-outage failure mode)."
        )


def test_probe_models_resolve_together_as_one_spec() -> None:
    """The script passes the whole roster as one comma-joined `-m` spec
    (`bench -m "$PROBE_MODELS" ...`), so resolve it that way too — catches a
    name that's ambiguous (matches >1 model) as well as one that matches none."""
    probe_models = _default_probe_models()
    spec = ",".join(probe_models)

    matched = resolve_models(spec, _catalog())
    assert len(matched) == len(probe_models), (
        f"spec {spec!r} resolved to {len(matched)} model(s), expected "
        f"{len(probe_models)} (one per PROBE_MODELS name)"
    )


def test_stale_model_name_fails_closed() -> None:
    """Regression proof, mirroring the actual outage: a retired name
    ('Claude Opus 4.7', retired when the catalog moved to 4.8) must raise —
    resolve_models fails closed with the CLI's own listing, it never
    silently returns zero models."""
    with pytest.raises(ValueError, match="No model matching"):
        resolve_models("Claude Opus 4.7", _catalog())
