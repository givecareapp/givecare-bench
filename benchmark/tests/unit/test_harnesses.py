from __future__ import annotations

import pytest
from invisiblebench.harnesses import adapter_name, is_mode_implemented, resolve_harness_mode


def test_resolve_default_provider_to_llm_raw() -> None:
    assert resolve_harness_mode(provider="openrouter") == ("llm", "raw")


def test_resolve_givecare_defaults_to_live() -> None:
    assert resolve_harness_mode(provider="givecare") == ("givecare", "live")


def test_harness_overrides_provider_mapping() -> None:
    assert resolve_harness_mode(harness="givecare", mode="live") == ("givecare", "live")


def test_llm_benchmark_alias_maps_to_raw() -> None:
    assert resolve_harness_mode(harness="llm", mode="benchmark") == ("llm", "raw")


def test_invalid_mode_raises() -> None:
    with pytest.raises(ValueError):
        resolve_harness_mode(harness="llm", mode="live")


def test_mode_implementation_tracking() -> None:
    assert is_mode_implemented("llm", "raw") is True
    assert is_mode_implemented("givecare", "live") is True
    assert is_mode_implemented("givecare", "orchestrator") is True


def test_adapter_name() -> None:
    assert adapter_name("givecare", "live") == "givecare-live"
