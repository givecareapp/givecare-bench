"""GiveCare orchestrator harness.

Runs benchmark scenarios directly against the @givecare/pi-orchestrator package via a
benchmark-owned runtime adapter, avoiding Convex/live SMS noise.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from invisiblebench.evaluation.branching import resolve_branch
from invisiblebench.models.scenario import ScenarioModel
from invisiblebench.utils.turn_index import get_turn_index

DEFAULT_ORCHESTRATOR_MODEL = os.environ.get(
    "GIVECARE_ORCHESTRATOR_MODEL", "gemini-3.1-flash-lite-preview"
)

MODEL_NAME_PREFIX = "GiveCare Orchestrator"
MODEL_ID_PREFIX = "givecare/orchestrator"
PROVIDER_NAME = "givecare"
PROVIDER_VERSION = "1.0.0"


def get_model_label(model_name: str) -> str:
    return f"{MODEL_NAME_PREFIX} ({model_name})"


def get_model_id(model_name: str) -> str:
    return f"{MODEL_ID_PREFIX}:{model_name}"


def _project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()


def _adapter_root() -> Path:
    return _project_root() / "benchmark" / "adapters" / "givecare-orchestrator"


def _bridge_build_script() -> Path:
    return _adapter_root() / "build.mjs"


def _bridge_bundle() -> Path:
    return _adapter_root() / "dist" / "bridge.cjs"


def _mono_root() -> Path:
    return _project_root().parent / "give-care-mono"


def _collect_source_paths() -> List[Path]:
    paths = [
        _bridge_build_script(),
        _adapter_root() / "src" / "bridge.ts",
        _mono_root() / "packages" / "pi-orchestrator" / "src",
        _mono_root() / "packages" / "care-domain" / "src",
    ]
    collected: List[Path] = []
    for path in paths:
        if not path.exists():
            continue
        if path.is_dir():
            collected.extend(p for p in path.rglob("*") if p.is_file())
        else:
            collected.append(path)
    return collected


def ensure_bridge_bundle() -> Path:
    """Build the GiveCare orchestrator bridge bundle if missing/stale."""
    bundle = _bridge_bundle()
    build_script = _bridge_build_script()
    if not build_script.exists():
        raise RuntimeError(f"Bridge build script not found: {build_script}")

    source_paths = _collect_source_paths()
    latest_src_mtime = max(path.stat().st_mtime for path in source_paths)
    if bundle.exists() and bundle.stat().st_mtime >= latest_src_mtime:
        return bundle

    result = subprocess.run(
        ["node", str(build_script)],
        cwd=str(_project_root()),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Failed to build GiveCare orchestrator bridge\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    if not bundle.exists():
        raise RuntimeError(f"Bridge bundle was not produced: {bundle}")
    return bundle


def bridge_healthcheck() -> Dict[str, Any]:
    """Run a no-op healthcheck against the bridge bundle."""
    bundle = ensure_bridge_bundle()
    result = subprocess.run(
        ["node", str(bundle)],
        input=json.dumps({"command": "healthcheck"}),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "Bridge healthcheck failed")
    return json.loads(result.stdout.strip() or "{}")


def _slugify(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value)


def _risk_level_for_turn(scenario: ScenarioModel, turn_number: int) -> str:
    severity_rank = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    risk_level = "low"
    for trigger in scenario.risk_triggers:
        if not isinstance(trigger, dict):
            continue
        trigger_turn = get_turn_index(trigger) or 0
        if trigger_turn <= turn_number:
            severity = str(trigger.get("severity", "low")).lower()
            if severity_rank.get(severity, 0) > severity_rank.get(risk_level, 0):
                risk_level = severity
    return risk_level


def _turns_for_scenario(scenario: ScenarioModel) -> List[Dict[str, Any]]:
    if scenario.sessions:
        turns: List[Dict[str, Any]] = []
        for session in scenario.sessions:
            for turn in session.turns:
                turns.append(turn.model_dump())
        return turns
    return [turn.model_dump() for turn in scenario.turns]


def _memory_dict(memories: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for memory in memories:
        key = str(memory.get("key", ""))
        if key:
            out[key] = {
                "key": key,
                "value": str(memory.get("value", "")),
                "confidence": float(memory.get("confidence", 0.5)),
            }
    return out


def _apply_fact_assignments(memory_state: Dict[str, Dict[str, Any]], assignments: List[str]) -> None:
    for item in assignments:
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        memory_state[key] = {"key": key, "value": value, "confidence": 1.0}


def _conversation_seed(scenario: ScenarioModel) -> Dict[str, Any]:
    persona = scenario.persona
    memory_state: Dict[str, Dict[str, Any]] = {}
    for key, value in {
        "caregiver_name": persona.name,
        "caregiver_role": persona.role or "caregiver",
        "care_recipient": persona.care_recipient,
        "care_duration": persona.care_duration,
    }.items():
        if value:
            memory_state[key] = {"key": key, "value": str(value), "confidence": 0.9}
    return {
        "memory_state": memory_state,
        "recent_messages": [],
        "followups": [],
        "critical_events": [],
        "alerts": [],
        "diagnostics": [],
        "assessment_runs": [],
        "eligibility_facts": [],
        "bootstrap_patches": [],
        "resource_offers": [],
        "resource_lookups": [],
        "nearby_queries": [],
        "screenings_run": [],
        "conversation_state": {
            "currentLoop": "activeSupport",
            "currentStage": "ongoing-support",
            "pendingPromptType": None,
            "pendingPromptInstrument": None,
            "assessmentOverdue": False,
            "benefitsScreeningDue": False,
            "sdoh30Due": False,
            "flaggedZoneCount": 0,
            "openAssessment": None,
            "cadence": {"hasSdoh6": False, "hasSdoh30": False, "flaggedZoneCount": 0},
            "skillDiscovery": None,
            "skillDiscoveryText": None,
            "zipCode": None,
            "latitude": None,
            "longitude": None,
            "bootstrapNeededFacts": [],
            "bootstrapCollectedFacts": [],
            "scoreSnapshot": None,
        },
    }


def _build_bridge_payload(
    *,
    model_name: str,
    state: Dict[str, Any],
    incoming_text: str,
    turn_number: int,
    scenario: ScenarioModel,
) -> Dict[str, Any]:
    conv = state["conversation_state"]
    return {
        "command": "run_turn",
        "modelName": model_name,
        "conversation": {
            "caregiverId": f"bench_cg_{scenario.scenario_id}",
            "conversationId": f"bench_conv_{scenario.scenario_id}",
            "inboundMessageId": f"bench_msg_{scenario.scenario_id}_{turn_number}",
            "currentLoop": conv["currentLoop"],
            "currentStage": conv["currentStage"],
            "riskLevel": _risk_level_for_turn(scenario, turn_number),
            "memory": list(state["memory_state"].values()),
            "recentMessages": state["recent_messages"],
            "incomingText": incoming_text,
            "skillDiscovery": conv["skillDiscovery"],
            "pendingPromptType": conv["pendingPromptType"],
            "pendingPromptInstrument": conv["pendingPromptInstrument"],
            "assessmentOverdue": conv["assessmentOverdue"],
            "benefitsScreeningDue": conv["benefitsScreeningDue"],
            "sdoh30Due": conv["sdoh30Due"],
            "flaggedZoneCount": conv["flaggedZoneCount"],
            "openAssessment": conv["openAssessment"],
            "cadence": conv["cadence"],
            "skillDiscoveryText": conv["skillDiscoveryText"],
            "zipCode": conv["zipCode"],
            "latitude": conv["latitude"],
            "longitude": conv["longitude"],
            "bootstrapNeededFacts": conv["bootstrapNeededFacts"],
            "bootstrapCollectedFacts": conv["bootstrapCollectedFacts"],
            "scoreSnapshot": conv["scoreSnapshot"],
        },
        "fixtures": {
            "resources": [
                {
                    "title": "Caregiver support line",
                    "description": "Deterministic benchmark fixture resource",
                    "url": "https://example.com/support",
                    "phone": "800-555-0100",
                }
            ],
            "nearbyResourcesSummary": "Found benchmark fixture support options nearby.",
        },
    }


def _apply_bridge_effects(state: Dict[str, Any], bridge_output: Dict[str, Any]) -> None:
    effects = bridge_output.get("runtimeEffects", {}) if isinstance(bridge_output, dict) else {}
    if not isinstance(effects, dict):
        return

    state["memory_state"] = _memory_dict(effects.get("memories", [])) | state["memory_state"]
    # Last write wins — update with most recent runtime memories.
    state["memory_state"].update(_memory_dict(effects.get("memories", [])))

    for key, target in (
        ("followups", "followups"),
        ("criticalEvents", "critical_events"),
        ("alerts", "alerts"),
        ("diagnostics", "diagnostics"),
        ("assessmentRuns", "assessment_runs"),
        ("eligibilityFacts", "eligibility_facts"),
        ("bootstrapPatches", "bootstrap_patches"),
        ("resourceOffers", "resource_offers"),
        ("resourceLookups", "resource_lookups"),
        ("nearbyQueries", "nearby_queries"),
        ("screeningsRun", "screenings_run"),
    ):
        values = effects.get(key)
        if isinstance(values, list):
            state[target].extend(values)


def _call_bridge(payload: Dict[str, Any]) -> Dict[str, Any]:
    bundle = ensure_bridge_bundle()
    result = subprocess.run(
        ["node", str(bundle)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=120,
    )
    stdout = result.stdout.strip()
    if not stdout:
        raise RuntimeError(result.stderr.strip() or "Bridge returned no output")
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid bridge JSON output: {stdout}") from e
    if result.returncode != 0 or not data.get("ok"):
        raise RuntimeError(str(data.get("error") or result.stderr.strip() or "Bridge failed"))
    return data


def run_scenario(
    model_name: str,
    scenario_path: str,
    output_dir: Path,
    verbose: bool = False,
) -> Tuple[Path, Dict[str, Any]]:
    """Run a single scenario against the GiveCare orchestrator bridge."""
    scenario = ScenarioModel.from_file(scenario_path)
    scenario_id = scenario.scenario_id
    turns = _turns_for_scenario(scenario)
    state = _conversation_seed(scenario)

    transcript: List[Dict[str, Any]] = []
    prev_assistant_msg: Optional[str] = None

    for turn in turns:
        turn_number = int(turn.get("turn_number", turn.get("t", 0)))
        _apply_fact_assignments(state["memory_state"], turn.get("facts", []))
        _apply_fact_assignments(state["memory_state"], turn.get("updates", []))

        user_msg, branch_id = resolve_branch(turn, prev_assistant_msg)
        if verbose:
            branch_label = f" [branch:{branch_id}]" if branch_id else ""
            print(f"[{turn_number}] User{branch_label}: {user_msg}")

        user_entry: Dict[str, Any] = {"turn": turn_number, "role": "user", "content": user_msg}
        if branch_id is not None:
            user_entry["branch_id"] = branch_id
        transcript.append(user_entry)
        state["recent_messages"].append({"direction": "inbound", "text": user_msg})

        payload = _build_bridge_payload(
            model_name=model_name,
            state=state,
            incoming_text=user_msg,
            turn_number=turn_number,
            scenario=scenario,
        )

        try:
            bridge_output = _call_bridge(payload)
            assistant_text = str(bridge_output.get("assistantText", "")).strip()
            if verbose:
                print(
                    f"    Orchestrator: {assistant_text[:100]}{'...' if len(assistant_text) > 100 else ''}"
                )
            transcript.append(
                {
                    "turn": turn_number,
                    "role": "assistant",
                    "content": assistant_text,
                    "template_id": bridge_output.get("templateId"),
                    "theme_id": bridge_output.get("themeId"),
                    "stop_reason": bridge_output.get("stopReason"),
                    "tool_calls": bridge_output.get("toolCalls", []),
                    "tool_results": bridge_output.get("toolResults", []),
                    "tool_timings": bridge_output.get("toolTimings", []),
                    "runtime_effects": bridge_output.get("runtimeEffects", {}),
                }
            )
            prev_assistant_msg = assistant_text
            state["recent_messages"].append({"direction": "outbound", "text": assistant_text})
            _apply_bridge_effects(state, bridge_output)
        except Exception as e:
            error_msg = f"[ERROR: {e}]"
            if verbose:
                print(f"    ERROR: {e}")
            transcript.append(
                {
                    "turn": turn_number,
                    "role": "assistant",
                    "content": error_msg,
                    "error": True,
                }
            )
            prev_assistant_msg = None
            state["recent_messages"].append({"direction": "outbound", "text": error_msg})

    output_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = output_dir / f"{_slugify(model_name)}_{scenario_id}.jsonl"
    with open(transcript_path, "w") as f:
        for row in transcript:
            f.write(json.dumps(row) + "\n")

    scenario_data = scenario.model_dump()
    if verbose:
        print(f"Saved: {transcript_path}")
    return transcript_path, scenario_data
