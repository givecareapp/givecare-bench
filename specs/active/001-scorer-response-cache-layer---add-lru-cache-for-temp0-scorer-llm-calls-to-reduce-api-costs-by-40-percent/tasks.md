# Tasks: Scorer Response Cache Layer - Add LRU cache for temp=0 scorer LLM calls to reduce API costs by 40 percent

## 1. Setup
- [x] 1.1 [Task]

## 2. Implementation
- [x] 2.1 LRU cache in `api/client.py` with thread-safe `_LRUCache`, SHA256 cache keys, temp=0 gating
- [x] 2.2 Integrated `use_cache=True` in belonging, safety, trauma scorers

## 3. Testing & Fixes
- [x] 3.1 Fixed pre-existing test failures in jurisdiction rules and loaders
- [x] 3.2 All 100 tests passing, ruff/black clean on changed files
