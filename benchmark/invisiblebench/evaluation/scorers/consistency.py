"""Deterministic intra-conversation consistency scorer."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from invisiblebench.scoring.consistency import ConsistencyChecker


def score(
    transcript: List[Dict[str, Any]],
    scenario: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Score consistency by tracking assistant claims across turns."""
    _ = scenario
    checker = ConsistencyChecker()
    checker.process_transcript(transcript)
    return checker.build_result()
