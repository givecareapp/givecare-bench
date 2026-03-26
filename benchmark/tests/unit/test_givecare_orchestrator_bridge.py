from __future__ import annotations

from pathlib import Path

import pytest

import invisiblebench.adapters.givecare_orchestrator as givecare_orchestrator
from invisiblebench.adapters.givecare_orchestrator import bridge_healthcheck, ensure_bridge_bundle

MONO_ROOT = Path(__file__).resolve().parents[4] / "give-care-mono"


@pytest.mark.skipif(not MONO_ROOT.exists(), reason="give-care-mono checkout not available")
def test_ensure_bridge_bundle_and_healthcheck() -> None:
    bundle = ensure_bridge_bundle()
    assert bundle.exists()
    health = bridge_healthcheck()
    assert health["ok"] is True
    assert health["status"] == "ready"


def test_bridge_diagnostics_reports_build_required_when_bundle_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mono_root = tmp_path / "give-care-mono"
    mono_root.mkdir()
    build_script = tmp_path / "build.mjs"
    build_script.write_text("// build")
    source_path = tmp_path / "bridge.ts"
    source_path.write_text("// source")
    bundle_path = tmp_path / "dist" / "bridge.cjs"

    monkeypatch.setattr(givecare_orchestrator, "_mono_root", lambda: mono_root)
    monkeypatch.setattr(givecare_orchestrator, "_bridge_build_script", lambda: build_script)
    monkeypatch.setattr(givecare_orchestrator, "_bridge_bundle", lambda: bundle_path)
    monkeypatch.setattr(givecare_orchestrator, "_collect_source_paths", lambda: [source_path])

    diagnostics = givecare_orchestrator.bridge_diagnostics()

    assert diagnostics["status"] == "build_required"
    assert diagnostics["bundle_exists"] is False
