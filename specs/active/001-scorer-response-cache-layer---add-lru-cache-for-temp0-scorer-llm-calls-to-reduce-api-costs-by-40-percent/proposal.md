# Proposal: Scorer Response Cache Layer - Add LRU cache for temp=0 scorer LLM calls to reduce API costs by 40 percent

## Intent
Reduce scorer LLM API costs by caching deterministic (temperature=0) requests that
repeat within a benchmark run, while preserving existing scoring behavior.

## Scope
**In scope:**
- LRU cache for temp=0 scorer LLM calls
- Cache key based on model + request payload
- Bounded cache size with configurable defaults

**Out of scope:**
- Caching for non-deterministic temperatures
- Cross-run persistence

## Approach
Introduce an in-memory LRU cache in the scorer LLM call path. When a scorer request
is made with temperature=0, compute a stable key from model + payload and return a
cached response when available; otherwise call the API and store the response.
