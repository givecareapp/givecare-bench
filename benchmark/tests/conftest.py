"""Disable live model calls during tests."""

import os

os.environ.setdefault("INVISIBLEBENCH_DISABLE_LLM", "1")
