# AutoResearch — upstream reference and GiveCare Bench adaptation

## Why this page exists

This page records how GiveCare Bench uses ideas from
`karpathy/autoresearch`, what is intentionally preserved, and what is changed
for benchmark scenario work.

## Upstream source

Primary references used during implementation:

- upstream repo: `karpathy/autoresearch`
- upstream docs used during implementation:
  - `README.md`
  - `program.md`
- DeepWiki summary was also consulted for workflow and invariants

## What the upstream repo is built for

The upstream project is a tightly scoped autonomous research loop over LLM
training code.

Core upstream pattern:

1. one mutable file: `train.py`
2. one fixed evaluator / environment: `prepare.py`
3. one objective metric: `val_bpb`
4. one experiment ledger: `results.tsv`
5. candidate commit -> run -> keep or discard
6. dedicated `autoresearch/<tag>` branch
7. loop continuously until manually stopped

This makes it a disciplined autonomous optimization framework, not just a pile
of helper scripts.

## What GiveCare Bench needs instead

GiveCare Bench does not want to optimize a training loop.
We want to optimize the **differentiation power of one benchmark scenario at a
time**.

So our local adaptation treats:

- one scenario JSON as the mutable file
- the benchmark harness + scorer stack as the fixed evaluator
- scenario differentiation as the search objective
- promotion to a broader model set as a benchmark-specific safety check

## What we preserved from upstream

### 1. Single mutable target per campaign
Each campaign should edit exactly one scenario JSON.

Current active example:

- `benchmark/scenarios/empathy/relational/impossible_constraint.json`

### 2. Fixed evaluator during the loop
A campaign does not modify scorer logic, runner logic, or docs.
The evaluator remains fixed while the scenario is being optimized.

### 3. Keep / discard discipline
A candidate is committed, evaluated, logged, and then either kept or reverted.

### 4. Campaign ledger
We keep an ignored `results.tsv` ledger for the frontier history.

### 5. Dedicated branch flow
Campaigns are expected to run on `autoresearch/<tag>` branches.

## What we changed for benchmark work

### 1. Objective metric
Upstream uses `val_bpb`.
We use **scenario spread** across a fixed probe model set.

### 2. Promotion gate
Upstream largely trusts its scalar objective.
We do not fully trust raw spread, because benchmark scenarios can be "improved"
by becoming unrealistic, gimmicky, or universally failing.

So GiveCare Bench adds a second stage:

- fast probe search
- broader promotion check before merge

### 3. Human realism requirement
A campaign winner still needs manual transcript review before merge.
This is important for benchmark integrity.

### 4. Scout vs campaign separation
We separate:

- scout mode: find flat scenarios worth improving
- campaign mode: run keep/discard optimization on one scenario

## Local implementation

### Core files
- `internal/autoresearch/README.md`
- `internal/autoresearch/program.md`
- `internal/autoresearch/run_campaign.py`
- `internal/autoresearch/_compute_spread.py`
- `internal/autoresearch/analyze_spread.py`
- `internal/autoresearch/run_scenario.sh`

### Ledger / artifacts
- `internal/autoresearch/results.tsv` — ignored experiment ledger
- `internal/autoresearch/results/` — ignored JSON artifacts per run

## Local workflow

### A. Scout mode
Find weak or flat scenarios across a broader results set.

Command:

```bash
uv run python internal/autoresearch/analyze_spread.py
```

This is not the optimization loop itself. It is just the scenario finder.

### B. Campaign setup
Create a dedicated branch and initialize the ledger.

Command:

```bash
uv run python internal/autoresearch/run_campaign.py setup --tag 2026-04-17-impossible
```

### C. Baseline
Record the untouched frontier on a clean tracked tree.

Command:

```bash
uv run python internal/autoresearch/run_campaign.py baseline
```

### D. Candidate experiment
After editing the one mutable scenario file:

```bash
uv run python internal/autoresearch/run_campaign.py experiment \
  --description "add deeper follow-up after blocked-resource frustration"
```

Runner behavior:

1. verify only the mutable file changed
2. create a candidate commit
3. run the fixed probe model set
4. compute spread + guardrail results
5. append a row to `results.tsv`
6. keep the commit only if it improves the frontier and passes guardrails
7. otherwise reset back to the previous frontier

### E. Promotion gate
Run a broader model set before merge.

Command:

```bash
uv run python internal/autoresearch/run_campaign.py promote
```

## Current campaign spec location

The active campaign is defined in:

- `internal/autoresearch/program.md`

That file is both human-readable and machine-readable:

- YAML front matter holds configuration
- markdown body holds campaign intent, goals, and operator guidance

## Current evaluator logic

The fixed evaluator currently computes:

- `spread`
- `mean`
- `min` / `max`
- status counts
- hard-fail counts
- guardrail failures

Guardrails matter because raw spread alone is not enough for benchmark design.
A scenario can become more differentiating in a bad way.

## Current local guardrail philosophy

Bad "wins" include:

- all matched models fail
- all matched models hard-fail
- evaluator errors dominate
- mean score drifts into collapse territory
- scenario turns into a lexical trap or scorer exploit
- scenario stops sounding like a plausible caregiver interaction

So the real local objective is:

> improve differentiation **without degrading benchmark legitimacy**

## Probe vs promotion sets

### Probe set
Used for fast iteration.
Current example in `program.md`:

- Claude Opus 4.6
- Claude Sonnet 4.5
- GPT-5 Mini

### Promotion set
Used before merge.
Current example in `program.md`:

- Claude Opus 4.6
- GPT-5.4
- Gemini 3.1 Pro
- Grok 4.1 Fast
- Qwen3.5 397B

## Important local assumptions

Safe assumptions:

- our autoresearch is a **repo-specific adaptation**, not a literal clone
- one scenario per campaign is the intended unit of optimization
- benchmark integrity matters more than raw spread
- promotion review is required before merge

Unsafe assumptions:

- that probe spread alone is enough to accept a change
- that the system should run forever unattended by default
- that campaigns may edit scorer logic or evaluator code
- that any spread increase is good for the benchmark

## Where this fits in the repo

This is an internal workflow, not public benchmark contract.

It belongs under `internal/` because it is:

- operationally useful
- benchmark-design facing
- not part of the public benchmark interface

## If you need to re-orient quickly

Start here, in order:

1. `internal/autoresearch/README.md`
2. `internal/autoresearch/program.md`
3. `internal/autoresearch/run_campaign.py`
4. `internal/autoresearch/_compute_spread.py`
5. `benchmark/scenarios/empathy/relational/impossible_constraint.json`

That path gets you from upstream inspiration to the actual GiveCare Bench
implementation.
