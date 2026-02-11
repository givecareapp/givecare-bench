"""
Utilities for loading and validating scenarios.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from invisiblebench.models import DimensionType, Scenario, TierLevel
from invisiblebench.utils.turn_index import get_turn_index, normalize_turn_indices


class ScenarioValidator:
    """Validate scenario JSON structure and content."""

    @staticmethod
    def _validate_probe_list(probes: Any, errors: List[str], label: str) -> None:
        if not isinstance(probes, list):
            errors.append(f"{label} must be a list")
            return

        for idx, probe in enumerate(probes):
            if not isinstance(probe, dict):
                errors.append(f"{label}[{idx}] must be an object")
                continue

            if get_turn_index(probe) is None:
                errors.append(f"{label}[{idx}] missing turn index (t/turn_number/turn)")

            kind = probe.get("kind")
            if not isinstance(kind, str) or not kind:
                errors.append(f"{label}[{idx}] missing kind")

            expected = probe.get("expected")
            if expected is None:
                errors.append(f"{label}[{idx}] missing expected list")
            elif not isinstance(expected, list):
                errors.append(f"{label}[{idx}].expected must be a list")

            from_sessions = probe.get("from_sessions")
            if from_sessions is not None and not isinstance(from_sessions, list):
                errors.append(f"{label}[{idx}].from_sessions must be a list")

    @staticmethod
    def _validate_risk_triggers(triggers: Any, errors: List[str], label: str) -> None:
        if not isinstance(triggers, list):
            errors.append(f"{label} must be a list")
            return

        for idx, trigger in enumerate(triggers):
            if not isinstance(trigger, dict):
                errors.append(f"{label}[{idx}] must be an object")
                continue

            if get_turn_index(trigger) is None:
                errors.append(f"{label}[{idx}] missing turn index (t/turn_number/turn)")

            cue = trigger.get("cue")
            if not isinstance(cue, str) or not cue:
                errors.append(f"{label}[{idx}] missing cue")

            severity = trigger.get("severity")
            if not isinstance(severity, str) or not severity:
                errors.append(f"{label}[{idx}] missing severity")

    @staticmethod
    def _validate_turn_list(turns: Any, errors: List[str], label: str) -> None:
        if not isinstance(turns, list):
            errors.append(f"{label} must be a list")
            return

        for idx, turn in enumerate(turns):
            if not isinstance(turn, dict):
                errors.append(f"{label}[{idx}] must be an object")
                continue

            if get_turn_index(turn) is None:
                errors.append(f"{label}[{idx}] missing turn index (t/turn_number/turn)")

            if "user_message" not in turn:
                errors.append(f"{label}[{idx}] missing user_message")

            if "autofail_triggers" not in turn:
                errors.append(f"{label}[{idx}] missing autofail_triggers")
            elif not isinstance(turn.get("autofail_triggers"), list):
                errors.append(f"{label}[{idx}].autofail_triggers must be a list")

            if "expected_behaviors" not in turn and "rubric_criteria" not in turn:
                errors.append(f"{label}[{idx}] must include expected_behaviors or rubric_criteria")

            if "expected_behaviors" in turn and not isinstance(
                turn.get("expected_behaviors"), list
            ):
                errors.append(f"{label}[{idx}].expected_behaviors must be a list")

            if "rubric_criteria" in turn and not isinstance(turn.get("rubric_criteria"), list):
                errors.append(f"{label}[{idx}].rubric_criteria must be a list")

            if "facts" in turn and not isinstance(turn.get("facts"), list):
                errors.append(f"{label}[{idx}].facts must be a list")

            if "updates" in turn and not isinstance(turn.get("updates"), list):
                errors.append(f"{label}[{idx}].updates must be a list")

            if "probes" in turn:
                ScenarioValidator._validate_probe_list(
                    turn.get("probes"), errors, f"{label}[{idx}].probes"
                )

    @staticmethod
    def validate_scenario(data: Dict[str, Any]) -> List[str]:
        """
        Validate scenario data structure.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Required fields (tier is accepted as legacy, category is preferred)
        required_fields = ["scenario_id", "title", "persona", "scoring_dimensions"]
        for field in required_fields:
            if field not in data:
                errors.append(f"Missing required field: {field}")

        # Must have either tier or category
        if "tier" not in data and "category" not in data:
            errors.append("Missing required field: tier or category")

        # Validate category values (accept both old tier_N and new category names)
        VALID_VALUES = {"safety", "empathy", "context", "continuity", "confidential",
                       "tier_0", "tier_1", "tier_2", "tier_3"}
        tier_val = data.get("tier", "")
        cat_val = data.get("category", "")
        if tier_val and tier_val not in VALID_VALUES:
            errors.append(f"Invalid tier: {tier_val}")
        if cat_val and cat_val not in VALID_VALUES:
            errors.append(f"Invalid category: {cat_val}")

        # Validate persona structure
        if "persona" in data:
            persona_required = ["name", "age", "care_recipient", "care_duration", "context"]
            for field in persona_required:
                if field not in data["persona"]:
                    errors.append(f"Missing persona field: {field}")

        # Validate turns or sessions
        tier_or_cat = data.get("tier", data.get("category", ""))
        if tier_or_cat == "continuity" or tier_or_cat == "tier_3":
            if "sessions" not in data or len(data["sessions"]) == 0:
                # Multi-session scenarios may also use turns
                if "turns" not in data or len(data["turns"]) == 0:
                    errors.append("Continuity scenarios must have sessions or turns")
        elif tier_or_cat:
            if "turns" not in data or len(data["turns"]) == 0:
                if "sessions" not in data or len(data["sessions"]) == 0:
                    errors.append("Scenarios must have turns or sessions")

        if "turns" in data:
            ScenarioValidator._validate_turn_list(data.get("turns"), errors, "turns")

        if "sessions" in data:
            sessions = data.get("sessions")
            if not isinstance(sessions, list):
                errors.append("sessions must be a list")
            else:
                for idx, session in enumerate(sessions):
                    if not isinstance(session, dict):
                        errors.append(f"sessions[{idx}] must be an object")
                        continue
                    if "session_number" not in session:
                        errors.append(f"sessions[{idx}] missing session_number")
                    if "time_elapsed" not in session:
                        errors.append(f"sessions[{idx}] missing time_elapsed")
                    ScenarioValidator._validate_turn_list(
                        session.get("turns"), errors, f"sessions[{idx}].turns"
                    )

        # Validate scoring dimensions
        if "scoring_dimensions" in data:
            for dim_str, max_score in data["scoring_dimensions"].items():
                try:
                    DimensionType(dim_str)
                except ValueError:
                    errors.append(f"Invalid dimension: {dim_str}")
                if not isinstance(max_score, int):
                    errors.append(f"Dimension {dim_str} score must be an integer")

        if "probes" in data:
            ScenarioValidator._validate_probe_list(data.get("probes"), errors, "probes")

        if "risk_triggers" in data:
            ScenarioValidator._validate_risk_triggers(
                data.get("risk_triggers"), errors, "risk_triggers"
            )

        if "metadata" in data and not isinstance(data.get("metadata"), dict):
            errors.append("metadata must be an object")

        if "dif_variables" in data and not isinstance(data.get("dif_variables"), list):
            errors.append("dif_variables must be a list")

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
        with open(file_path, "r") as f:
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


def create_example_scenario(tier: TierLevel = TierLevel.SAFETY) -> Dict[str, Any]:
    """
    Generate example scenario template for given category.

    Useful for creating new scenarios.
    """
    if tier == TierLevel.SAFETY:
        return {
            "scenario_id": "safety_example_001",
            "tier": "safety",
            "category": "safety",
            "title": "Example Safety Scenario",
            "persona": {
                "name": "Example User",
                "age": 45,
                "role": "Adult child caregiver",
                "care_recipient": "Elderly parent",
                "care_duration": "1 year",
                "context": {
                    "living_situation": "Parent lives with user",
                    "employment": "Full-time employed",
                    "support_system": "Limited family support",
                },
            },
            "turns": [
                {
                    "turn_number": 1,
                    "user_message": "Example user message",
                    "expected_behaviors": ["Expected behavior 1", "Expected behavior 2"],
                    "autofail_triggers": ["Autofail condition 1"],
                }
            ],
            "scoring_dimensions": {
                "crisis_safety": 3,
                "regulatory_fitness": 3,
                "trauma_informed_flow": 3,
                "belonging_cultural_fitness": 2,
                "relational_quality": 3,
                "actionable_support": 3,
            },
            "dif_variables": ["income", "race"],
        }
    elif tier == TierLevel.CONTINUITY:
        return {
            "scenario_id": "continuity_example_001",
            "tier": "continuity",
            "category": "continuity",
            "title": "Example Continuity Multi-Session Scenario",
            "persona": {
                "name": "Example User",
                "age": 45,
                "role": "Adult child caregiver",
                "care_recipient": "Elderly parent",
                "care_duration": "2 years",
                "context": {
                    "living_situation": "Parent lives with user",
                    "employment": "Full-time employed",
                },
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
                            "autofail_triggers": [],
                        }
                    ],
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
                            "autofail_triggers": [],
                        }
                    ],
                },
            ],
            "scoring_dimensions": {
                "crisis_safety": 3,
                "regulatory_fitness": 3,
                "trauma_informed_flow": 3,
                "belonging_cultural_fitness": 2,
                "relational_quality": 3,
                "actionable_support": 3,
                "longitudinal_consistency": 2,
                "memory_hygiene": 1,
            },
            "dif_variables": ["income", "race"],
        }

    return {}
