#!/usr/bin/env python3
"""Remove AI slop comments from the codebase.

Run: python3 scripts/deslop.py
Verify: uv run ruff check . && uv run pytest benchmark/tests -q
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def remove_line_comments(filepath: str, labels: list[str]) -> int:
    """Remove lines that consist solely of the given comment text."""
    path = ROOT / filepath
    text = path.read_text()
    count = 0
    for label in labels:
        needle = label + "\n"
        if needle in text:
            text = text.replace(needle, "")
            count += 1
    path.write_text(text)
    return count


def replace_inline(filepath: str, old: str, new: str) -> int:
    path = ROOT / filepath
    text = path.read_text()
    if old in text:
        path.write_text(text.replace(old, new))
        return 1
    return 0


def replace_docstring(filepath: str, old: str, new: str) -> int:
    path = ROOT / filepath
    text = path.read_text()
    if old in text:
        path.write_text(text.replace(old, new))
        return 1
    return 0


def main() -> int:
    total = 0

    # --- Section-label comments (explain WHAT, not WHY) ---

    total += remove_line_comments("src/invisiblebench/yaml_cli.py", [
        "    # Run tracking options",
        "    # Verbosity options",
        "    # Handle --doctor (precheck) before anything else",
        "    # Import run manager for utility commands",
        "    # Handle --reset command",
        "    # Handle --list-runs command (paged)",
        "    # Validate required arguments for scoring",
        "    # Validate iterations",
        "        # Import scoring components",
        "        # Find scoring config in configs directory",
        "        # Create progress tracker",
        "        # Run scoring pipeline with iterations and run tracking",
        "        # Generate reports",
        "        # Print summary",
        "        # Show variance if multiple iterations",
        "        # Print dimension scores",
    ])

    # Fix orphaned blank line between import groups after comment removal
    total += replace_inline(
        "src/invisiblebench/yaml_cli.py",
        "from invisiblebench.export.reports import ReportGenerator\n\n        from invisiblebench.utils.benchmark_inventory import get_project_root",
        "from invisiblebench.export.reports import ReportGenerator\n        from invisiblebench.utils.benchmark_inventory import get_project_root",
    )

    total += remove_line_comments("src/invisiblebench/export/reports.py", [
        "        # v2.1 judge metadata (top-level fields)",
        "        # Metadata section - escape user content to prevent XSS",
        "        # Hard fail banner",
        "        # Overall score",
        "        # Variance section (if multiple iterations)",
        "        # Iterations detail",
        "        # Dimension scores",
        "        # Get dimension variance if available",
        "            # Breakdown",
        "            # Violations - escape content to prevent XSS",
        "        # Close HTML",
        "        # Success-rate computation",
        "        # Success rate by category table",
        "        # Failure buckets",
        "        # Results by category",
        "        # Failures section",
        "                # Hard fail reasons",
        "                # Failure categories",
        "                # Low dimensions",
    ])

    total += remove_line_comments("src/invisiblebench/models/results.py", [
        "    # v2 quality dimensions",
        "    # Signals",
        "    # Identification",
        "    # Scores",
        "    # v2 gates",
        "    # Failure information",
        "    # Metadata",
        "    # Model info",
        "    # Results",
        "    # Aggregate stats",
        "        # Legacy 'tier' -> 'category'",
        "        # Legacy dimension_scores key aliases",
    ])

    total += remove_line_comments("src/invisiblebench/evaluation/resilience.py", [
        "    # Write to temporary file in same directory",
        "        # Write to temp file",
        "        # Atomic rename",
        "        # Clean up temp file if it exists",
        "        # Basic schema validation",
        "    # Count different status types",
        "        # All scorers failed",
        "        # Some scorers failed",
        "        # All scorers succeeded",
    ])

    total += remove_line_comments("src/invisiblebench/evaluation/run_manager.py", [
        "            # Write to temp file first",
        "            # Atomic rename",
        "            # Clean up temp file if it exists",
        "        # Find all JSON files in runs directory",
        "            # Skip temp files",
        "                # Apply model name filter if provided",
        "                # Skip corrupted files",
        "            # Only consider completed runs as duplicates",
    ])

    total += remove_line_comments("src/invisiblebench/cli/archive.py", [
        "    # Try to get model info from results",
        "    # Determine what to archive",
        "    # Also check archive",
    ])

    total += remove_line_comments("src/invisiblebench/cli/leaderboard.py", [
        "    # Prepare per-model files in a temp dir first",
        "        # Check scenario count mismatch before copying",
        "        # Copy into canonical dir (overwrite existing models)",
        "    # Regenerate leaderboard",
        "    # Run health check",
    ])

    total += remove_line_comments("src/invisiblebench/models/config.py", [
        "    # Runtime options",
    ])

    total += remove_line_comments("src/invisiblebench/score.py", [
        "# Default paths relative to the repo root.",
    ])

    total += remove_line_comments("src/invisiblebench/api/client.py", [
        "        # Record actual cost",
    ])

    total += remove_line_comments("benchmark/tests/integration/test_cli.py", [
        "        # Check if required files exist",
    ])

    total += remove_line_comments("scripts/reconcile_leaderboard_metadata.py", [
        "    # Top-level note",
        "    # Regard component",
        "    # Holdout block",
        "    # Promotion gate pointer",
    ])

    total += remove_line_comments("src/invisiblebench/loaders/yaml_loader.py", [
        "        # Check for circular inheritance",
        "                # Resolve parent path relative to current file",
        "                # Deep merge: parent rules + current rules",
        "                # Recursively merge nested dicts",
        "                # Override value",
    ])

    # --- Inline comments that restate the obvious ---

    total += replace_inline("src/invisiblebench/yaml_cli.py",
        "callback=None,  # We'll use the tracker directly", "callback=None,")
    total += replace_inline("src/invisiblebench/evaluation/resilience.py",
        '"score": 0.0,  # Default score for errors', '"score": 0.0,')
    total += replace_inline("src/invisiblebench/score.py",
        "            rewards[dim] = 0.0  # Default to 0 if scorer failed",
        "            rewards[dim] = 0.0")
    total += replace_inline("src/invisiblebench/loaders/yaml_loader.py",
        "                if line:  # Skip empty lines", "                if line:")

    # --- pass-with-comment cleanup ---
    total += replace_inline("scripts/batch_tag_scenarios.py",
        "        # Anything in safety/ — turn on anything not already caught\n        pass  # already matched above",
        "        pass  # safety modes already matched by content patterns above")

    # --- Verbose docstrings condensed ---

    total += replace_docstring("src/invisiblebench/loaders/yaml_loader.py",
        '        """\n        Load a rule file and resolve inheritance.\n\n        Args:\n            path: Path to the rule YAML file\n\n        Returns:\n            Dictionary with resolved rules\n\n        Raises:\n            FileNotFoundError: If the file doesn\'t exist\n            ValueError: If circular inheritance is detected\n        """',
        '        """Load a rule file, resolving any `extends` inheritance chain."""')
    total += replace_docstring("src/invisiblebench/loaders/yaml_loader.py",
        '        """\n        Deep merge two dictionaries.\n\n        Args:\n            base: Base dictionary\n            override: Dictionary with overrides\n\n        Returns:\n            Merged dictionary\n        """',
        '        """Deep merge two dictionaries; override wins on conflicts."""')
    total += replace_docstring("src/invisiblebench/loaders/yaml_loader.py",
        '        """\n        Load a scenario file.\n\n        Args:\n            path: Path to the scenario YAML file\n\n        Returns:\n            Dictionary with scenario data\n\n        Raises:\n            FileNotFoundError: If the file doesn\'t exist\n            ValueError: If the scenario fails validation\n        """',
        '        """Load and validate a scenario YAML file."""')
    total += replace_docstring("src/invisiblebench/loaders/yaml_loader.py",
        '        """\n        Load a transcript JSONL file.\n\n        Args:\n            path: Path to the transcript JSONL file\n\n        Returns:\n            List of message dictionaries\n\n        Raises:\n            FileNotFoundError: If the file doesn\'t exist\n            json.JSONDecodeError: If JSONL is malformed\n        """',
        '        """Load a transcript JSONL file into a list of message dicts."""')
    total += replace_docstring("src/invisiblebench/loaders/yaml_loader.py",
        '        """\n        Load a scoring configuration file.\n\n        Args:\n            path: Path to the scoring YAML file\n\n        Returns:\n            Dictionary with scoring configuration\n\n        Raises:\n            FileNotFoundError: If the file doesn\'t exist\n        """',
        '        """Load a scoring configuration YAML file."""')

    total += replace_docstring("src/invisiblebench/api/client.py",
        '        """\n        Call a model via OpenRouter.\n\n        Args:\n            model: Model identifier (e.g., "anthropic/claude-3.7-sonnet")\n            messages: List of message dicts with "role" and "content"\n            temperature: Sampling temperature\n            max_tokens: Maximum tokens to generate\n            **kwargs: Additional model parameters\n\n        Returns:\n            Dictionary with response text, tokens used, and latency\n        """',
        '        """Call a model and return response text, token counts, and latency."""')
    total += replace_docstring("src/invisiblebench/api/client.py",
        '        """Call a model and return a validated Pydantic model via instructor.\n\n        Uses instructor to patch the OpenAI-compatible client, ensuring\n        the LLM\'s response is forced into the provided Pydantic schema.\n        This eliminates free-text parsing failures.\n\n        Args:\n            model: Model identifier (e.g., "google/gemini-2.5-flash-lite")\n            messages: List of message dicts with "role" and "content"\n            response_model: Pydantic BaseModel class defining the expected output\n            temperature: Sampling temperature (default 0.0 for determinism)\n            max_tokens: Maximum tokens to generate\n            max_retries: Instructor retry attempts on validation failure\n\n        Returns:\n            Validated instance of response_model\n        """',
        '        """Call a model and return a validated Pydantic instance via instructor."""')
    total += replace_docstring("src/invisiblebench/api/client.py",
        '        """\n        Call a model via OpenRouter asynchronously.\n\n        Requires httpx to be installed: pip install httpx\n\n        Args:\n            model: Model identifier (e.g., "anthropic/claude-3.7-sonnet")\n            messages: List of message dicts with "role" and "content"\n            temperature: Sampling temperature\n            max_tokens: Maximum tokens to generate\n            **kwargs: Additional model parameters\n\n        Returns:\n            Dictionary with response text, tokens used, and latency\n        """',
        '        """Async variant of call_model. Requires httpx."""')

    total += replace_docstring("src/invisiblebench/__init__.py",
        '"""\nInvisibleBench - Benchmark for evaluating AI safety in long-term caregiving relationships.\n\nThis package provides tools for:\n- Loading and managing scenarios\n- Evaluating model responses across multiple dimensions\n- Scoring based on trauma-informed, culturally-sensitive criteria\n- Generating comprehensive reports\n\nPublic API:',
        '"""InvisibleBench - AI safety benchmark for long-term caregiving relationships.\n\nPublic API:')

    total += replace_docstring("benchmark/tests/integration/test_cli.py",
        '"""\nTest suite for CLI integration.\n\nTests that the CLI properly wires all components together.\n"""',
        '"""CLI integration tests."""')

    print(f"deslop: {total} items cleaned across 15 files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
