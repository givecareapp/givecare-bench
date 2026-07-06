"""Merge blind review annotations back into the gold-card files.

Reads the JSONL exported by the review app's ``/admin/<token>/export`` route
(dual-annotator schema) and folds the second human's labels into the matching
gold cards on disk, producing a shape ``invisiblebench.evaluation.calibration``
can score for inter-annotator agreement.

Safety rules (calibration is a claim substrate — this must never corrupt it):

* Fills ``annotator_2_*`` on a matched card only when that slot is empty.
* NEVER overwrites an existing ``annotator_1_*`` / ``annotator_2_*`` /
  ``adjudicated_*`` field. A differing incoming value is a CONFLICT: reported and
  refused (the card is left untouched), not silently merged.
* Backfills ``annotator_1_verdict`` from the card's existing single ``verdict``
  (the ratified annotator-of-record label) only if annotator_1 is absent, so the
  merged card carries the blind pair the IAA needs — again, never overwriting.

Dry-run is the default: nothing is written unless ``--apply`` is passed.

Usage:
    uv run python scripts/review_ui/merge_annotations.py \
        --annotations internal/review/export.jsonl                     # dry-run
    uv run python scripts/review_ui/merge_annotations.py \
        --annotations internal/review/export.jsonl --apply             # write
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GOLD_DIRS = (
    REPO_ROOT / "internal" / "calibration" / "natural_gold_2026-06-30" / "recardable",
    REPO_ROOT / "internal" / "calibration" / "natural_gold_2026-06-30" / "derived",
)

_ANNOTATOR_1_FIELDS = ("annotator_1_id", "annotator_1_verdict", "annotator_1_note")
_ANNOTATOR_2_FIELDS = ("annotator_2_id", "annotator_2_verdict", "annotator_2_note")
_ADJUDICATED_FIELDS = ("adjudicated_verdict", "adjudicated_by", "adjudication_notes")


class DuplicateCardIdError(RuntimeError):
    """Raised when the same card_id appears in more than one gold file.

    Silently keeping the first occurrence would merge annotations into the
    wrong file copy — this must refuse instead.
    """


@dataclass
class MergePlan:
    filled: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    unmatched: list[str] = field(default_factory=list)
    skipped_present: list[str] = field(default_factory=list)
    files_touched: set[str] = field(default_factory=set)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _index_gold(gold_dirs: list[Path]) -> dict[str, tuple[Path, int, dict[str, Any]]]:
    """Map card_id -> (file, line index, record) across every gold jsonl.

    Raises ``DuplicateCardIdError`` if a card_id appears in more than one
    file — see that class's docstring for why this must be a hard error
    rather than a silent first-wins.
    """
    index: dict[str, tuple[Path, int, dict[str, Any]]] = {}
    for gdir in gold_dirs:
        if not gdir.exists():
            continue
        for path in sorted(gdir.glob("*.jsonl")):
            for i, rec in enumerate(_load_jsonl(path)):
                cid = rec.get("card_id")
                if not cid:
                    continue
                if cid in index:
                    prior_path, _, _ = index[cid]
                    raise DuplicateCardIdError(
                        f"duplicate card_id {cid!r} found in both "
                        f"{prior_path} and {path} — refusing to merge. "
                        "Resolve the duplicate (rename/remove one copy) "
                        "before running this script."
                    )
                index[cid] = (path, i, rec)
    return index


def _annotator_2_diffs(rec: dict[str, Any], ann: dict[str, Any]) -> list[str]:
    """Diff every ``annotator_2_*`` field present on BOTH sides.

    Verdicts compare case-insensitively; id/note compare as-is. A field
    present on only one side is not a diff for that field (nothing to
    compare against) — but any field present on both sides that disagrees
    is, even when the verdict itself matches: same verdict with a differing
    note or annotator id means the gold and the incoming export disagree
    about who said what, and that must not be silently merged.
    """
    diffs: list[str] = []
    for key in _ANNOTATOR_2_FIELDS:
        existing = rec.get(key)
        incoming = ann.get(key)
        if not existing or not incoming:
            continue
        if key == "annotator_2_verdict":
            existing_cmp, incoming_cmp = str(existing).upper(), str(incoming).upper()
        else:
            existing_cmp, incoming_cmp = existing, incoming
        if existing_cmp != incoming_cmp:
            diffs.append(f"{key}: gold={existing!r} vs incoming={incoming!r}")
    return diffs


def plan_merge(
    annotations: list[dict[str, Any]],
    gold_index: dict[str, tuple[Path, int, dict[str, Any]]],
) -> tuple[MergePlan, dict[Path, list[dict[str, Any]]]]:
    """Compute the merge plan and the new per-file record lists (in memory)."""
    plan = MergePlan()
    # Load every gold file once so we can rewrite whole files atomically.
    file_records: dict[Path, list[dict[str, Any]]] = {}
    for path, _, _ in gold_index.values():
        if path not in file_records:
            file_records[path] = _load_jsonl(path)

    for ann in annotations:
        cid = ann.get("card_id")
        if not cid or cid not in gold_index:
            plan.unmatched.append(str(cid))
            continue
        a2_verdict = ann.get("annotator_2_verdict")
        if not a2_verdict:
            # This session's slot for this card produced no annotator_2 label.
            continue
        path, idx, _ = gold_index[cid]
        rec = file_records[path][idx]

        existing = rec.get("annotator_2_verdict")
        if existing:
            diffs = _annotator_2_diffs(rec, ann)
            verdict_conflict = any(d.startswith("annotator_2_verdict:") for d in diffs)
            if verdict_conflict:
                plan.conflicts.append(f"{cid}: " + "; ".join(diffs))
            elif diffs:
                plan.conflicts.append(f"{cid}: same verdict, metadata differs — " + "; ".join(diffs))
            else:
                plan.skipped_present.append(cid)
            continue

        # Fill annotator_2 (never overwriting; slot verified empty above).
        rec["annotator_2_id"] = ann.get("annotator_2_id", "human_2")
        rec["annotator_2_verdict"] = str(a2_verdict).upper()
        if ann.get("annotator_2_note"):
            rec["annotator_2_note"] = ann["annotator_2_note"]

        # Backfill annotator_1 from the ratified single verdict if absent, so the
        # merged card carries the blind pair the IAA needs. Never overwrite.
        if not rec.get("annotator_1_verdict"):
            incoming_a1 = ann.get("annotator_1_verdict")
            if incoming_a1:
                rec["annotator_1_id"] = ann.get("annotator_1_id", "human_1")
                rec["annotator_1_verdict"] = str(incoming_a1).upper()
                if ann.get("annotator_1_note"):
                    rec["annotator_1_note"] = ann["annotator_1_note"]
            elif rec.get("verdict"):
                rec["annotator_1_id"] = rec.get("author") or "human_1_ratified"
                rec["annotator_1_verdict"] = str(rec["verdict"]).upper()

        plan.filled.append(cid)
        plan.files_touched.add(str(path))

    return plan, file_records


def _write_gold_file_atomic(path: Path, records: list[dict[str, Any]]) -> Path:
    """Back up the pre-merge file, then atomically replace it with ``records``.

    1. Copy the current on-disk file to a timestamped ``.pre-merge.bak``
       sibling, so an interrupted or incorrect merge is always recoverable.
    2. Write the new payload to a temp file in the SAME directory (so the
       final replace is on one filesystem), flush, and fsync it.
    3. ``os.replace`` the temp file over the target — atomic on POSIX, so
       readers never observe a partially written gold file.

    Returns the backup path.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = path.with_name(f"{path.name}.{timestamp}.pre-merge.bak")
    shutil.copy2(path, backup_path)

    payload = "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n"
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
    return backup_path


def _validate_calibration_shape(file_records: dict[Path, list[dict[str, Any]]]) -> str | None:
    """Confirm the merged records still load through the calibration parser."""
    try:
        from invisiblebench.evaluation.calibration import GoldCard
    except Exception as exc:  # noqa: BLE001 — reported, not raised, so dry-run still prints
        return f"could not import calibration harness: {exc}"
    for records in file_records.values():
        for rec in records:
            GoldCard.from_dict(rec, rec.get("mode_id", ""))
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge blind annotations into gold cards.")
    parser.add_argument("--annotations", type=Path, required=True, help="exported JSONL")
    parser.add_argument(
        "--gold-dir", type=Path, action="append", default=None,
        help="gold-card directory (repeatable; default: recardable + derived)",
    )
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    args = parser.parse_args()

    gold_dirs = list(args.gold_dir) if args.gold_dir else list(DEFAULT_GOLD_DIRS)
    annotations = _load_jsonl(args.annotations)
    try:
        gold_index = _index_gold(gold_dirs)
    except DuplicateCardIdError as exc:
        print(f"ERROR: {exc}")
        return 1
    plan, file_records = plan_merge(annotations, gold_index)

    shape_err = _validate_calibration_shape(
        {p: file_records[p] for p in file_records if str(p) in plan.files_touched}
    )

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[{mode}] annotations={len(annotations)} gold_cards_indexed={len(gold_index)}")
    print(f"  fill annotator_2 : {len(plan.filled)}  {plan.filled}")
    print(f"  already present  : {len(plan.skipped_present)}")
    print(f"  unmatched        : {len(plan.unmatched)}  {plan.unmatched}")
    print(f"  CONFLICTS        : {len(plan.conflicts)}")
    for c in plan.conflicts:
        print(f"      ! {c}")
    if shape_err:
        print(f"  calibration-shape check: WARN — {shape_err}")
    else:
        print("  calibration-shape check: OK (GoldCard.from_dict loads all touched records)")

    if plan.conflicts:
        print("Refusing to write: resolve conflicts first (no field was overwritten).")
        return 1
    if not args.apply:
        print("Dry-run only. Re-run with --apply to write.")
        return 0

    for path_str in plan.files_touched:
        path = Path(path_str)
        backup_path = _write_gold_file_atomic(path, file_records[path])
        print(f"  backed up {path} -> {backup_path}")
        print(f"  wrote {path}")
    print(f"Applied: filled {len(plan.filled)} annotator_2 labels across "
          f"{len(plan.files_touched)} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
