# Spec: Benchmark Run Comparison CLI - Add bench diff command to compare two runs and show per-model score deltas and regressions

## Requirements

### Requirement: `bench diff` Command
The system SHALL provide a `bench diff` subcommand to compare two benchmark runs and display per-model
score deltas and regressions.

#### Scenario: [Happy path]
- GIVEN two completed benchmark runs, each producing an `all_results.json` file under a run directory
  (e.g., `results/run_YYYYMMDD_HHMMSS/all_results.json`)
- WHEN the user runs `uv run bench diff <base_run> <new_run>`
- THEN the CLI prints a per-model comparison table including:
  - Base average overall score and new average overall score
  - Delta (new - base) for average overall score
  - Base and new counts of statuses: `pass`, `fail`, `error`
  - A regression indicator when the new run is worse than the base run

#### Scenario: Run Reference Flexibility
- GIVEN the user has two run references that may be:
  - A path to an `all_results.json` file
  - A run directory containing `all_results.json`
  - A run ID or unique prefix matching a directory under `results/` or `results/archive/`
- WHEN the user runs `uv run bench diff <base_ref> <new_ref>`
- THEN the CLI resolves each reference to exactly one `all_results.json` or exits with a clear error

#### Scenario: Missing Models Or Scenarios
- GIVEN the base run and new run do not contain identical model sets or scenario sets
- WHEN the user runs `uv run bench diff <base> <new>`
- THEN the CLI still produces output:
  - Models missing in either run are shown with blanks/`N/A` for unavailable values
  - Regression detection considers only comparable metrics where both sides are present

#### Scenario: Regression Definition
- GIVEN the CLI is computing regression indicators
- WHEN a model's average overall score decreases (delta < 0) OR hard failure count increases
- THEN the model is marked as regressed in the output

#### Scenario: Exit Codes
- GIVEN `bench diff` completes successfully
- WHEN it finishes
- THEN it exits with code 0
