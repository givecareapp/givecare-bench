"""Build the blind gold-card review batch — blindness enforced at the source.

Tomorrow's human-review batch is assembled from the gitignored
``internal/calibration/`` tree and written to ``internal/review/batch.json``.
Every card is rebuilt from an explicit allowlist of fields, so no prior label
(verdict, annotator field, judge output, adjudication note) can ride along — the
reviewers grade cold.

Batch composition (three source buckets; see the memos cited inline):

* ``relabel-flagged`` (12) — the 9 UNCLEAR + 3 suspect-FAIL crisis cards whose
  labels the recardable rescore flagged, re-presented at the FULL recovered
  window (``internal/calibration/recardable-rescore-decision-2026-07-05.md``).
* ``crisis-readjudicate`` (5) — the remaining recardable crisis FAILs, at full
  window, for the holistic-vs-timeliness re-adjudication
  (``internal/calibration/omission-redesign-results-2026-07.md``).
* ``tier-b-2nd-human`` (8) — the ``needs_2nd_human`` Tier-B judgment calls from
  the ratified gold (``natural_gold_2026-06-30/source/gold-set-ratified.md``):
  the non-policy human-ratified cards that require a second independent human.

Cards that appear in more than one bucket are exported once, carrying every
source tag. Each card gets the check's human rubric (pass/fail rule + failure
mode) pulled from ``checks/<layer>/<dimension>/<id>.yaml`` — the *definition*,
never the verifier ``prompt:`` block (reviewers apply the human rubric, not the
judge prompt).
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CALIB_DIR = REPO_ROOT / "internal" / "calibration"
RECARDABLE_DIR = CALIB_DIR / "natural_gold_2026-06-30" / "recardable"
GOLD_JOINED = CALIB_DIR / "natural_gold_2026-06-30" / "source" / "gold_joined.jsonl"
CHECKS_DIR = REPO_ROOT / "checks"
DEFAULT_OUT = REPO_ROOT / "internal" / "review" / "batch.json"

# --------------------------------------------------------------------------- #
# Blindness contract — every field a prior label could hide in. The export
# NEVER copies a source dict through; it rebuilds each card from the allowlist
# below. This frozenset is the negative pin the unit test asserts against.
# --------------------------------------------------------------------------- #
BANNED_LABEL_KEYS: frozenset[str] = frozenset(
    {
        "verdict",
        "final_gold",
        "final_verdict",
        "gold",
        "gold_verdict",
        "label",
        "human",
        "human_verdict",
        "annotator_1",
        "annotator_2",
        "annotator_1_id",
        "annotator_2_id",
        "annotator_1_verdict",
        "annotator_2_verdict",
        "annotator_1_note",
        "annotator_2_note",
        "adjudicated_verdict",
        "adjudicated_by",
        "adjudication_notes",
        "reps",
        "post_guard",
        "pre_guard",
        "any_fail",
        "guard_fired",
        "rationale_code",
        "rationale",
        "confidence",
        "pass_rule_result",
        "fail_rule_result",
        "score",
        "overall_score",
        "hard_fail_reason",
    }
)

# Only these check-definition fields reach the reviewer. The verifier `prompt:`,
# `scorer:`, `routing:`, `calibration:` (carries a status), and `source_grounding`
# blocks are intentionally excluded.
_CHECK_ALLOW = ("id", "name", "severity", "scope", "hard_fail", "pass_rule", "fail_rule",
                "good_complement", "caregiver_benefit")

# --------------------------------------------------------------------------- #
# Batch composition (card_ids). Derived from the cited memos; see module docs.
# --------------------------------------------------------------------------- #
# 9 UNCLEAR + 3 suspect-FAIL, per the recardable-rescore decision memo.
FLAGGED: tuple[str, ...] = (
    "crisis.abuse-neglect__card_4",  # UNCLEAR
    "crisis.decay__card_3",  # UNCLEAR
    "crisis.decay__card_7",  # UNCLEAR
    "crisis.direct-ideation__card_5",  # UNCLEAR
    "crisis.direct-ideation__card_9",  # UNCLEAR
    "crisis.disengagement__card_3",  # UNCLEAR
    "crisis.disengagement__card_5",  # UNCLEAR
    "crisis.disengagement__card_6",  # UNCLEAR
    "crisis.disengagement__card_9",  # UNCLEAR
    "crisis.passive-ideation__card_4",  # suspect-FAIL
    "crisis.passive-ideation__card_7",  # suspect-FAIL
    "crisis.direct-ideation__card_10",  # suspect-FAIL
)
# The remaining recardable crisis FAILs, re-presented at full window.
CRISIS_READJUDICATE: tuple[str, ...] = (
    "crisis.abuse-neglect__card_2",
    "crisis.direct-ideation__card_6",
    "crisis.disengagement__card_7",
    "crisis.passive-ideation__card_1",
    "crisis.passive-ideation__card_12",
)
# The 8 needs_2nd_human Tier-B judgment calls (non-policy human-ratified cards).
TIER_B: tuple[str, ...] = (
    "crisis.decay__card_4",
    "crisis.direct-ideation__card_5",
    "crisis.direct-ideation__card_9",
    "crisis.disengagement__card_5",
    "crisis.disengagement__card_6",
    "crisis.disengagement__card_9",
    "crisis.false-reassurance__card_11",
    "crisis.passive-ideation__card_17",
)

SOURCE_BUCKETS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("relabel-flagged", FLAGGED),
    ("crisis-readjudicate", CRISIS_READJUDICATE),
    ("tier-b-2nd-human", TIER_B),
)

SCENARIOS_DIR = REPO_ROOT / "benchmark" / "scenarios"


def _scenario_cue_index() -> dict[str, list[dict[str, Any]]]:
    """Map scenario_id -> its authored ``cue_anchors`` (the CANONICAL cue source).

    Highlights come from anchors authored on the scenario (``add_cue_anchors.py``),
    never from guessing here. Scenarios without anchors simply don't highlight —
    the honest state until an anchor is authored upstream.
    """
    index: dict[str, list[dict[str, Any]]] = {}
    for path in SCENARIOS_DIR.rglob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        sid = data.get("id") or data.get("scenario_id")
        anchors = data.get("cue_anchors")
        if sid and anchors:
            index[sid] = anchors
    return index


def canonical_cue_turn(
    scenario_id: str, check_id: str, cue_index: dict[str, list[dict[str, Any]]]
) -> int | None:
    """Cue turn from the scenario anchor whose ``modes`` scope this check."""
    for anchor in cue_index.get(scenario_id, []):
        if check_id in (anchor.get("modes") or []):
            return anchor.get("cue_turn")
    return None

_TURN_HEADER = re.compile(r"\[Turn\s+(\d+),\s*(USER|ASSISTANT|SYSTEM)\]\s*\n", re.IGNORECASE)

# Gold-joined windows are stored as an annotation card: every transcript line
# is markdown-blockquoted (``> ``) and a scoring template is appended
# (``LABEL: ____ (PASS / FAIL / UNCLEAR) reason: ____``). Neither belongs in the
# text a blind reviewer grades — the template would render mid-card and prompt
# the verdict. Strip both. (Recardable windows are already clean transcripts.)
_GOLD_TEMPLATE_RE = re.compile(r"\n[>\s]*LABEL:\s*_.*\Z", re.S)


def clean_gold_window(window: str) -> str:
    window = _GOLD_TEMPLATE_RE.sub("", window)  # drop the trailing scoring template
    window = re.sub(r"(?m)^>\s?", "", window)  # unquote each blockquoted line
    return window.strip()


# --------------------------------------------------------------------------- #
# Loading helpers
# --------------------------------------------------------------------------- #
def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _check_id_of(card_id: str) -> str:
    """``crisis.passive-ideation__card_4`` -> ``crisis.passive-ideation``."""
    return card_id.split("__", 1)[0]


def parse_turns(window: str) -> list[dict[str, Any]]:
    """Parse a rendered ``[Turn N, ROLE]`` window into ordered turn dicts."""
    matches = list(_TURN_HEADER.finditer(window or ""))
    turns: list[dict[str, Any]] = []
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(window)
        turns.append(
            {
                "turn": int(match.group(1)),
                "role": match.group(2).lower(),
                "content": window[start:end].strip(),
            }
        )
    return turns


def load_check_rubric(check_id: str) -> dict[str, Any]:
    """Extract the human rubric (definition only) from the check YAML."""
    matches = list(CHECKS_DIR.rglob(f"{check_id}.yaml"))
    if not matches:
        raise FileNotFoundError(f"no check YAML for {check_id!r} under {CHECKS_DIR}")
    data = yaml.safe_load(matches[0].read_text(encoding="utf-8")) or {}
    rubric: dict[str, Any] = {}
    for key in _CHECK_ALLOW:
        if key in data and data[key] not in (None, ""):
            value = data[key]
            rubric[key] = value.strip() if isinstance(value, str) else value
    return rubric


def _index_recardable() -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for path in RECARDABLE_DIR.glob("crisis.*.jsonl"):
        for rec in _load_jsonl(path):
            index[rec["card_id"]] = rec
    return index


def _index_gold_joined() -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for rec in _load_jsonl(GOLD_JOINED):
        cid = rec.get("card_id") or f"{rec.get('check')}__card_{rec.get('card')}"
        index[cid] = rec
    return index


# --------------------------------------------------------------------------- #
# Card assembly (allowlist rebuild — the blindness guarantee)
# --------------------------------------------------------------------------- #
def build_card(
    card_id: str,
    source_tags: list[str],
    recardable: dict[str, dict[str, Any]],
    gold_joined: dict[str, dict[str, Any]],
    rubric_cache: dict[str, dict[str, Any]],
    cue_index: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    check_id = _check_id_of(card_id)
    if card_id in recardable:
        src = recardable[card_id]
        window = src["transcript_window"]
        provenance = "recardable-full"
        scenario_id = (src.get("_recovered_from") or {}).get("scenario", "")
    elif card_id in gold_joined:
        src = gold_joined[card_id]
        window = clean_gold_window(src["transcript_window"])
        provenance = "gold-joined"
        scenario_id = src.get("scenario_id", "")
    else:
        raise KeyError(f"card {card_id!r} not found in recardable or gold_joined sources")

    if check_id not in rubric_cache:
        rubric_cache[check_id] = load_check_rubric(check_id)

    # Cue metadata comes from the scenario's authored cue_anchors (canonical),
    # matched to this check; the source card's own cue_turn is a fallback. Never
    # guessed here. cue_turn is a turn index, never a verdict — no label leak.
    cue: dict[str, Any] | None = None
    cue_turn = canonical_cue_turn(scenario_id, check_id, cue_index) or src.get("cue_turn")
    if cue_turn is not None:
        cue = {"cue_turn": cue_turn}

    # Rebuilt from scratch: nothing from `src` is copied through except the
    # transcript text and (optional) scenario id / cue anchor.
    return {
        "card_id": card_id,
        "check_id": check_id,
        "scenario_id": scenario_id,
        "source_tags": source_tags,
        "window_provenance": provenance,
        "check": rubric_cache[check_id],
        "transcript_window": window,
        "turns": parse_turns(window),
        "cue": cue,
    }


def build_batch() -> list[dict[str, Any]]:
    recardable = _index_recardable()
    gold_joined = _index_gold_joined()

    tags_by_card: dict[str, list[str]] = {}
    order: list[str] = []
    for tag, card_ids in SOURCE_BUCKETS:
        for card_id in card_ids:
            if card_id not in tags_by_card:
                tags_by_card[card_id] = []
                order.append(card_id)
            tags_by_card[card_id].append(tag)

    rubric_cache: dict[str, dict[str, Any]] = {}
    cue_index = _scenario_cue_index()
    return [
        build_card(card_id, tags_by_card[card_id], recardable, gold_joined, rubric_cache, cue_index)
        for card_id in order
    ]


def shuffle_order(n: int, seed: int) -> list[int]:
    """Deterministic per-seed presentation order (index permutation).

    The app applies this per reviewer token so each reviewer sees an independent
    order; the same helper keeps the ordering reproducible and testable.
    """
    order = list(range(n))
    random.Random(seed).shuffle(order)
    return order


def _summarize(batch: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for card in batch:
        for tag in card["source_tags"]:
            counts[tag] = counts.get(tag, 0) + 1
    lines = [f"  {tag}: {counts.get(tag, 0)}" for tag, _ in SOURCE_BUCKETS]
    lines.append(f"  unique review units: {len(batch)}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the blind gold-card review batch.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="batch JSON output path")
    args = parser.parse_args()

    batch = build_batch()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(batch, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Wrote {len(batch)} blind cards -> {args.out}")
    print(_summarize(batch))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
