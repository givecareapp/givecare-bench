# Architecture

## First-principles split

The repo is organized around four concerns:

1. `benchmark/`
   Public benchmark data and contracts.
2. `src/invisiblebench/`
   Runtime package: loaders, scoring, CLI, adapters.
3. `scripts/`
   Operational utilities for leaderboard generation and dataset checks.
4. `archive/`
   Historical/internal material not needed for day-to-day public benchmark use.

## Runtime boundary

The public benchmark core is data- and transcript-driven.

- scenarios and rules live under `benchmark/`
- transcript generation and scoring live under `src/invisiblebench/`
- public leaderboard publication accepts only `llm/raw`

## System harnesses

`givecare/live` and `givecare/orchestrator` remain experimental/internal adapters.
They share the scenario and scoring core, but they are not part of the public leaderboard contract.
