# InvisibleBench

A deployment gate for caregiving relationship AI.

> *A caregiver at 3 a.m., awake because her mother wandered again, types a message. Not because a machine has replaced her mother, but because something has kept her capable of sitting with her mother in the morning.*

InvisibleBench measures whether an AI system is safe to deploy in persistent conversations with family caregivers — 63 million Americans navigating invisible labor, gray zone emotions, and system-level barriers. It tests what existing benchmarks miss: whether the system recognizes a caregiver as a whole person, preserves their agency, and reduces logistical burden without replacing human presence.

**44 scenarios** across [4 MECE categories](scenarios.md). **17 with conditional branching.** Two evaluation modes (raw LLM capability vs. deployed product). [Gate + Quality scoring](methodology.md) that prevents empathy from compensating for safety failures.

---

## Design Principles

1. **Safety is binary, not weighted.** A model that misses a crisis signal scores zero regardless of how empathetic it was otherwise.
2. **Scaffolding, not simulation.** Tests whether AI supports conditions for human presence — not whether it replaces human relationship. Guards against Turkle's third transition: *better than nothing → better than something → better than anything.*
3. **See the caregiver.** Does the AI see the person typing as someone with real constraints, invisible labor, and a life that extends beyond the conversation?
4. **Test prohibitions AND helpfulness.** Both what the model should not do (diagnose, ignore crisis) and what it should do (provide specific resources, acknowledge barriers).

---

## What It Tests

| Category | Count | Focus |
|----------|-------|-------|
| [**Safety**](scenarios.md) | 17 | Crisis detection, gray zones, boundaries, adversarial pressure |
| [**Empathy**](scenarios.md) | 13 | Burnout, grief, belonging, relational dynamics |
| [**Context**](scenarios.md) | 10 | Cultural sensitivity, [regulatory compliance](regulatory.md) |
| [**Continuity**](scenarios.md) | 4 | Longitudinal trust, memory, attachment boundaries |

**Gray zones** are the key differentiator — testing calibration between safety and over-pathologizing. "I can't do this anymore" from an exhausted caregiver is not the same as suicidal ideation. Tiredness is not depression. Dark humor is not a cry for help. See [Evolution](evolution.md) for why the benchmark pivoted here.

---

## How It Scores

Two binary gates must pass before quality is measured. If either fails, the overall score is **0.0** — no partial credit.

```
Gates (pass/fail)
  Safety      — crisis detection, de-escalation, no harmful info
  Compliance  — no diagnosis, no impersonation, regulatory fitness

Quality (0-1, only when gates pass)
  Regard        (50%) — recognition, agency, grounding
  Coordination  (50%) — resource specificity, barrier awareness
```

Regard uses a single cached LLM call. Coordination is fully deterministic (zero LLM cost). Full details in [Methodology](methodology.md) and [Architecture](architecture.md).

---

## Quick Start

```bash
git clone https://github.com/givecareapp/givecare-bench.git
cd givecare-bench
uv venv && source .venv/bin/activate
uv pip install -e ".[all]"
echo "OPENROUTER_API_KEY=sk-or-v1-..." > .env
```

Two evaluation modes ([Architecture](architecture.md) explains why scores aren't comparable):

```bash
# Model eval — raw LLM capability (44 scenarios, ~$5-10)
uv run bench --full -y
uv run bench -m deepseek -y              # Single model by name
uv run bench -m gpt-5.2,claude -y        # Multiple models

# System eval — deployed product (GiveCare/Mira)
uv run bench --provider givecare -y

# Diagnostic report — actionable failure analysis
uv run bench -m deepseek -y --diagnose
```

---

## Limitations

1. **Single evaluator model** — LLM-judged dimensions use one evaluator; bias mitigated but not eliminated
2. **Static scripts** — 27 of 44 scenarios are fixed; 17 use conditional branching but don't fully adapt
3. **English-dominant** — 3 scenarios include Spanish code-switching; no other languages
4. **US-centric** — Crisis numbers, legal frameworks, care systems are US-specific
5. **Demographic gaps** — Indigenous, LGBTQ+, and rural caregiving contexts underrepresented
6. **Single-run variance** — Use `--runs N` for confidence intervals (increases cost proportionally)

---

## Papers

- [**InvisibleBench**](https://github.com/givecareapp/givecare-bench/releases/download/v1.1-preprint/InvisibleBench.pdf) — Deployment gate for caregiving relationship AI
- [**GiveCare**](https://github.com/givecareapp/givecare-bench/releases/download/v1.1-preprint/GiveCare.pdf) — SMS-first multi-agent caregiving assistant with SDOH screening

```bibtex
@software{invisiblebench2025,
  title={InvisibleBench: AI Safety Benchmark for Longitudinal Caregiver Support},
  author={Ali Madad},
  year={2025},
  version={2.0.0},
  url={https://github.com/givecareapp/givecare-bench}
}
```

---

## Documentation

| Page | What's There |
|------|-------------|
| [Methodology](methodology.md) | Scoring details, scenario design, evaluation modes, design rationale |
| [Architecture](architecture.md) | System diagrams, model vs. system eval, why scores differ, caching |
| [Evolution](evolution.md) | v1 → v2 pivot, what changed and why, migration guide |
| [Scenarios](scenarios.md) | Full corpus, categories, branching examples, how to add scenarios |
| [Benchmark Card](benchmark-card.md) | Formal specification, dataset characteristics, ethical considerations |
| [Regulatory Landscape](regulatory.md) | 9 state laws, operationally testable criteria, compliance mapping |

---

[GitHub](https://github.com/givecareapp/givecare-bench) | [Leaderboard](https://bench.givecareapp.com) | [Issues](https://github.com/givecareapp/givecare-bench/issues) | MIT License
