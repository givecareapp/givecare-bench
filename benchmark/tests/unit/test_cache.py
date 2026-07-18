"""Tests for LRU scorer response cache."""

from __future__ import annotations

from invisiblebench.api.client import APIConfig, ModelAPIClient, _LRUCache


class TestLRUCache:
    def test_get_miss(self):
        cache = _LRUCache(4)
        assert cache.get("nonexistent") is None

    def test_set_and_get(self):
        cache = _LRUCache(4)
        cache.set("k1", {"response": "hello"})
        assert cache.get("k1") == {"response": "hello"}

    def test_returns_deepcopy(self):
        cache = _LRUCache(4)
        original = {"response": "hello", "nested": [1, 2]}
        cache.set("k1", original)
        retrieved = cache.get("k1")
        retrieved["nested"].append(3)
        assert cache.get("k1")["nested"] == [1, 2]

    def test_eviction(self):
        cache = _LRUCache(2)
        cache.set("a", {"v": 1})
        cache.set("b", {"v": 2})
        cache.set("c", {"v": 3})  # evicts "a"
        assert cache.get("a") is None
        assert cache.get("b") == {"v": 2}
        assert cache.get("c") == {"v": 3}

    def test_lru_ordering(self):
        cache = _LRUCache(2)
        cache.set("a", {"v": 1})
        cache.set("b", {"v": 2})
        cache.get("a")  # touch "a", making "b" the LRU
        cache.set("c", {"v": 3})  # evicts "b"
        assert cache.get("a") == {"v": 1}
        assert cache.get("b") is None
        assert cache.get("c") == {"v": 3}

    def test_disabled_when_zero(self):
        cache = _LRUCache(0)
        cache.set("k", {"v": 1})
        assert cache.get("k") is None

    def test_overwrite_existing_key(self):
        cache = _LRUCache(4)
        cache.set("k", {"v": 1})
        cache.set("k", {"v": 2})
        assert cache.get("k") == {"v": 2}


class TestCacheability:
    def test_temp_zero_cacheable(self):
        payload = {"model": "m", "messages": [], "temperature": 0.0, "max_tokens": 100}
        assert ModelAPIClient._is_cacheable(payload) is True

    def test_temp_nonzero_not_cacheable(self):
        payload = {"model": "m", "messages": [], "temperature": 0.7, "max_tokens": 100}
        assert ModelAPIClient._is_cacheable(payload) is False

    def test_stream_not_cacheable(self):
        payload = {"model": "m", "messages": [], "temperature": 0.0, "max_tokens": 100, "stream": True}
        assert ModelAPIClient._is_cacheable(payload) is False

    def test_missing_temp_not_cacheable(self):
        payload = {"model": "m", "messages": [], "max_tokens": 100}
        assert ModelAPIClient._is_cacheable(payload) is False


class TestCacheKey:
    def test_deterministic(self):
        payload = {"model": "m", "messages": [{"role": "user", "content": "hi"}], "temperature": 0.0}
        assert ModelAPIClient._cache_key(payload) == ModelAPIClient._cache_key(payload)

    def test_different_content_different_key(self):
        p1 = {"model": "m", "messages": [{"role": "user", "content": "a"}], "temperature": 0.0}
        p2 = {"model": "m", "messages": [{"role": "user", "content": "b"}], "temperature": 0.0}
        assert ModelAPIClient._cache_key(p1) != ModelAPIClient._cache_key(p2)

    def test_key_is_sha256_hex(self):
        payload = {"model": "m", "messages": [], "temperature": 0.0}
        key = ModelAPIClient._cache_key(payload)
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)


class TestAPIConfig:
    def test_from_env_reads_timeout_and_retry_knobs(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        monkeypatch.setenv("INVISIBLEBENCH_API_TIMEOUT_SECONDS", "30")
        monkeypatch.setenv("INVISIBLEBENCH_API_MAX_RETRIES", "1")
        monkeypatch.setenv("INVISIBLEBENCH_API_RETRY_DELAY_SECONDS", "0.25")

        config = APIConfig.from_env()

        assert config.openrouter_api_key == "sk-test"
        assert config.timeout == 30
        assert config.max_retries == 1
        assert config.retry_delay == 0.25

    def test_from_env_reads_connection_pool_size(self, monkeypatch):
        monkeypatch.setenv("INVISIBLEBENCH_API_POOL_MAXSIZE", "24")

        config = APIConfig.from_env()

        assert config.pool_maxsize == 24

    def test_from_env_ignores_invalid_timeout_and_retry_knobs(self, monkeypatch):
        monkeypatch.setenv("INVISIBLEBENCH_API_TIMEOUT_SECONDS", "bogus")
        monkeypatch.setenv("INVISIBLEBENCH_API_MAX_RETRIES", "0")
        monkeypatch.setenv("INVISIBLEBENCH_API_RETRY_DELAY_SECONDS", "-1")

        config = APIConfig.from_env()

        assert config.timeout == 120
        assert config.max_retries == 3
        assert config.retry_delay == 2.0
        assert config.pool_maxsize == 32


class TestConnectionPool:
    def test_client_mounts_configured_pool(self, monkeypatch):
        monkeypatch.delenv("INVISIBLEBENCH_DISABLE_LLM", raising=False)
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        client = ModelAPIClient(APIConfig(pool_maxsize=24))

        assert client.session.get_adapter("https://")._pool_maxsize == 24
        assert client.session.get_adapter("http://")._pool_maxsize == 24
