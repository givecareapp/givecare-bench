"""
Data loaders for LongitudinalBench.

Loads rules (with inheritance), scenarios, transcripts, and scoring configuration.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import yaml


class RuleLoader:
    """Loads rule YAML files with inheritance resolution."""

    def __init__(self):
        self._loading_stack: List[str] = []

    def load(self, path: str) -> Dict[str, Any]:
        """
        Load a rule file and resolve inheritance.

        Args:
            path: Path to the rule YAML file

        Returns:
            Dictionary with resolved rules

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If circular inheritance is detected
        """
        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Rule file not found: {path}")

        # Check for circular inheritance
        abs_path = str(path_obj.resolve())
        if abs_path in self._loading_stack:
            raise ValueError(f"Circular inheritance detected: {abs_path} -> {' -> '.join(self._loading_stack)}")

        self._loading_stack.append(abs_path)

        try:
            with open(path_obj) as f:
                rules = yaml.safe_load(f)

            if rules is None:
                rules = {}

            # Handle inheritance
            if "extends" in rules:
                parent_file = rules.pop("extends")
                # Resolve parent path relative to current file
                parent_path = path_obj.parent / parent_file

                # Load parent rules recursively
                parent_rules = self.load(str(parent_path))

                # Deep merge: parent rules + current rules
                merged = self._deep_merge(parent_rules, rules)
                return merged

            return rules
        finally:
            self._loading_stack.pop()

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge two dictionaries.

        Args:
            base: Base dictionary
            override: Dictionary with overrides

        Returns:
            Merged dictionary
        """
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # Recursively merge nested dicts
                result[key] = self._deep_merge(result[key], value)
            else:
                # Override value
                result[key] = value

        return result


class ScenarioLoader:
    """Loads scenario YAML files."""

    def load(self, path: str) -> Dict[str, Any]:
        """
        Load a scenario file.

        Args:
            path: Path to the scenario YAML file

        Returns:
            Dictionary with scenario data

        Raises:
            FileNotFoundError: If the file doesn't exist
        """
        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Scenario file not found: {path}")

        with open(path_obj) as f:
            scenario = yaml.safe_load(f)

        return scenario if scenario else {}


class TranscriptLoader:
    """Loads JSONL transcript files."""

    def load(self, path: str) -> List[Dict[str, Any]]:
        """
        Load a transcript JSONL file.

        Args:
            path: Path to the transcript JSONL file

        Returns:
            List of message dictionaries

        Raises:
            FileNotFoundError: If the file doesn't exist
            json.JSONDecodeError: If JSONL is malformed
        """
        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Transcript file not found: {path}")

        messages = []
        with open(path_obj) as f:
            for line in f:
                line = line.strip()
                if line:  # Skip empty lines
                    messages.append(json.loads(line))

        return messages


class ScoringConfigLoader:
    """Loads scoring configuration YAML files."""

    def load(self, path: str) -> Dict[str, Any]:
        """
        Load a scoring configuration file.

        Args:
            path: Path to the scoring YAML file

        Returns:
            Dictionary with scoring configuration

        Raises:
            FileNotFoundError: If the file doesn't exist
        """
        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Scoring config file not found: {path}")

        with open(path_obj) as f:
            config = yaml.safe_load(f)

        return config if config else {}
