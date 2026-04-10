"""Short-lived in-memory response cache for paginated list endpoints.

Provides a simple TTL-based cache that eliminates redundant MongoDB
round-trips when multiple users (or the same user polling) hit
list endpoints within a short window.

Usage::

    from crewai_productfeature_planner.apis._response_cache import response_cache

    cached = response_cache.get("ideas", page=1, page_size=10, project_id="p1")
    if cached is not None:
        return cached
    result = ... # fetch from DB
    response_cache.put("ideas", result, page=1, page_size=10, project_id="p1")
"""

from __future__ import annotations

import threading
import time
from typing import Any

_CACHE_TTL: float = 5.0  # seconds


class _ResponseCache:
    """Thread-safe, TTL-based cache for API responses."""

    __slots__ = ("_store", "_lock", "_ttl")

    def __init__(self, ttl: float = _CACHE_TTL) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()
        self._ttl = ttl

    def _make_key(self, endpoint: str, **params: Any) -> str:
        """Build a deterministic cache key from endpoint + sorted params."""
        parts = [endpoint]
        for k in sorted(params):
            v = params[k]
            if v is not None:
                parts.append(f"{k}={v}")
        return "|".join(parts)

    def get(self, endpoint: str, **params: Any) -> Any | None:
        """Return cached value if still valid, else ``None``."""
        key = self._make_key(endpoint, **params)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            ts, value = entry
            if (time.monotonic() - ts) >= self._ttl:
                del self._store[key]
                return None
            return value

    def put(self, endpoint: str, value: Any, **params: Any) -> None:
        """Store a value with the current timestamp."""
        key = self._make_key(endpoint, **params)
        with self._lock:
            self._store[key] = (time.monotonic(), value)

    def invalidate(self, endpoint: str | None = None) -> None:
        """Clear cache entries — all or for a specific endpoint prefix."""
        with self._lock:
            if endpoint is None:
                self._store.clear()
            else:
                to_remove = [k for k in self._store if k.startswith(endpoint)]
                for k in to_remove:
                    del self._store[k]


#: Module-level singleton shared by all API endpoints.
response_cache = _ResponseCache()
