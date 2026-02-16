"""
Certify Intel - Cache Layer

Provides a unified caching interface with two backends:
- InMemoryCache: Process-local dict with TTL (default, zero dependencies)
- RedisCache: Redis-backed cache for multi-process/distributed deployments

Usage:
    from cache import get_cache
    cache = get_cache()
    cache.set("key", {"data": "value"}, ttl=300)
    result = cache.get("key")
"""
import json
import time
import os
import logging

logger = logging.getLogger(__name__)


class InMemoryCache:
    """Fallback cache when Redis is not available."""

    def __init__(self, max_entries: int = 1000):
        self._cache = {}  # key -> (value, expiry_timestamp)
        self._max_entries = max_entries

    def get(self, key: str):
        """Get a value by key. Returns None if not found or expired."""
        if key in self._cache:
            value, expiry = self._cache[key]
            if expiry and time.time() > expiry:
                del self._cache[key]
                return None
            return value
        return None

    def set(self, key: str, value, ttl: int = 300):
        """Set a key-value pair with optional TTL in seconds."""
        if len(self._cache) >= self._max_entries:
            self._cleanup()
        expiry = time.time() + ttl if ttl else None
        self._cache[key] = (value, expiry)

    def delete(self, key: str):
        """Delete a key."""
        self._cache.pop(key, None)

    def clear(self):
        """Clear all cached entries."""
        self._cache.clear()

    def keys(self, pattern: str = None) -> list:
        """List keys, optionally filtered by prefix pattern."""
        self._cleanup()
        if pattern and pattern.endswith("*"):
            prefix = pattern[:-1]
            return [k for k in self._cache if k.startswith(prefix)]
        return list(self._cache.keys())

    def _cleanup(self):
        """Remove expired entries and evict oldest if over capacity."""
        now = time.time()
        expired = [k for k, (v, exp) in self._cache.items() if exp and now > exp]
        for k in expired:
            del self._cache[k]
        if len(self._cache) >= self._max_entries:
            # Remove oldest 25%
            items = sorted(
                self._cache.items(),
                key=lambda x: x[1][1] or float('inf')
            )
            for k, _ in items[:len(items) // 4]:
                del self._cache[k]


class RedisCache:
    """Redis-backed cache."""

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        import redis as redis_lib
        self._client = redis_lib.from_url(redis_url, decode_responses=True)
        # Test the connection
        self._client.ping()

    def get(self, key: str):
        """Get a value by key. Returns None if not found."""
        val = self._client.get(key)
        if val:
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                return val
        return None

    def set(self, key: str, value, ttl: int = 300):
        """Set a key-value pair with optional TTL in seconds."""
        serialized = json.dumps(value) if not isinstance(value, str) else value
        if ttl:
            self._client.setex(key, ttl, serialized)
        else:
            self._client.set(key, serialized)

    def delete(self, key: str):
        """Delete a key."""
        self._client.delete(key)

    def clear(self):
        """Flush the current database."""
        self._client.flushdb()

    def keys(self, pattern: str = None) -> list:
        """List keys matching a pattern (supports Redis glob patterns)."""
        if pattern:
            return self._client.keys(pattern)
        return self._client.keys("*")


# Singleton
_cache_instance = None


def get_cache():
    """Get the singleton cache instance (Redis if enabled, else in-memory)."""
    global _cache_instance
    if _cache_instance is None:
        if os.environ.get("REDIS_ENABLED", "false").lower() == "true":
            redis_url = os.environ.get(
                "REDIS_URL", "redis://localhost:6379/0"
            )
            try:
                _cache_instance = RedisCache(redis_url)
                logger.info("Redis cache initialized: %s", redis_url)
            except Exception as e:
                logger.warning(
                    "Redis unavailable, falling back to in-memory: %s", e
                )
                _cache_instance = InMemoryCache()
        else:
            _cache_instance = InMemoryCache()
            logger.info("Using in-memory cache (REDIS_ENABLED=false)")
    return _cache_instance


def reset_cache():
    """Reset the singleton (used in tests)."""
    global _cache_instance
    _cache_instance = None
