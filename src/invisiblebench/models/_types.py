"""Shared type aliases for the benchmark runtime.

These aliases give names to dict/list shapes that recur across many modules.
They are intentionally *aliases*, not TypedDicts, because the underlying data
comes from JSON/YAML and flows through many boundaries where strict structural
typing would require pervasive validation boilerplate for no safety gain.

Import from ``invisiblebench.models`` (which re-exports everything here).
"""

from __future__ import annotations

from typing import Any

# -- Generic JSON alias (replaces module-local ``JsonMap``) --
JsonMap = dict[str, Any]

# -- Transcript: ordered turn list [{"role": ..., "turn": ..., "content": ...}]
Transcript = list[dict[str, Any]]

# -- Raw scenario JSON before Pydantic model parsing --
ScenarioData = dict[str, Any]

# -- Flat result row (one scenario x one model) as carried by results_io / stats --
ResultRow = dict[str, Any]

# -- check definition (checks/<ID>.yaml) for one mode --
ModeConfig = dict[str, Any]

# -- routing block (checks/<ID>.yaml `routing:`) for one mode --
RoutingConfig = dict[str, Any]

# -- Chat message {"role": ..., "content": ...} used in API call signatures --
ChatMessage = dict[str, str]
