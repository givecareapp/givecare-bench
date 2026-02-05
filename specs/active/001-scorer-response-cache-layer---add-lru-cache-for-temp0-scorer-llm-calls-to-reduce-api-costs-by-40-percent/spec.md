# Spec: Scorer Response Cache Layer - Add LRU cache for temp=0 scorer LLM calls to reduce API costs by 40 percent

## Requirements

### Requirement: Cache deterministic scorer LLM calls
The system SHALL reuse cached responses for scorer LLM calls when the request is
deterministic (temperature = 0) and the full request payload matches a prior call
in the same run, using a bounded LRU cache.

#### Scenario: [Happy path]
- GIVEN a scorer LLM call with temperature 0 has already completed for a given model
  and prompt payload
- WHEN the scorer issues the same call again during the run
- THEN the response is served from the LRU cache and no external API request is made
