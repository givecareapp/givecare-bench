"""Scenario loading and validation."""

import json
from pathlib import Path
from typing import Any, Dict, List

from invisiblebench.models import Scenario, ScenarioCategory, ScoringDimension
from invisiblebench.utils.turn_index import get_turn_index, normalize_turn_indices


class ScenarioValidator:


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

            if (
                "expected_behaviors" not in turn
                and "rubric" not in turn
                and "rubric_criteria" not in turn
            ):
                errors.append(f"{label}[{idx}] must include expected_behaviors, rubric, or rubric_criteria")

            if "expected_behaviors" in turn and not isinstance(
                turn.get("expected_behaviors"), list
            ):
                errors.append(f"{label}[{idx}].expected_behaviors must be a list")

            if "rubric" in turn and not isinstance(turn.get("rubric"), list):
                errors.append(f"{label}[{idx}].rubric must be a list")

            if "autofail_rubric" in turn and not isinstance(turn.get("autofail_rubric"), list):
                errors.append(f"{label}[{idx}].autofail_rubric must be a list")

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

        if "tier" in data:
            errors.append(
                "Legacy 'tier' field is no longer accepted; use 'category' instead"
            )

        required_fields = ["scenario_id", "title", "persona", "scoring_dimensions", "category"]
        for field in required_fields:
            if field not in data:
                errors.append(f"Missing required field: {field}")

        valid_categories = {category.value for category in ScenarioCategory}
        cat_val = data.get("category", "")
        if cat_val and cat_val not in valid_categories:
            errors.append(f"Invalid category: {cat_val}")

        if "persona" in data:
            persona_required = ["name", "age", "care_recipient", "care_duration", "context"]
            for field in persona_required:
                if field not in data["persona"]:
                    errors.append(f"Missing persona field: {field}")

        if cat_val == "continuity":
            if "sessions" not in data or len(data["sessions"]) == 0:
                if "turns" not in data or len(data["turns"]) == 0:
                    errors.append("Continuity scenarios must have sessions or turns")
        elif cat_val:
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

        if "scoring_dimensions" in data:
            for dim_str, max_score in data["scoring_dimensions"].items():
                try:
                    ScoringDimension(dim_str)
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


    def __init__(self, scenario_dir: str = "./scenarios"):

        self.scenario_dir = Path(scenario_dir)
        self.validator = ScenarioValidator()

    def load_all(self) -> List[Scenario]:

        scenarios = []

        if not self.scenario_dir.exists():
            raise FileNotFoundError(f"Scenario directory not found: {self.scenario_dir}")

        for json_file in sorted(self.scenario_dir.rglob("*.json")):
            scenario = self.load_scenario(json_file)
            scenarios.append(scenario)

        return scenarios

    def load_scenario(self, file_path: Path) -> Scenario:

        with open(file_path, "r") as f:
            data = json.load(f)

        normalize_turn_indices(data)

        errors = self.validator.validate_scenario(data)
        if errors:
            raise ValueError(f"Scenario validation errors in {file_path}:\n" + "\n".join(errors))

        scenario = Scenario.from_dict(data)
        return scenario
