"""Data loaders for InvisibleBench."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from invisiblebench.loaders.scenario_loader import ScenarioValidator
from invisiblebench.utils.turn_index import normalize_turn_indices


class RuleLoader:


    def __init__(self):
        self._loading_stack: list[str] = []

    def load(self, path: str) -> dict[str, Any]:
        """Load a rule file, resolving any `extends` inheritance chain."""
        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Rule file not found: {path}")

        abs_path = str(path_obj.resolve())
        if abs_path in self._loading_stack:
            raise ValueError(
                f"Circular inheritance detected: {abs_path} -> {' -> '.join(self._loading_stack)}"
            )

        self._loading_stack.append(abs_path)

        try:
            with open(path_obj) as f:
                rules = yaml.safe_load(f)

            if rules is None:
                rules = {}

            if "extends" in rules:
                parent_file = rules.pop("extends")
                parent_path = path_obj.parent / parent_file

                parent_rules = self.load(str(parent_path))

                merged = self._deep_merge(parent_rules, rules)
                return merged

            return rules
        finally:
            self._loading_stack.pop()

    def _deep_merge(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """Deep merge two dictionaries; override wins on conflicts."""
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result


class ScenarioLoader:


    def __init__(self, validate: bool = True) -> None:
        self.validator = ScenarioValidator()
        self.validate = validate

    def load(self, path: str) -> dict[str, Any]:
        """Load and validate a scenario YAML file."""
        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Scenario file not found: {path}")

        with open(path_obj) as f:
            scenario = yaml.safe_load(f)

        scenario = scenario if scenario else {}
        normalize_turn_indices(scenario)

        if self.validate:
            errors = self.validator.validate_scenario(scenario)
            if errors:
                error_text = "\n".join(errors)
                raise ValueError(f"Scenario validation errors in {path}:\n{error_text}")

        return scenario


class TranscriptLoader:


    def load(self, path: str) -> list[dict[str, Any]]:
        """Load a transcript JSONL file into a list of message dicts."""
        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Transcript file not found: {path}")

        messages = []
        with open(path_obj) as f:
            for line in f:
                line = line.strip()
                if line:
                    messages.append(json.loads(line))

        return messages


class ScoringConfigLoader:


    def load(self, path: str) -> dict[str, Any]:
        """Load a scoring configuration YAML file."""
        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Scoring config file not found: {path}")

        with open(path_obj) as f:
            config = yaml.safe_load(f)

        return config if config else {}
