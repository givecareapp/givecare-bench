from __future__ import annotations

from pathlib import Path

import tomllib

import invisiblebench


def test_package_version_matches_pyproject() -> None:
    pyproject = Path("pyproject.toml")
    expected_version = tomllib.loads(pyproject.read_text())["project"]["version"]

    assert invisiblebench.__version__ == expected_version
