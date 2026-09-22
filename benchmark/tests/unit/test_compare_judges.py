"""Judge comparison uses the ordinary scan executor, including interruption and resume."""

import json

import pytest

from benchmark.tests.fixtures.current_scan import FixtureJudge, ScriptedJudge, write_source_run
from invisiblebench.api import typesafe
from invisiblebench.cli.compare import compare_ledgers
from invisiblebench.judge import (
    ANSWERS_FILE,
    PLAN_FILE,
    load_scan,
    plan_rejudge,
    plan_scan,
    run_scan,
)


def test_rejudge_retains_progress_and_compares_native_scans(tmp_path, monkeypatch):
    monkeypatch.setitem(typesafe.JUDGE_PRICING, "candidate", 0.042)
    source = write_source_run(tmp_path, roster=[("fixture", "context")])
    old = tmp_path / "old"
    plan_scan([source], old)
    run_scan(old, max_cost_usd=1, client=ScriptedJudge({"cue": 0.9, "routing": 0.9}))
    original = {p.relative_to(old): p.read_bytes() for p in old.rglob("*") if p.is_file()}
    new = tmp_path / "new"
    plan = plan_rejudge(old, new, model="candidate")

    class Interrupted(FixtureJudge):
        calls = 0

        def ask(self, **kwargs):
            self.calls += 1
            if self.calls == 2:
                raise KeyboardInterrupt
            return super().ask(**kwargs)

    with pytest.raises(KeyboardInterrupt):
        run_scan(new, max_cost_usd=1, client=Interrupted())
    retained = (new / ANSWERS_FILE).read_bytes()
    assert len(retained.splitlines()) == 1
    run_scan(new, max_cost_usd=1, client=FixtureJudge())
    assert (new / ANSWERS_FILE).read_bytes().startswith(retained)
    assert len(load_scan(new, complete=True)[1]) == plan.planned_requests
    assert original == {p.relative_to(old): p.read_bytes() for p in old.rglob("*") if p.is_file()}
    report = compare_ledgers(old, new)
    assert report["old_judge"] == typesafe.DEFAULT_JUDGE_MODEL
    assert report["new_judge"] == "candidate"
    assert report["verdict_flips"]
    assert report["accuracy_claim"] is False
    assert json.loads((new / PLAN_FILE).read_bytes())["judge"]["model"] == "candidate"
    for answer in load_scan(new)[1]:
        assert answer.plan_sha256 != load_scan(old)[1][0].plan_sha256


def test_rejudge_cannot_write_into_or_over_its_source(tmp_path):
    with pytest.raises(ValueError, match="separate"):
        plan_rejudge(tmp_path, tmp_path / "nested")
