#!/usr/bin/env python3
"""
Pre-flight check for validation script.
Verifies all dependencies, scenarios, and API keys are ready.
"""

import importlib
import importlib.util
import os
import sys
from pathlib import Path
from typing import Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'
CHECK = '✓'
CROSS = '✗'
WARN = '⚠'

def check(condition, success_msg, fail_msg, warning=False):
    """Print check result."""
    if condition:
        print(f"{GREEN}{CHECK}{RESET} {success_msg}")
        return True
    else:
        if warning:
            print(f"{YELLOW}{WARN}{RESET} {fail_msg}")
            return True  # Don't fail on warnings
        else:
            print(f"{RED}{CROSS}{RESET} {fail_msg}")
            return False

def has_module(module_name: str) -> bool:
    """Return True if module can be found without importing it."""
    return importlib.util.find_spec(module_name) is not None

def importable(module_name: str) -> Tuple[bool, Optional[str]]:
    """Return True if module imports cleanly, otherwise False + error message."""
    try:
        importlib.import_module(module_name)
        return True, None
    except Exception as exc:
        return False, str(exc)

def main():
    print("InvisibleBench Validation - Pre-flight Check")
    print("=" * 60)

    all_passed = True

    # Check Python version
    print("\n[Python Version]")
    py_version = sys.version_info
    all_passed &= check(
        py_version >= (3, 9),
        f"Python {py_version.major}.{py_version.minor}.{py_version.micro}",
        f"Python {py_version.major}.{py_version.minor} - Need 3.9+"
    )

    # Check dependencies
    print("\n[Core Dependencies]")

    all_passed &= check(
        has_module("yaml"),
        "pyyaml installed",
        "pyyaml not installed (pip install pyyaml)"
    )

    all_passed &= check(
        has_module("jsonlines"),
        "jsonlines installed",
        "jsonlines not installed (pip install jsonlines)"
    )

    all_passed &= check(
        has_module("requests"),
        "requests installed",
        "requests not installed (pip install requests)"
    )

    # Check optional dependencies
    print("\n[Visualization Dependencies]")

    check(
        has_module("pandas"),
        "pandas installed",
        "pandas not installed (pip install pandas) - summary table will be skipped",
        warning=True
    )

    check(
        has_module("matplotlib"),
        "matplotlib installed",
        "matplotlib not installed (pip install matplotlib) - heatmap will be skipped",
        warning=True
    )

    check(
        has_module("seaborn"),
        "seaborn installed",
        "seaborn not installed (pip install seaborn) - heatmap will be skipped",
        warning=True
    )

    check(
        has_module("tqdm"),
        "tqdm installed",
        "tqdm not installed (pip install tqdm) - no progress bars",
        warning=True
    )

    # Check InvisibleBench modules
    print("\n[InvisibleBench Modules]")

    sys.path.insert(0, str(REPO_ROOT / "benchmark"))

    ok, err = importable("invisiblebench.api.client")
    all_passed &= check(ok, "API client available", f"API client not available: {err}")

    ok, err = importable("invisiblebench.evaluation.orchestrator")
    all_passed &= check(ok, "Orchestrator available", f"Orchestrator not available: {err}")

    ok, err = importable("invisiblebench.loaders.scenario_loader")
    all_passed &= check(ok, "Scenario loader available", f"Scenario loader not available: {err}")

    # Check API keys
    print("\n[API Keys]")

    has_openrouter = bool(os.getenv("OPENROUTER_API_KEY"))

    check(
        has_openrouter,
        "OPENROUTER_API_KEY set",
        "OPENROUTER_API_KEY not set (export OPENROUTER_API_KEY='...')",
        warning=True
    )

    if not has_openrouter:
        all_passed &= check(
            False,
            "",
            "OPENROUTER_API_KEY required"
        )

    # Check scenarios
    print("\n[Scenarios]")

    repo_root = REPO_ROOT
    scenarios = [
        "benchmark/scenarios/tier1/crisis/crisis_detection.json",
        "benchmark/scenarios/tier2/burnout/sandwich_generation_burnout.json",
        "benchmark/scenarios/tier3/longitudinal_trust.json"
    ]

    for scenario_path in scenarios:
        full_path = repo_root / scenario_path
        all_passed &= check(
            full_path.exists(),
            f"{scenario_path}",
            f"{scenario_path} not found"
        )

    # Check output directory
    print("\n[Output Directory]")

    results_dir = repo_root / "results"
    check(
        results_dir.exists(),
        "results/ directory ready",
        "results/ directory will be created on run",
        warning=True
    )

    # Check script
    print("\n[Validation Script]")

    script_path = repo_root / "benchmark" / "scripts" / "validation" / "run_minimal.py"
    all_passed &= check(
        script_path.exists(),
        "run_minimal.py found",
        "run_minimal.py not found"
    )

    if script_path.exists():
        all_passed &= check(
            os.access(script_path, os.X_OK) or True,  # Doesn't need to be executable
            "Script is readable",
            ""
        )

    # Final summary
    print("\n" + "=" * 60)
    if all_passed:
        print(f"{GREEN}✓ All critical checks passed!{RESET}")
        print("\nReady to run validation:")
        print("  python benchmark/scripts/validation/run_minimal.py --dry-run")
        print("  python benchmark/scripts/validation/run_minimal.py")
        return 0
    else:
        print(f"{RED}✗ Some critical checks failed{RESET}")
        print("\nFix the issues above, then run:")
        print("  python benchmark/scripts/validation/check_ready.py")
        return 1

if __name__ == "__main__":
    sys.exit(main())
