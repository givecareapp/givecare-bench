"""Data loaders for scenarios and configurations."""

from .scenario_loader import ScenarioLoader
from .yaml_loader import RuleLoader, ScenarioLoader as YamlScenarioLoader, TranscriptLoader, ScoringConfigLoader

# Backwards-compatible exports
loaders = {
    "ScenarioLoader": ScenarioLoader,
    "RuleLoader": RuleLoader,
    "YamlScenarioLoader": YamlScenarioLoader,
    "TranscriptLoader": TranscriptLoader,
    "ScoringConfigLoader": ScoringConfigLoader,
}

__all__ = [
    "ScenarioLoader",
    "RuleLoader",
    "YamlScenarioLoader",
    "TranscriptLoader",
    "ScoringConfigLoader",
]
