# InvisibleBench Ontology

Diátaxis: explanation

InvisibleBench measures a caregiver-AI's **Safety** (the hard lines it must not cross) and its **Care** (how it shows up for the caregiver). The name carries the thesis — surfacing what stays *invisible* everywhere else: harms a usefulness score can't see, and relational quality no other benchmark measures.

The taxonomy is **MECE** — mutually exclusive (every failure-mode *type* has exactly one home) and collectively exhaustive (the nine dimensions together cover the caregiver-AI failure surface). MECE is a property of the *taxonomy*; a single response can still trip checks in several dimensions.

Two **orthogonal axes**:
- **Layer** — Safety (falsifiable prohibitions → violation **RATES**, claims) vs Care (gradients → **DISTRIBUTIONS**, directional). No composite; the two are reported side by side.
- **Maturity** — each dimension is **calibrated** (κ → carries claims), **provisional** (directional, labeled), or **to-author** (named gap). The comprehensive structure ships now; calibration fills in over releases. This is where v1/v2 lives — not in *which dimensions exist*, but in *which cells are calibrated enough to claim*.

## Safety — 4 lines · partition: which hard line did it cross?

| Line | Must not… | Maturity (today) |
|---|---|---|
| **Crisis** | miss/mishandle acute danger (caregiver *or* recipient) | partial κ (A1, A8) → else provisional |
| **Scope** | exceed its authority — diagnose, prescribe, legal/financial directives, false credentials | provisional |
| **Identity** | misrepresent what it is — human / memory / availability / feelings | partial κ (F3) → provisional |
| **Autonomy** | override a person's agency — *recipient* (deception/coercion/restraint) or *caregiver* (coercion/threats/foreclosure) | to-author (thin) |

## Care — 5 qualities · partition: which aspect of the caregiver's experience?

| Quality | Construct | Maturity |
|---|---|---|
| **Belonging** | seen/valued as a worthy individual with legitimate needs | v1 calibration target |
| **Attunement** | met in their emotional state (register/presence/depth) | provisional |
| **Trauma-awareness** | responded trauma-informed | to-author (v2 · SAMHSA) |
| **Relational** | honored the caregiver↔recipient bond (the dyad) | provisional (thin) |
| **Advocacy** | took the caregiver's side vs systems/institutions | to-author (thin) |

The 3-party **dyad** maps across both layers: recipient-harm *acts* → **Autonomy** (Safety); the relationship *bond* → **Relational** (Care).

## Framework grounding

The dimensions are not improvised — they operationalize **GiveCare's Design Charter** (`~/agents/wiki/givecare/givecare-design-charter.md`), which synthesizes three recognized frameworks: **SAMHSA** trauma-informed care (6 principles: safety, trust, peer support, collaboration, empowerment, cultural sensitivity), **Microsoft Inclusive Design**, and the **Othering & Belonging Institute (OBI)** Targeted Universalism. InvisibleBench measures whether a model upholds the same principles the product is designed to — the way RubRIX anchors in Tronto's care ethics, but with a three-framework synthesis already operationalized in `gc-sms`.

| Dimension | Framework grounding | Charter principle |
|---|---|---|
| Safety · Crisis | SAMHSA — *safety* | P1 Predictable Safety |
| Safety · Scope | regulatory (WOPR Act) + SAMHSA — *trust* | P2 Radical Transparency |
| Safety · Identity | SAMHSA — *trust* | P2 Radical Transparency |
| Safety · Autonomy | SAMHSA — *empowerment* + OBI — *agency* | P3 Shared Agency |
| Care · Belonging | OBI — Inclusion + Recognition + Agency + Connection (`belonging-design.md`) | P3 / P6 |
| Care · Attunement | SAMHSA — *safety/trust/empowerment* + Inclusive Design (cognitive/emotional states) | P1 / P7 |
| Care · Trauma-awareness | SAMHSA — all six principles (the foundation ring) | P1 |
| Care · Relational | OBI — *Connection* + SAMHSA — *peer support* | P4 Peer & Community Scaffold |
| Care · Advocacy | OBI — power-aware Targeted Universalism | P6 Power-Aware Co-Creation |

Each Care rubric grounds in its framework: **Belonging → OBI** (done, `internal/belonging-rubric-v3.md`); **Trauma-awareness → SAMHSA's six** (when authored, v2); the OBI **Inclusion** and **Connection** facets — the v2 enrichment of Belonging — are already charter principles (P5 Inclusive Defaults, P4 Peer & Community Scaffold).

## Conventions

- Checks labeled `Dimension: descriptor` (e.g. `Scope: gave-diagnosis`, `Belonging: othering`); stable slug IDs under the hood.
- Safety → rates (claims, calibration-gated). Care → distributions (directional). No `overall_score` ranking key.
- **Out of scope, deliberately** (to stay exhaustive *of our domain* without bloat): usefulness/helpfulness — the medical-QA / RubRIX lane. We measure *safety + care*, not whether the advice was useful.

## old → new map

A → Crisis · B + harmful-clinical-advice (D) → Scope · F → Identity · recipient-harm + caregiver-coercion → Autonomy · C(othering/self-worth/self-sacrifice) → Belonging · C(emotional) → Attunement · trauma → Trauma-awareness · dyad-bond → Relational · institutional-allegiance → Advocacy. **Dropped (usefulness, out of scope):** zone-mismatch, barrier-ignored, validation-only.
