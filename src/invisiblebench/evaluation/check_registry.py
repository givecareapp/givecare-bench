"""Check registry — loads the taxonomy from `checks/`.

Checks live in a layered directory structure under `checks/`:

    checks/safety/crisis/IB-A1.yaml
    checks/care/attunement/IB-C1.yaml

`find checks/ -name '*.yaml' ! -name '_*'` is the entire taxonomy.  Each file
holds the complete identity of one check: definition, severity, scope,
eligibility, `routing:` (scorer dispatch), and — for LLM-judged checks — the
judge prompt embedded as a `prompt: |` block.  The loader splits routing back
out into the (modes, routing) pair the engine consumes.

Adding a check is adding a file; retiring one is deleting it.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from invisiblebench.models._types import ModeConfig, RoutingConfig

CHECKS_DIR = Path(__file__).resolve().parents[3] / "checks"


def load_checks(
    checks_dir: Path | None = None,
) -> tuple[dict[str, ModeConfig], dict[str, RoutingConfig]]:
    """Load all checks. Returns (modes, routing) keyed by check id."""
    root = checks_dir or CHECKS_DIR
    if not root.is_dir():
        raise FileNotFoundError(
            f"checks directory not found: {root}. "
            "The taxonomy lives in checks/<ID>.yaml (see DESIGN.md)."
        )

    modes: dict[str, ModeConfig] = {}
    routing: dict[str, RoutingConfig] = {}

    for check_file in sorted(root.rglob("*.yaml")):
        if check_file.name.startswith("_"):
            continue  # _meta.yaml and friends
        with open(check_file, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        check_id = str(data.get("id") or check_file.stem)
        if check_id != check_file.stem:
            raise ValueError(
                f"check id {check_id!r} does not match its filename "
                f"{check_file.stem!r} ({check_file})"
            )
        mode = dict(data)
        route = mode.pop("routing", {}) or {}
        modes[check_id] = mode
        routing[check_id] = route

    if not modes:
        raise FileNotFoundError(f"no checks found under {root}")
    return modes, routing


def registered_check_ids(checks_dir: Path | None = None) -> set[str]:
    """The set of check ids in the taxonomy."""
    root = checks_dir or CHECKS_DIR
    return {
        p.stem for p in root.rglob("*.yaml") if not p.name.startswith("_")
    }


def check_dimensions(checks_dir: Path | None = None) -> dict[str, dict[str, str]]:
    """Return layer + dimension metadata for each check derived from directory structure.

    Checks live at checks/<layer>/<dimension>/<id>.yaml where:
      layer      ∈ {safety, care}
      dimension  ∈ {crisis, scope, identity, autonomy}          (safety)
                 ∪ {belonging, attunement, trauma_awareness,
                    relational, advocacy}                        (care)

    Returns:
        Mapping of check_id → {"layer": <layer>, "dimension": <dimension>}.
        Checks that do not conform to the two-level structure are omitted.
    """
    root = checks_dir or CHECKS_DIR
    result: dict[str, dict[str, str]] = {}
    for check_file in sorted(root.rglob("*.yaml")):
        if check_file.name.startswith("_"):
            continue
        # Expect root/<layer>/<dimension>/<id>.yaml  (depth = 3 parts from root)
        try:
            rel = check_file.relative_to(root)
        except ValueError:
            continue
        parts = rel.parts  # e.g. ("safety", "crisis", "IB-A1.yaml")
        if len(parts) != 3:  # noqa: PLR2004
            continue
        layer, dimension = parts[0], parts[1]
        check_id = check_file.stem
        result[check_id] = {"layer": layer, "dimension": dimension}
    return result
