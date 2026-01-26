"""
Scenario configurations for InvisibleBench.

Centralized scenario definitions for minimal and full benchmark scripts.
"""
from typing import Dict, List

# Minimal scenarios for quick validation (1 per tier)
SCENARIOS_MINIMAL: List[Dict] = [
    {
        "tier": 1,
        "path": "benchmark/scenarios/tier1/crisis/crisis_detection.json",
        "name": "Crisis Detection",
        "yaml_path": None
    },
    {
        "tier": 2,
        "path": "benchmark/scenarios/tier2/burnout/sandwich_generation_burnout.json",
        "name": "Sandwich Generation Burnout",
        "yaml_path": None
    },
    {
        "tier": 3,
        "path": "benchmark/scenarios/tier3/longitudinal_trust.json",
        "name": "Longitudinal Trust",
        "yaml_path": None
    }
]

# All public scenarios (22 total)
SCENARIOS_FULL: List[Dict] = [
    # Tier 0 scenarios - Smoke tests (2 turns each)
    {
        "tier": 0,
        "path": "benchmark/scenarios/tier0/attachment_engineering.json",
        "name": "Attachment Engineering",
        "yaml_path": None
    },
    {
        "tier": 0,
        "path": "benchmark/scenarios/tier0/diagnosis_trap.json",
        "name": "Diagnosis Trap",
        "yaml_path": None
    },
    {
        "tier": 0,
        "path": "benchmark/scenarios/tier0/dosing_trap.json",
        "name": "Dosing Trap",
        "yaml_path": None
    },
    {
        "tier": 0,
        "path": "benchmark/scenarios/tier0/explicit_si.json",
        "name": "Explicit SI",
        "yaml_path": None
    },
    {
        "tier": 0,
        "path": "benchmark/scenarios/tier0/masked_si.json",
        "name": "Masked SI",
        "yaml_path": None
    },
    # Tier 1 scenarios (3-5 turns)
    {
        "tier": 1,
        "path": "benchmark/scenarios/tier1/crisis/crisis_detection.json",
        "name": "Crisis Detection",
        "yaml_path": None
    },
    {
        "tier": 1,
        "path": "benchmark/scenarios/tier1/crisis/uk_teen_caregiver_crisis.json",
        "name": "UK Teen Caregiver Crisis",
        "yaml_path": None
    },
    {
        "tier": 1,
        "path": "benchmark/scenarios/tier1/boundaries/attachment_boundary_test.json",
        "name": "Attachment Boundary Test",
        "yaml_path": None
    },
    {
        "tier": 1,
        "path": "benchmark/scenarios/tier1/boundaries/medical_boundary_violation.json",
        "name": "Medical Boundary Violation",
        "yaml_path": None
    },
    {
        "tier": 1,
        "path": "benchmark/scenarios/tier1/cultural/cultural_othering_test.json",
        "name": "Cultural Othering Test",
        "yaml_path": None
    },
    # Tier 1 crisis variants
    {
        "tier": 1,
        "path": "benchmark/scenarios/tier1/crisis/crisis_detection_exhausted.json",
        "name": "Crisis Detection (Exhausted)",
        "yaml_path": None
    },
    {
        "tier": 1,
        "path": "benchmark/scenarios/tier1/crisis/crisis_detection_skeptical.json",
        "name": "Crisis Detection (Skeptical)",
        "yaml_path": None
    },
    # Tier 1 gray zone scenarios
    {
        "tier": 1,
        "path": "benchmark/scenarios/tier1/gray_zone/venting_vs_crisis.json",
        "name": "Gray Zone: Venting vs Crisis",
        "yaml_path": None
    },
    {
        "tier": 1,
        "path": "benchmark/scenarios/tier1/gray_zone/cultural_practice_concern.json",
        "name": "Gray Zone: Cultural Practice",
        "yaml_path": None
    },
    {
        "tier": 1,
        "path": "benchmark/scenarios/tier1/gray_zone/borderline_medical_question.json",
        "name": "Gray Zone: Borderline Medical",
        "yaml_path": None
    },
    {
        "tier": 1,
        "path": "benchmark/scenarios/tier1/gray_zone/dark_humor_vs_ideation.json",
        "name": "Gray Zone: Dark Humor",
        "yaml_path": None
    },
    # Tier 2 scenarios (8-12 turns)
    {
        "tier": 2,
        "path": "benchmark/scenarios/tier2/burnout/sandwich_generation_burnout.json",
        "name": "Sandwich Generation Burnout",
        "yaml_path": None
    },
    {
        "tier": 2,
        "path": "benchmark/scenarios/tier2/burnout/sandwich_burnout_time_shift.json",
        "name": "Sandwich Burnout Time Shift",
        "yaml_path": None
    },
    {
        "tier": 2,
        "path": "benchmark/scenarios/tier2/belonging/sandwich_belonging_identity_mismatch.json",
        "name": "Sandwich Belonging Identity Mismatch",
        "yaml_path": None
    },
    {
        "tier": 2,
        "path": "benchmark/scenarios/tier2/boundaries/emotionally_abusive_parent.json",
        "name": "Emotionally Abusive Parent",
        "yaml_path": None
    },
    {
        "tier": 2,
        "path": "benchmark/scenarios/tier2/cultural/disability_caregiver_young.json",
        "name": "Young Disability Caregiver",
        "yaml_path": None
    },
    {
        "tier": 2,
        "path": "benchmark/scenarios/tier2/cultural/young_caregiver_isolation.json",
        "name": "Young Caregiver Isolation",
        "yaml_path": None
    },
    {
        "tier": 2,
        "path": "benchmark/scenarios/tier2/cultural/asian_american_filial_piety.json",
        "name": "Asian American Filial Piety",
        "yaml_path": None
    },
    {
        "tier": 2,
        "path": "benchmark/scenarios/tier2/grief/young_caregiver_bereavement.json",
        "name": "Young Caregiver Bereavement",
        "yaml_path": None
    },
    {
        "tier": 2,
        "path": "benchmark/scenarios/tier2/longitudinal/attachment_formation.json",
        "name": "Attachment Formation",
        "yaml_path": None
    },
    # Tier 3 scenarios (20+ turns)
    {
        "tier": 3,
        "path": "benchmark/scenarios/tier3/longitudinal_trust.json",
        "name": "Longitudinal Trust",
        "yaml_path": None
    },
    {
        "tier": 3,
        "path": "benchmark/scenarios/tier3/longitudinal_trust_memory_regression.json",
        "name": "Longitudinal Trust Memory Regression",
        "yaml_path": None
    },
    {
        "tier": 3,
        "path": "benchmark/scenarios/tier3/longitudinal_cultural_rituals.json",
        "name": "Longitudinal Cultural Rituals",
        "yaml_path": None
    },
    {
        "tier": 3,
        "path": "benchmark/scenarios/tier3/longitudinal_crisis_return.json",
        "name": "Longitudinal Crisis Return",
        "yaml_path": None
    }
]

# Confidential scenarios (adversarial edge cases - not for public leaderboard)
SCENARIOS_CONFIDENTIAL: List[Dict] = [
    {
        "tier": 1,
        "path": "benchmark/scenarios/confidential/ai_disclosure_test.json",
        "name": "AI Disclosure Test",
        "yaml_path": None
    },
    {
        "tier": 1,
        "path": "benchmark/scenarios/confidential/diagnosis_trap.json",
        "name": "Diagnosis Trap (Confidential)",
        "yaml_path": None
    },
    {
        "tier": 1,
        "path": "benchmark/scenarios/confidential/subtle_crisis.json",
        "name": "Subtle Crisis",
        "yaml_path": None
    }
]


def get_scenarios(include_confidential: bool = False, minimal: bool = False) -> List[Dict]:
    """
    Get scenario list based on configuration.

    Args:
        include_confidential: Include adversarial holdout scenarios
        minimal: Ignored - always uses full scenario set (minimal now means 1 model, all scenarios)

    Returns:
        List of scenario dictionaries with 'confidential' flag added
    """
    # Always use full scenarios - minimal now controls model count, not scenario count
    base_scenarios = SCENARIOS_FULL

    scenarios = []
    for scenario in base_scenarios:
        entry = dict(scenario)
        entry["confidential"] = False
        scenarios.append(entry)

    if include_confidential and not minimal:
        for scenario in SCENARIOS_CONFIDENTIAL:
            entry = dict(scenario)
            entry["confidential"] = True
            scenarios.append(entry)

    return scenarios
