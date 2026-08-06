#!/usr/bin/env python3
"""Build a bounded Hound candidate-intake request from gc-evals records.

This compiler never writes benchmark truth. Hound owns the human-gated final
write into ``benchmark/scenarios``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
GIVECARE_ROOT = REPO_ROOT.parent
GIVECARE_PROTOCOL = GIVECARE_ROOT / "scripts" / "givecare_protocol.py"

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
            "notes": "Promoted from the exact gc-evals owner projection by a human-approved Hound plan.",
        },
    }

    if risk_triggers:
        scenario["risk_triggers"] = risk_triggers

    return scenario




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


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_verified_projection(
    *,
    source_plan_id: str,
) -> tuple[dict[str, Any], bytes, list[dict[str, Any]]]:
    """Use the shared verifier, then load only its exact owner projection."""
    if re.fullmatch(r"[0-9a-f]{64}", source_plan_id) is None:
        raise ValueError("--source-plan-id must be a lowercase SHA-256 Hound plan id")
    owner_root = (GIVECARE_ROOT / "gc-evals").resolve()
    project_run = owner_root / ".hound" / "runs" / source_plan_id
    verification = subprocess.run(
        [
            sys.executable,
            str(GIVECARE_PROTOCOL),
            "--root",
            str(GIVECARE_ROOT),
            "projection-ref",
            "--run-dir",
            str(project_run),
            "--owner-repo",
            "gc-evals",
            "--driver-id",
            "gc-evals",
            "--artifact-owner",
            "evals.dataset",
            "--artifact-id",
            "data/all.jsonl",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if verification.returncode != 0:
        detail = verification.stderr.strip() or verification.stdout.strip()
        raise ValueError(f"gc-evals Hound projection verification failed: {detail}")

    try:
        source = json.loads(verification.stdout)
    except json.JSONDecodeError as error:
        raise ValueError("shared projection verifier emitted invalid JSON") from error
    expected_fields = {
        "schema_version",
        "owner",
        "kind",
        "artifact_id",
        "revision",
        "sha256",
        "access",
    }
    if not isinstance(source, dict) or set(source) != expected_fields:
        raise ValueError("shared verifier returned an invalid projection ArtifactRef")
    digest = source.get("sha256")
    if source != {
        "schema_version": "givecare.artifact-ref/v1",
        "owner": "evals.dataset",
        "kind": "owner-projection",
        "artifact_id": "data/all.jsonl",
        "revision": f"sha256:{digest}",
        "sha256": digest,
        "access": "public",
    }:
        raise ValueError("verified projection ArtifactRef does not match the gc-evals contract")

    projection = (owner_root / source["artifact_id"]).resolve()
    try:
        projection.relative_to(owner_root)
        projection_bytes = projection.read_bytes()
    except (OSError, ValueError) as error:
        raise ValueError("gc-evals projection is unreadable") from error
    if _sha256(projection_bytes) != digest:
        raise ValueError("gc-evals projection bytes do not match the Hound ArtifactRef")

    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(projection_bytes.splitlines(), start=1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"gc-evals projection line {line_number} is invalid JSON") from error
        if not isinstance(record, dict):
            raise ValueError(f"gc-evals projection line {line_number} is not an object")
        records.append(record)
    if not records:
        raise ValueError("gc-evals projection is empty")

    return source, projection_bytes, records




def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compile a verified gc-evals Hound projection for gc-bench intake.",
    )
    parser.add_argument(
        "--source-plan-id",
        required=True,
        help="Exact verified gc-evals corpus.project Hound plan id",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Write the exact Hound input JSON to this path",
    )
    parser.add_argument(
        "--selected-id",
        required=True,
        help="One exact eval record id selected for the human-gated plan",
    )
    args = parser.parse_args()

    try:
        _source, _projection_bytes, all_records = load_verified_projection(
            source_plan_id=args.source_plan_id,
        )
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)

    selected = next(
        (record for record in all_records if record.get("id") == args.selected_id),
        None,
    )
    if not isinstance(selected, dict) or not selected.get("input"):
        print("ERROR: selected eval record is absent or incomplete", file=sys.stderr)
        sys.exit(1)
    request = {
        "schema_version": "gc-bench.candidate-intake.input/v1",
        "source_plan_id": args.source_plan_id,
        "selected_ids": [args.selected_id],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(request, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote one Hound candidate request for {args.selected_id} to {args.output}"
    )


if __name__ == "__main__":
    main()
