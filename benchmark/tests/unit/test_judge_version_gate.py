"""The version gate re-asks a frozen scan and never touches its bundle."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import scripts.judge_version_gate as judge_version_gate_mod
from benchmark.tests.fixtures.current_scan import FixtureJudge, write_source_run
from invisiblebench.api.typesafe import DEFAULT_JUDGE_MODEL
from invisiblebench.judge import (
    ANSWERS_FILE,
    LEDGER_FILE,
    PLAN_FILE,
    load_scan,
    plan_scan,
    run_scan,
)
from invisiblebench.utils.io import load_jsonl
from scripts.judge_version_gate import gate, main

BUDGET = 1.0


@pytest.fixture(autouse=True)
def _priced_candidates(monkeypatch):
    """Register a price for the candidate model IDs this test file invents.

    `JUDGE_PRICING` only ever carries the currently pinned judge model; a
    version-gate candidate is by definition a different, newly priced model.
    """
    from invisiblebench.api import typesafe

    monkeypatch.setitem(typesafe.JUDGE_PRICING, "candidate-jev", 0.05)
    monkeypatch.setitem(typesafe.JUDGE_PRICING, "cli-candidate", 0.05)


def source_run(root: Path) -> Path:
    return write_source_run(root, roster=[("fixture-case", "context")])


class TurnJudge(FixtureJudge):
    """Confident, constant answers except `routing` at the second reply."""

    def __init__(self, turn2_routing: float):
        self.turn2_routing = turn2_routing

    def ask(self, *, model: str, state: Any, questions: dict[str, Any]) -> dict[str, Any]:
        second_reply = bool(state.get("earlier_assistant"))
        values = {
            "cue": 0.9,
            "routing": self.turn2_routing if second_reply else 0.9,
            "claim": 0.0,
            "acknowledges": 0.9,
        }
        return {
            "model": model,
            "nouls": {key: values[key.split("/")[-1]] for key in questions},
            "input_tokens": 100,
        }


class ModelRoutingJudge(FixtureJudge):
    """Constant answers except `routing`/`claim` at the second reply, chosen by model id.

    Lets a single client instance answer differently depending on whether
    it is being asked as the frozen model (the `--baseline` re-ask) or the
    candidate, so a test can control each re-ask's drift independently.
    """

    def __init__(
        self,
        routing_by_model: dict[str, float],
        claim_by_model: dict[str, float] | None = None,
    ):
        self.routing_by_model = routing_by_model
        self.claim_by_model = claim_by_model or {}

    def ask(self, *, model: str, state: Any, questions: dict[str, Any]) -> dict[str, Any]:
        second_reply = bool(state.get("earlier_assistant"))
        values = {
            "cue": 0.9,
            "routing": self.routing_by_model.get(model, 0.9) if second_reply else 0.9,
            "claim": self.claim_by_model.get(model, 0.0),
            "acknowledges": 0.9,
        }
        return {
            "model": model,
            "nouls": {key: values[key.split("/")[-1]] for key in questions},
            "input_tokens": 100,
        }


def frozen_bundle(root: Path) -> Path:
    bundle = root / "scan"
    plan_scan([source_run(root)], bundle, judge_model=DEFAULT_JUDGE_MODEL)
    run_scan(bundle, max_cost_usd=BUDGET, client=TurnJudge(turn2_routing=0.9))
    return bundle


def bundle_hashes(bundle: Path) -> dict[str, bytes]:
    return {
        name: (bundle / name).read_bytes()
        for name in (PLAN_FILE, ANSWERS_FILE, LEDGER_FILE)
    }


def test_gate_reports_drift_and_flips_without_touching_the_frozen_bundle(tmp_path):
    bundle = frozen_bundle(tmp_path)
    before = bundle_hashes(bundle)

    report = gate(
        bundle,
        "candidate-jev",
        client=TurnJudge(turn2_routing=0.0),
        max_cost_usd=BUDGET,
    )

    assert bundle_hashes(bundle) == before

    assert report["frozen_model"] == DEFAULT_JUDGE_MODEL
    assert report["candidate_model"] == "candidate-jev"
    assert report["requests"] == load_scan(bundle)[0].planned_requests
    assert report["totals"]["band_flips"] == 1
    assert report["totals"]["max_abs_delta"] == pytest.approx(0.9)
    assert report["questions"]["crisis.fixture-cue/routing"]["band_flips"] == 1
    assert report["questions"]["crisis.fixture-cue/routing"]["n"] == 2
    assert report["questions"]["identity.fixture-prohibition/claim"]["band_flips"] == 0
    assert report["verdict_flips"] == [
        {
            "model_id": "fixture/model",
            "scenario_id": "fixture-case",
            "check_id": "crisis.fixture-cue",
            "frozen": "PASS",
            "candidate": "FAIL",
        }
    ]

    output = bundle / "version-gate" / "candidate-jev"
    written_answers = load_jsonl(output / ANSWERS_FILE)
    assert len(written_answers) == report["requests"]
    assert all(row["plan_sha256"] == report["plan_sha256"] for row in written_answers)
    written_judgments = load_jsonl(output / LEDGER_FILE)
    flipped = [row for row in written_judgments if row["check_id"] == "crisis.fixture-cue"]
    assert flipped[0]["verdict"] == "FAIL"


def test_a_clean_gate_has_no_flips_and_exits_zero(tmp_path):
    bundle = frozen_bundle(tmp_path)
    report = gate(
        bundle,
        DEFAULT_JUDGE_MODEL,
        client=TurnJudge(turn2_routing=0.9),
        max_cost_usd=BUDGET,
        output=tmp_path / "clean-gate",
    )
    assert report["verdict_flips"] == []
    assert report["totals"]["band_flips"] == 0


def test_baseline_reports_drift_beyond_the_frozen_models_own_noise_floor(tmp_path):
    bundle = frozen_bundle(tmp_path)
    frozen_model = DEFAULT_JUDGE_MODEL

    # Both the baseline re-ask (frozen model vs itself) and the candidate
    # flip `crisis.fixture-cue`'s routing question the same way — that flip
    # is noise floor, not candidate drift. Only the candidate also flips
    # `identity.fixture-prohibition`'s claim question, which the baseline
    # never sees.
    client = ModelRoutingJudge(
        routing_by_model={frozen_model: 0.0, "candidate-jev": 0.0},
        claim_by_model={"candidate-jev": 1.0},
    )

    report = gate(bundle, "candidate-jev", client=client, max_cost_usd=BUDGET, baseline=True)

    assert len(report["verdict_flips"]) == 2
    assert report["baseline"]["verdict_flips"] == [
        {
            "model_id": "fixture/model",
            "scenario_id": "fixture-case",
            "check_id": "crisis.fixture-cue",
            "frozen": "PASS",
            "candidate": "FAIL",
        }
    ]
    assert report["baseline"]["band_flips"] == 1
    assert report["beyond_baseline"]["verdict_flips"] == [
        {
            "model_id": "fixture/model",
            "scenario_id": "fixture-case",
            "check_id": "identity.fixture-prohibition",
            "frozen": "PASS",
            "candidate": "FAIL",
        }
    ]
    assert report["beyond_baseline"]["band_flips"] == max(
        report["totals"]["band_flips"] - report["baseline"]["band_flips"], 0
    )

    baseline_output = bundle / "version-gate" / f"baseline-{frozen_model}"
    assert (baseline_output / "report.json").exists()


def test_baseline_with_identical_flips_exits_clean_via_the_cli(tmp_path):
    bundle = frozen_bundle(tmp_path)
    frozen_model = DEFAULT_JUDGE_MODEL

    # The candidate flips exactly what the frozen model flips against
    # itself: no drift beyond the noise floor.
    client = ModelRoutingJudge(routing_by_model={frozen_model: 0.0, "candidate-jev": 0.0})

    report = gate(bundle, "candidate-jev", client=client, max_cost_usd=BUDGET, baseline=True)
    assert report["verdict_flips"] != []
    assert report["beyond_baseline"]["verdict_flips"] == []
    assert report["beyond_baseline"]["band_flips"] == 0


def test_baseline_cli_exit_code_reflects_beyond_baseline_drift(tmp_path, monkeypatch):
    bundle = frozen_bundle(tmp_path)
    frozen_model = DEFAULT_JUDGE_MODEL
    client = ModelRoutingJudge(
        routing_by_model={frozen_model: 0.0, "candidate-jev": 0.0},
        claim_by_model={"candidate-jev": 1.0},
    )
    monkeypatch.setattr(judge_version_gate_mod, "SystemOneClient", lambda: client)

    output = tmp_path / "baseline-report"
    exit_code = main(
        [
            "--frozen",
            str(bundle),
            "--candidate-model",
            "candidate-jev",
            "--baseline",
            "--max-cost-usd",
            str(BUDGET),
            "--output",
            str(output),
        ]
    )
    assert exit_code == 1
    report = json.loads((output / "report.json").read_text())
    assert len(report["beyond_baseline"]["verdict_flips"]) == 1


def test_baseline_cli_exits_clean_when_flips_match_the_noise_floor(tmp_path, monkeypatch):
    bundle = frozen_bundle(tmp_path)
    frozen_model = DEFAULT_JUDGE_MODEL
    client = ModelRoutingJudge(routing_by_model={frozen_model: 0.0, "candidate-jev": 0.0})
    monkeypatch.setattr(judge_version_gate_mod, "SystemOneClient", lambda: client)

    output = tmp_path / "baseline-clean-report"
    exit_code = main(
        [
            "--frozen",
            str(bundle),
            "--candidate-model",
            "candidate-jev",
            "--baseline",
            "--max-cost-usd",
            str(BUDGET),
            "--output",
            str(output),
        ]
    )
    assert exit_code == 0
    report = json.loads((output / "report.json").read_text())
    assert report["verdict_flips"] != []
    assert report["beyond_baseline"]["verdict_flips"] == []


def test_cli_writes_a_report_and_the_exit_code_reflects_verdict_flips(tmp_path):
    # `--client-only-for-tests` always answers every question with a confident
    # no. Against a frozen bundle built the same way, every saved probability
    # matches and the gate is clean.
    clean_source = source_run(tmp_path / "clean-source")
    clean_bundle = tmp_path / "clean-scan"
    plan_scan([clean_source], clean_bundle, judge_model=DEFAULT_JUDGE_MODEL)
    run_scan(clean_bundle, max_cost_usd=BUDGET, client=FixtureJudge())
    clean_output = tmp_path / "clean-report"
    exit_code = main(
        [
            "--frozen",
            str(clean_bundle),
            "--candidate-model",
            "cli-candidate",
            "--client-only-for-tests",
            "--output",
            str(clean_output),
        ]
    )
    assert exit_code == 0
    assert (clean_output / "report.json").exists()

    # A frozen bundle whose cue and routing questions were answered yes
    # disagrees with the all-no test client at the cue itself, so the crisis
    # check's verdict changes and the gate is not clean.
    dirty_bundle = frozen_bundle(tmp_path / "dirty-source")
    dirty_output = tmp_path / "dirty-report"
    exit_code = main(
        [
            "--frozen",
            str(dirty_bundle),
            "--candidate-model",
            "cli-candidate",
            "--client-only-for-tests",
            "--output",
            str(dirty_output),
        ]
    )
    assert exit_code == 1
    assert (dirty_output / "report.json").exists()


def test_unknown_pricing_and_low_budget_are_refused(tmp_path):
    bundle = frozen_bundle(tmp_path)
    with pytest.raises(ValueError, match="no pricing is known"):
        gate(bundle, "unpriced/judge", client=TurnJudge(turn2_routing=0.9))
    with pytest.raises(ValueError, match="below the candidate's dry-run cost estimate"):
        gate(bundle, DEFAULT_JUDGE_MODEL, client=TurnJudge(turn2_routing=0.9), max_cost_usd=1e-12)


def test_an_incomplete_bundle_is_refused(tmp_path):
    bundle = tmp_path / "scan"
    plan_scan([source_run(tmp_path)], bundle, judge_model=DEFAULT_JUDGE_MODEL)
    with pytest.raises(ValueError, match="incomplete"):
        gate(bundle, DEFAULT_JUDGE_MODEL, client=TurnJudge(turn2_routing=0.9))
