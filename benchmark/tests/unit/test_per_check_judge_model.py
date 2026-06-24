"""Per-check judge_model routing: scope gates calibrate to a stronger judge
while crisis gates and the rest stay on the global default. Pins the mechanism
behind the frozen gate->(judge) config."""

from invisiblebench.evaluation.mode_engine import ModeEngine


class _StubClient:
    def call_model(self, *args, **kwargs):  # pragma: no cover - never called here
        return "{}"


def _engine() -> ModeEngine:
    return ModeEngine(
        llm_api_client=_StubClient(),
        llm_model="google/gemini-2.5-flash-lite",
    )


def test_scope_gates_use_overridden_judge_model():
    eng = _engine()
    for mode_id in ("IB-B1", "IB-B2"):
        verifier = eng._route_verifier(mode_id)
        assert verifier is not None
        assert verifier.model == "openai/gpt-5.5"


def test_crisis_gates_use_default_judge_model():
    eng = _engine()
    for mode_id in ("IB-A1", "IB-A8"):
        verifier = eng._route_verifier(mode_id)
        assert verifier is not None
        assert verifier.model == "google/gemini-2.5-flash-lite"


def test_one_verifier_cached_per_distinct_model():
    eng = _engine()
    eng._route_verifier("IB-B1")
    eng._route_verifier("IB-B2")
    eng._route_verifier("IB-A1")
    # Default judge lives on self.llm_verifier; only non-default judges are
    # cached, and the same non-default model reuses one instance.
    assert set(eng._llm_verifiers) == {"openai/gpt-5.5"}
    assert eng._route_verifier("IB-B1") is eng._route_verifier("IB-B2")
    assert eng._route_verifier("IB-A1") is eng.llm_verifier


def test_no_api_client_returns_none_for_llm_routes():
    eng = ModeEngine(llm_api_client=None)
    assert eng._route_verifier("IB-B1") is None
