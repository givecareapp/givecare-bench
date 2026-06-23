# Taxonomy

Diátaxis: reference

InvisibleBench organizes 50 failure modes into a **9-dimension MECE taxonomy** — two orthogonal layers (Safety + Care) that together cover the caregiver-AI failure surface without overlap or gap.

---

## Two layers, one thesis

| Layer | What it measures | Reported as | Source of truth |
|-------|-----------------|-------------|----------------|
| **Safety** | falsifiable prohibitions — hard lines the model must not cross | violation **rates** per line | calibration-gated claims |
| **Care** | gradients — how the model shows up for the caregiver | **distributions** (directional) | provisional and to-author |

The two layers are reported side by side. There is no composite. A model can score well on Care and still fail Safety; a model can hit zero Safety violations and still show poor Care quality.

---

## Safety — 4 lines

Safety partitions by **which hard line the model crossed**. A FAIL on a Safety check is counted in its line's violation rate; severity tiers annotate how serious the violation is, but no single check gates or zeros a composite score.

| Line | Must not… | Checks | Maturity |
|------|-----------|--------|----------|
| **Crisis** | miss or mishandle acute danger (caregiver or recipient) | 10 | partial κ (A1 kappa=1.000, A8 kappa=0.747) → else provisional |
| **Scope** | exceed authority — diagnose, prescribe, legal/financial directives, false credentials | 13 | provisional (layer-level 60-trace gate gold) |
| **Identity** | misrepresent what it is — human / memory / availability / feelings | 8 | partial κ (F3 kappa=0.795) → provisional |
| **Autonomy** | override a person's agency — recipient (deception/coercion/restraint) or caregiver (coercion/foreclosure) | 4 | to-author (thin) |

**Safety total: 35 checks.**

The dyad maps into Safety: acts that harm the recipient's autonomy (deception, restraint, manipulation directives) belong to **Autonomy**.

---

## Care — 5 qualities

Care partitions by **which aspect of the caregiver's experience** the model failed. Care checks feed directional distributions, not violation rates. A FAIL on a Care check contributes to that quality's distribution — it does not produce a pass/fail gate.

| Quality | Construct | Checks | Maturity |
|---------|-----------|--------|----------|
| **Belonging** | seen and valued as a worthy individual with legitimate needs | 5 | v1 calibration target (provisional κ=0.82 inter-model) |
| **Attunement** | met in their emotional state — register, presence, depth | 8 | provisional |
| **Trauma-awareness** | responded to trauma-informed | 0 | to-author (v2, SAMHSA) |
| **Relational** | honored the caregiver↔recipient bond (the dyad) | 1 | provisional (thin) |
| **Advocacy** | took the caregiver's side vs systems and institutions | 1 | to-author (thin) |

**Care total: 15 checks.**

The dyad maps into Care too: the relationship bond between caregiver and recipient belongs to **Relational**.

---

## The dyad

No other benchmark models the 3-party structure of caregiving. InvisibleBench's most distinctive claim is that the caregiver, the care recipient, and the AI form a triad — and failures arise specifically from that structure. The dyad maps across both layers:

- **Recipient-harm acts** (advising restraint, manipulation, autonomy override) → **Safety · Autonomy**
- **The bond** (relational blindness, treating the caregiver as if the recipient doesn't exist) → **Care · Relational**

---

## How Safety differs from Care

Safety checks are falsifiable: a verifier can determine PASS or FAIL on a single transcript. The violation either happened or it didn't. Calibration at kappa >= 0.65 is required before a Safety check can carry public claims.

Care checks are gradients: how well did the model attune, belong, advocate? These produce distributions across the fleet, not binary verdicts per transcript. Provisional care checks are labeled directional; validated care checks (kappa-confirmed) carry claims.

Severity tiers (S2–S5) are annotation metadata on every check. They describe the potential harm magnitude of a violation. They do not gate any composite score. S5 and S4_GATE checks are the most serious, but their FAIL outcome is still a violation counted in the line's rate — not a multiplier that zeros another number.

---

## Framework grounding

The dimensions operationalize GiveCare's Design Charter, which synthesizes three recognized frameworks: **SAMHSA** trauma-informed care, **Microsoft Inclusive Design**, and the **Othering & Belonging Institute (OBI)** Targeted Universalism.

| Dimension | Framework grounding | Charter principle |
|-----------|---------------------|-------------------|
| Safety · Crisis | SAMHSA — safety | P1 Predictable Safety |
| Safety · Scope | Regulatory (WOPR Act) + SAMHSA — trust | P2 Radical Transparency |
| Safety · Identity | SAMHSA — trust | P2 Radical Transparency |
| Safety · Autonomy | SAMHSA — empowerment + OBI — agency | P3 Shared Agency |
| Care · Belonging | OBI — Inclusion + Recognition + Agency + Connection | P3 / P6 |
| Care · Attunement | SAMHSA — safety/trust/empowerment + Inclusive Design | P1 / P7 |
| Care · Trauma-awareness | SAMHSA — all six principles | P1 |
| Care · Relational | OBI — Connection + SAMHSA — peer support | P4 Peer & Community Scaffold |
| Care · Advocacy | OBI — power-aware Targeted Universalism | P6 Power-Aware Co-Creation |

---

## Maturity dimension

Every dimension has a maturity status. Maturity describes *which cells are calibrated enough to carry claims* — not whether the dimension exists. The comprehensive 9-dimension structure is the current model; calibration fills in over releases.

| Status | Meaning |
|--------|---------|
| **validated** | kappa >= 0.65 vs human expert labels, n >= 40; carries public claims |
| **provisional** | directional evidence exists; labeled accordingly in reports |
| **to-author** | dimension defined; checks not yet authored |

---

## Why no composite

The Safety + Care model reports two surfaces. A composite would require weighting them against each other — a design choice that hides the structure. A model that shows perfect Care while routinely missing crisis signals should not look good on a single number. Reporting separately keeps the two layers visible.

---

## Legacy (v3.1): A/B/C/D/F

_Historical provenance only. The v3.1 framework is superseded by Safety + Care._

The v3.1 benchmark organized 53 checks into 5 dimensions: A (Safety, gate), B (Compliance, gate), C (Communication, quality), D (Coordination, quality), F (Boundary integrity, quality). Gates A and B zeroed an overall composite score; C/D/F were averaged into it. That composite architecture is retired. The old → new mapping:

A → Crisis · B + harmful-clinical-advice (D) → Scope · F → Identity · recipient-harm + caregiver-coercion → Autonomy · C (othering/self-worth/self-sacrifice) → Belonging · C (emotional) → Attunement · trauma → Trauma-awareness · dyad-bond → Relational · institutional-allegiance → Advocacy. Dropped (out of scope for this benchmark): zone-mismatch, barrier-ignored, validation-only.

---

## References

- SAMHSA. *SAMHSA's Concept of Trauma and Guidance for a Trauma-Informed Approach.* HHS Publication No. (SMA) 14-4884, 2014.
- powell, john a. and Menendian, S. *Belonging without Othering.* Stanford University Press, 2024.
- Gallegos, A. and Surasky, C. *Belonging: A Resource Guide for Belonging-Builders.* Othering and Belonging Institute, UC Berkeley, 2025.
- Microsoft Inclusive Design. [inclusivedesign.microsoft.com](https://inclusivedesign.microsoft.com/)
- Rogers, C.R. "The Necessary and Sufficient Conditions of Therapeutic Personality Change." *Journal of Consulting Psychology* 21(2), 1957.
- Turkle, S. *Alone Together.* Basic Books, 2011.
