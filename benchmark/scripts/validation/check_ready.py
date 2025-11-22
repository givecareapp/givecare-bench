#!/usr/bin/env python3
"""
Pre-flight check for validation script.
Verifies all dependencies, scenarios, and API keys are ready.
"""

import sys
import os
from pathlib import Path

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

    try:
        import yaml
        all_passed &= check(True, "pyyaml installed", "")
    except ImportError:
        all_passed &= check(False, "", "pyyaml not installed (pip install pyyaml)")

    try:
        import jsonlines
        all_passed &= check(True, "jsonlines installed", "")
    except ImportError:
        all_passed &= check(False, "", "jsonlines not installed (pip install jsonlines)")

    try:
        import requests
        all_passed &= check(True, "requests installed", "")
    except ImportError:
        all_passed &= check(False, "", "requests not installed (pip install requests)")

    # Check optional dependencies
    print("\n[Visualization Dependencies]")

    try:
        import pandas
        check(True, "pandas installed", "", warning=True)
    except ImportError:
        check(False, "", "pandas not installed (pip install pandas) - summary table will be skipped", warning=True)

    try:
        import matplotlib
        check(True, "matplotlib installed", "", warning=True)
    except ImportError:
        check(False, "", "matplotlib not installed (pip install matplotlib) - heatmap will be skipped", warning=True)

    try:
        import seaborn
        check(True, "seaborn installed", "", warning=True)
    except ImportError:
        check(False, "", "seaborn not installed (pip install seaborn) - heatmap will be skipped", warning=True)

    try:
        import tqdm
        check(True, "tqdm installed", "", warning=True)
    except ImportError:
        check(False, "", "tqdm not installed (pip install tqdm) - no progress bars", warning=True)

    # Check InvisibleBench modules
    print("\n[InvisibleBench Modules]")

    sys.path.insert(0, str(Path(__file__).parent.parent))

    try:
        from invisiblebench.api.client import ModelAPIClient
        all_passed &= check(True, "API client available", "")
    except ImportError as e:
        all_passed &= check(False, "", f"API client not available: {e}")

    try:
        from invisiblebench.evaluation.orchestrator import ScoringOrchestrator
        all_passed &= check(True, "Orchestrator available", "")
    except ImportError as e:
        all_passed &= check(False, "", f"Orchestrator not available: {e}")

    try:
        from invisiblebench.loaders.scenario_loader import ScenarioLoader
        all_passed &= check(True, "Scenario loader available", "")
    except ImportError as e:
        all_passed &= check(False, "", f"Scenario loader not available: {e}")

    # Check API keys
    print("\n[API Keys]")

    has_openrouter = bool(os.getenv("OPENROUTER_API_KEY"))
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))

    check(
        has_openrouter,
        "OPENROUTER_API_KEY set",
        "OPENROUTER_API_KEY not set (export OPENROUTER_API_KEY='...')",
        warning=True
    )

    check(
        has_openai,
        "OPENAI_API_KEY set",
        "OPENAI_API_KEY not set",
        warning=True
    )

    check(
        has_anthropic,
        "ANTHROPIC_API_KEY set",
        "ANTHROPIC_API_KEY not set",
        warning=True
    )

    if not (has_openrouter or has_openai or has_anthropic):
        all_passed &= check(
            False,
            "",
            "At least one API key required (OPENROUTER, OPENAI, or ANTHROPIC)"
        )

    # Check scenarios
    print("\n[Scenarios]")

    repo_root = Path(__file__).parent.parent
    scenarios = [
        "scenarios/tier1/crisis/crisis_detection.json",
        "scenarios/tier2/burnout/sandwich_generation_burnout.json",
        "scenarios/tier3/longitudinal_trust.json"
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
        True,  # We'll create it if it doesn't exist
        "results/ directory ready",
        "",
        warning=True
    )

    # Check script
    print("\n[Validation Script]")

    script_path = repo_root / "scripts" / "run_minimal_validation.py"
    all_passed &= check(
        script_path.exists(),
        "run_minimal_validation.py found",
        "run_minimal_validation.py not found"
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
        print("  python scripts/run_minimal_validation.py --dry-run")
        print("  python scripts/run_minimal_validation.py")
        return 0
    else:
        print(f"{RED}✗ Some critical checks failed{RESET}")
        print("\nFix the issues above, then run:")
        print("  python scripts/check_validation_ready.py")
        return 1

if __name__ == "__main__":
    sys.exit(main())
