"""
Utilities for loading and validating scenarios.
"""
import json
from pathlib import Path
from typing import List, Dict, Any
from invisiblebench.models import Scenario, TierLevel, DimensionType
from invisiblebench.utils.turn_index import normalize_turn_indices


class ScenarioValidator:
    """Validate scenario JSON structure and content."""

    @staticmethod
    def validate_scenario(data: Dict[str, Any]) -> List[str]:
        """
        Validate scenario data structure.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Required fields
        required_fields = ["scenario_id", "tier", "title", "persona", "scoring_dimensions"]
        for field in required_fields:
            if field not in data:
                errors.append(f"Missing required field: {field}")

        # Validate tier
        if "tier" in data:
            try:
                TierLevel(data["tier"])
            except ValueError:
                errors.append(f"Invalid tier: {data['tier']}")

        # Validate persona structure
        if "persona" in data:
            persona_required = ["name", "age", "role", "care_recipient", "care_duration", "context"]
            for field in persona_required:
                if field not in data["persona"]:
                    errors.append(f"Missing persona field: {field}")

        # Validate turns or sessions
        if "tier" in data:
            tier = TierLevel(data["tier"])
            if tier == TierLevel.TIER_3:
                if "sessions" not in data or len(data["sessions"]) == 0:
                    errors.append("Tier 3 scenarios must have sessions")
            else:
                if "turns" not in data or len(data["turns"]) == 0:
                    errors.append("Tier 1/2 scenarios must have turns")

        # Validate scoring dimensions
        if "scoring_dimensions" in data:
            for dim_str in data["scoring_dimensions"].keys():
                try:
                    DimensionType(dim_str)
                except ValueError:
                    errors.append(f"Invalid dimension: {dim_str}")

        return errors


class ScenarioLoader:
    """Load and manage scenarios."""

    def __init__(self, scenario_dir: str = "./scenarios"):
        """Initialize with scenario directory."""
        self.scenario_dir = Path(scenario_dir)
        self.validator = ScenarioValidator()

    def load_all(self) -> List[Scenario]:
        """Load all scenarios from directory."""
        scenarios = []

        if not self.scenario_dir.exists():
            raise FileNotFoundError(f"Scenario directory not found: {self.scenario_dir}")

        for json_file in sorted(self.scenario_dir.rglob("*.json")):
            try:
                scenario = self.load_scenario(json_file)
                scenarios.append(scenario)
            except Exception as e:
                print(f"Error loading {json_file}: {e}")

        return scenarios

    def load_scenario(self, file_path: Path) -> Scenario:
        """Load single scenario from file."""
        with open(file_path, 'r') as f:
            data = json.load(f)

        normalize_turn_indices(data)

        # Validate
        errors = self.validator.validate_scenario(data)
        if errors:
            raise ValueError(f"Scenario validation errors in {file_path}:\n" + "\n".join(errors))

        # Parse
        scenario = Scenario.from_dict(data)
        return scenario

    def load_by_tier(self, tier: TierLevel) -> List[Scenario]:
        """Load scenarios filtered by tier."""
        all_scenarios = self.load_all()
        return [s for s in all_scenarios if s.tier == tier]

    def load_by_id(self, scenario_id: str) -> Scenario:
        """Load specific scenario by ID."""
        all_scenarios = self.load_all()
        scenario = next((s for s in all_scenarios if s.scenario_id == scenario_id), None)

        if not scenario:
            raise ValueError(f"Scenario not found: {scenario_id}")

        return scenario


def create_example_scenario(tier: TierLevel = TierLevel.TIER_1) -> Dict[str, Any]:
    """
    Generate example scenario template for given tier.

    Useful for creating new scenarios.
    """
    if tier == TierLevel.TIER_1:
        return {
            "scenario_id": "tier1_example_001",
            "tier": "tier_1",
            "title": "Example Tier 1 Scenario",
            "persona": {
                "name": "Example User",
                "age": 45,
                "role": "Adult child caregiver",
                "care_recipient": "Elderly parent",
                "care_duration": "1 year",
                "context": {
                    "living_situation": "Parent lives with user",
                    "employment": "Full-time employed",
                    "support_system": "Limited family support"
                }
            },
            "turns": [
                {
                    "turn_number": 1,
                    "user_message": "Example user message",
                    "expected_behaviors": [
                        "Expected behavior 1",
                        "Expected behavior 2"
                    ],
                    "autofail_triggers": [
                        "Autofail condition 1"
                    ]
                }
            ],
            "scoring_dimensions": {
                "crisis_safety": 3,
                "regulatory_fitness": 3,
                "trauma_informed_flow": 3,
                "belonging_cultural_fitness": 2,
                "relational_quality": 3,
                "actionable_support": 3
            },
            "dif_variables": ["income", "race"]
        }
    elif tier == TierLevel.TIER_3:
        return {
            "scenario_id": "tier3_example_001",
            "tier": "tier_3",
            "title": "Example Tier 3 Multi-Session Scenario",
            "persona": {
                "name": "Example User",
                "age": 45,
                "role": "Adult child caregiver",
                "care_recipient": "Elderly parent",
                "care_duration": "2 years",
                "context": {
                    "living_situation": "Parent lives with user",
                    "employment": "Full-time employed"
                }
            },
            "sessions": [
                {
                    "session_number": 1,
                    "time_elapsed": "Day 0",
                    "session_context": "Initial interaction",
                    "turns": [
                        {
                            "turn_number": 1,
                            "user_message": "Example message",
                            "expected_behaviors": ["Expected behavior"],
                            "autofail_triggers": []
                        }
                    ]
                },
                {
                    "session_number": 2,
                    "time_elapsed": "3 months later",
                    "session_context": "Follow-up after time gap",
                    "turns": [
                        {
                            "turn_number": 2,
                            "user_message": "Example follow-up message",
                            "expected_behaviors": ["Remember prior conversation"],
                            "autofail_triggers": []
                        }
                    ]
                }
            ],
            "scoring_dimensions": {
                "crisis_safety": 3,
                "regulatory_fitness": 3,
                "trauma_informed_flow": 3,
                "belonging_cultural_fitness": 2,
                "relational_quality": 3,
                "actionable_support": 3,
                "longitudinal_consistency": 2,
                "memory_hygiene": 1
            },
            "dif_variables": ["income", "race"]
        }

    return {}
