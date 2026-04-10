"""Tests for the response cache module."""

import time

from crewai_productfeature_planner.apis._response_cache import _ResponseCache


class TestResponseCache:
    def test_miss_returns_none(self):
        cache = _ResponseCache(ttl=5.0)
        assert cache.get("ideas", page=1, page_size=10) is None

    def test_put_then_get(self):
        cache = _ResponseCache(ttl=5.0)
        cache.put("ideas", {"items": []}, page=1, page_size=10)
        assert cache.get("ideas", page=1, page_size=10) == {"items": []}

    def test_different_params_are_separate(self):
        cache = _ResponseCache(ttl=5.0)
        cache.put("ideas", "page1", page=1, page_size=10)
        cache.put("ideas", "page2", page=2, page_size=10)
        assert cache.get("ideas", page=1, page_size=10) == "page1"
        assert cache.get("ideas", page=2, page_size=10) == "page2"

    def test_ttl_expiry(self):
        cache = _ResponseCache(ttl=0.05)  # 50ms TTL
        cache.put("ideas", "data", page=1, page_size=10)
        assert cache.get("ideas", page=1, page_size=10) == "data"
        time.sleep(0.06)
        assert cache.get("ideas", page=1, page_size=10) is None

    def test_invalidate_all(self):
        cache = _ResponseCache(ttl=5.0)
        cache.put("ideas", "a", page=1, page_size=10)
        cache.put("projects", "b", page=1, page_size=10)
        cache.invalidate()
        assert cache.get("ideas", page=1, page_size=10) is None
        assert cache.get("projects", page=1, page_size=10) is None

    def test_invalidate_by_endpoint(self):
        cache = _ResponseCache(ttl=5.0)
        cache.put("ideas", "a", page=1, page_size=10)
        cache.put("projects", "b", page=1, page_size=10)
        cache.invalidate("ideas")
        assert cache.get("ideas", page=1, page_size=10) is None
        assert cache.get("projects", page=1, page_size=10) == "b"

    def test_none_params_ignored_in_key(self):
        cache = _ResponseCache(ttl=5.0)
        cache.put("ideas", "data", page=1, page_size=10, project_id=None)
        assert cache.get("ideas", page=1, page_size=10, project_id=None) == "data"
        # Same key as without the None param
        assert cache.get("ideas", page=1, page_size=10) == "data"
