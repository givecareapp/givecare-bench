#!/usr/bin/env python3
"""Import givecare-evals JSONL records into gc-bench scenario staging.

Reads givecare-evals data/*.jsonl files, converts each eval case to a
gc-bench candidate scenario JSON, deduplicates against existing scenarios
in benchmark/scenarios/, and writes new candidates to benchmark/staging/.

Usage:
    uv run python scripts/import_evals.py
    uv run python scripts/import_evals.py --evals-dir ../givecare-evals/data
    uv run python scripts/import_evals.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVALS_DIR = REPO_ROOT.parent / "givecare-evals" / "data"
SCENARIOS_DIR = REPO_ROOT / "benchmark" / "scenarios"
STAGING_DIR = REPO_ROOT / "benchmark" / "staging"

# Eval categories → gc-bench ScenarioCategory
CATEGORY_MAP: dict[str, str] = {
    # Safety
    "crisis": "safety",
    "therapy-boundary": "safety",
    "bright-line-on": "safety",
    "bright-line-off": "safety",
    "boundary": "safety",
    "jailbreak": "safety",
    "prompt-injection": "safety",
    "pii-extraction": "safety",
    "crescendo": "safety",
    "authority": "safety",
    "identity-manipulation": "safety",
    "indirect-harm": "safety",
    "harmful-support": "safety",
    # Empathy
    "reddit": "empathy",
    "validation": "empathy",
    "supportive": "empathy",
    "reassurance": "empathy",
    "anti-sycophancy": "empathy",
    "p1": "empathy",
    "p6": "empathy",
    # Context
    "identity": "context",
    "independence": "context",
    "principal": "context",
    "sms-format": "context",
    "onboarding": "context",
    # Continuity
    "memory": "continuity",
    "bootstrap": "continuity",
    "assessment": "continuity",
}

# Eval categories → sub-directory under category
SUBDIR_MAP: dict[str, str] = {
    "crisis": "crisis",
    "therapy-boundary": "boundaries",
    "bright-line-on": "boundaries",
    "bright-line-off": "boundaries",
    "boundary": "boundaries",
    "jailbreak": "adversarial",
    "prompt-injection": "adversarial",
    "pii-extraction": "adversarial",
    "crescendo": "adversarial",
    "authority": "adversarial",
    "identity-manipulation": "adversarial",
    "indirect-harm": "adversarial",
    "harmful-support": "gray_zone",
    "reddit": "burnout",
    "validation": "relational",
    "supportive": "relational",
    "reassurance": "relational",
    "anti-sycophancy": "relational",
    "p1": "burnout",
    "p6": "burnout",
    "identity": "regulatory",
    "independence": "regulatory",
    "principal": "regulatory",
    "sms-format": "regulatory",
    "onboarding": "regulatory",
    "memory": "",
    "bootstrap": "",
    "assessment": "",
}

# Reddit subcategory → more precise gc-bench mapping overrides
REDDIT_CATEGORY_OVERRIDES: dict[str, tuple[str, str]] = {
    "Crisis-adjacent": ("safety", "crisis"),
    "Grief": ("empathy", "grief"),
    "Hospice": ("empathy", "grief"),
    "End of life": ("empathy", "grief"),
    "Humor": ("empathy", "relational"),
    "Positive": ("empathy", "relational"),
    "Victory": ("empathy", "relational"),
    "Financial": ("empathy", "burnout"),
    "Burnout": ("empathy", "burnout"),
    "Dementia": ("empathy", "relational"),
    "Medical": ("safety", "boundaries"),
    "Practical": ("context", "cultural"),
    "Facility": ("context", "cultural"),
    "Family": ("empathy", "relational"),
    "Identity": ("empathy", "belonging"),
    "Complex": ("empathy", "relational"),
}

# Default scoring dimension weights by category
DEFAULT_SCORING: dict[str, dict[str, int]] = {
    "safety": {
        "crisis_safety": 3,
        "regulatory_fitness": 2,
        "trauma_informed_flow": 2,
        "relational_quality": 2,
        "actionable_support": 2,
    },
    "empathy": {
        "crisis_safety": 1,
        "regulatory_fitness": 1,
        "trauma_informed_flow": 3,
        "relational_quality": 3,
        "actionable_support": 2,
    },
    "context": {
        "crisis_safety": 1,
        "regulatory_fitness": 3,
        "trauma_informed_flow": 2,
        "relational_quality": 2,
        "actionable_support": 2,
    },
    "continuity": {
        "crisis_safety": 1,
        "regulatory_fitness": 1,
        "trauma_informed_flow": 2,
        "relational_quality": 2,
        "actionable_support": 2,
        "longitudinal_consistency": 3,
    },
}

# Default persona template (evals don't carry persona data)
DEFAULT_PERSONA = {
    "name": "Caregiver",
    "age": 45,
    "care_recipient": "Family member",
    "care_duration": "Unknown",
    "context": {
        "living_situation": "Unknown",
        "emotional_state": "Distressed",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "_", s)
    s = re.sub(r"-+", "_", s)
    return s[:80].strip("_")


def make_title(rec: dict[str, Any]) -> str:
    """Generate a human-readable title from an eval record."""
    subcat = rec.get("subcategory", "")
    category = rec.get("category", "unknown")
    split = rec.get("split", "")
    if subcat:
        # Clean up subcategory for title
        title = subcat
        # Remove leading category prefix if redundant
        for prefix in ["Burnout — ", "Crisis-adjacent — ", "Grief — ",
                       "Hospice — ", "Financial — ", "Dementia — ",
                       "Medical — ", "Practical — ", "Family — ",
                       "Facility — ", "Humor — ", "Identity — ",
                       "Complex — ", "End of life — ", "Victory — ",
                       "Positive — "]:
            if title.startswith(prefix):
                # Keep the prefix for context
                break
        return f"[eval-import] {title}"
    return f"[eval-import] {split}/{category} case"


def resolve_bench_category(rec: dict[str, Any]) -> tuple[str, str]:
    """Return (category, subdir) for the eval record."""
    cat = rec.get("category", "unknown")
    subcat_text = rec.get("subcategory", "")

    # Reddit records: use subcategory prefix for better mapping
    if cat == "reddit" and subcat_text:
        prefix = subcat_text.split(" — ")[0].split(" — ")[0]
        if prefix in REDDIT_CATEGORY_OVERRIDES:
            return REDDIT_CATEGORY_OVERRIDES[prefix]

    bench_cat = CATEGORY_MAP.get(cat, "empathy")
    bench_sub = SUBDIR_MAP.get(cat, "")
    return bench_cat, bench_sub


def eval_to_scenario(rec: dict[str, Any]) -> dict[str, Any]:
    """Convert a single eval JSONL record to a gc-bench scenario dict."""
    rec_id = rec["id"]
    bench_cat, bench_sub = resolve_bench_category(rec)
    title = make_title(rec)

    # Build a single-turn scenario from the eval input
    turn: dict[str, Any] = {
        "turn_number": 1,
        "t": 1,
        "user_message": rec["input"],
        "expected_behaviors": rec.get("expected_behaviors", []),
        "autofail_triggers": [],
    }

    # Convert forbidden_patterns to autofail_triggers
    forbidden = rec.get("forbidden_patterns", [])
    if forbidden:
        turn["autofail_triggers"] = [
            f"Response contains: '{p}'" for p in forbidden
        ]

    # Build risk_triggers for crisis-related evals
    risk_triggers: list[dict[str, Any]] = []
    if bench_cat == "safety" and bench_sub == "crisis":
        risk_triggers.append({
            "t": 1,
            "cue": rec.get("subcategory", "crisis cue in user message"),
            "severity": "high",
        })

    scenario: dict[str, Any] = {
        "scenario_id": f"eval_{slugify(rec_id)}",
        "category": bench_cat,
        "title": title,
        "description": (
            f"Imported from givecare-evals split={rec.get('split', '?')}, "
            f"category={rec.get('category', '?')}, "
            f"subcategory={rec.get('subcategory', '?')}. "
            f"Single-turn scenario — review and expand for full benchmark use."
        ),
        "persona": dict(DEFAULT_PERSONA),
        "turns": [turn],
        "scoring_dimensions": dict(DEFAULT_SCORING.get(bench_cat, DEFAULT_SCORING["empathy"])),
        "metadata": {
            "author": "import_evals.py",
            "created_date": "2026-04-30",
            "expert_reviewed": False,
            "version": "0.1.0",
            "tags": [
                "eval-import",
                f"split:{rec.get('split', 'unknown')}",
                f"eval-cat:{rec.get('category', 'unknown')}",
            ],
            "source_eval_id": rec_id,
            "source_split": rec.get("split", ""),
            "notes": "Candidate scenario from givecare-evals. Needs persona enrichment, multi-turn expansion, and expert review before promotion.",
        },
    }

    if risk_triggers:
        scenario["risk_triggers"] = risk_triggers

    return scenario


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def load_existing_scenario_fingerprints(scenarios_dir: Path) -> dict[str, set[str]]:
    """Build fingerprint sets from existing scenarios for dedup.

    Returns dict with:
      - 'ids': set of scenario_id values
      - 'titles': set of lowercased title values
      - 'messages': set of lowercased first-turn user messages
    """
    ids: set[str] = set()
    titles: set[str] = set()
    messages: set[str] = set()

    for root, _dirs, files in os.walk(scenarios_dir):
        for fname in files:
            if not fname.endswith(".json"):
                continue
            path = Path(root) / fname
            try:
                with open(path) as f:
                    s = json.load(f)
                ids.add(s.get("scenario_id", ""))
                titles.add(s.get("title", "").lower().strip())

                # First-turn message
                turns = s.get("turns", [])
                sessions = s.get("sessions", [])
                if turns:
                    msg = turns[0].get("user_message", "").lower().strip()
                    if msg:
                        messages.add(msg)
                elif sessions:
                    for sess in sessions:
                        sess_turns = sess.get("turns", [])
                        if sess_turns:
                            msg = sess_turns[0].get("user_message", "").lower().strip()
                            if msg:
                                messages.add(msg)
                            break
            except (json.JSONDecodeError, OSError):
                continue

    return {"ids": ids, "titles": titles, "messages": messages}


def is_duplicate(
    scenario: dict[str, Any],
    fingerprints: dict[str, set[str]],
) -> str | None:
    """Check if scenario duplicates an existing one.

    Returns a reason string if duplicate, None otherwise.
    """
    sid = scenario.get("scenario_id", "")
    if sid in fingerprints["ids"]:
        return f"scenario_id '{sid}' already exists"

    # Check first-turn message overlap (exact match after normalization)
    turns = scenario.get("turns", [])
    if turns:
        msg = turns[0].get("user_message", "").lower().strip()
        if msg and msg in fingerprints["messages"]:
            return "first-turn message matches existing scenario"

    return None


def compute_similarity(msg_a: str, msg_b: str) -> float:
    """Simple word-overlap Jaccard similarity between two messages."""
    words_a = set(re.findall(r'\w+', msg_a.lower()))
    words_b = set(re.findall(r'\w+', msg_b.lower()))
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


def find_near_duplicates(
    scenario: dict[str, Any],
    fingerprints: dict[str, set[str]],
    threshold: float = 0.6,
) -> list[str]:
    """Find near-duplicate existing messages (Jaccard > threshold)."""
    turns = scenario.get("turns", [])
    if not turns:
        return []
    msg = turns[0].get("user_message", "")
    near = []
    for existing_msg in fingerprints["messages"]:
        sim = compute_similarity(msg, existing_msg)
        if sim >= threshold:
            near.append(f"Jaccard={sim:.2f} with: '{existing_msg[:80]}...'")
    return near


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import givecare-evals into gc-bench staging.",
    )
    parser.add_argument(
        "--evals-dir",
        type=Path,
        default=DEFAULT_EVALS_DIR,
        help="Path to givecare-evals/data/ directory",
    )
    parser.add_argument(
        "--staging-dir",
        type=Path,
        default=STAGING_DIR,
        help="Output directory for candidate scenarios",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print summary without writing files",
    )
    parser.add_argument(
        "--splits",
        nargs="*",
        default=["core-behaviors", "red-team", "reddit-caregivers", "multi-turn"],
        help="Which JSONL splits to import (default: all four)",
    )
    parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=0.6,
        help="Jaccard threshold for near-duplicate warnings (default: 0.6)",
    )
    args = parser.parse_args()

    evals_dir: Path = args.evals_dir
    staging_dir: Path = args.staging_dir

    if not evals_dir.is_dir():
        print(f"ERROR: evals directory not found: {evals_dir}", file=sys.stderr)
        sys.exit(1)

    # Load existing scenario fingerprints
    print(f"Loading existing scenarios from {SCENARIOS_DIR} ...")
    fingerprints = load_existing_scenario_fingerprints(SCENARIOS_DIR)
    print(f"  {len(fingerprints['ids'])} scenario IDs, "
          f"{len(fingerprints['messages'])} unique first-turn messages")

    # Also load already-staged scenarios to avoid re-staging
    if staging_dir.is_dir():
        staged_fp = load_existing_scenario_fingerprints(staging_dir)
        for key in fingerprints:
            fingerprints[key] |= staged_fp[key]
        print(f"  + {len(staged_fp['ids'])} already-staged scenarios")

    # Read all eval records
    all_records: list[dict[str, Any]] = []
    for split_name in args.splits:
        jsonl_path = evals_dir / f"{split_name}.jsonl"
        if not jsonl_path.exists():
            print(f"  WARN: {jsonl_path} not found, skipping", file=sys.stderr)
            continue
        with open(jsonl_path) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    all_records.append(rec)
                except json.JSONDecodeError as e:
                    print(f"  WARN: {jsonl_path}:{line_num} bad JSON: {e}",
                          file=sys.stderr)

    print(f"\nLoaded {len(all_records)} eval records from {len(args.splits)} splits")

    # Convert and deduplicate
    imported = 0
    duplicates = 0
    near_dupes = 0
    skipped_no_input = 0
    by_category: dict[str, int] = {}
    by_split: dict[str, int] = {}

    if not args.dry_run:
        staging_dir.mkdir(parents=True, exist_ok=True)

    for rec in all_records:
        if not rec.get("input"):
            skipped_no_input += 1
            continue

        scenario = eval_to_scenario(rec)
        bench_cat, bench_sub = resolve_bench_category(rec)

        # Check exact duplicate
        dup_reason = is_duplicate(scenario, fingerprints)
        if dup_reason:
            duplicates += 1
            continue

        # Check near-duplicates (warn but still import)
        near = find_near_duplicates(scenario, fingerprints, args.similarity_threshold)
        if near:
            near_dupes += 1
            scenario["metadata"]["near_duplicates"] = near

        # Determine output path
        subdir_parts = [bench_cat]
        if bench_sub:
            subdir_parts.append(bench_sub)
        out_dir = staging_dir / "/".join(subdir_parts)

        filename = f"{slugify(rec['id'])}.json"

        if not args.dry_run:
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / filename
            with open(out_path, "w") as f:
                json.dump(scenario, f, indent=2, ensure_ascii=False)
                f.write("\n")

        # Track for fingerprint set (prevent self-duplicates within batch)
        fingerprints["ids"].add(scenario["scenario_id"])
        turns = scenario.get("turns", [])
        if turns:
            msg = turns[0].get("user_message", "").lower().strip()
            if msg:
                fingerprints["messages"].add(msg)

        imported += 1
        by_category[bench_cat] = by_category.get(bench_cat, 0) + 1
        split = rec.get("split", "unknown")
        by_split[split] = by_split.get(split, 0) + 1

    # Print summary
    print("\n" + "=" * 60)
    print("IMPORT SUMMARY")
    print("=" * 60)
    print(f"  Total eval records read:  {len(all_records)}")
    print(f"  Imported (new candidates): {imported}")
    print(f"  Exact duplicates skipped:  {duplicates}")
    print(f"  Near-duplicates flagged:   {near_dupes}")
    if skipped_no_input:
        print(f"  Skipped (no input):        {skipped_no_input}")
    print()
    print("  By gc-bench category:")
    for cat in sorted(by_category):
        print(f"    {cat}: {by_category[cat]}")
    print()
    print("  By source split:")
    for split in sorted(by_split):
        print(f"    {split}: {by_split[split]}")
    print()

    if args.dry_run:
        print("  (dry-run — no files written)")
    else:
        print(f"  Staged to: {staging_dir}")
        # Count files written
        staged_count = sum(1 for _ in staging_dir.rglob("*.json"))
        print(f"  Total files in staging: {staged_count}")

    print()
    print("Next steps:")
    print("  1. Review candidates in benchmark/staging/")
    print("  2. Enrich persona fields (name, age, care details)")
    print("  3. Expand single-turn cases to multi-turn scenarios")
    print("  4. Add rubric/autofail_rubric for verifier scoring")
    print("  5. Run: uv run pytest benchmark/tests -q")
    print("  6. Move reviewed scenarios to benchmark/scenarios/")


if __name__ == "__main__":
    main()
