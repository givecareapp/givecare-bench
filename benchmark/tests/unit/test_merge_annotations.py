"""Hardening tests for scripts/review_ui/merge_annotations.py.

merge_annotations.py folds the second human annotator's exported labels back
into the gold-card JSONL files that back calibration
(``invisiblebench.evaluation.calibration``) — human labels become the claim
substrate, so a wrong merge (records scrambled across files, conflicts
silently dropped, or an interrupted write leaving a half-written gold file)
directly corrupts the thing IAA numbers are measured against.

Synthetic only: no real card text, gold directories, or annotator data — every
fixture is built fresh under ``tmp_path`` per test. ``merge_annotations.py``
has no Flask/PEP-723 dependency (stdlib only), so unlike
``scripts/review_ui/app.py`` it's importable directly in this environment.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.review_ui.merge_annotations import (
    DuplicateCardIdError,
    _annotator_2_diffs,
    _index_gold,
    _write_gold_file_atomic,
    main,
    plan_merge,
)


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


def _gold_card(card_id: str, **overrides: Any) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "card_id": card_id,
        "mode_id": "crisis.synthetic",
        "verdict": "PASS",
        "transcript_window": (
            "[Turn 1, USER]\nsynthetic user line\n[Turn 1, ASSISTANT]\nsynthetic reply\n"
        ),
        "scenario_id": "synthetic_scenario_001",
    }
    rec.update(overrides)
    return rec


def _annotation(card_id: str, **overrides: Any) -> dict[str, Any]:
    ann: dict[str, Any] = {
        "card_id": card_id,
        "mode_id": "crisis.synthetic",
        "scenario_id": "synthetic_scenario_001",
        "cue_turn": None,
        "transcript_window": (
            "[Turn 1, USER]\nsynthetic user line\n[Turn 1, ASSISTANT]\nsynthetic reply\n"
        ),
        "source_tags": [],
        "annotator_2_id": "rev2",
        "annotator_2_verdict": "PASS",
    }
    ann.update(overrides)
    return ann


# --------------------------------------------------------------------------- #
# FIX 1 — duplicate card_id across gold files is a hard error
# --------------------------------------------------------------------------- #
def test_index_gold_raises_on_duplicate_card_id_across_files(tmp_path: Path) -> None:
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir()
    file_a = gold_dir / "a.jsonl"
    file_b = gold_dir / "b.jsonl"
    _write_jsonl(file_a, [_gold_card("crisis.synthetic__dup")])
    _write_jsonl(file_b, [_gold_card("crisis.synthetic__dup")])

    with pytest.raises(DuplicateCardIdError) as exc_info:
        _index_gold([gold_dir])

    message = str(exc_info.value)
    assert "crisis.synthetic__dup" in message
    assert str(file_a) in message
    assert str(file_b) in message


def test_index_gold_ok_when_card_ids_are_unique(tmp_path: Path) -> None:
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir()
    _write_jsonl(gold_dir / "a.jsonl", [_gold_card("crisis.synthetic__1")])
    _write_jsonl(gold_dir / "b.jsonl", [_gold_card("crisis.synthetic__2")])

    index = _index_gold([gold_dir])

    assert set(index) == {"crisis.synthetic__1", "crisis.synthetic__2"}


# --------------------------------------------------------------------------- #
# FIX 2 — full-field annotator_2_* conflict detection
# --------------------------------------------------------------------------- #
def test_plan_merge_fills_empty_annotator_2_slot(tmp_path: Path) -> None:
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir()
    path = gold_dir / "a.jsonl"
    _write_jsonl(path, [_gold_card("crisis.synthetic__1")])
    gold_index = _index_gold([gold_dir])

    annotations = [
        _annotation("crisis.synthetic__1", annotator_2_verdict="fail", annotator_2_note="quote-backed")
    ]
    plan, file_records = plan_merge(annotations, gold_index)

    assert plan.filled == ["crisis.synthetic__1"]
    assert not plan.conflicts
    rec = file_records[path][0]
    assert rec["annotator_2_verdict"] == "FAIL"
    assert rec["annotator_2_note"] == "quote-backed"
    # annotator_1 is backfilled from the ratified single `verdict`.
    assert rec["annotator_1_verdict"] == "PASS"


def test_plan_merge_verdict_conflict_is_refused_and_not_overwritten(tmp_path: Path) -> None:
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir()
    path = gold_dir / "a.jsonl"
    _write_jsonl(
        path,
        [_gold_card("crisis.synthetic__1", annotator_2_id="rev2", annotator_2_verdict="PASS")],
    )
    gold_index = _index_gold([gold_dir])

    annotations = [_annotation("crisis.synthetic__1", annotator_2_verdict="FAIL")]
    plan, file_records = plan_merge(annotations, gold_index)

    assert plan.filled == []
    assert len(plan.conflicts) == 1
    assert "annotator_2_verdict" in plan.conflicts[0]
    # Untouched: the gold record must not be overwritten.
    assert file_records[path][0]["annotator_2_verdict"] == "PASS"


def test_plan_merge_same_verdict_but_differing_note_is_a_conflict(tmp_path: Path) -> None:
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir()
    path = gold_dir / "a.jsonl"
    _write_jsonl(
        path,
        [
            _gold_card(
                "crisis.synthetic__1",
                annotator_2_id="rev2",
                annotator_2_verdict="PASS",
                annotator_2_note="original quote",
            )
        ],
    )
    gold_index = _index_gold([gold_dir])

    annotations = [
        _annotation(
            "crisis.synthetic__1",
            annotator_2_id="rev2",
            annotator_2_verdict="pass",  # same verdict, different case
            annotator_2_note="a different quote",
        )
    ]
    plan, file_records = plan_merge(annotations, gold_index)

    assert plan.filled == []
    assert plan.skipped_present == []
    assert len(plan.conflicts) == 1
    assert "same verdict, metadata differs" in plan.conflicts[0]
    assert "annotator_2_note" in plan.conflicts[0]
    # Untouched: the original note must survive.
    assert file_records[path][0]["annotator_2_note"] == "original quote"


def test_plan_merge_identical_annotator_2_is_silently_skipped(tmp_path: Path) -> None:
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir()
    path = gold_dir / "a.jsonl"
    _write_jsonl(
        path,
        [
            _gold_card(
                "crisis.synthetic__1",
                annotator_2_id="rev2",
                annotator_2_verdict="PASS",
                annotator_2_note="same quote",
            )
        ],
    )
    gold_index = _index_gold([gold_dir])

    annotations = [
        _annotation(
            "crisis.synthetic__1",
            annotator_2_id="rev2",
            annotator_2_verdict="PASS",
            annotator_2_note="same quote",
        )
    ]
    plan, _ = plan_merge(annotations, gold_index)

    assert plan.filled == []
    assert plan.conflicts == []
    assert plan.skipped_present == ["crisis.synthetic__1"]


def test_annotator_2_diffs_ignores_fields_present_on_only_one_side() -> None:
    rec = {"annotator_2_verdict": "PASS"}
    ann = {"annotator_2_verdict": "PASS", "annotator_2_note": "brand new note"}
    assert _annotator_2_diffs(rec, ann) == []


# --------------------------------------------------------------------------- #
# FIX 3 — atomic, backed-up writes
# --------------------------------------------------------------------------- #
def test_write_gold_file_atomic_backs_up_original_and_replaces_target(tmp_path: Path) -> None:
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir()
    path = gold_dir / "a.jsonl"
    original = [_gold_card("crisis.synthetic__1")]
    _write_jsonl(path, original)
    original_bytes = path.read_bytes()

    new_records = [_gold_card("crisis.synthetic__1", annotator_2_verdict="FAIL")]
    backup_path = _write_gold_file_atomic(path, new_records)

    assert backup_path.exists()
    assert backup_path.name.endswith(".pre-merge.bak")
    assert backup_path.read_bytes() == original_bytes

    written = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert written == new_records

    # No leftover temp files.
    assert list(gold_dir.glob(f".{path.name}.*.tmp")) == []


# --------------------------------------------------------------------------- #
# End-to-end: main() dry-run vs --apply
# --------------------------------------------------------------------------- #
def _run_main(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> int:
    monkeypatch.setattr("sys.argv", argv)
    return main()


def test_main_dry_run_never_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir()
    path = gold_dir / "a.jsonl"
    _write_jsonl(path, [_gold_card("crisis.synthetic__1")])
    original_bytes = path.read_bytes()

    annotations_path = tmp_path / "export.jsonl"
    _write_jsonl(
        annotations_path, [_annotation("crisis.synthetic__1", annotator_2_verdict="FAIL")]
    )

    exit_code = _run_main(
        monkeypatch,
        [
            "merge_annotations",
            "--annotations", str(annotations_path),
            "--gold-dir", str(gold_dir),
        ],
    )

    assert exit_code == 0
    assert path.read_bytes() == original_bytes
    assert list(gold_dir.glob("*.bak")) == []
    assert "DRY-RUN" in capsys.readouterr().out


def test_main_apply_writes_and_backs_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir()
    path = gold_dir / "a.jsonl"
    _write_jsonl(path, [_gold_card("crisis.synthetic__1")])

    annotations_path = tmp_path / "export.jsonl"
    _write_jsonl(
        annotations_path,
        [
            _annotation(
                "crisis.synthetic__1", annotator_2_verdict="FAIL", annotator_2_note="quote-backed"
            )
        ],
    )

    exit_code = _run_main(
        monkeypatch,
        [
            "merge_annotations",
            "--annotations", str(annotations_path),
            "--gold-dir", str(gold_dir),
            "--apply",
        ],
    )

    assert exit_code == 0
    rewritten = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert rewritten[0]["annotator_2_verdict"] == "FAIL"
    backups = list(gold_dir.glob("*.pre-merge.bak"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") != path.read_text(encoding="utf-8")
    assert "APPLY" in capsys.readouterr().out


def test_main_refuses_on_duplicate_card_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir()
    _write_jsonl(gold_dir / "a.jsonl", [_gold_card("crisis.synthetic__dup")])
    _write_jsonl(gold_dir / "b.jsonl", [_gold_card("crisis.synthetic__dup")])

    annotations_path = tmp_path / "export.jsonl"
    _write_jsonl(annotations_path, [])

    exit_code = _run_main(
        monkeypatch,
        [
            "merge_annotations",
            "--annotations", str(annotations_path),
            "--gold-dir", str(gold_dir),
        ],
    )

    assert exit_code == 1
    assert "crisis.synthetic__dup" in capsys.readouterr().out
