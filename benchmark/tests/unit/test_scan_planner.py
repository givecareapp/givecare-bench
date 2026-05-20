from __future__ import annotations

from scripts.run_scan import apply_scan_profile, build_scan_plan, load_scan_profile


def test_scan_profile_filters_modes_and_overrides_repetitions() -> None:
    modes = {
        "IB-A1": {
            "id": "IB-A1",
            "primary_bucket": "A",
            "severity": "S5",
            "scope": "trigger",
            "eligibility": {"scenario_tags_any": ["passive_ideation"]},
        },
        "IB-C1": {
            "id": "IB-C1",
            "primary_bucket": "C",
            "severity": "S2",
            "scope": "universal",
        },
    }
    routing = {
        "IB-A1": {"route": "hybrid_llm", "repetitions": 3},
        "IB-C1": {"route": "llm_primary", "repetitions": 3},
    }
    profile = load_scan_profile("dev")

    filtered_modes, filtered_routing = apply_scan_profile(modes, routing, profile)

    assert set(filtered_modes) == {"IB-A1"}
    assert filtered_routing["IB-A1"]["repetitions"] == 1
    assert filtered_routing["IB-A1"]["adaptive_repetitions"] is True


def test_build_scan_plan_counts_profiled_llm_calls() -> None:
    modes = {
        "IB-A1": {
            "id": "IB-A1",
            "primary_bucket": "A",
            "severity": "S5",
            "scope": "trigger",
            "eligibility": {"scenario_tags_any": ["passive_ideation"]},
        },
        "IB-F1-human-identity": {
            "id": "IB-F1-human-identity",
            "primary_bucket": "F",
            "severity": "S4_GATE",
            "scope": "universal",
        },
    }
    routing = {
        "IB-A1": {"route": "hybrid_llm", "repetitions": 1},
        "IB-F1-human-identity": {"route": "regex_with_llm_edge", "repetitions": 1},
    }
    profile = load_scan_profile("full")

    plan = build_scan_plan(
        [{"scenario_id": "s1", "failure_mode_tags": ["passive_ideation"]}],
        modes,
        routing,
        profile,
        judge_model="google/gemini-2.5-flash-lite",
        llm_enabled=True,
    )

    assert plan["transcript_count"] == 1
    assert plan["eligible_checks"] == 2
    assert plan["planned_llm_calls"] == 1
    assert plan["by_mode"]["IB-A1"]["planned_llm_calls"] == 1
    assert plan["by_mode"]["IB-F1-human-identity"]["planned_llm_calls"] == 0
