"""Shared rich Console construction policy for CLI surfaces.

One decision site for color/terminal behavior: honor the NO_COLOR env var
and non-tty stdout, and disable rich's automatic highlighting.
"""
from __future__ import annotations

import os
import sys

try:
    from rich.console import Console as _RichConsole
except ImportError:
    _RichConsole = None  # type: ignore


def no_color() -> bool:
    """Honor NO_COLOR env var and non-tty stdout."""
    return bool(os.environ.get("NO_COLOR")) or not sys.stdout.isatty()


def make_console(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Build a rich Console honoring NO_COLOR / isatty, or None without rich."""
    if _RichConsole is None:
        return None
    kwargs.setdefault("no_color", no_color())
    kwargs.setdefault("force_terminal", not no_color())
    kwargs.setdefault("highlight", False)
    return _RichConsole(*args, **kwargs)
