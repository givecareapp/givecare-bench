# A Safety Framework for AI in Caregiving: What Standard Evaluations Miss

<!-- Diátaxis: reference -->

**Poster 25 · 4th Biennial National Conference on Caregiving Research · Salt Lake City · September 23, 2026**
Ali Madad, GiveCare

[Download the poster (PDF, 48 × 36 in)](assets/nccr/poster.pdf){ .md-button .md-button--primary }
[Add Ali to your contacts (vCard)](assets/nccr/ali-madad.vcf){ .md-button }

Email: [ali@givecareapp.com](mailto:ali@givecareapp.com) · Web: [givecareapp.com](https://givecareapp.com)

## The claim

A safety verdict you cannot re-derive from saved evidence is an opinion.

Every verdict on the poster is a pure function of a frozen scan plan and the
judge model's saved answers. Re-deriving all 196 judgments calls no model and
costs nothing. Asking the same frozen plan a second time returned 193 of 196
identical verdicts on the earlier September 19 plan.

## The run

| | |
| --- | --- |
| Run | `2026-09-19_14-04-44Z` |
| Conversations | 4 scripted caregiver cases, target model `inception/mercury-2.5` at T=0.7 |
| Judge | `jev-1.13.0`, thresholds no ≤ 0.35 · yes ≥ 0.65 |
| Requests | 40 (one per turn), 2,391 saved probabilities, $0.016 |
| Judgments | 196 derived (4 × 49 checks): 101 PASS · 11 FAIL · 5 UNCLEAR · 79 N/A |
| Benchmark | 5.1.0 · engine v2.0 · source `ec1849e9` |

## The ledger

The three files below are the complete record. Anyone can re-derive every
verdict from the first two with `scripts/rescore_diff.py` or read them
directly.

- [scan_plan.json](assets/nccr/ledger/scan_plan.json): frozen checks,
  questions, thresholds, judge model, and the transcript hashes.
- [answers.jsonl](assets/nccr/ledger/answers.jsonl): one row per turn with
  every question's probability, request hash, tokens, and cost.
- [judgments.jsonl](assets/nccr/ledger/judgments.jsonl): one derived verdict
  per conversation and check, with rationale and quoted evidence.
- [jury-card.md](assets/nccr/ledger/jury-card.md): the standard report for
  this run.

## Contest a verdict

Pick any judgment. Read its probabilities. Propose a rule change as a diff to
the check in `checks/`. We rerun the plan for two cents and publish both
ledgers side by side.

Clinicians and caregivers: the 11 FAIL and 5 UNCLEAR judgments in this run
need human labels before anything else. Write to
[ali@givecareapp.com](mailto:ali@givecareapp.com).


## The comparison matrix, as published

The poster's matrix reads five design properties off each benchmark's own
paper or README; this page keeps a sixth column, whether the judge was checked
against human labels, that the board omits for space. ● documented · ◐ partial · ○ not documented · — not
applicable. It is a design comparison. Nothing here was run against another
benchmark.

| Benchmark | Whole conversation | Care recipient in scope | Omissions scored | Across sessions | Replays without the model | Checked against humans | Source |
| --- | --- | --- | --- | --- | --- | --- | --- |
| InvisibleBench, this pilot | ● five-turn conversations; every check sees all turns | ● relational and recipient-harm checks | ● an unmet required behavior fails | ● memory-claim, crisis-decay, retraction, and false-record checks exist; this run is one session with no memory, so they did not fire | ● judgments derive from saved probabilities by code | ○ no human labels | this page |
| K-Bench (2026) | ● "200 multi-turn vignettes" | ○ not documented in the abstract | ◐ "risk exploration" is scored; rubric not public | ○ | ○ frozen GPT-4o judge | ● "94.2% exact agreement with clinician consensus" | [arXiv:2609.15855](https://arxiv.org/abs/2609.15855) |
| HealthBench (2025) | ● single response to a multi-turn context, mean 2.6 turns | ◐ personas include "a loved one" | ◐ an unmet positive criterion earns nothing; no negative points for omission | ○ | ○ GPT-4.1 grader | ● macro-F1 0.709 against physician labels | [arXiv:2505.08775](https://arxiv.org/abs/2505.08775) |
| CARE-Bench (2026) | ● "dynamic multi-turn interactions" with expert-guided simulated clients | ○ | ○ scales for relationship, empathy, and skills; omission not documented | ○ | ○ GPT-4o scores dialogue histories | ● 0.72 consistency with two psychologists on 100 dialogues | [arXiv:2511.09407](https://arxiv.org/html/2511.09407v1) · [AAAI 2026](https://doi.org/10.1609/aaai.v40i46.41287) |
| RubRIX (2026) | ○ one caregiver post, one reply; "turns" are refinement passes | ● Q2 patient harm, Q3 third-person harm | ● Inattention: "miss or fail to respond" | ○ | ○ GPT-5-nano auditor | ◐ 88.7% agreement with three coauthors on 150 items; clinician review qualitative | [arXiv:2601.13235](https://arxiv.org/abs/2601.13235) |
| CounselBench (2025) | ○ single-turn by design | ○ | ○ | ○ | ○ experts rate; LLM judges shown to overrate | ● the labels are the experts | [arXiv:2506.08584](https://arxiv.org/abs/2506.08584) |
| Single-turn safety and knowledge sets | ○ | ○ | ○ | ○ | ● scored against answer keys or a fixed classifier | — | [SafetyBench](https://arxiv.org/abs/2309.07045) · [HarmBench](https://arxiv.org/abs/2402.04249) · [EQ-Bench](https://arxiv.org/abs/2312.06281) · [ADRD-Bench](https://github.com/IIRL-ND/ADRD-Bench) |

Read on September 20, 2026. Corrections welcome at the address above.

## Method and source

- [Method at this run's revision](https://github.com/givecareapp/givecare-bench/blob/ec1849e940dc76949beb10bd60693146de60cf57/docs/methodology.md)
- [Current method](methodology.md) on this site
- Paper: Madad, A. (2025). *InvisibleBench: A Deployment Gate for Caregiving
  Relationship AI.* [arXiv:2511.20733](https://arxiv.org/abs/2511.20733)
- Code: [github.com/givecareapp/givecare-bench](https://github.com/givecareapp/givecare-bench)

## Limits

Four scripted conversations, one target model, one judge model. No comparator,
no clinical outcome, no human labels. The questions were authored against a
small set of saved conversations that includes these four. Calibration is a
vendor property that this repository does not verify.
