"""Apply the same LLM judge to every active criterion."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from invisiblebench.api.client import DEFAULT_JUDGE_MODEL
from invisiblebench.evaluation.check_registry import load_checks
from invisiblebench.evaluation.verifiers.llm_verifier import LLMVerifier
from invisiblebench.models._types import ScenarioData, Transcript
from invisiblebench.version import ENGINE_VERSION

if TYPE_CHECKING:
    from invisiblebench.api.client import ModelAPIClient


@dataclass
class ModeEngineOutput:
    mode_results: list[dict[str, Any]] = field(default_factory=list)
    engine_version: str = ENGINE_VERSION

    def to_dict(self) -> dict[str, Any]:
        eligible = [r for r in self.mode_results if r["eligible"]]
        resolved = sum(r["verdict"] in {"PASS", "FAIL"} for r in eligible)
        return {
            "mode_results": self.mode_results, "engine_version": self.engine_version,
            "eligible_count": len(eligible), "resolved_count": resolved,
            "unclear_count": sum(r["verdict"] == "UNCLEAR" for r in eligible),
            "coverage_rate": resolved / len(eligible) if eligible else 0.0,
        }


class ModeEngine:
    def __init__(
        self, checks_dir: Path | None = None, llm_api_client: ModelAPIClient | None = None,
        llm_model: str = DEFAULT_JUDGE_MODEL,
    ):
        self.modes = load_checks(checks_dir)
        self.llm_verifier = LLMVerifier(llm_api_client, llm_model) if llm_api_client else None

    def evaluate(self, transcript: Transcript, scenario: ScenarioData) -> ModeEngineOutput:
        if self.llm_verifier is None:
            raise ValueError("A judge client is required to evaluate a transcript; use a dry-run to plan.")
        if not transcript or not any(t.get("role") == "assistant" for t in transcript):
            raise ValueError("A complete transcript with an assistant response is required.")
        return ModeEngineOutput(mode_results=[
            self.llm_verifier.verify(transcript, scenario, check).to_dict()
            for check in self.modes.values()
        ])
