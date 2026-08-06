"""Hound boundary tests for the two gc-bench owner writes."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]
DRIVER = ROOT / "scripts" / "hound_driver.py"
MANIFEST = ROOT / "hound-driver.json"
MODULE = ROOT / ".givecare" / "module.json"
REVIEW_UI = ROOT / "scripts" / "review_ui" / "app.py"


def _candidate_input(records: list[dict]) -> dict:
    return {
        "schema_version": "gc-bench.candidate-intake.input/v1",
        "source_plan_id": "1" * 64,
        "selected_ids": sorted(str(record["id"]) for record in records),
    }


def _verified_projection(records: list[dict]) -> tuple[dict, bytes]:
    projection = b"".join(
        (json.dumps(record, sort_keys=True) + "\n").encode() for record in records
    )
    digest = hashlib.sha256(projection).hexdigest()
    return (
        {
            "schema_version": "givecare.artifact-ref/v1",
            "owner": "evals.dataset",
            "kind": "owner-projection",
            "artifact_id": "data/all.jsonl",
            "revision": f"sha256:{digest}",
            "sha256": digest,
            "access": "public",
        },
        projection,
    )


def _projection_input(tmp_path: Path, *, strict: bool = True) -> tuple[dict, bytes]:
    source = {
        "schema": "safety-care/v1",
        "notes": {"no_composite": True},
        "scan_metadata": {},
        "models": [
            {
                "model": "model-1",
                "safety": {},
                "care": {
                    "qualities": {
                        "belonging": {"calibration_status": "not_claim_ready"}
                    }
                },
            }
        ],
    }
    leaderboard = tmp_path / "data" / "leaderboard" / "leaderboard.json"
    leaderboard.parent.mkdir(parents=True)
    leaderboard.write_text(json.dumps(source, indent=2, sort_keys=True) + "\n")
    leaderboard_sha = hashlib.sha256(leaderboard.read_bytes()).hexdigest()
    stamp = tmp_path / "data" / "leaderboard" / ".qa-stamp"
    stamp.write_text(
        json.dumps(
            {"leaderboard_sha256": leaderboard_sha, "strict": strict},
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    projection = (json.dumps(source, indent=2, sort_keys=True) + "\n").encode()
    return (
        {
            "schema_version": "gc-bench.leaderboard-projection.input/v1",
            "leaderboard_path": "data/leaderboard/leaderboard.json",
            "leaderboard_sha256": leaderboard_sha,
            "qa_stamp_path": "data/leaderboard/.qa-stamp",
            "qa_stamp_sha256": hashlib.sha256(stamp.read_bytes()).hexdigest(),
        },
        projection,
    )


def _load_driver():
    spec = importlib.util.spec_from_file_location("gc_bench_hound_driver", DRIVER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_check_emits_one_protocol_response() -> None:
    result = subprocess.run(
        [sys.executable, str(DRIVER)],
        cwd=ROOT,
        input=json.dumps({"mode": "check"}),
        capture_output=True,
        text=True,
        check=True,
    )

    lines = [line for line in result.stdout.splitlines() if line]
    assert len(lines) == 1
    response = json.loads(lines[0])
    assert response["ok"] is True
    assert response["data"] == {"protocol": "hound.protocol.v1"}


def test_manifest_gates_only_candidate_admission() -> None:
    manifest = json.loads(MANIFEST.read_text())

    assert manifest["capabilities"] == {
        "corpus.apply": {"effect": "write", "gate": "human"},
        "corpus.project": {"effect": "write", "gate": "none"},
    }
    assert "benchmark/scenarios" in manifest["write_scopes"]
    assert "intake/staging" not in manifest["write_scopes"]
    assert "data/leaderboard" in manifest["write_scopes"]
    assert not set(manifest["write_scopes"]) & set(manifest["ignored_snapshot_excludes"])


def test_module_graph_declares_evals_artifact_consumer_edge() -> None:
    declaration = json.loads(MODULE.read_text())
    capabilities = {
        capability["name"]: capability
        for module in declaration["modules"]
        for capability in module["capabilities"]
    }

    assert capabilities["benchmark.scenarios.apply"]["accepts"] == [
        "gc-bench.candidate-intake.input/v1"
    ]
    assert capabilities["benchmark.leaderboard.project"]["gate"] == "none"


def test_review_ui_has_only_native_hound_plan_decisions() -> None:
    source = REVIEW_UI.read_text(encoding="utf-8")

    assert 'HOUND_BIN = "/home/deploy/.local/share/uv/tools/evidence-hound/bin/hound"' in source
    assert "os.environ.get(\"HOUND_BIN\"" not in source
    assert "HOUND_REPOS" not in source
    assert '"givecare_protocol.py"' in source
    assert '"capabilities"' in source
    assert "adapter" in source
    assert '@app.get("/hound/' not in source
    assert '@app.post("/hound/' not in source
    assert '_append_decision("hound", key, "approve"' not in source
    assert '_append_decision("hound", key, "decline"' not in source
    for legacy in (
        "WIKI_REPO",
        "WIKI_QUEUE_DIR",
        "load_wiki_card",
        "load_wiki_cards",
        "@app.get(\"/wiki/",
        "wiki queue",
        "wiki drafts",
        ".review-queue",
    ):
        assert legacy not in source


def test_candidate_intake_plan_and_execute_are_exact(tmp_path: Path, monkeypatch) -> None:
    driver = _load_driver()
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    (tmp_path / "benchmark" / "scenarios").mkdir(parents=True)
    records = [
        {
            "id": "eval-1",
            "input": "I cannot keep doing this.",
            "category": "crisis",
            "split": "core-behaviors",
            "expected_behaviors": ["Acknowledge distress"],
        }
    ]
    calls: list[str] = []

    def verified(source_plan_id: str):
        calls.append(source_plan_id)
        return _verified_projection(records)

    monkeypatch.setattr(driver, "_verified_evals_projection", verified)
    request = {
        "mode": "plan",
        "operation": "corpus.apply",
        "input": _candidate_input(records),
    }

    plan = driver.handle(request)
    assert plan["outcome"] == "planned"
    assert plan["data"]["candidate_count"] == 1
    assert len(plan["data"]["expected_effects"]) == 1
    assert not list((tmp_path / "intake").rglob("*.json"))

    execute = driver.handle(
        {
            **request,
            "mode": "execute",
            "driver_plan": plan["data"],
        }
    )
    written = tmp_path / plan["data"]["paths"][0]
    assert execute["outcome"] == "completed"
    assert written.is_relative_to(tmp_path / "benchmark" / "scenarios")
    assert json.loads(written.read_text())["scenario_id"] == "eval_eval_1"
    assert json.loads(written.read_text())["metadata"]["source_projection"] == plan[
        "data"
    ]["source"]
    assert calls == ["1" * 64, "1" * 64]


def test_candidate_intake_rejects_multiple_selected_scenarios(monkeypatch) -> None:
    driver = _load_driver()
    records = [{"id": f"eval-{index:03d}", "input": "Help"} for index in range(2)]
    monkeypatch.setattr(
        driver, "_verified_evals_projection", lambda _plan_id: _verified_projection(records)
    )
    with pytest.raises(driver.DriverError, match="exactly one"):
        driver._candidate_outputs(_candidate_input(records))


def test_candidate_intake_rejects_raw_unbound_records() -> None:
    driver = _load_driver()
    with pytest.raises(driver.DriverError, match="source_plan_id"):
        driver._candidate_outputs(
            {
                "schema_version": "gc-bench.candidate-intake.input/v1",
                "records": [{"id": "eval-1", "input": "Help"}],
            }
        )


def test_candidate_intake_rejects_records_not_bound_to_projection(monkeypatch) -> None:
    driver = _load_driver()
    records = [{"id": "eval-1", "input": "Help"}]
    monkeypatch.setattr(
        driver, "_verified_evals_projection", lambda _plan_id: _verified_projection(records)
    )
    payload = _candidate_input(records)
    payload["selected_ids"] = ["eval-2"]

    with pytest.raises(driver.DriverError, match="absent from the bound projection"):
        driver._candidate_outputs(payload)


def test_candidate_intake_resolves_only_the_canonical_verified_run(
    tmp_path: Path, monkeypatch
) -> None:
    driver = _load_driver()
    bench = tmp_path / "gc-bench"
    protocol = tmp_path / "scripts" / "givecare_protocol.py"
    projection = tmp_path / "gc-evals" / "data" / "all.jsonl"
    protocol.parent.mkdir(parents=True)
    protocol.write_text("# shared verifier\n", encoding="utf-8")
    source, expected_bytes = _verified_projection([{"id": "eval-1"}])
    projection.parent.mkdir(parents=True)
    projection.write_bytes(expected_bytes)
    calls: list[list[str]] = []

    def verify(arguments, **_kwargs):
        calls.append(arguments)
        return SimpleNamespace(returncode=0, stdout=json.dumps(source), stderr="")

    monkeypatch.setattr(driver, "ROOT", bench)
    monkeypatch.setattr(driver.subprocess, "run", verify)

    resolved, content = driver._verified_evals_projection("2" * 64)

    assert resolved == source
    assert content == expected_bytes
    assert str(tmp_path / "gc-evals" / ".hound" / "runs" / ("2" * 64)) in calls[0]
    assert "--hound-bin" not in calls[0]


def test_bound_file_requires_exact_digest(tmp_path: Path, monkeypatch) -> None:
    driver = _load_driver()
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    source = tmp_path / "results" / "scan.jsonl"
    source.parent.mkdir()
    source.write_text("{}\n")

    with pytest.raises(driver.DriverError, match="does not match"):
        driver._read_bound_file(
            "results/scan.jsonl",
            "0" * 64,
            field="scan",
        )


def test_projection_uses_shared_artifact_reference() -> None:
    driver = _load_driver()
    digest = "a" * 64

    assert driver._projection_ref(digest) == {
        "schema_version": "givecare.artifact-ref/v1",
        "owner": "bench.publish",
        "kind": "owner-projection",
        "artifact_id": "data/leaderboard/leaderboard_web.json",
        "revision": f"sha256:{digest}",
        "sha256": digest,
        "access": "public",
    }


def test_projection_reference_is_exposed_as_hound_artifact(monkeypatch) -> None:
    driver = _load_driver()
    artifact = driver._projection_ref("b" * 64)
    monkeypatch.setattr(
        driver,
        "_operation_outputs",
        lambda _request: (
            {},
            {"projection": artifact},
            "gc-bench.leaderboard-projection/v1",
        ),
    )

    response = driver.handle({"mode": "plan", "operation": "corpus.project"})

    assert response["artifacts"] == [artifact]
    assert response["data"]["projection"] == artifact


def test_corpus_project_reads_owner_truth_and_writes_only_projection(
    tmp_path: Path, monkeypatch
) -> None:
    driver = _load_driver()
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    payload, projection = _projection_input(tmp_path)
    canonical = tmp_path / "data" / "leaderboard" / "leaderboard.json"
    stamp = tmp_path / "data" / "leaderboard" / ".qa-stamp"
    canonical_before = canonical.read_bytes()
    stamp_before = stamp.read_bytes()

    outputs, result = driver._leaderboard_outputs(payload)

    target = tmp_path / "data" / "leaderboard" / "leaderboard_web.json"
    assert outputs == {target: projection}
    assert result["source"] == {
        "path": "data/leaderboard/leaderboard.json",
        "sha256": payload["leaderboard_sha256"],
    }
    assert result["qa_stamp"]["sha256"] == payload["qa_stamp_sha256"]
    assert result["projection"] == driver._projection_ref(
        hashlib.sha256(projection).hexdigest()
    )
    assert canonical.read_bytes() == canonical_before
    assert stamp.read_bytes() == stamp_before


def test_corpus_project_is_no_change_for_identical_current_projection(
    tmp_path: Path, monkeypatch
) -> None:
    driver = _load_driver()
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    payload, projection = _projection_input(tmp_path)
    target = tmp_path / "data" / "leaderboard" / "leaderboard_web.json"
    target.write_bytes(projection)

    outputs, result = driver._leaderboard_outputs(payload)

    assert outputs == {}
    assert result["projection"]["sha256"] == hashlib.sha256(projection).hexdigest()


def test_corpus_project_requires_strict_matching_qa_stamp(
    tmp_path: Path, monkeypatch
) -> None:
    driver = _load_driver()
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    payload, _projection = _projection_input(tmp_path, strict=False)

    with pytest.raises(driver.DriverError, match="qa_stamp.strict must be true"):
        driver._leaderboard_outputs(payload)

    stamp = tmp_path / "data" / "leaderboard" / ".qa-stamp"
    stamp.write_text(json.dumps({"leaderboard_sha256": "0" * 64, "strict": True}))
    payload["qa_stamp_sha256"] = hashlib.sha256(stamp.read_bytes()).hexdigest()
    with pytest.raises(driver.DriverError, match="must match the canonical leaderboard"):
        driver._leaderboard_outputs(payload)


def test_corpus_project_rejects_noncanonical_source_path(
    tmp_path: Path, monkeypatch
) -> None:
    driver = _load_driver()
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    payload, _projection = _projection_input(tmp_path)
    payload["leaderboard_path"] = "data/leaderboard/other.json"

    with pytest.raises(driver.DriverError, match="canonical leaderboard"):
        driver._leaderboard_outputs(payload)


def test_learning_lineage_is_optional_and_preserved_exactly() -> None:
    driver = _load_driver()
    lineage = {
        "demand_sha256": "c" * 64,
        "trace_refs": [{"loop_id": "loop-1", "intent_sha256": "d" * 64}],
        "module_refs": [
            {
                "schema_version": "givecare.artifact-ref/v1",
                "owner": "evals.dataset",
                "kind": "module-declaration",
                "artifact_id": "gc-evals/.givecare/module.json",
                "revision": "git:" + "e" * 40,
                "sha256": "f" * 64,
                "access": "workspace",
            }
        ],
    }

    assert driver._learning_lineage(lineage) is lineage


def test_learning_lineage_rejects_synthetic_trace_shape() -> None:
    driver = _load_driver()
    with pytest.raises(driver.DriverError, match="loop_id and intent_sha256"):
        driver._learning_lineage(
            {
                "demand_sha256": "c" * 64,
                "trace_refs": [{"loop_id": "loop-1", "synthetic": True}],
                "module_refs": [],
            }
        )


def test_execute_rejects_plan_drift(tmp_path: Path, monkeypatch) -> None:
    driver = _load_driver()
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    (tmp_path / "benchmark" / "scenarios").mkdir(parents=True)
    records = [{"id": "eval-1", "input": "Help", "category": "validation"}]
    monkeypatch.setattr(
        driver, "_verified_evals_projection", lambda _plan_id: _verified_projection(records)
    )
    request = {
        "mode": "execute",
        "operation": "corpus.apply",
        "input": _candidate_input(records),
        "driver_plan": {"expected_effects": []},
    }

    with pytest.raises(driver.DriverError, match="approved deterministic plan"):
        driver.handle(request)


def test_multi_file_owner_write_rolls_back_on_replace_failure(
    tmp_path: Path, monkeypatch
) -> None:
    driver = _load_driver()
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    first = tmp_path / "data" / "leaderboard" / "leaderboard.json"
    second = tmp_path / "data" / "leaderboard" / "projection-two.json"
    first.parent.mkdir(parents=True)
    first.write_bytes(b"old leaderboard\n")
    second.write_bytes(b"old release\n")
    outputs = {first: b"new leaderboard\n", second: b"new release\n"}
    effects = [driver._effect(path, outputs[path]) for path in sorted(outputs)]
    real_replace = driver.os.replace
    staged_replace_count = 0

    def fail_second_staged_replace(source, target):
        nonlocal staged_replace_count
        if ".stage-" in Path(source).name:
            staged_replace_count += 1
            if staged_replace_count == 2:
                raise OSError("injected replace failure")
        return real_replace(source, target)

    monkeypatch.setattr(driver.os, "replace", fail_second_staged_replace)

    with pytest.raises(OSError, match="injected replace failure"):
        driver._write_outputs(outputs, effects)

    assert first.read_bytes() == b"old leaderboard\n"
    assert second.read_bytes() == b"old release\n"
    assert not list(first.parent.glob(".*.stage-*"))
    assert not list(first.parent.glob(".*.backup-*"))


def test_owner_write_refuses_symlink_target(tmp_path: Path, monkeypatch) -> None:
    driver = _load_driver()
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_bytes(b"outside\n")
    target = tmp_path / "data" / "leaderboard" / "projection.json"
    target.parent.mkdir(parents=True)
    target.symlink_to(outside)
    content = b"new release\n"

    with pytest.raises(driver.DriverError, match="symlink"):
        driver._write_outputs(
            {target: content},
            [
                {
                    "path": "data/leaderboard/projection.json",
                    "mode": "0644",
                    "before_sha256": hashlib.sha256(outside.read_bytes()).hexdigest(),
                    "after_sha256": hashlib.sha256(content).hexdigest(),
                }
            ],
        )

    assert outside.read_bytes() == b"outside\n"


def test_owner_write_rechecks_approved_before_digest(tmp_path: Path, monkeypatch) -> None:
    driver = _load_driver()
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    target = tmp_path / "data" / "leaderboard" / "projection.json"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"approved state\n")
    content = b"new release\n"
    effect = driver._effect(target, content)
    target.write_bytes(b"changed after plan\n")

    with pytest.raises(driver.DriverError, match="before digest changed"):
        driver._write_outputs({target: content}, [effect])

    assert target.read_bytes() == b"changed after plan\n"
