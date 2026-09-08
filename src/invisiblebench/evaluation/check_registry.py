"""Load the canonical criteria and derive their taxonomy from file paths."""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from invisiblebench.models.scan import Check, CheckDefinition
from invisiblebench.utils.prompt_hash import prompt_template_hash

CHECKS_DIR = Path(__file__).resolve().parents[3] / "checks"


def load_checks(checks_dir: Path | None = None) -> dict[str, Check]:
    root = checks_dir or CHECKS_DIR
    paths = sorted(path for path in root.rglob("*.yaml") if not path.name.startswith("_"))
    if not paths:
        raise FileNotFoundError(f"No checks found under {root}")
    checks = {}
    for path in paths:
        raw = path.read_bytes()
        definition = CheckDefinition.model_validate(yaml.safe_load(raw))
        if definition.id != path.stem or definition.id in checks:
            raise ValueError(f"Duplicate or mismatched check ID: {path}")
        checks[definition.id] = Check(
            **definition.model_dump(), layer=path.parent.parent.name,
            dimension=path.parent.name, definition_sha256=hashlib.sha256(raw).hexdigest(),
        )
    return checks


def registered_check_ids(checks_dir: Path | None = None) -> set[str]:
    return set(load_checks(checks_dir))


def check_definition_hashes(checks_dir: Path | None = None) -> dict[str, str]:
    return {ident: check.definition_sha256 for ident, check in load_checks(checks_dir).items()}


def check_prompt_hashes(checks_dir: Path | None = None) -> dict[str, str]:
    from invisiblebench.evaluation.judgment import prompt_for_check

    return {ident: prompt_template_hash(prompt_for_check(check))
            for ident, check in load_checks(checks_dir).items()}
