#!/usr/bin/env python3
"""
Validate community submission format.

Usage:
    python benchmark/scripts/community/validate_submission.py benchmark/community/submissions/your-model.json
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Set

REQUIRED_FIELDS = {
    "model_info": ["name", "version", "provider"],
    "submitter": ["name", "submission_date"],
    "evaluation_setup": ["num_scenarios", "tiers_tested", "total_evaluations"],
    "results": ["overall_score", "dimension_scores", "tier_scores", "hard_fails"],
    "metadata": ["total_cost_usd", "evaluation_time_minutes"]
}

DIMENSION_NAMES = [
    "crisis_safety", "regulatory_fitness", "trauma_informed_flow",
    "belonging_cultural_fitness", "relational_quality", "actionable_support",
    "longitudinal_consistency", "memory_hygiene"
]

def validate_structure(data: Dict) -> List[str]:
    """Validate JSON structure matches template."""
    errors = []

    # Check top-level sections
    for section, fields in REQUIRED_FIELDS.items():
        if section not in data:
            errors.append(f"Missing section: {section}")
            continue

        # Check required fields
        for field in fields:
            if field not in data[section]:
                errors.append(f"Missing field: {section}.{field}")

    return errors

def validate_scores(data: Dict) -> List[str]:
    """Validate score ranges and consistency."""
    errors = []

    if "results" not in data:
        return ["Missing results section"]

    results = data["results"]

    # Check overall score range
    if "overall_score" in results:
        if not (0 <= results["overall_score"] <= 1):
            errors.append(f"overall_score out of range [0,1]: {results['overall_score']}")

    # Check dimension scores
    if "dimension_scores" in results:
        dims = results["dimension_scores"]
        for dim in DIMENSION_NAMES:
            if dim not in dims:
                errors.append(f"Missing dimension score: {dim}")
            elif not (0 <= dims[dim] <= 1):
                errors.append(f"{dim} out of range [0,1]: {dims[dim]}")

    # Check tier scores
    if "tier_scores" in results:
        for tier in ["tier_1", "tier_2", "tier_3"]:
            if tier not in results["tier_scores"]:
                errors.append(f"Missing tier score: {tier}")
            elif not (0 <= results["tier_scores"][tier] <= 1):
                errors.append(f"{tier} out of range [0,1]: {results['tier_scores'][tier]}")

    # Check hard fails are non-negative
    if "hard_fails" in results:
        for fail_type, count in results["hard_fails"].items():
            if not isinstance(count, int) or count < 0:
                errors.append(f"Invalid hard_fail count for {fail_type}: {count}")

    return errors

def validate_metadata(data: Dict) -> List[str]:
    """Validate metadata fields."""
    errors = []

    if "metadata" not in data:
        return ["Missing metadata section"]

    meta = data["metadata"]

    # Check cost is reasonable
    if "total_cost_usd" in meta:
        if meta["total_cost_usd"] < 0:
            errors.append(f"Negative cost: {meta['total_cost_usd']}")
        elif meta["total_cost_usd"] > 1000:
            errors.append(f"Suspiciously high cost: {meta['total_cost_usd']} (>$1000)")

    # Check evaluation time is reasonable
    if "evaluation_time_minutes" in meta:
        if meta["evaluation_time_minutes"] < 0:
            errors.append(f"Negative time: {meta['evaluation_time_minutes']}")
        elif meta["evaluation_time_minutes"] > 600:  # 10 hours
            errors.append(f"Suspiciously long time: {meta['evaluation_time_minutes']} minutes")

    return errors


def load_confidential_ids(base_dir: Path) -> Set[str]:
    """Load confidential scenario IDs from the repo."""
    confidential_dir = base_dir / "benchmark" / "scenarios" / "confidential"
    if not confidential_dir.exists():
        return set()

    ids: Set[str] = set()
    for scenario_file in confidential_dir.glob("*.json"):
        with open(scenario_file) as f:
            data = json.load(f)
        scenario_id = data.get("scenario_id")
        if scenario_id:
            ids.add(scenario_id)
    return ids


def validate_confidential_holdout(
    data: Dict,
    confidential_ids: Set[str],
    include_confidential: bool,
) -> List[str]:
    """Reject confidential scenarios unless explicitly allowed."""
    if include_confidential:
        return []

    errors = []
    scenarios = data.get("scenarios") or data.get("results", {}).get("scenarios") or []
    for scenario in scenarios:
        if scenario.get("confidential") is True:
            errors.append("Submission includes confidential scenarios; remove them for leaderboard eligibility.")
            break
        scenario_id = scenario.get("scenario_id")
        if scenario_id and scenario_id in confidential_ids:
            errors.append("Submission includes confidential scenarios; remove them for leaderboard eligibility.")
            break
    return errors

def check_duplicate(submission_path: Path) -> List[str]:
    """Check for duplicate submissions."""
    errors = []

    with open(submission_path) as f:
        data = json.load(f)

    model_name = data.get("model_info", {}).get("name", "unknown")

    # Check for existing submissions
    community_dir = submission_path.parent
    for existing in community_dir.glob("*.json"):
        if existing == submission_path or existing.name == "TEMPLATE.json":
            continue

        with open(existing) as f:
            existing_data = json.load(f)

        existing_name = existing_data.get("model_info", {}).get("name", "")
        if existing_name == model_name:
            errors.append(f"Duplicate submission found: {existing.name}")
            errors.append("Please update existing file or use different model name")

    return errors

def main():
    parser = argparse.ArgumentParser(description="Validate community submission")
    parser.add_argument("submission", type=Path, help="Path to submission JSON")
    parser.add_argument("--strict", action="store_true", help="Strict validation (fail on warnings)")
    parser.add_argument(
        "--include-confidential",
        action="store_true",
        help="Allow confidential scenarios in submissions (not for public leaderboard).",
    )

    args = parser.parse_args()

    if not args.submission.exists():
        print(f"ERROR: File not found: {args.submission}")
        sys.exit(1)

    # Load submission
    try:
        with open(args.submission) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON: {e}")
        sys.exit(1)

    # Run validations
    errors = []
    errors.extend(validate_structure(data))
    errors.extend(validate_scores(data))
    errors.extend(validate_metadata(data))
    confidential_ids = load_confidential_ids(Path(__file__).resolve().parents[3])
    errors.extend(
        validate_confidential_holdout(data, confidential_ids, args.include_confidential)
    )

    warnings = []
    warnings.extend(check_duplicate(args.submission))

    # Report results
    print(f"\n{'='*60}")
    print(f"VALIDATION RESULTS: {args.submission.name}")
    print(f"{'='*60}\n")

    if errors:
        print(f"❌ ERRORS ({len(errors)}):")
        for error in errors:
            print(f"  - {error}")
        print()

    if warnings:
        print(f"⚠️  WARNINGS ({len(warnings)}):")
        for warning in warnings:
            print(f"  - {warning}")
        print()

    if not errors and not warnings:
        print("✅ All checks passed!")
        print("\nYour submission is ready to submit via pull request.")
    elif not errors and warnings and not args.strict:
        print("✅ Validation passed (with warnings)")
        print("\nYou can submit, but please review warnings above.")
    else:
        print("❌ Validation failed")
        print("\nPlease fix errors above before submitting.")
        sys.exit(1)

if __name__ == "__main__":
    main()
