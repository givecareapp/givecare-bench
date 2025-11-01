#!/usr/bin/env python3
"""
Stop Hook - Runs quality checks after Claude finishes responding
"""
import json
import sys
import subprocess
from pathlib import Path

def load_edit_log():
    """Load the edit log created by postToolUse hook"""
    log_path = Path(__file__).parent / ".edit-log.json"
    if not log_path.exists():
        return []

    try:
        with open(log_path) as f:
            return json.load(f)
    except Exception:
        return []

def clear_edit_log():
    """Clear edit log for next round"""
    log_path = Path(__file__).parent / ".edit-log.json"
    try:
        with open(log_path, 'w') as f:
            json.dump([], f)
    except Exception:
        pass

def run_command(cmd, timeout=60):
    """Run a shell command and return output"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=Path(__file__).parent.parent.parent
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)

def check_python_files(files):
    """Run checks on Python files"""
    notification = ""

    # Filter to benchmark files
    benchmark_files = [f for f in files if 'benchmark/supportbench/' in f]

    if not benchmark_files:
        return ""

    notification += f"\n📝 Detected changes to {len(files)} Python file(s)\n\n"

    # Run pytest
    notification += "🧪 Running tests...\n"
    code, stdout, stderr = run_command(
        "cd benchmark && python -m pytest tests/ -v --tb=short --maxfail=5",
        timeout=60
    )

    output = stdout + stderr
    if "FAILED" in output:
        import re
        failed = re.findall(r'FAILED.*$', output, re.MULTILINE)
        notification += f"❌ {len(failed)} test(s) failed:\n"
        for test in failed[:5]:
            notification += f"   {test}\n"
        if len(failed) > 5:
            notification += f"   ... and {len(failed) - 5} more\n"
    elif "passed" in output:
        match = re.search(r'(\d+) passed', output)
        if match:
            notification += f"✅ All {match.group(1)} tests passed\n"
        else:
            notification += "✅ Tests passed\n"
    else:
        notification += "⚠️  Tests completed with warnings\n"

    # Run mypy
    notification += "\n🔍 Running type checks...\n"
    code, stdout, stderr = run_command(
        "cd benchmark && python -m mypy supportbench/ --ignore-missing-imports --no-error-summary",
        timeout=30
    )

    if stdout and "error:" in stdout:
        errors = [line for line in stdout.split('\n') if 'error:' in line]
        if errors:
            notification += f"⚠️  {len(errors)} type error(s) found:\n"
            for err in errors[:3]:
                notification += f"   {err.strip()}\n"
            if len(errors) > 3:
                notification += f"   ... and {len(errors) - 3} more\n"
    else:
        notification += "✅ No type errors\n"

    # Run ruff
    notification += "\n🧹 Running linter...\n"
    code, stdout, stderr = run_command(
        "cd benchmark && python -m ruff check supportbench/ --quiet",
        timeout=20
    )

    if stdout and stdout.strip():
        issues = [line for line in stdout.split('\n') if line.strip()]
        notification += f"⚠️  {len(issues)} linting issue(s):\n"
        for issue in issues[:3]:
            notification += f"   {issue}\n"
        if len(issues) > 3:
            notification += f"   ... and {len(issues) - 3} more\n"
    else:
        notification += "✅ No linting issues\n"

    return notification

def check_latex_files(files):
    """Check LaTeX files for paper-code alignment"""
    notification = ""

    givecare_files = [f for f in files if 'papers/givecare/' in f and f.endswith('.tex')]
    supportbench_files = [f for f in files if 'papers/supportbench/' in f and f.endswith('.tex')]

    if not (givecare_files or supportbench_files):
        return ""

    notification += f"\n📄 Detected changes to {len(files)} LaTeX file(s)\n\n"

    if givecare_files:
        notification += "📝 GiveCare paper modified\n"
        notification += "   💡 Remember to:\n"
        notification += "   - Verify figures are up-to-date (run generate_figures.py)\n"
        notification += "   - Check citations match references.bib\n"
        notification += "   - Validate claims match code implementation\n\n"

    if supportbench_files:
        notification += "📝 SupportBench paper modified\n"
        notification += "   💡 Remember to:\n"
        notification += "   - Verify scenario counts match benchmark/scenarios/\n"
        notification += "   - Check dimension weights match configs/scoring.yaml\n"
        notification += "   - Validate methodology matches implementation\n\n"

    return notification

def main():
    # Read edit log
    edit_log = load_edit_log()
    if not edit_log:
        # No edits, nothing to check
        sys.exit(0)

    # Clear log for next round
    clear_edit_log()

    # Extract file paths
    files = [entry['file'] for entry in edit_log]

    # Separate by file type
    python_files = [f for f in files if f.endswith('.py')]
    latex_files = [f for f in files if f.endswith('.tex')]

    if not (python_files or latex_files):
        # No files to check
        sys.exit(0)

    # Build notification
    notification = "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    notification += "🔍 BUILD & QUALITY CHECKS\n"
    notification += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Check Python files
    if python_files:
        notification += check_python_files(python_files)

    # Check LaTeX files
    if latex_files:
        notification += check_latex_files(latex_files)

    notification += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

    # Return notification
    print(json.dumps({"notification": notification}))
    sys.exit(0)

if __name__ == '__main__':
    main()
