"""Publication preserves one configuration per model across complete native sources."""

import json

import pytest

from benchmark.tests.fixtures.current_scan import FixtureJudge, write_source_run
from invisiblebench.cli.transcript import transcript_policy
from invisiblebench.judge import _publication_sources, plan_scan, run_scan
from invisiblebench.scoring import build_scorecard


def source(root, models=("fixture/a",), *, endpoint=None, temperature=0.7, part=None):
    path = write_source_run(root, model_ids=models)
    manifest_path = path / "run_manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["transcript_policy"] = transcript_policy(
        None, [{"id": model, "endpoint": endpoint} for model in models]
    )
    manifest["transcript_policy"]["temperature"] = temperature
    # A shared manifest may contain private fields; these must not be projected.
    manifest["transcript_policy"]["private_note"] = "DO NOT PUBLISH"
    summary_path = path / "transcript_run.json"
    summary = json.loads(summary_path.read_bytes())
    if part is not None:
        selected = sorted(manifest["scenario_ids"])
        selected = selected[:1] if part == "first" else selected[1:]
        manifest["scenario_ids"] = selected
        summary["transcripts"] = [
            row for row in summary["transcripts"] if row["scenario_id"] in selected
        ]
        summary["expected_transcripts"] = summary["transcript_count"] = len(summary["transcripts"])
    for row in summary["transcripts"]:
        transcript = path / row["transcript_path"]
        turns = [json.loads(line) for line in transcript.read_text().splitlines()]
        for turn in turns:
            if turn["role"] == "assistant":
                turn["resolved_provider"] = row["model_id"] + "/observed"
        transcript.write_text("".join(json.dumps(turn) + "\n" for turn in turns))
    # This run-wide list must not leak model B's provider into model A's result.
    summary["resolved_providers"] = [model + "/observed" for model in models]
    manifest_path.write_text(json.dumps(manifest))
    summary_path.write_text(json.dumps(summary))
    return path


@pytest.mark.parametrize("combined", [False, True])
def test_complete_models_publish_with_per_model_serving(tmp_path, combined):
    sources = (
        [source(tmp_path / "both", ("fixture/a", "fixture/b"))]
        if combined
        else [source(tmp_path / name, (f"fixture/{name}",)) for name in ("a", "b")]
    )
    bundle = tmp_path / "scan"
    plan = plan_scan(sources, bundle)
    _publication_sources(bundle, plan)
    run_scan(bundle, max_cost_usd=1, client=FixtureJudge())
    board = build_scorecard(bundle, publication=True)
    assert board["schema"] == "safety-care/v4"
    for model in board["models"]:
        config = model["evaluation_configuration"]
        assert config["serving"]["measurement"] == "routed_service"
        assert config["serving"]["provider"] == {
            "allow_fallbacks": True,
            "require_parameters": True,
        }
        assert config["observed_providers"] == [model["model_id"] + "/observed"]
        assert config["provider_observation_complete"] is True
        assert config["generation"]["temperature"] == 0.7
        assert len(config["generation"]["system_prompt_hash"]) == 64
    assert "DO NOT PUBLISH" not in json.dumps(board)
    assert "private_note" not in json.dumps(board)


@pytest.mark.parametrize("drift", [False, True])
def test_partitioned_same_model_requires_consistent_serving(tmp_path, drift):
    sources = [
        source(tmp_path / "first", part="first", endpoint="provider/region"),
        source(tmp_path / "rest", part="rest", endpoint="other" if drift else "provider/region"),
    ]
    bundle = tmp_path / "scan"
    plan = plan_scan(sources, bundle)
    if drift:
        with pytest.raises(ValueError, match="serving policy.*fixture/a"):
            _publication_sources(bundle, plan)
    else:
        _publication_sources(bundle, plan)


@pytest.mark.parametrize("changed", ["temperature", "code"])
def test_common_policy_drift_is_not_reported_as_missing_coverage(tmp_path, changed):
    sources = [
        source(tmp_path / "a"),
        source(
            tmp_path / "b", ("fixture/b",), temperature=0.2 if changed == "temperature" else 0.7
        ),
    ]
    if changed == "code":
        path = sources[1] / "run_manifest.json"
        manifest = json.loads(path.read_bytes())
        manifest["git_sha"] = "b" * 40
        path.write_text(json.dumps(manifest))
    bundle = tmp_path / "scan"
    plan = plan_scan(sources, bundle)
    with pytest.raises(ValueError, match="common generation"):
        _publication_sources(bundle, plan)


def test_different_models_can_have_different_serving_restrictions(tmp_path):
    sources = [
        source(tmp_path / "a"),
        source(tmp_path / "b", ("fixture/b",), endpoint="provider/region"),
    ]
    bundle = tmp_path / "scan"
    plan = plan_scan(sources, bundle)
    _publication_sources(bundle, plan)
    run_scan(bundle, max_cost_usd=1, client=FixtureJudge())
    models = build_scorecard(bundle, publication=True)["models"]
    assert [model["evaluation_configuration"]["serving"]["measurement"] for model in models] == [
        "routed_service",
        "pinned_provider",
    ]


@pytest.mark.parametrize("commit", [None, "unknown", "abc123", "g" * 40, 123])
def test_publication_rejects_unverified_source_commit(tmp_path, commit):
    path = source(tmp_path / "a")
    manifest_path = path / "run_manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["git_sha"] = commit
    manifest_path.write_text(json.dumps(manifest))
    bundle = tmp_path / "scan"
    plan = plan_scan([path], bundle)
    with pytest.raises(ValueError, match="complete, comparable"):
        _publication_sources(bundle, plan)


def test_missing_coverage_still_refuses_publication(tmp_path):
    bundle = tmp_path / "scan"
    plan = plan_scan([source(tmp_path / "a", part="first")], bundle)
    with pytest.raises(ValueError, match="complete current scenario roster"):
        _publication_sources(bundle, plan)


def test_restricted_provider_and_missing_observations_are_not_inferred(tmp_path):
    path = source(tmp_path / "a", part="first", endpoint="provider/region")
    # Remove all recorded provider identities, including those for selected transcripts.
    for transcript_path in (path / "transcripts").glob("*.jsonl"):
        turns = [json.loads(line) for line in transcript_path.read_text().splitlines()]
        for turn in turns:
            turn.pop("resolved_provider", None)
        transcript_path.write_text("".join(json.dumps(turn) + "\n" for turn in turns))
    bundle = tmp_path / "scan"
    plan_scan([path], bundle)
    run_scan(bundle, max_cost_usd=1, client=FixtureJudge())
    config = build_scorecard(bundle)["models"][0]["evaluation_configuration"]
    assert config["serving"] == {
        "measurement": "pinned_provider",
        "provider": {
            "only": ["provider/region"],
            "allow_fallbacks": False,
            "require_parameters": True,
        },
    }
    assert config["observed_providers"] == []
    assert config["provider_observation_complete"] is False


@pytest.mark.parametrize("mutation", ["extra", "fallback", "missing_model", "generation_type"])
def test_projection_rejects_malformed_public_configuration(tmp_path, mutation):
    path = source(tmp_path / "a", part="first")
    manifest_path = path / "run_manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    policy = manifest["transcript_policy"]
    if mutation == "extra":
        policy["serving"]["fixture/a"]["provider"]["private"] = "DO NOT PUBLISH"
    elif mutation == "fallback":
        policy["serving"]["fixture/a"]["provider"]["allow_fallbacks"] = False
    elif mutation == "missing_model":
        policy["serving"] = {}
    else:
        policy["tools"] = {"private": "DO NOT PUBLISH"}
    manifest_path.write_text(json.dumps(manifest))
    bundle = tmp_path / "scan"
    plan_scan([path], bundle)
    run_scan(bundle, max_cost_usd=1, client=FixtureJudge())
    with pytest.raises(ValueError):
        build_scorecard(bundle)


def test_missing_policy_is_unknown_for_inspection_but_cannot_publish(tmp_path):
    path = source(tmp_path / "a", part="first")
    manifest_path = path / "run_manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    del manifest["transcript_policy"]["serving"]
    manifest_path.write_text(json.dumps(manifest))
    bundle = tmp_path / "scan"
    plan = plan_scan([path], bundle)
    run_scan(bundle, max_cost_usd=1, client=FixtureJudge())
    config = build_scorecard(bundle)["models"][0]["evaluation_configuration"]
    assert config["serving"] is None
    with pytest.raises(ValueError, match="recorded serving policy"):
        _publication_sources(bundle, plan)
