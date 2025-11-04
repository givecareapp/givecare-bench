# Paper Revision Tasks

**Status**: Pre-submission revision
**Target**: Submission-ready in 13-17 hours
**Last Updated**: 2025-10-24

---

## Priority 0: Critical Blockers (MUST FIX - 3-4 hours)

### 1. Replace Placeholders in Paper 1 ⚠️ SUBMISSION BLOCKER
**File**: `papers/paper1-longitudinalbench/paper.tex`
**Status**: ❌ Not Started
**Effort**: 2-3 hours (if running analyses) OR 30 min (if moving to Future Work)

**Lines to fix**:
- [ ] Line 296: `PC1 explains XX\% of variance`
- [ ] Line 299: `Spearman $\rho$ = X.XX`
- [ ] Line 302: `mean $\pm$ standard deviation`
- [ ] Line 305: Table~\ref{tab:trait-robustness} (missing)

**Decision needed**: Run validation studies OR move to "Planned Validation" section?

**Fix options**:
- **Option A** (Quick): Move all validation results to Section 6.2 "Planned Validation Studies" with clear timeline
- **Option B** (Better): Run mini-validation on existing data (PCA, IRR calculation on current judge outputs)

**Recommended**: Option A for immediate submission, Option B for camera-ready

---

### 2. Fix WOPR Act Inconsistency ⚠️ CROSS-PAPER BLOCKER
**Files**: Both papers + references.bib
**Status**: ❌ Not Started
**Effort**: 30-45 minutes

**Current inconsistencies**:
- Paper 1: "Illinois WOPR Act (2025)"
- Paper 3: "Illinois WOPR Act (PA 103-0560, 2024)"
- BibTeX: `wopr2024hypothetical`

**Action items**:
- [ ] Search/replace all WOPR references in Paper 1 with unified language
- [ ] Search/replace all WOPR references in Paper 3 with unified language
- [ ] Update references.bib entry
- [ ] Verify no other citations broken

**Unified replacement text**:
```
We evaluate regulatory compliance using synthetic policy constraints
modeled on standard AI safety best practices: no medical diagnosis,
no treatment recommendations, and no dosing advice. These constraints
reflect common regulatory boundaries (e.g., FDA guidance on medical
devices, state telemedicine laws) without depending on specific
enacted legislation~\cite{wopr2024hypothetical}.
```

**Files to update**:
- `papers/paper1-longitudinalbench/paper.tex`
- `papers/paper1-longitudinalbench/references.bib`
- `papers/paper3-givecare-system/paper.tex`
- `papers/paper3-givecare-system/references.bib`

---

### 3. Address Judge Bias Risk (Paper 1) ⚠️ METHODOLOGICAL FLAW
**File**: `papers/paper1-longitudinalbench/paper.tex`
**Status**: ❌ Not Started
**Effort**: 1 hour (text) + 3-4 hours (if running ablation)

**Current issue**: 2/3 judges are Anthropic models (Claude Sonnet 3.7, Claude Opus 4)

**Action items**:
- [ ] Line 178-184: Replace judge assignment section with cross-family justification
- [ ] Add Judge 3: GPT-4o (OpenAI) instead of Claude Opus 4
- [ ] Add rationale for each judge family choice
- [ ] (Optional) Run judge-swap ablation and report stability

**Text replacement ready**: See comprehensive assessment section 3

**Optional validation**:
- Re-run top 5 models (N=100 scenarios) with swapped judge
- Report ranking stability (Spearman ρ)
- Estimated cost: ~$50, time: 3-4 hours

---

### 4. Soften Overly Strong Claims (Paper 3) ⚠️ CREDIBILITY RISK
**File**: `papers/paper3-givecare-system/paper.tex` & `manuscript_clean.md`
**Status**: ❌ Not Started
**Effort**: 45 minutes

**Lines with overly definitive claims**:
- [ ] Line 51: "100% regulatory compliance"
- [ ] Line 229: "0 medical advice violations"
- [ ] Lines 468-469: Table with absolute safety claims
- [ ] Line 489: "100% Azure AI compliance"

**Action items**:
- [ ] Add "preliminary" and "automated evaluation" qualifiers
- [ ] Add limitations paragraph after results
- [ ] Update table to show "automated scoring, human validation pending"
- [ ] Frame as feasibility demonstration, not efficacy proof

**Replacement text ready**: See comprehensive assessment section 4

---

## Priority 1: High Priority (Fix Before Submission - 4-5 hours)

### 5. Unify Cost Model (Paper 1)
**File**: `papers/paper1-longitudinalbench/paper.tex`
**Status**: ❌ Not Started
**Effort**: 15 minutes

**Current inconsistency**:
- Line 259: "$140-190 total"
- Earlier: "$18-22 total"

**Action**:
- [ ] Line 259: Clarify base ($18-22) vs. full validation ($140-190) breakdown
- [ ] Add footnote explaining what's included in each cost tier
- [ ] Verify all cost figures consistent across paper

---

### 6. Clarify Expected vs. Completed Results (Paper 1)
**File**: `papers/paper1-longitudinalbench/paper.tex`
**Status**: ❌ Not Started
**Effort**: 30 minutes

**Current issue**: Lines 308-314 describe "Expected results" ambiguously

**Action**:
- [ ] Move human-judge calibration to new "Planned Validation" subsection
- [ ] Clearly label as future work with timeline
- [ ] Update abstract/intro to reflect what's completed vs. planned

---

### 7. Add Psychometric Validation Plan (Paper 3)
**File**: `papers/paper3-givecare-system/paper.tex`
**Status**: ❌ Not Started
**Effort**: 1 hour

**Current issue**: GC-SDOH-28 presented without psychometric validation

**Action**:
- [ ] Add "Psychometric Validation Plan" subsection to Section 4.1
- [ ] List planned analyses (α, ω, CFA, test-retest, DIF)
- [ ] Report preliminary convergent validity (CWBS r=0.68, REACH-II r=0.71)
- [ ] Add timeline (Q1-Q2 2025)

**Template ready**: See comprehensive assessment section 7

---

### 8. Document Multi-Layer Safety Approach (Paper 3)
**File**: `papers/paper3-givecare-system/paper.tex`
**Status**: ❌ Not Started
**Effort**: 45 minutes

**Current issue**: Azure Content Safety is sole evaluator

**Action**:
- [ ] Section 5.1: Expand to show layered approach
- [ ] List: Azure (automated) + Rule-based + Manual spot-check + Planned audit
- [ ] Acknowledge limitations of single-platform evaluation
- [ ] Add planned independent third-party audit (Q1 2025)

**Template ready**: See comprehensive assessment section 8

---

## Priority 2: Quality Enhancements (Optional - 6-8 hours)

### 9. Add Scenario Realism (Paper 1)
**Status**: ⏸️ Deferred
**Effort**: 2-3 hours

- [ ] Add 1-2 anonymized real caregiver quotes to ground scenarios
- [ ] Cite source (e.g., caregiver forums, interviews)
- [ ] Demonstrate authentic language patterns

---

### 10. Illustrate Crisis Signal Examples (Paper 1)
**Status**: ⏸️ Deferred
**Effort**: 1 hour

- [ ] Add side-by-side explicit vs. masked crisis example
- [ ] Show how models miss subtle cues
- [ ] Place in Section 4.2 (Crisis Detection Results)

---

### 11. Detail Human Anchor Validation (Both Papers)
**Status**: ⏸️ Deferred
**Effort**: 2-3 hours

- [ ] Design 10-15% human rating protocol
- [ ] Recruit crisis counselor + MSW + caregiver advocate
- [ ] Report κ/ICC and human-LLM correlation
- [ ] OR clearly describe as planned study with timeline

---

### 12. Add Ethics/IRB Statement (Paper 3)
**Status**: ⏸️ Deferred
**Effort**: 1-2 hours

- [ ] Add consent language used in beta
- [ ] Describe data retention policy
- [ ] Document PHI handling procedures
- [ ] Describe crisis escalation SOP
- [ ] Note IRB exemption or approval status

---

## Cross-Paper Alignment Tasks

### 13. Terminology Consistency Audit
**Status**: ❌ Not Started
**Effort**: 1 hour

- [ ] Verify identical 8 dimension names across both papers
- [ ] Verify identical 5 failure mode names across both papers
- [ ] Check cost figures are consistent where cross-referenced
- [ ] Ensure citation formatting matches

**Files**: Both paper.tex files

---

### 14. Abstract Rewrites (Both Papers)
**Status**: ❌ Not Started
**Effort**: 30 minutes

- [ ] Paper 1: Replace abstract (lines 62-63) with tighter version
- [ ] Paper 3: Replace abstract (lines 51-52) with clearer framing
- [ ] Both: Lead with problem→contribution→result, not methodology

**Replacement text ready**: See comprehensive assessment "Quick-Win Abstract Rewrites"

---

### 15. Create Shared Responsible Use Appendix (Optional)
**Status**: ⏸️ Deferred
**Effort**: 2 hours

- [ ] Create `papers/shared-appendix-responsible-use.tex`
- [ ] Include: consent language, data retention, PII minimization, crisis SOP
- [ ] Include in both papers via `\input{../shared-appendix-responsible-use}`
- [ ] Verify stays within 15-file limit

---

## Quick-Win Validation Studies (Optional)

### Study A: Judge Family Swap Ablation (Paper 1)
**Effort**: 2-3 days
**Cost**: ~$50
**Impact**: High credibility boost

- [ ] Re-run top 5 models (N=100 scenarios) with Judge 3 = GPT-4o instead of Claude Opus 4
- [ ] Calculate Spearman ρ for ranking stability
- [ ] Report score deltas (±2-3 percentage points expected)
- [ ] Add results to Section 4.4 or Appendix

---

### Study B: Human Safety Spot-Check (Paper 3)
**Effort**: 1-2 days
**Cost**: $300 (1 expert × 3 hours)
**Impact**: Addresses Azure-only concern

- [ ] Recruit licensed crisis counselor or MSW
- [ ] Random sample 10% of beta conversations (N=14)
- [ ] Score for: crisis detection, medical boundary violations, trauma-informed approach
- [ ] Report agreement with automated metrics (κ or ICC)
- [ ] Add to Section 5.1

---

### Study C: GC-SDOH-28 Mini Psychometric Pilot (Paper 3)
**Effort**: 1 week
**Cost**: $500 (N=50 × $10 incentives)
**Impact**: Preliminary reliability data

- [ ] Recruit N=50 caregivers via Prolific or caregiver networks
- [ ] Administer GC-SDOH-28 twice (2-week interval)
- [ ] Calculate: Cronbach's α, test-retest ICC
- [ ] Report preliminary internal consistency
- [ ] Add to Section 4.1

---

## Compilation & Submission Checklist

### Pre-Submission Checks
- [ ] Paper 1: `pdflatex paper.tex` compiles without errors
- [ ] Paper 1: `bibtex paper` resolves all citations
- [ ] Paper 1: No "??" or "XX" placeholders in output PDF
- [ ] Paper 3: `pdflatex paper.tex` compiles without errors
- [ ] Paper 3: All figures render correctly
- [ ] Both: References.bib complete and formatted correctly
- [ ] Both: Page limits met (if applicable)
- [ ] Both: Anonymized for review (if double-blind)

### Submission Package
- [ ] Paper 1 PDF (generated from paper.tex)
- [ ] Paper 3 PDF (generated from paper.tex)
- [ ] Source files (.tex, .bib, figures/)
- [ ] README with compilation instructions
- [ ] Supplementary materials (scenarios, code, if required)

---

## Timeline Estimate

**Critical Path (Minimum for Submission)**:
- Day 1 (4 hours): P0 tasks 1-4 (blockers)
- Day 2 (4 hours): P1 tasks 5-8 (high priority)
- Day 3 (2 hours): Cross-paper alignment + compilation checks
- **Total**: 10 hours, 3 days

**Full Quality Pass (Recommended)**:
- Day 1: P0 tasks (4 hours)
- Day 2: P1 tasks (5 hours)
- Day 3: P2 tasks (4 hours)
- Day 4: Validation studies (if pursued, 8 hours)
- Day 5: Final checks + compilation (2 hours)
- **Total**: 23 hours, 5 days

---

## Decision Points

### Decision 1: Validation Studies Timing
**Options**:
- **A**: Move all validation to "Future Work", submit now → Fastest path
- **B**: Run quick mini-studies (judge swap, spot-check) → Stronger submission
- **C**: Run full validation suite → Delay submission 2-3 weeks

**Recommendation**: Option A for conference deadline, Option B for journal submission

---

### Decision 2: Judge Configuration (Paper 1)
**Options**:
- **A**: Keep current 2 Anthropic + 1 Google, add strong justification → Quick fix
- **B**: Swap Judge 3 to OpenAI GPT-4o, re-run evals → Better methodology
- **C**: Add 4th judge (OpenAI) for full cross-family coverage → Most robust

**Recommendation**: Option B (best balance of rigor and effort)

---

### Decision 3: Safety Claims Strength (Paper 3)
**Options**:
- **A**: Keep strong claims, add detailed limitations section → Minimal changes
- **B**: Soften all claims to "preliminary automated evaluation" → Conservative framing
- **C**: Run human validation, keep strong claims with evidence → Best but time-intensive

**Recommendation**: Option B for immediate submission, Option C for camera-ready

---

## References

- **Comprehensive Assessment**: See root-level assessment document
- **Fix Templates**: See assessment sections 1-8 for ready-to-paste text
- **Quick-Win Rewrites**: See assessment "Quick-Win Abstract Rewrites" section

---

## Notes

- All line numbers reference current .tex files (as of 2025-10-24)
- Estimated efforts are for single person; can parallelize some tasks
- Cost estimates based on current OpenRouter/API pricing
- Respects CLAUDE.md 15-file limit (no new documentation files)

---

**Next Action**: Review P0 tasks, make Decision 1-3, allocate time block for Day 1 critical fixes.
