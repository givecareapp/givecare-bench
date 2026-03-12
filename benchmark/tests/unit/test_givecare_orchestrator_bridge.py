from __future__ import annotations

from pathlib import Path

import pytest
from invisiblebench.givecare_orchestrator import bridge_healthcheck, ensure_bridge_bundle

MONO_ROOT = Path(__file__).resolve().parents[4] / "give-care-mono"


@pytest.mark.skipif(not MONO_ROOT.exists(), reason="give-care-mono checkout not available")
def test_ensure_bridge_bundle_and_healthcheck() -> None:
    bundle = ensure_bridge_bundle()
    assert bundle.exists()
    health = bridge_healthcheck()
    assert health["ok"] is True
    assert health["status"] == "ready"
