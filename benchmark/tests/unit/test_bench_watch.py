"""Unit tests for scripts/bench_watch.py — the read-only OpenRouter release watcher.

The watcher is a proposal-only lane (see AUTOMATION.md § Watch): it never
scans and never spends money, so these tests exercise eligibility filtering
and proposal assembly against a fixture catalog and fixture repo files, never
the live OpenRouter API or a real leaderboard.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from scripts import bench_watch

NOW = dt.datetime(2026, 9, 3, tzinfo=dt.UTC)


def _model(model_id: str, created: dt.datetime, prompt: float = 1.0, completion: float = 2.0) -> dict:
    return {
        "id": model_id,
        "created": int(created.timestamp()),
        "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
        "pricing": {"prompt": prompt / 1e6, "completion": completion / 1e6},
    }


def _image_output_model(model_id: str, created: dt.datetime) -> dict:
    """A model whose output is not pure text — excluded by is_text_chat.

    (Multimodal *input* with text output, e.g. a vision-capable chat model,
    is deliberately kept eligible — see openrouter.py's is_text_chat, which
    this filter mirrors.)
    """
    model = _model(model_id, created)
    model["architecture"] = {"input_modalities": ["text", "image"], "output_modalities": ["text", "image"]}
    return model


def _roster(**overrides) -> dict:
    base = {
        "roster_version": "1.0.0",
        "updated": "2026-09-03",
        "rules": {
            "top_n_capability": {"index": "", "n": None},
            "product_models": ["qwen/qwen3.8-max"],
            "requested_by_field": [],
            "providers_in_scope": ["anthropic", "qwen", "google", "openai"],
        },
        "settle_days": 7,
        "monthly_scan_budget_usd": None,
        "scanned": [
            {"model_id": "anthropic/claude-opus-4.8", "leaderboard_version": "4.0.0"},
            {"model_id": "qwen/qwen3.6-35b-a3b", "leaderboard_version": "4.0.0"},
        ],
    }
    base.update(overrides)
    return base


SCANNED = {"anthropic/claude-opus-4.8": "4.0.0", "qwen/qwen3.6-35b-a3b": "4.0.0"}

# The scanned models themselves, as they'd appear in a live catalog fetch —
# eligible_candidates looks up each scanned id's own `created` date from the
# catalog to tell a genuinely newer release apart from an older one that
# merely shares the family name.
SCANNED_IN_CATALOG = [
    _model("anthropic/claude-opus-4.8", created=NOW - dt.timedelta(days=90)),
    _model("qwen/qwen3.6-35b-a3b", created=NOW - dt.timedelta(days=90)),
]


# ---------------------------------------------------------------------------
# family_stem
# ---------------------------------------------------------------------------


def test_family_stem_matches_across_a_version_bump() -> None:
    assert bench_watch.family_stem("anthropic/claude-opus-4.8") == bench_watch.family_stem(
        "anthropic/claude-opus-5.0"
    )


def test_family_stem_does_not_match_a_different_model_name() -> None:
    assert bench_watch.family_stem("google/gemma-4-26b-a4b-it") != bench_watch.family_stem(
        "google/gemma-4-31b-it"
    )


# ---------------------------------------------------------------------------
# eligible_candidates: settle window
# ---------------------------------------------------------------------------


def test_settle_window_excludes_a_release_that_has_not_settled() -> None:
    roster = _roster()
    catalog = [_model("qwen/qwen3.8-max", created=NOW - dt.timedelta(days=2))]

    candidates, notes = bench_watch.eligible_candidates(catalog, roster, SCANNED, NOW)

    assert candidates == []


def test_settle_window_includes_a_release_once_settled() -> None:
    roster = _roster()
    catalog = [_model("qwen/qwen3.8-max", created=NOW - dt.timedelta(days=8))]

    candidates, notes = bench_watch.eligible_candidates(catalog, roster, SCANNED, NOW)

    assert [c["model_id"] for c in candidates] == ["qwen/qwen3.8-max"]
    assert candidates[0]["qualifying_rule"] == "product_models"


# ---------------------------------------------------------------------------
# eligible_candidates: already-scanned
# ---------------------------------------------------------------------------


def test_already_scanned_exact_id_is_excluded() -> None:
    roster = _roster()
    catalog = [_model("anthropic/claude-opus-4.8", created=NOW - dt.timedelta(days=365))]

    candidates, notes = bench_watch.eligible_candidates(catalog, roster, SCANNED, NOW)

    assert candidates == []


def test_a_batch_variant_of_an_already_scanned_id_is_excluded() -> None:
    # Same model, same version, just a different pricing SKU — not a release.
    roster = _roster()
    catalog = SCANNED_IN_CATALOG + [
        _model("anthropic/claude-opus-4.8:batch", created=NOW - dt.timedelta(days=30))
    ]

    candidates, notes = bench_watch.eligible_candidates(catalog, roster, SCANNED, NOW)

    assert candidates == []


# ---------------------------------------------------------------------------
# eligible_candidates: version bump of a scanned family
# ---------------------------------------------------------------------------


def test_new_version_of_a_scanned_model_is_included() -> None:
    roster = _roster()
    catalog = SCANNED_IN_CATALOG + [_model("anthropic/claude-opus-4.9", created=NOW - dt.timedelta(days=30))]

    candidates, notes = bench_watch.eligible_candidates(catalog, roster, SCANNED, NOW)

    assert [c["model_id"] for c in candidates] == ["anthropic/claude-opus-4.9"]
    assert candidates[0]["qualifying_rule"] == "new_version_of_scanned"
    assert notes == []


def test_an_older_release_in_the_same_family_is_excluded() -> None:
    # claude-opus-4 (2025-05) predates the scanned claude-opus-4.8 (2026-05
    # in SCANNED_IN_CATALOG) — sharing a family stem is not enough; it must
    # be newer than what was actually scanned.
    roster = _roster()
    catalog = SCANNED_IN_CATALOG + [_model("anthropic/claude-opus-4", created=NOW - dt.timedelta(days=400))]

    candidates, notes = bench_watch.eligible_candidates(catalog, roster, SCANNED, NOW)

    assert candidates == []


def test_family_match_is_skipped_with_a_note_when_the_scanned_sibling_is_delisted() -> None:
    # The scanned id no longer appears in the live catalog at all, so there
    # is nothing to compare "newer than" against — decline, don't guess.
    roster = _roster()
    catalog = [_model("anthropic/claude-opus-4.9", created=NOW - dt.timedelta(days=30))]

    candidates, notes = bench_watch.eligible_candidates(catalog, roster, SCANNED, NOW)

    assert candidates == []
    assert any("anthropic/claude-opus-4.8" in n for n in notes)


def test_an_unrelated_model_in_scope_but_matching_no_rule_is_excluded() -> None:
    roster = _roster()
    catalog = [_model("anthropic/claude-haiku-5.0", created=NOW - dt.timedelta(days=30))]

    candidates, notes = bench_watch.eligible_candidates(catalog, roster, SCANNED, NOW)

    assert candidates == []


# ---------------------------------------------------------------------------
# eligible_candidates: provider scope
# ---------------------------------------------------------------------------


def test_provider_out_of_scope_is_excluded_even_if_otherwise_eligible() -> None:
    roster = _roster()
    catalog = [_model("mistralai/claude-opus-4.9", created=NOW - dt.timedelta(days=30))]

    candidates, notes = bench_watch.eligible_candidates(catalog, roster, SCANNED, NOW)

    assert candidates == []


def test_non_text_chat_model_is_excluded() -> None:
    roster = _roster()
    catalog = [_image_output_model("qwen/qwen3.8-max", created=NOW - dt.timedelta(days=30))]

    candidates, notes = bench_watch.eligible_candidates(catalog, roster, SCANNED, NOW)

    assert candidates == []


# ---------------------------------------------------------------------------
# standard_change_candidates
# ---------------------------------------------------------------------------


def test_standard_change_proposes_every_scanned_model_for_rescan() -> None:
    candidates = bench_watch.standard_change_candidates(SCANNED, "4.1.0", "4.0.0")

    assert {c["model_id"] for c in candidates} == set(SCANNED)
    assert all(c["qualifying_rule"] == "standard_change" for c in candidates)


def test_standard_change_declines_when_version_unchanged() -> None:
    assert bench_watch.standard_change_candidates(SCANNED, "4.0.0", "4.0.0") == []


def test_standard_change_declines_when_no_leaderboard_published_yet() -> None:
    assert bench_watch.standard_change_candidates(SCANNED, "4.0.0", None) == []


def test_standard_change_declines_when_current_version_is_older() -> None:
    # A stale local checkout should never propose a "downgrade" rescan.
    assert bench_watch.standard_change_candidates(SCANNED, "3.9.0", "4.0.0") == []


# ---------------------------------------------------------------------------
# build_proposal / run_propose — end-to-end against a fixture repo layout
# ---------------------------------------------------------------------------


@pytest.fixture
def fixture_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "benchmark" / "configs").mkdir(parents=True)
    (tmp_path / "data" / "leaderboard").mkdir(parents=True)
    (tmp_path / "delivery" / "watch").mkdir(parents=True)

    roster_path = tmp_path / "benchmark" / "configs" / "roster.json"
    roster_path.write_text(json.dumps(_roster()))

    inventory_path = tmp_path / "benchmark" / "benchmark_inventory.json"
    inventory_path.write_text(json.dumps({"benchmark_version": "4.0.0"}))

    leaderboard_path = tmp_path / "data" / "leaderboard" / "leaderboard.json"
    leaderboard_path.write_text(
        json.dumps(
            {
                "scan_metadata": {
                    "benchmark_version": "4.0.0",
                    "generated_at": "2026-07-10T16:40:55.511183+00:00",
                    "source_merge": {
                        "sources": [
                            {"model_ids": ["anthropic/claude-opus-4.8"], "actual_cost_usd": 5.85},
                            {"model_ids": ["qwen/qwen3.6-35b-a3b"], "actual_cost_usd": 6.42},
                        ]
                    },
                }
            }
        )
    )

    watch_dir = tmp_path / "delivery" / "watch"

    monkeypatch.setattr(bench_watch, "ROSTER_PATH", roster_path)
    monkeypatch.setattr(bench_watch, "INVENTORY_PATH", inventory_path)
    monkeypatch.setattr(bench_watch, "LEADERBOARD_PATH", leaderboard_path)
    monkeypatch.setattr(bench_watch, "WATCH_DIR", watch_dir)
    return tmp_path


def test_build_proposal_with_no_eligible_releases_has_empty_candidates(
    fixture_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bench_watch, "fetch_catalog", lambda: [])

    proposal = bench_watch.build_proposal("2026-09-03")

    assert proposal["candidates"] == []
    assert proposal["standard_change"]["detected"] is False
    assert any("top_n_capability inactive" in n for n in proposal["notes"])


def test_build_proposal_estimates_cost_from_last_scan_source_merge(
    fixture_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        bench_watch,
        "fetch_catalog",
        lambda: [_model("qwen/qwen3.8-max", created=NOW - dt.timedelta(days=30))],
    )
    proposal = bench_watch.build_proposal("2026-09-03", now=NOW)

    assert len(proposal["candidates"]) == 1
    # (5.85 + 6.42) / 2 == 6.135, which round() resolves to 6.13 under
    # float64 representation (6.135 is not exactly representable).
    assert proposal["candidates"][0]["estimated_scan_cost_usd"] == round((5.85 + 6.42) / 2, 2)


def test_run_propose_writes_dated_files_and_prints_declined_token(
    fixture_repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr(bench_watch, "fetch_catalog", lambda: [])

    exit_code = bench_watch.run_propose(now=NOW)

    out = capsys.readouterr().out
    assert exit_code == 0
    assert out.strip().splitlines()[-1] == "DECLINED"
    assert (fixture_repo / "delivery" / "watch" / "2026-09-03.json").exists()
    assert (fixture_repo / "delivery" / "watch" / "2026-09-03.md").exists()


def test_run_propose_prints_done_token_when_a_candidate_is_found(
    fixture_repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr(
        bench_watch,
        "fetch_catalog",
        lambda: [_model("qwen/qwen3.8-max", created=NOW - dt.timedelta(days=30))],
    )
    exit_code = bench_watch.run_propose(now=NOW)

    out = capsys.readouterr().out
    assert exit_code == 0
    assert out.strip().splitlines()[-1] == "DONE"


def test_run_propose_reports_broken_on_malformed_roster(
    fixture_repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    bench_watch.ROSTER_PATH.write_text("not json")

    exit_code = bench_watch.run_propose(now=NOW)

    out = capsys.readouterr().out.strip().splitlines()
    assert exit_code == 1
    assert out[-1] == "BROKEN"
    assert out[-2].startswith("FAILED_CHECK: roster_schema:")


def test_run_propose_reports_broken_when_catalog_is_unreachable(
    fixture_repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    def _raise() -> list[dict]:
        raise bench_watch.WatchError("catalog_fetch", "timed out")

    monkeypatch.setattr(bench_watch, "fetch_catalog", _raise)

    exit_code = bench_watch.run_propose(now=NOW)

    out = capsys.readouterr().out.strip().splitlines()
    assert exit_code == 1
    assert out[-1] == "BROKEN"
    assert out[-2] == "FAILED_CHECK: catalog_fetch: timed out"


def test_standard_change_detected_end_to_end_proposes_rescan_of_scanned_models(
    fixture_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bench_watch.INVENTORY_PATH.write_text(json.dumps({"benchmark_version": "4.1.0"}))
    monkeypatch.setattr(bench_watch, "fetch_catalog", lambda: [])

    proposal = bench_watch.build_proposal("2026-09-03")

    assert proposal["standard_change"]["detected"] is True
    rules = {c["qualifying_rule"] for c in proposal["candidates"]}
    assert rules == {"standard_change"}
    assert {c["model_id"] for c in proposal["candidates"]} == set(SCANNED)

