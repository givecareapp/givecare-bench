"""Judge routing: all checks use the single global default judge. Per-check
`judge_model` overrides were removed when every judge was unified on GPT-5 Mini.
Pins that no check carries a private judge and all route to the one default
verifier (the routing mechanism still works, it just has nothing to override)."""

from invisiblebench.evaluation.mode_engine import ModeEngine


class _StubClient:
    def call_model(self, *args, **kwargs):  # pragma: no cover - never called here
        return "{}"


def _engine() -> ModeEngine:
    return ModeEngine(
        llm_api_client=_StubClient(),
        llm_model="google/gemini-2.5-flash-lite",
    )


def test_scope_gates_use_default_judge_model():
    # Per-check overrides removed: B1/B2 now route to the single default judge.
    eng = _engine()
    for mode_id in ("IB-B1", "IB-B2"):
        verifier = eng._route_verifier(mode_id)
        assert verifier is not None
        assert verifier is eng.llm_verifier


def test_crisis_gates_use_default_judge_model():
    eng = _engine()
    for mode_id in ("IB-A1", "IB-A8"):
        verifier = eng._route_verifier(mode_id)
        assert verifier is not None
        assert verifier.model == "google/gemini-2.5-flash-lite"


def test_all_checks_share_the_single_default_judge():
    eng = _engine()
    # Every LLM-routed check resolves to the one default verifier...
    for mode_id in ("IB-B1", "IB-B2", "IB-A1", "IB-A8"):
        assert eng._route_verifier(mode_id) is eng.llm_verifier
    # ...and no per-check override judges are cached anymore.
    assert eng._llm_verifiers == {}


def test_no_api_client_returns_none_for_llm_routes():
    eng = ModeEngine(llm_api_client=None)
    assert eng._route_verifier("IB-B1") is None
