# Scoring Prompts

This directory contains the LLM judge prompts used by InvisibleBench scorers. These files are **not included in the public repository** to prevent benchmark gaming.

## Required Files

| File | Used by | Template variables |
|------|---------|-------------------|
| `safety_crisis_eval.txt` | Safety scorer | `{conversation}` |
| `safety_reference.txt` | Safety scorer | (none) |
| `attunement_boundary.txt` | Safety scorer | `{conversation}` |
| `attunement_trauma.txt` | Safety scorer | `{conversation}` |
| `regard_eval.txt` | Regard scorer | `{conversation}` |
| `compliance_confirmation.txt` | Compliance scorer | `{candidates}`, `{conversation}` |
| `compliance_framework.txt` | Compliance scorer | `{crisis_context}`, `{conversation}` |

## Setup

If you're a contributor who needs scoring prompts:

1. Request access from the project maintainer
2. Place the `.txt` files in this directory
3. Verify with: `uv run pytest benchmark/tests/ -v`

## Format

Each file is a plain-text prompt template. Variables use Python `str.format()` syntax (e.g., `{conversation}`). The scorer loads the file and calls `.format()` with the appropriate values at runtime.

## Without Prompts

The CLI still works for non-scoring operations:
- `uv run bench --dry-run` (cost estimates)
- `uv run bench --help`
- `uv run bench health`
- `uv run bench stats`

Scoring will fail with a clear `FileNotFoundError` pointing to this README.
