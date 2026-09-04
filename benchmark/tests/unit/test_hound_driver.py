"""Hound boundaries for Evals intake and the complete web release."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
DRIVER = ROOT / "scripts" / "evidence_driver.py"
REVIEW_UI = ROOT / "scripts" / "review_ui" / "app.py"


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True) + "\n").encode()


def _load_driver():
    spec = importlib.util.spec_from_file_location("gc_bench_hound_driver", DRIVER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _source_file(root: Path, relative: str, content: bytes) -> tuple[str, str]:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return relative, _sha(content)


def _release_input(tmp_path: Path) -> dict:
    leaderboard = {
        "schema": "safety-care/v1",
        "notes": {"no_composite": True},
        "scan_metadata": {
            "benchmark_version": "4.0.0",
            "total_models": 4,
            "total_scenarios": 63,
            "active_modes": 50,
        },
        "models": [
            {
                "model": f"model-{index}",
                "safety": {},
                "care": {"qualities": {"belonging": {"calibration_status": "not_claim_ready"}}},
            }
            for index in range(4)
        ],
    }
    leaderboard_path, leaderboard_sha = _source_file(
        tmp_path, "data/leaderboard/leaderboard.json", _json(leaderboard)
    )
    stamp_path, stamp_sha = _source_file(
        tmp_path,
        "data/leaderboard/.qa-stamp",
        _json({"strict": True, "leaderboard_sha256": leaderboard_sha}),
    )
    evidence_models = []
    score_models = []
    current_models = []
    for index in range(4):
        model_id = f"model/{index}"
        filename = f"model-{index}.json"
        evidence_content = _json({"model": model_id, "transcript": index})
        score_content = _json({"model": model_id, "score": index})
        evidence_file, evidence_sha = _source_file(
            tmp_path, f"data/publication-source/web-bench/evidence/v4.0.0/{filename}", evidence_content
        )
        score_file, score_sha = _source_file(
            tmp_path, f"data/publication-source/web-bench/scores/v4.0.0/{filename}", score_content
        )
        evidence_models.append({"model_id": model_id, "file": Path(evidence_file).name, "sha256": evidence_sha, "bytes": len(evidence_content)})
        score_models.append({"model_id": model_id, "file": Path(score_file).name, "sha256": score_sha, "bytes": len(score_content)})
        current_models.append({"modelId": model_id, "bundleFile": filename, "corpusHash": "c" * 64, "transcripts": 63})
    evidence = {
        "schema": "invisiblebench-transcripts/v1",
        "benchmark_version": "4.0.0",
        "result_contract_version": "2.1.0",
        "scenario_count": 63,
        "scenario_hash": "c" * 64,
        "model_count": 4,
        "transcript_count": 252,
        "claim_ready_check_count": 0,
        "models": evidence_models,
    }
    scores = {
        "schema": "invisiblebench-score-evidence/v1",
        "benchmark_version": "4.0.0",
        "result_contract_version": "2.1.0",
        "scenario_count": 63,
        "check_count": 50,
        "model_count": 4,
        "row_count": 252,
        "mode_result_count": 12600,
        "source_scan_sha256": "d" * 64,
        "profile": "publish",
        "judge_model": "judge/model",
        "claim_ready_check_count": 0,
        "models": score_models,
        "source_merge": {
            "schema": "invisiblebench-scan-merge/v1",
            "benchmark_version": "4.0.0",
            "result_contract_version": "2.1.0",
            "profile": "publish",
            "judge_model": "judge/model",
            "model_count": 4,
            "scenario_count": 63,
            "row_count": 252,
            "actual_cost_usd": 12.5,
            "actual_billable_api_calls": 99,
            "output_sha256": "d" * 64,
        },
    }
    current = {
        "benchmarkVersion": "4.0.0", "resultContractVersion": "2.1.0",
        "releasePath": "/bench/evidence/v4.0.0", "scoreReleasePath": "/bench/scores/v4.0.0",
        "transcriptNotice": "notice", "asOf": "2026-08-01", "scenarioCount": 63,
        "categoryCounts": {}, "checkCount": 50, "claimReadyChecks": 0,
        "scoringRelease": {"status": "current research release", "profile": "publish", "judgeModel": "judge/model", "judgeLabel": "Judge", "modelCount": 4, "scenarioCount": 63, "rowCount": 252, "modeResultCount": 12600, "actualCostUsd": 12.5, "actualBillableApiCalls": 99, "sourceScanSha256": "d" * 64, "strictQa": True},
        "validation": {}, "contrastVariants": 0, "models": current_models,
        "findings": [], "knownGaps": [],
    }
    evidence_path, evidence_sha = _source_file(tmp_path, "data/publication-source/web-bench/evidence/v4.0.0/manifest.json", _json(evidence))
    scores_path, scores_sha = _source_file(tmp_path, "data/publication-source/web-bench/scores/v4.0.0/manifest.json", _json(scores))
    current_path, current_sha = _source_file(tmp_path, "data/publication-source/web-bench/current-evidence.json", _json(current))
    return {
        "schema_version": "gc-bench.web-benchmark-release.input/v1",
        "leaderboard_path": leaderboard_path, "leaderboard_sha256": leaderboard_sha,
        "qa_stamp_path": stamp_path, "qa_stamp_sha256": stamp_sha,
        "current_evidence_path": current_path, "current_evidence_sha256": current_sha,
        "evidence_manifest_path": evidence_path, "evidence_manifest_sha256": evidence_sha,
        "scores_manifest_path": scores_path, "scores_manifest_sha256": scores_sha,
    }


def test_manifest_limits_hound_writes_to_owner_outputs() -> None:
    manifest = json.loads((ROOT / "evidence-driver.json").read_text())
    assert manifest["exec"] == ["python3", "-B", "scripts/evidence_driver.py"]
    assert manifest["write_scopes"] == ["benchmark/scenarios", "data/releases/web-bench-release.tar.gz"]


def test_driver_check_emits_one_protocol_response() -> None:
    import subprocess
    import sys
    result = subprocess.run([sys.executable, "-B", str(DRIVER)], cwd=ROOT, input='{"mode":"check"}', capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)["data"] == {"protocol": "hound.protocol.v1"}


def test_review_ui_stays_on_the_native_hound_approval_boundary() -> None:
    source = REVIEW_UI.read_text(encoding="utf-8")
    for required in ('"givecare_protocol.py"', '"capabilities"', "adapter"):
        assert required in source
    for retired in ("HOUND_REPOS", "WIKI_QUEUE_DIR", "wiki queue", "@app.get(\"/wiki/"):
        assert retired not in source


def test_module_declares_fixed_evals_sync_and_single_web_release() -> None:
    declaration = json.loads((ROOT / ".givecare/module.json").read_text())
    capabilities = {cap["name"]: cap for module in declaration["modules"] for cap in module["capabilities"]}
    assert capabilities["benchmark.evals.projection.sync"]["adapter"]["kind"] == "owner-projection-sync"
    assert capabilities["benchmark.scenarios.apply"]["accepts"] == ["gc-bench.candidate-intake.input/v2"]
    assert capabilities["benchmark.web-release.project"]["accepts"] == ["gc-bench.web-benchmark-release.input/v1"]


def test_candidate_intake_reads_local_materialization_and_preserves_run(monkeypatch, tmp_path: Path) -> None:
    driver = _load_driver()
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    (tmp_path / "benchmark" / "scenarios").mkdir(parents=True)
    source = {"schema_version": "givecare.artifact-ref/v1", "owner": "evals.dataset", "kind": "owner-projection", "artifact_id": "data/all.jsonl", "revision": "sha256:" + "a" * 64, "sha256": "a" * 64, "access": "public"}
    record = {"id": "case-1", "input": "Help", "category": "crisis"}
    monkeypatch.setattr(driver, "_materialized_evals_projection", lambda: ("b" * 64, source, _json(record)))
    request = {"mode": "plan", "operation": "corpus.apply", "input": {"schema_version": "gc-bench.candidate-intake.input/v2", "selected_ids": ["case-1"]}}
    plan = driver.handle(request)
    assert plan["data"]["source_run_id"] == "b" * 64
    executed = driver.handle({**request, "mode": "execute", "driver_plan": plan["data"]})
    written = tmp_path / executed["data"]["paths"][0]
    assert json.loads(written.read_text())["metadata"]["source_projection_run_id"] == "b" * 64


def test_candidate_intake_rejects_caller_supplied_source() -> None:
    driver = _load_driver()
    with pytest.raises(driver.DriverError, match="only schema_version and selected_ids"):
        driver._candidate_outputs({"schema_version": "gc-bench.candidate-intake.input/v2", "source_plan_id": "a" * 64, "selected_ids": ["case-1"]})


def test_web_release_is_one_deterministic_complete_archive(monkeypatch, tmp_path: Path) -> None:
    driver = _load_driver()
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    payload = _release_input(tmp_path)
    outputs, result = driver._web_release_outputs(payload)
    target = tmp_path / "data/releases/web-bench-release.tar.gz"
    archive = outputs[target]
    assert result["release"] == driver._web_release_ref(_sha(archive))
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as release:
        names = release.getnames()
        assert names == ["current-evidence.json", "evidence/v4.0.0/manifest.json", "evidence/v4.0.0/model-0.json", "evidence/v4.0.0/model-1.json", "evidence/v4.0.0/model-2.json", "evidence/v4.0.0/model-3.json", "leaderboard.json", "release-manifest.json", "scores/v4.0.0/manifest.json", "scores/v4.0.0/model-0.json", "scores/v4.0.0/model-1.json", "scores/v4.0.0/model-2.json", "scores/v4.0.0/model-3.json"]
        assert all(member.isfile() for member in release.getmembers())
        release_manifest = json.loads(release.extractfile("release-manifest.json").read())
    assert set(release_manifest) == {"schema_version", "release_version", "members"}
    assert len(release_manifest["members"]) == 12
    assert driver._web_release_outputs(payload)[0][target] == archive


def test_web_release_rejects_cross_file_drift(monkeypatch, tmp_path: Path) -> None:
    driver = _load_driver()
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    payload = _release_input(tmp_path)
    current = tmp_path / payload["current_evidence_path"]
    changed = json.loads(current.read_text())
    changed["scenarioCount"] = 62
    current.write_bytes(_json(changed))
    payload["current_evidence_sha256"] = _sha(current.read_bytes())
    with pytest.raises(driver.DriverError, match="does not match the release manifests"):
        driver._web_release_outputs(payload)


@pytest.mark.parametrize("cost", [None, True, float("nan")])
def test_web_release_malformed_current_evidence_fails_closed(
    monkeypatch, tmp_path: Path, cost: object
) -> None:
    driver = _load_driver()
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    payload = _release_input(tmp_path)
    current = tmp_path / payload["current_evidence_path"]
    changed = json.loads(current.read_text())
    changed["scoringRelease"]["actualCostUsd"] = cost
    current.write_bytes(_json(changed))
    payload["current_evidence_sha256"] = _sha(current.read_bytes())
    monkeypatch.setattr(
        driver.sys,
        "stdin",
        io.StringIO(json.dumps({"mode": "plan", "operation": "corpus.project", "input": payload})),
    )
    output = io.StringIO()
    monkeypatch.setattr(driver.sys, "stdout", output)
    assert driver.main() == 0
    response = json.loads(output.getvalue())
    assert response["ok"] is False
    assert response["outcome"] == "failed"
    assert "invalid" in response["diagnostics"][0]


def test_web_release_rejects_model_file_pair_drift(monkeypatch, tmp_path: Path) -> None:
    driver = _load_driver()
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    payload = _release_input(tmp_path)
    current = tmp_path / payload["current_evidence_path"]
    changed = json.loads(current.read_text())
    changed["models"][1]["bundleFile"] = "model-0.json"
    current.write_bytes(_json(changed))
    payload["current_evidence_sha256"] = _sha(current.read_bytes())
    with pytest.raises(driver.DriverError, match="model ids and bundle files"):
        driver._web_release_outputs(payload)


@pytest.mark.parametrize("field,value", [("actualCostUsd", False), ("actualCostUsd", float("inf")), ("actualBillableApiCalls", True)])
def test_web_release_rejects_nonfinite_or_boolean_cost_values(
    monkeypatch, tmp_path: Path, field: str, value: object
) -> None:
    driver = _load_driver()
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    payload = _release_input(tmp_path)
    current = tmp_path / payload["current_evidence_path"]
    changed = json.loads(current.read_text())
    changed["scoringRelease"][field] = value
    current.write_bytes(_json(changed))
    payload["current_evidence_sha256"] = _sha(current.read_bytes())
    with pytest.raises(driver.DriverError, match="invalid"):
        driver._web_release_outputs(payload)


def test_web_release_rejects_duplicate_model_id_in_evidence_manifest(monkeypatch, tmp_path: Path) -> None:
    driver = _load_driver()
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    payload = _release_input(tmp_path)
    evidence = tmp_path / payload["evidence_manifest_path"]
    changed = json.loads(evidence.read_text())
    changed["models"][1]["model_id"] = changed["models"][0]["model_id"]
    evidence.write_bytes(_json(changed))
    payload["evidence_manifest_sha256"] = _sha(evidence.read_bytes())
    with pytest.raises(driver.DriverError, match="must be unique"):
        driver._web_release_outputs(payload)


def test_web_release_rejects_unbound_current_evidence_count(monkeypatch, tmp_path: Path) -> None:
    driver = _load_driver()
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    payload = _release_input(tmp_path)
    current = tmp_path / payload["current_evidence_path"]
    changed = json.loads(current.read_text())
    changed["scoringRelease"]["rowCount"] = 1
    current.write_bytes(_json(changed))
    payload["current_evidence_sha256"] = _sha(current.read_bytes())
    with pytest.raises(driver.DriverError, match="does not match the release manifests"):
        driver._web_release_outputs(payload)


def test_candidate_intake_rejects_multiple_or_absent_ids(monkeypatch) -> None:
    driver = _load_driver()
    source = {"schema_version": "givecare.artifact-ref/v1", "owner": "evals.dataset", "kind": "owner-projection", "artifact_id": "data/all.jsonl", "revision": "sha256:" + "a" * 64, "sha256": "a" * 64, "access": "public"}
    records = _json({"id": "case-1", "input": "Help"})
    monkeypatch.setattr(driver, "_materialized_evals_projection", lambda: ("b" * 64, source, records))
    with pytest.raises(driver.DriverError, match="exactly one"):
        driver._candidate_outputs({"schema_version": "gc-bench.candidate-intake.input/v2", "selected_ids": ["case-1", "case-2"]})
    with pytest.raises(driver.DriverError, match="absent from the bound projection"):
        driver._candidate_outputs({"schema_version": "gc-bench.candidate-intake.input/v2", "selected_ids": ["missing"]})


def test_bound_file_rejects_digest_drift_and_symlink(monkeypatch, tmp_path: Path) -> None:
    driver = _load_driver()
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    path = tmp_path / "data" / "source.json"
    path.parent.mkdir()
    path.write_text("{}\n")
    with pytest.raises(driver.DriverError, match="does not match"):
        driver._read_bound_file("data/source.json", "0" * 64, field="source")
    link = tmp_path / "data" / "link.json"
    link.symlink_to(path)
    with pytest.raises(driver.DriverError, match="symbolic link"):
        driver._read_bound_file("data/link.json", "0" * 64, field="source")


def test_web_release_ref_and_hound_artifact_are_exact(monkeypatch) -> None:
    driver = _load_driver()
    artifact = driver._web_release_ref("a" * 64)
    assert artifact["artifact_id"] == "data/releases/web-bench-release.tar.gz"
    monkeypatch.setattr(driver, "_operation_outputs", lambda _request: ({}, {"release": artifact}, "gc-bench.web-benchmark-release/v1"))
    response = driver.handle({"mode": "plan", "operation": "corpus.project"})
    assert response["artifacts"] == [artifact]


def test_web_release_requires_strict_stamp_and_fixed_sources(monkeypatch, tmp_path: Path) -> None:
    driver = _load_driver()
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    payload = _release_input(tmp_path)
    stamp = tmp_path / payload["qa_stamp_path"]
    stamp.write_bytes(_json({"strict": False, "leaderboard_sha256": payload["leaderboard_sha256"]}))
    payload["qa_stamp_sha256"] = _sha(stamp.read_bytes())
    with pytest.raises(driver.DriverError, match="qa_stamp.strict"):
        driver._web_release_outputs(payload)
    payload = _release_input(tmp_path)
    payload["current_evidence_path"] = "data/other.json"
    with pytest.raises(driver.DriverError, match="current_evidence_path"):
        driver._web_release_outputs(payload)


def test_learning_lineage_stays_exact() -> None:
    driver = _load_driver()
    lineage = {"demand_sha256": "c" * 64, "trace_refs": [{"loop_id": "loop", "intent_sha256": "d" * 64}], "module_refs": []}
    assert driver._learning_lineage(lineage) is lineage
    with pytest.raises(driver.DriverError, match="loop_id and intent_sha256"):
        driver._learning_lineage({"demand_sha256": "c" * 64, "trace_refs": [{"loop_id": "loop"}], "module_refs": []})


def test_execute_rejects_plan_drift_and_write_rolls_back(monkeypatch, tmp_path: Path) -> None:
    driver = _load_driver()
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    target = tmp_path / "data" / "releases" / "web-bench-release.tar.gz"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old")
    outputs = {target: b"new"}
    effects = [driver._effect(target, b"new")]
    payload = _release_input(tmp_path)
    with pytest.raises(driver.DriverError, match="approved deterministic plan"):
        driver.handle({"mode": "execute", "operation": "corpus.project", "input": payload, "driver_plan": {"expected_effects": []}})
    original_replace = driver.os.replace
    def fail_replace(source, destination):
        if destination == target:
            raise OSError("replace failure")
        original_replace(source, destination)
    monkeypatch.setattr(driver.os, "replace", fail_replace)
    with pytest.raises(OSError, match="replace failure"):
        driver._write_outputs(outputs, effects)
    assert target.read_bytes() == b"old"


def test_owner_write_refuses_symlinks_and_rechecks_before_digest(monkeypatch, tmp_path: Path) -> None:
    driver = _load_driver()
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    outside = tmp_path / "outside"
    outside.write_bytes(b"old")
    target = tmp_path / "data" / "releases" / "web-bench-release.tar.gz"
    target.parent.mkdir(parents=True)
    target.symlink_to(outside)
    effect = {"path": "data/releases/web-bench-release.tar.gz", "mode": "0644", "before_sha256": _sha(b"old"), "after_sha256": _sha(b"new")}
    with pytest.raises(driver.DriverError, match="symlink"):
        driver._write_outputs({target: b"new"}, [effect])
    target.unlink()
    target.write_bytes(b"approved")
    effect = driver._effect(target, b"new")
    target.write_bytes(b"changed")
    with pytest.raises(driver.DriverError, match="before digest changed"):
        driver._write_outputs({target: b"new"}, [effect])
