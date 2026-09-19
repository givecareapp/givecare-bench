"""Disable live model calls and judge every test scan against the fixture checks."""

import os
from pathlib import Path

import pytest

os.environ.setdefault("INVISIBLEBENCH_DISABLE_LLM", "1")

FIXTURE_CHECKS = Path(__file__).resolve().parent / "fixtures" / "checks"
PUBLISHED_CHECKS = Path(__file__).resolve().parents[2] / "checks"


@pytest.fixture(autouse=True, scope="session")
def fixture_checks():
    """Point the check registry at three stable fixture checks.

    The published checks change with the corpus. Tests about planning, the
    ledger, scoring, and the Jury Card need a registry that does not. The
    session scope keeps the patch in place for fixtures built once per module.
    """
    from _pytest.monkeypatch import MonkeyPatch

    from invisiblebench.evaluation import check_registry

    patch = MonkeyPatch()
    patch.setattr(check_registry, "CHECKS_DIR", FIXTURE_CHECKS)
    yield
    patch.undo()


@pytest.fixture
def published_checks(monkeypatch):
    """Read the real `checks/` directory, for tests about the published corpus."""
    from invisiblebench.evaluation import check_registry

    monkeypatch.setattr(check_registry, "CHECKS_DIR", PUBLISHED_CHECKS)
    return PUBLISHED_CHECKS
