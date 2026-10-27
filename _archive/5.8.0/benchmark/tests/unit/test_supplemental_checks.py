"""Owner-local checks use the same scan journal without changing the public standard."""

import json

import pytest

from benchmark.tests.fixtures.current_scan import ScriptedJudge, write_source_run
from invisiblebench import judge
from invisiblebench.cli import runner
from invisiblebench.evaluation.check_registry import load_checks
from invisiblebench.jury_card import write_jury_card
from invisiblebench.models.scan import Verdict


@pytest.fixture
def supplemental(tmp_path):
    root = tmp_path / "owner-checks"
    path = root / "care/advocacy/advocacy.development.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(
        "id: advocacy.development\nname: development\nseverity: S1\n"
        "summary: An owner-local development observation.\nbasis: product_contract\n"
        "questions:\n  flag:\n    instructions: Is the observation present in `assistant`?\n"
        "    inputs: [assistant]\nfail_if: [{question: flag, is: true}]\n"
    )
    return root, path


def plan_local(tmp_path, supplemental):
    source = write_source_run(tmp_path, roster=[("development", "context")])
    bundle = tmp_path / "scan"
    assert (
        runner.main(
            [
                "scan",
                "plan",
                str(source),
                "--output",
                str(bundle),
                "--supplemental-checks",
                str(supplemental[0]),
            ]
        )
        == 0
    )
    return bundle


@pytest.mark.parametrize("probability,verdict", [(0.0, "PASS"), (0.9, "FAIL"), (0.5, "UNCLEAR")])
def test_supplemental_findings_use_native_saved_answers_and_cannot_publish(
    tmp_path, supplemental, probability, verdict
):
    bundle = plan_local(tmp_path, supplemental)
    plan, _, _ = judge.load_scan(bundle)
    canonical = load_checks()
    assert {check.id for check in plan.checks} == {*canonical, "advocacy.development"}
    # The owner source can change after planning; the frozen evidence stays authoritative.
    supplemental[1].write_text("changed after planning\n")
    judge.run_scan(bundle, max_cost_usd=0.5, client=ScriptedJudge({"flag": probability}))
    plan, answers, judgments = judge.load_scan(bundle, complete=True)
    assert answers and (bundle / judge.ATTEMPTS_FILE).is_file()
    local = next(row for row in judgments if row.check_id == "advocacy.development")
    assert local.verdict == Verdict(verdict)
    if verdict == "FAIL":
        assert {span.role for span in local.evidence} == {"user", "assistant"}
    assert judge.replay_scan(bundle) == []
    assert "not eligible for public benchmark projection" in write_jury_card(bundle).read_text()
    rejudged = tmp_path / "rejudged"
    judge.plan_rejudge(bundle, rejudged)
    judge.run_scan(rejudged, max_cost_usd=0.5, client=ScriptedJudge({"flag": probability}))
    repeated = next(
        row for row in judge.load_scan(rejudged, complete=True)[2] if row.check_id == local.check_id
    )
    assert repeated.verdict == local.verdict
    with pytest.raises(ValueError, match="current benchmark, checks, or judge settings"):
        judge.load_scan(bundle, current=True)


def test_owner_checks_cannot_replace_a_canonical_check(tmp_path, supplemental):
    source = write_source_run(tmp_path, roster=[("development", "context")])
    root, original = supplemental
    canonical = next(iter(load_checks().values()))
    replacement = root / canonical.layer / canonical.dimension / f"{canonical.id}.yaml"
    replacement.parent.mkdir(parents=True, exist_ok=True)
    replacement.write_text(original.read_text().replace("advocacy.development", canonical.id))
    bundle = tmp_path / "scan"
    with pytest.raises(ValueError, match="duplicate checks"):
        judge.plan_scan([source], bundle, supplemental_checks=root)
    assert not bundle.exists()


@pytest.mark.parametrize("mutation", ["snapshot", "planned_question", "canonical_question"])
def test_changed_checks_stop_before_any_provider_call(
    tmp_path, supplemental, monkeypatch, mutation
):
    bundle = plan_local(tmp_path, supplemental)
    payload = json.loads((bundle / judge.PLAN_FILE).read_text())
    if mutation == "snapshot":
        (bundle / payload["supplemental_checks"][0]["path"]).write_text("tampered\n")
    else:
        check = payload["checks"][-1 if mutation == "planned_question" else 0]
        next(iter(check["questions"].values()))["instructions"] = "changed"
        (bundle / judge.PLAN_FILE).write_text(json.dumps(payload))
    monkeypatch.setattr(judge, "SystemOneClient", lambda: pytest.fail("tampered check reached API"))
    with pytest.raises(ValueError, match="changed|differs"):
        judge.run_scan(bundle, max_cost_usd=0.5)
