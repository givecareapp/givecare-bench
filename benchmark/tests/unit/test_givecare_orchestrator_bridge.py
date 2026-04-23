from __future__ import annotations

import os
from pathlib import Path

import pytest

import invisiblebench.adapters.givecare_orchestrator as givecare_orchestrator
from invisiblebench.adapters.givecare_orchestrator import bridge_healthcheck, ensure_bridge_bundle

REPO_ROOT = Path(__file__).resolve().parents[3]
MONO_ROOT = REPO_ROOT.parent / "give-care-mono"
BRIDGE_BUNDLE = REPO_ROOT / "adapters/givecare-orchestrator/dist/bridge.cjs"
PI_ORCHESTRATOR_SOURCE = MONO_ROOT / "packages/pi-orchestrator/src/index.ts"


@pytest.mark.skipif(
    not (MONO_ROOT.exists() and (BRIDGE_BUNDLE.exists() or PI_ORCHESTRATOR_SOURCE.exists())),
    reason="give-care bridge bundle or mono source checkout not available",
)
def test_ensure_bridge_bundle_and_healthcheck() -> None:
    bundle = ensure_bridge_bundle()
    assert bundle.exists()
    health = bridge_healthcheck()
    assert health["ok"] is True
    assert health["status"] == "ready"


def test_ensure_bridge_bundle_uses_prebuilt_bundle_when_mono_sources_are_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mono_root = tmp_path / "give-care-mono"
    mono_root.mkdir()
    build_script = tmp_path / "build.mjs"
    build_script.write_text("// build")
    source_path = tmp_path / "bridge.ts"
    source_path.write_text("// source")
    bundle_path = tmp_path / "dist" / "bridge.cjs"
    bundle_path.parent.mkdir(parents=True)
    bundle_path.write_text("// prebuilt bundle")
    os.utime(bundle_path, (1, 1))

    monkeypatch.setattr(givecare_orchestrator, "_mono_root", lambda: mono_root)
    monkeypatch.setattr(givecare_orchestrator, "_bridge_build_script", lambda: build_script)
    monkeypatch.setattr(givecare_orchestrator, "_bridge_bundle", lambda: bundle_path)
    monkeypatch.setattr(givecare_orchestrator, "_collect_source_paths", lambda: [source_path])

    def _unexpected_rebuild(*args, **kwargs):
        raise AssertionError("ensure_bridge_bundle should reuse the prebuilt bundle")

    monkeypatch.setattr(givecare_orchestrator.subprocess, "run", _unexpected_rebuild)

    assert givecare_orchestrator.ensure_bridge_bundle() == bundle_path


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
