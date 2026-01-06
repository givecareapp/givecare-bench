#!/usr/bin/env python3
"""
Lint docs and script usage strings for known stale commands/paths.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

TARGET_FILES = [
    "README.md",
    "benchmark/README.md",
    "benchmark/scripts/README.md",
    "benchmark/scripts/validation/QUICKSTART.md",
    "benchmark/community/README.md",
    "benchmark/community/SUBMISSION_GUIDE.md",
    "benchmark/scenarios/README.md",
    "docs/CHAI_MEETING_PREP.md",
    "docs/COLLINEAR_COMPARISON.md",
    "docs/traitbasis-research-analysis.md",
    "benchmark/scripts/run_benchmark.sh",
    "benchmark/scripts/community/update_leaderboard.py",
    "benchmark/scripts/community/validate_submission.py",
    "benchmark/huggingface/README.md",
    "benchmark/huggingface/README_HF.md",
    "benchmark/huggingface/validate_structure.py",
]

BANNED_PATTERNS = {
    "run_minimal_validation.py": "Use benchmark/scripts/validation/run_minimal.py",
    "community_results/": "Use benchmark/community/ for templates and submissions",
    "scripts/validate_submission.py": "Use benchmark/scripts/community/validate_submission.py",
    "scripts/update_leaderboard.py": "Use benchmark/scripts/community/update_leaderboard.py",
    "benchmarks.cli": "Use python -m invisiblebench.cli",
    "longbench.yaml_cli": "Use python -m benchmark.invisiblebench.yaml_cli",
    "docs/INSTALLATION.md": "Point to benchmark/README.md or validation quickstart",
    "docs/USAGE.md": "Point to benchmark/scripts/validation/QUICKSTART.md",
    "docs/ARCHITECTURE.md": "Point to benchmark/README.md",
    "docs/CONTRIBUTING.md": "Point to benchmark/community/SUBMISSION_GUIDE.md",
    "docs/CHANGELOG.md": "Point to releases or benchmark/README.md",
    "docs/VALIDATION_GUIDE.md": "Point to benchmark/scripts/validation/QUICKSTART.md",
    "docs/scenarios.md": "Point to benchmark/scenarios/SCENARIO_SCHEMA.yaml",
    "python huggingface/upload_script.py": "Use python benchmark/huggingface/upload_script.py",
    "python huggingface/validate_structure.py": "Use python benchmark/huggingface/validate_structure.py",
}


def lint_files() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    missing: list[str] = []

    for rel_path in TARGET_FILES:
        path = REPO_ROOT / rel_path
        if not path.exists():
            missing.append(rel_path)
            continue

        content = path.read_text(encoding="utf-8")
        for token, guidance in BANNED_PATTERNS.items():
            if token in content:
                errors.append(f"{rel_path}: contains '{token}' -> {guidance}")

    return errors, missing


def main() -> int:
    errors, missing = lint_files()

    if missing:
        print("Doc lint: missing files in target list:")
        for rel_path in missing:
            print(f"  - {rel_path}")

    if errors:
        print("Doc lint: stale commands/paths found:")
        for error in errors:
            print(f"  - {error}")

    if missing or errors:
        return 1

    print("Doc lint: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
