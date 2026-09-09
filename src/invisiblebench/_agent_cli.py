"""CLI health checks, confirmation, and JSON output."""
from __future__ import annotations

import json
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

__all__ = [
    "DoctorCheck",
    "doctor_runner",
    "confirm_or_abort",
    "emit_json",
    "is_tty",
]


def is_tty() -> bool:
    """True if stdout is a real terminal."""
    return sys.stdout.isatty()


@dataclass
class DoctorCheck:
    name: str
    check: Callable[[], bool]
    hint: str | None = None  # printed on failure


def doctor_runner(checks: Iterable[DoctorCheck | tuple], *, exit_on_fail: bool = True) -> int:
    """Run doctor checks, print status, exit nonzero on any failure.

    Each check is a DoctorCheck or a tuple (name, check_fn[, hint]).
    Returns the exit code (0 = all pass).
    """
    normalized: list[DoctorCheck] = []
    for item in checks:
        if isinstance(item, DoctorCheck):
            normalized.append(item)
        else:
            name = item[0]
            fn = item[1]
            hint = item[2] if len(item) > 2 else None
            normalized.append(DoctorCheck(name=name, check=fn, hint=hint))

    failures = 0
    width = max((len(c.name) for c in normalized), default=0)
    for c in normalized:
        try:
            ok = bool(c.check())
        except Exception as e:
            ok = False
            err_hint = f"{c.hint or ''} ({e})".strip()
        else:
            err_hint = c.hint or ""
        mark = "PASS" if ok else "FAIL"
        line = f"  [{mark}] {c.name.ljust(width)}"
        if not ok and err_hint:
            line += f"  — {err_hint}"
        print(line, file=sys.stderr)
        if not ok:
            failures += 1

    if failures:
        print(f"\ndoctor: {failures} check(s) failed", file=sys.stderr)
        if exit_on_fail:
            sys.exit(1)
        return 1
    print("\ndoctor: all checks passed", file=sys.stderr)
    return 0



def confirm_or_abort(
    prompt: str,
    *,
    dry_run: bool = False,
    yes: bool = False,
    force: bool = False,
    destructive: bool = False,
    preview: str | None = None,
    cost_estimate: str | None = None,
) -> bool:
    """Gate a mutation.

    - dry_run=True: print the preview + intended action to stderr, return False
      (caller should NOT execute).
    - yes=True: bypass interactive prompt, return True (execute).
    - destructive=True: refuse to run without force=True even when yes=True.
    - Otherwise: print prompt (+ optional cost), read y/N from stdin.

    Returns True when the caller should proceed.
    """
    if preview:
        print(f"[preview]\n{preview}", file=sys.stderr)
    if cost_estimate:
        print(f"[cost] {cost_estimate}", file=sys.stderr)

    if dry_run:
        print(f"[dry-run] would: {prompt}", file=sys.stderr)
        return False

    if destructive and not force:
        print(
            f"[refused] {prompt} — destructive op requires --force",
            file=sys.stderr,
        )
        raise SystemExit(2)

    if yes:
        return True

    # interactive
    if not is_tty():
        print(
            f"[refused] {prompt} — non-interactive shell; pass --yes to confirm",
            file=sys.stderr,
        )
        raise SystemExit(2)
    try:
        reply = input(f"{prompt} [y/N] ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\n[aborted]", file=sys.stderr)
        raise SystemExit(130) from None
    if reply not in {"y", "yes"}:
        print("[aborted]", file=sys.stderr)
        raise SystemExit(130)
    return True



def emit_json(
    *,
    status: str = "ok",
    command: str,
    data: Any = None,
    error: str | None = None,
) -> None:
    """Write a {status, command, data} envelope to stdout.

    Canonical shape lifted from phantom-loom. No ANSI, no indent by default
    (agents parse, humans pipe to `jq`).
    """
    payload: dict[str, Any] = {"status": status, "command": command}
    if data is not None:
        payload["data"] = data
    if error is not None:
        payload["error"] = error
    sys.stdout.write(json.dumps(payload, separators=(",", ":"), default=str) + "\n")
    sys.stdout.flush()
