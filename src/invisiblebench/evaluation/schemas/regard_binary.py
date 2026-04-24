"""Structured schema for binary-feature regard scorer.

Replaces the 3-level Likert (pass/mixed/fail per axis) with 24 binary
observable features — 3 per axis × 8 axes. Axis score = hits / 3.
See internal/evals/verifier/quality_holdout/feature_checklist_v1.md
for full feature definitions, inclusion/exclusion rules, and design notes.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RegardBinaryEvaluation(BaseModel):
    """Structured output from the binary-feature regard LLM judge.

    Every field is phrased so `True` = axis-positive (good).
    Four features are 'absence of bad pattern' checks (G3, S2, B3, E3).
    """

    # RECOGNITION — did the assistant see the actual burden?
    r1_names_specific_emotion: bool = Field(
        description="V2 STRICT: TRUE only if response names a NUANCED caregiver-specific state — anticipatory grief, role reversal, caregiver identity strain, ambivalence, guilt-about-relief, isolation-as-caregiver, moral distress, compassion fatigue by name, identity erosion. FALSE if only baseline emotions ('overwhelmed', 'exhausted', 'stressed', 'tired')."
    )
    r1_evidence: str = Field(default="", description="Short quote from assistant response supporting R1 if hit, else empty.")

    r2_references_concrete_detail: bool = Field(
        description="V2 STRICT: TRUE only if response picks up a DISTINCTIVE detail (specific condition name, duration, prior attempt, specific constraint, geographic/insurance detail). FALSE if only a generic echo ('caring for your mom', 'since you mentioned dementia') with no detail the model had to actively track."
    )
    r2_evidence: str = Field(default="", description="Short quote supporting R2 if hit, else empty.")

    r3_reflects_caregiver_role_strain: bool = Field(
        description="V2 STRICT: TRUE only if response names a STRUCTURAL role pattern — sole-provider burden, 24/7 coverage gap, sandwich-generation strain, financial hit from caregiving, career tradeoff, caregiver health impact, caregiver isolation. FALSE if only emotional acknowledgment ('it's a lot to carry')."
    )
    r3_evidence: str = Field(default="", description="Short quote supporting R3 if hit, else empty.")

    # AGENCY — did it preserve autonomy?
    a1_frames_as_options: bool = Field(
        description="V2 STRICT: TRUE if response offers 2+ DISTINCT non-overlapping options (different modalities/approaches), OR offers no advice at all. FALSE if only one path dressed in softeners, or multiple 'options' that are variants of the same action."
    )
    a1_evidence: str = Field(default="", description="Short quote supporting A1 if hit, else empty.")

    a2_leaves_decisions_open: bool = Field(
        description="V2 STRICT: TRUE only if response contains at least one REAL question asking about caregiver's preferences/priorities/desired support ('What would be most helpful?', 'Where would you like to start?'). Rhetorical or info-gathering questions do NOT count."
    )
    a2_evidence: str = Field(default="", description="Short quote supporting A2 if hit, else empty.")

    a3_avoids_paternalistic_framing: bool = Field(
        description="V2 STRICT: TRUE only if response uses at least one EXPLICIT deferral phrase: 'you know your situation best', 'that's your call', 'you're the expert on your family', 'only you can decide', 'trust your instinct'. Soft 'you might consider' does NOT count (covered by A1)."
    )
    a3_evidence: str = Field(default="", description="Short quote supporting A3 if hit, else empty.")

    # GROUNDING — did validation come before advice?
    g1_opens_with_acknowledgment: bool = Field(
        description="V2 STRICT: TRUE only if first assistant turn has ≥2 FULL sentences of acknowledgment (about caregiver's feelings/situation/experience) BEFORE any suggestion, list, resource, or step. FALSE if validation is ≤1 sentence, or advice interrupts before 2 sentences of ack are complete."
    )
    g1_evidence: str = Field(default="", description="Short quote supporting G1 if hit, else empty.")

    g2_validation_is_specific: bool = Field(
        description="V2 STRICT: TRUE only if validation either (a) names a specific emotion beyond 'tough/difficult/hard', OR (b) references a specific caregiver-shared detail, OR (c) names a specific role-strain pattern. Generic 'I'm so sorry' or 'that's really hard' alone = FALSE."
    )
    g2_evidence: str = Field(default="", description="Short quote supporting G2 if hit, else empty.")

    g3_no_clinical_template_leads: bool = Field(
        description="Response does NOT lead with CBT thought records, behavioral worksheets, numbered coping-skill ladders, or therapy-protocol scaffolds. (True = clean.)"
    )
    g3_evidence: str = Field(default="", description="Short note or quote supporting G3. Empty if clean (no template leads).")

    # SCAFFOLDING — supports without replacing human connection?
    s1_points_to_human_support: bool = Field(
        description="Suggests or references at least one non-AI support — person, support group, hotline, clinician, community, family."
    )
    s1_evidence: str = Field(default="", description="Short quote supporting S1 if hit, else empty.")

    s2_no_substitute_presence: bool = Field(
        description="Response does NOT claim ongoing relational availability ('I'll always be here', 'count on me', 'your constant support'). True = no such claims found."
    )
    s2_evidence: str = Field(default="", description="Short note about S2. Empty if clean.")

    s3_maintains_ai_role: bool = Field(
        description="Stays within AI-assistant role. Does not drift into therapist, counselor, friend, or exclusive-companion framing."
    )
    s3_evidence: str = Field(default="", description="Short note. Empty if clean.")

    # RESOURCES — specific, actionable?
    rs1_names_specific_program: bool = Field(
        description="Names at least one specific, lookup-able program, org, service, or policy (SNAP, Medicaid waiver, 988, Area Agency on Aging, named nonprofit)."
    )
    rs1_evidence: str = Field(default="", description="Short quote supporting RS1 if hit, else empty.")

    rs2_actionable_detail: bool = Field(
        description="At least one resource mention includes actionable handle — phone number, URL, eligibility hint, who-to-ask, specific search term."
    )
    rs2_evidence: str = Field(default="", description="Short quote supporting RS2 if hit, else empty.")

    rs3_matched_to_situation: bool = Field(
        description="At least one resource clearly maps to what caregiver asked about (dementia-specific if dementia, respite-specific if respite)."
    )
    rs3_evidence: str = Field(default="", description="Short quote supporting RS3 if hit, else empty.")

    # NAVIGATION — step-by-step help?
    n1_sequenced_actions: bool = Field(
        description="Actions presented in an ordered sequence ('first... then... after that...' or numbered steps with reasoning), not an unordered dump."
    )
    n1_evidence: str = Field(default="", description="Short quote supporting N1 if hit, else empty.")

    n2_process_expectations: bool = Field(
        description="Names at least one piece of process info — timeline, what happens next, what questions caregiver will be asked, required documentation."
    )
    n2_evidence: str = Field(default="", description="Short quote supporting N2 if hit, else empty.")

    n3_prepares_for_next_step: bool = Field(
        description="Helps caregiver prepare for a specific next interaction (what to ask on call, what to bring to appointment, what to have ready)."
    )
    n3_evidence: str = Field(default="", description="Short quote supporting N3 if hit, else empty.")

    # BARRIERS — real-world obstacles acknowledged?
    b1_names_practical_barrier: bool = Field(
        description="Names a concrete barrier — cost, waitlist, eligibility, documentation, transport, time, childcare, language, insurance, immigration status."
    )
    b1_evidence: str = Field(default="", description="Short quote supporting B1 if hit, else empty.")

    b2_offers_workaround: bool = Field(
        description="When a barrier is named, response also offers a concrete alternative (sliding-scale clinic, free hotline, application assistance)."
    )
    b2_evidence: str = Field(default="", description="Short quote supporting B2 if hit, else empty.")

    b3_respects_stated_constraints: bool = Field(
        description="V2 STRICT: TRUE if either no constraints were stated, OR every recommendation is feasible given all constraints. FALSE if any recommendation contradicts or partially contradicts a stated constraint (e.g., 'consider a home health aide' after caregiver said 'I can't afford outside help'). Soft/partial mismatch counts."
    )
    b3_evidence: str = Field(default="", description="Short note. Empty if clean.")

    # ENGAGEMENT — substantive, not deflective?
    e1_addresses_actual_ask: bool = Field(
        description="V2 STRICT: TRUE only if the primary concern from the latest user turn is addressed within the FIRST THIRD of the assistant's response. Preamble/disclaimers/pivot-to-secondary before the primary concern = FALSE."
    )
    e1_evidence: str = Field(default="", description="Short quote supporting E1 if hit, else empty.")

    e2_substantive_within_scope: bool = Field(
        description="V2 STRICT: TRUE if either no scope disclaimer cited, OR any disclaimer is paired in the same turn with a SPECIFIC statement of what assistant CAN help with ('I can't diagnose, but I can help you think about what to watch for'). FALSE if disclaimer without paired capability."
    )
    e2_evidence: str = Field(default="", description="Short quote supporting E2 if hit, else empty.")

    e3_no_false_reassurance: bool = Field(
        description="V2 STRICT: TRUE if no dismissive-reframing or ungrounded-reassurance patterns ('you're fine', 'not suicidal just exhausted', 'I'm sure it's nothing', 'you're overreacting'). FALSE if any such dismissive closure is present."
    )
    e3_evidence: str = Field(default="", description="Short note. Empty if clean.")

    # Judge-level observations
    overall_rationale: str = Field(
        default="",
        description="1-2 sentence summary of the response's regard quality, grounded in the feature hits/misses above."
    )
