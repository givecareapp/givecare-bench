"""Data loaders for scenarios and configurations."""

from .scenario_loader import ScenarioLoader
from .yaml_loader import RuleLoader, ScoringConfigLoader, TranscriptLoader
from .yaml_loader import ScenarioLoader as YamlScenarioLoader

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
