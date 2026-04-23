#!/usr/bin/env python3
"""Batch-tag scenarios with failure_mode_tags + eligible_modes.

Additive — never overwrites scenarios that already have `failure_mode_tags`.
Infers tags from scenario_id, category/tier, title, risk_triggers cues,
rubric/expected_behaviors text.

Tag surface matches eligibility conditions in benchmark/configs/failure_modes.yaml.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

REPO = pathlib.Path("/home/deploy/gc-repos/givecare-bench")
SCEN = REPO / "benchmark/scenarios"


# Mode groupings for quick eligibility mapping
MODE_GROUPS = {
    "f_boundary_universal": [
        # These apply to essentially any assistant response
        "IB-F1-feelings-claim",
        "IB-F1-body-presence",
        "IB-F1-human-identity",
        "IB-F2-availability-promise",
        "IB-F2-exclusivity",
        "IB-F3-false-memory",
        "IB-F3-capability-overclaim",
    ],
    "c_voice_universal": [
        "IB-C3-coercive-imperatives",
        "IB-C3-conditional-threats",
        "IB-C3-clinical-template-openers",
    ],
    "crisis_core": [
        "IB-A1", "IB-A7", "IB-A8",
        "IB-C1",
        "IB-D3-self-sacrifice-affirmation",
    ],
    "direct_crisis": ["IB-A2"],
    "cr_harm": ["IB-A3"],
    "elder_abuse": ["IB-A4"],
    "acute_medical": ["IB-A5"],
    "financial_exploit": ["IB-A6"],
    "scope_medical": ["IB-B1", "IB-B2"],
    "hipaa_proxy": ["IB-B3", "IB-B4"],
    "ai_identity": ["IB-B5", "IB-B7"],
    "clinical_memory": ["IB-B8"],
    "long_session": ["IB-B6", "IB-F2-dependency-escalation"],
    "emotional_disclosure": [
        "IB-C1", "IB-C2-recognition-missing",
        "IB-C2-advice-before-validation", "IB-C2-minimizing",
        "IB-D2-infodump",
    ],
    "practical_ask": [
        "IB-D1-zone-mismatch", "IB-D2-validation-only",
        "IB-D2-barrier-ignored", "IB-C2-options-closed",
    ],
    "self_sacrifice": ["IB-D3-self-sacrifice-affirmation"],
    "pushback": ["IB-D3-retraction-under-pushback"],
    "institutional": ["IB-D4-institutional-allegiance"],
    "cr_autonomy": ["IB-D4-cr-endangerment"],
    "cultural": ["IB-C2-othering"],
    "benefits": [
        "IB-E1-program-invention", "IB-E2-beneficiary-confusion",
        "IB-E3-wrong-jurisdiction", "IB-E4-entitlement-overclaim",
        "IB-E5-no-verification-path", "IB-E6-work-leave-confusion",
    ],
}


def infer_tags(scenario: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Return (failure_mode_tags, eligible_modes) for a scenario."""
    scenario_id = (scenario.get("scenario_id") or "").lower()
    title = (scenario.get("title") or "").lower()
    category = (scenario.get("category") or scenario.get("tier") or "").lower()
    description = (scenario.get("description") or "").lower()

    # Flatten everything scannable
    scannable_parts: list[str] = [scenario_id, title, description]

    # risk_triggers can be strings or dicts
    for rt in scenario.get("risk_triggers") or []:
        if isinstance(rt, str):
            scannable_parts.append(rt.lower())
        elif isinstance(rt, dict):
            for k in ("cue", "name", "description", "type", "trigger", "id"):
                v = rt.get(k)
                if isinstance(v, str):
                    scannable_parts.append(v.lower())

    # rubric and expected_behaviors
    scannable_parts.append(json.dumps(scenario.get("rubric") or {}).lower())
    scannable_parts.append(json.dumps(scenario.get("autofail_rubric") or {}).lower())
    for eb in scenario.get("expected_behaviors") or []:
        if isinstance(eb, str):
            scannable_parts.append(eb.lower())
        else:
            scannable_parts.append(json.dumps(eb).lower())

    # Turn content (user turns only — capture what caregiver said)
    for t in scenario.get("turns") or []:
        if isinstance(t, dict) and (t.get("role") == "user" or t.get("who") == "user"):
            txt = t.get("content") or t.get("text") or ""
            if isinstance(txt, str):
                scannable_parts.append(txt.lower()[:500])

    # Probes
    for p in scenario.get("probes") or []:
        if isinstance(p, dict):
            scannable_parts.append(json.dumps(p).lower()[:500])

    text = " ".join(scannable_parts)

    tags: set[str] = set()
    modes: set[str] = set(MODE_GROUPS["f_boundary_universal"])  # always-applicable F mass
    modes.update(MODE_GROUPS["c_voice_universal"])  # always-applicable C3

    # ---- Crisis/safety tags ----
    if any(k in text for k in [
        "cssrs", "passive_sms", "wish i", "wish to be dead",
        "not wake up", "fall asleep and not wake",
        "not worth living", "disappear", "tired of being alive",
    ]):
        tags.update(["passive_ideation", "cssrs", "masked_crisis"])
        modes.update(MODE_GROUPS["crisis_core"])

    if any(k in text for k in [
        "direct_ideation", "kill myself", "end my life",
        "want to die", "suicide",
    ]):
        tags.update(["direct_ideation"])
        modes.update(MODE_GROUPS["crisis_core"])
        modes.update(MODE_GROUPS["direct_crisis"])

    if any(k in text for k in [
        "indirect", "bridge", "dual_concern", "masked",
    ]):
        tags.update(["masked_crisis", "indirect_self_harm"])
        modes.update(MODE_GROUPS["crisis_core"])

    if any(k in text for k in [
        "shake him", "shake her", "hit him", "hit her",
        "harm him", "caregiver_violence", "cr_harm",
    ]):
        tags.update(["caregiver_to_cr_harm_intent", "caregiver_violence_risk"])
        modes.update(MODE_GROUPS["cr_harm"])

    if any(k in text for k in [
        "elder abuse", "neglect", "unsafe caregiving", "aps",
    ]):
        tags.update(["elder_abuse_signal", "neglect_signal"])
        modes.update(MODE_GROUPS["elder_abuse"])

    if any(k in text for k in [
        "chest pain", "stroke", "overdose", "poison",
        "can't breathe", "unresponsive", "acute_medical",
    ]):
        tags.update(["acute_medical_symptom"])
        modes.update(MODE_GROUPS["acute_medical"])

    if any(k in text for k in [
        "financial exploitation", "coerced", "scam",
        "financial abuse", "elder fraud",
    ]):
        tags.update(["financial_exploitation", "coerced_unpaid_labor"])
        modes.update(MODE_GROUPS["financial_exploit"])

    # ---- Scope/compliance tags ----
    if any(k in text for k in [
        "symptom", "diagnos", "medical discussion", "clinical",
        "medication", "treatment", "dose",
    ]):
        tags.update(["symptom_description", "medical_discussion"])
        modes.update(MODE_GROUPS["scope_medical"])
    if "medication" in text or "prescri" in text:
        tags.add("medication_question")
    if "treatment" in text or "therapy" in text:
        tags.add("treatment_question")

    if any(k in text for k in [
        "hipaa", "proxy", "authori", "records access", "power of attorney", "poa",
    ]):
        tags.update(["proxy_access_question", "hipaa_context", "records_access"])
        modes.update(MODE_GROUPS["hipaa_proxy"])

    if any(k in text for k in [
        "are you real", "are you human", "are you a person",
        "ai_identity", "identity_probe", "is this a real",
    ]):
        tags.update(["ai_identity_probe", "human_check_question"])
        modes.update(MODE_GROUPS["ai_identity"])

    if any(k in text for k in [
        "therapist", "licensed", "professional_identity",
        "clinician", "credential",
    ]):
        tags.update(["professional_identity_probe", "clinical_context"])
        modes.update(MODE_GROUPS["ai_identity"])
        modes.update(MODE_GROUPS["clinical_memory"])

    if any(k in text for k in [
        "long session", "3 hour", "multi_session", "session_continuity",
        "weeks", "across sessions",
    ]):
        tags.update(["long_session_3hr_plus", "ai_companion_context", "multi_session"])
        modes.update(MODE_GROUPS["long_session"])

    # ---- Communication/emotional tags ----
    if any(k in text for k in [
        "emotional", "distress", "overwhelmed", "breakdown", "burnout",
        "grief", "weeping", "crying", "tears",
    ]):
        tags.update(["emotional_disclosure", "emotional_ask",
                     "caregiver_burden_disclosure", "distress_disclosure"])
        modes.update(MODE_GROUPS["emotional_disclosure"])

    if any(k in text for k in [
        "burden", "exhaustion", "strain", "overwhelmed", "fumes",
        "running on empty", "can't keep up",
    ]):
        tags.update(["caregiver_burden_disclosure"])
        modes.update(MODE_GROUPS["emotional_disclosure"])

    if any(k in text for k in [
        "how do i", "where do i", "who do i call", "what should i",
        "practical", "next step", "help me find",
    ]):
        tags.update(["practical_ask", "action_request", "decision_turn"])
        modes.update(MODE_GROUPS["practical_ask"])

    if any(k in text for k in [
        "self_sacrifice", "handle it alone", "my needs don't",
        "should be able to handle", "i don't deserve",
        "selfish to", "not the sick one",
    ]):
        tags.update(["self_sacrifice_statement", "caregiver_self_neglect"])
        modes.update(MODE_GROUPS["self_sacrifice"])

    if any(k in text for k in [
        "i'm a terrible", "i'm failing", "i'm a bad", "i'm a failure",
        "caregiver_self_blame", "self_diminish",
    ]):
        tags.update(["caregiver_self_blame", "self_diminishment_turn"])
        modes.update(["IB-C1"])

    if any(k in text for k in [
        "pushback", "adversarial_reframe", "you're wrong",
        "disagree", "changed my mind",
    ]):
        tags.add("pushback_turn")
        modes.update(MODE_GROUPS["pushback"])

    if any(k in text for k in [
        "insurance", "hospital policy", "payer", "employer",
        "hr", "benefits administrator",
    ]):
        tags.add("institutional_conflict")
        modes.update(MODE_GROUPS["institutional"])

    if any(k in text for k in [
        "override", "restrain", "manipulate", "deceive",
        "take the keys", "lock him in", "lock her in",
        "cr_autonomy",
    ]):
        tags.update(["cr_autonomy_conflict", "restraint_question"])
        modes.update(MODE_GROUPS["cr_autonomy"])

    if any(k in text for k in [
        "asian", "latino", "hispanic", "black", "white",
        "lgbtq", "cultural", "heritage", "tradition",
        "immigrant", "kinship", "familismo",
    ]):
        tags.update(["cultural_context", "demographic_disclosure"])
        modes.update(MODE_GROUPS["cultural"])

    # ---- Benefits tags ----
    if any(k in text for k in [
        "benefit", "medicaid", "medicare", "nfcsp", "hcbs",
        "waiver", "fmla", "pfml", "pfl", "ihss", "cdpap",
        "eligibility", "assistance program",
    ]):
        tags.update(["benefits_question", "program_ask", "eligibility_ask"])
        modes.update(MODE_GROUPS["benefits"])

    if any(k in text for k in [
        "working caregiver", "employment", "job", "work schedule",
        "leave of absence", "parental leave", "family leave",
    ]):
        tags.add("working_caregiver_context")
        modes.add("IB-E6-work-leave-confusion")

    # ---- Stated barriers ----
    if any(k in text for k in [
        "can't afford", "no money", "limited income", "budget",
        "geographic", "no transport", "time constraint",
        "can't drive", "no car", "rural",
    ]):
        tags.update(["stated_constraint", "barrier_disclosure"])
        modes.add("IB-D2-barrier-ignored")

    # ---- Category-based fallbacks ----
    if category == "safety":
        pass  # safety modes already matched by content patterns above
    if category == "empathy":
        tags.update(["emotional_disclosure", "caregiver_burden_disclosure"])
        modes.update(MODE_GROUPS["emotional_disclosure"])
    if category == "context":
        tags.add("cultural_context")
        modes.update(MODE_GROUPS["cultural"])
    if category == "continuity":
        tags.update(["multi_session", "long_session"])
        modes.update(MODE_GROUPS["long_session"])

    return sorted(tags), sorted(modes)


def main():
    modified = 0
    skipped = 0
    no_change = 0
    for p in sorted(SCEN.rglob("*.json")):
        if "SCENARIO_SCHEMA" in p.name:
            continue
        with open(p) as f:
            try:
                scenario = json.load(f)
            except json.JSONDecodeError:
                skipped += 1
                continue

        if scenario.get("failure_mode_tags"):
            no_change += 1
            continue

        tags, modes = infer_tags(scenario)
        if not tags:
            tags = ["emotional_disclosure"]  # default fallback
        if not modes:
            modes = MODE_GROUPS["f_boundary_universal"]

        scenario["failure_mode_tags"] = tags
        scenario["eligible_modes"] = modes

        with open(p, "w") as f:
            json.dump(scenario, f, indent=2, ensure_ascii=False)

        modified += 1
        print(f"  [ok] {p.relative_to(SCEN)}: {len(tags)} tags, {len(modes)} modes")

    print(f"\n  Modified: {modified} | Already tagged: {no_change} | Skipped: {skipped}")


if __name__ == "__main__":
    main()
