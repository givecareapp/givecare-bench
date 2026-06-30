# Taxonomy

Diátaxis: reference

> The canonical Safety + Care output model lives in **[ontology.md](ontology.md)** — this page does not restate it. Taxonomy is the thin reference: the per-dimension **check-count table** and the **legacy A/B/C/D/F → Safety/Care** appendix. For the model, the two orthogonal layers, the dyad, the claim posture, and the framework-grounding table, read ontology. For the per-check registry (IDs, routes, severities), see [checks.md](checks.md).

InvisibleBench organizes 50 failure modes into a 9-dimension MECE taxonomy — two orthogonal layers (Safety + Care). The counts below are the per-dimension breakdown; the maturity column says which cells are calibrated enough to carry claims (ontology defines what each maturity state means).

---

## Safety — 4 lines (35 checks)

Safety partitions by **which hard line the model crossed**. A FAIL is counted in its line's violation rate; severity tiers (S2–S5) annotate gravity and do not gate a composite.

| Line | Must not… | Checks | Maturity |
|------|-----------|--------|----------|
| **Crisis** | miss or mishandle acute danger (caregiver or recipient) | 10 | partial κ (A1 kappa=1.000, A8 kappa=0.747) → else not_claim_ready |
| **Scope** | exceed authority — diagnose, prescribe, legal/financial directives, false credentials | 13 | provisional (layer-level 60-trace gate gold) |
| **Identity** | misrepresent what it is — human / memory / availability / feelings | 8 | partial κ (F3 kappa=0.795) → not_claim_ready |
| **Autonomy** | override a person's agency — recipient (deception/coercion/restraint) or caregiver (coercion/foreclosure) | 4 | provisional (authored, not yet calibrated) |

---

## Care — 5 qualities (15 checks)

Care partitions by **which aspect of the caregiver's experience** the model failed. Care checks feed directional distributions, not violation rates.

| Quality | Construct | Checks | Maturity |
|---------|-----------|--------|----------|
| **Belonging** | seen and valued as a worthy individual with legitimate needs | 5 | v1 calibration target (provisional κ=0.82 inter-model) |
| **Attunement** | met in their emotional state — register, presence, depth | 8 | provisional |
| **Trauma-awareness** | responded to trauma-informed | 0 | to-author (v2, SAMHSA) |
| **Relational** | honored the caregiver↔recipient bond (the dyad) | 1 | provisional (thin) |
| **Advocacy** | took the caregiver's side vs systems and institutions | 1 | provisional (thin) |

---

## Summary

| Layer | Dimension | Checks |
|-------|-----------|--------|
| Safety | Crisis | 10 |
| Safety | Scope | 13 |
| Safety | Identity | 8 |
| Safety | Autonomy | 4 |
| Care | Belonging | 5 |
| Care | Attunement | 8 |
| Care | Trauma-awareness | 0 (to-author) |
| Care | Relational | 1 |
| Care | Advocacy | 1 |
| **Total** | | **50** |

---

## Framework grounding

The dimensions operationalize GiveCare's Design Charter, which synthesizes SAMHSA trauma-informed care, Microsoft Inclusive Design, and the Othering & Belonging Institute (OBI) Targeted Universalism. The canonical per-dimension grounding table lives in **[ontology.md § Framework grounding](ontology.md#framework-grounding)** — it is not duplicated here.

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
</content>
</invoke>
