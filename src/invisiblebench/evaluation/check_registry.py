"""Load the canonical checks and derive their taxonomy from file paths."""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from invisiblebench.models.scan import Check, CheckDefinition

CHECKS_DIR = Path(__file__).resolve().parents[3] / "checks"


def load_check(path: Path) -> Check:
    raw = path.read_bytes()
    definition = CheckDefinition.model_validate(yaml.safe_load(raw))
    if definition.id != path.stem:
        raise ValueError(f"check ID does not match its file name: {path}")
    return Check(
        **definition.model_dump(by_alias=True),
        layer=path.parent.parent.name,
        dimension=path.parent.name,
        definition_sha256=hashlib.sha256(raw).hexdigest(),
    )


def load_checks(checks_dir: Path | None = None) -> dict[str, Check]:
    root = checks_dir or CHECKS_DIR
    paths = sorted(path for path in root.rglob("*.yaml") if not path.name.startswith("_"))
    if not paths:
        raise FileNotFoundError(f"No checks found under {root}")
    checks = {}
    for path in paths:
        check = load_check(path)
        if check.id in checks:
            raise ValueError(f"Duplicate check ID: {path}")
        checks[check.id] = check
    return checks


def registered_check_ids(checks_dir: Path | None = None) -> set[str]:
    return set(load_checks(checks_dir))
