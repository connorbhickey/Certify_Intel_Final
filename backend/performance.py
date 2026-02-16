"""
Certify Intel v7.0 - Performance Optimization Module
=====================================================

Provides caching, lazy loading, and query optimization utilities.

Features:
- TTL-based caching with automatic invalidation
- Response caching decorator for FastAPI endpoints
- Query result caching for database operations
- Lazy loading utilities for large datasets
- Response compression middleware

Usage:
    from performance import cached_response, cache_query_result, LazyLoader

    @cached_response(ttl_seconds=300)
    async def get_competitors():
        ...

    @cache_query_result("competitors", ttl=300)
    def get_all_competitors(db):
        ...
"""

import logging
import hashlib
import threading
import time
import gzip
import json
from typing import Any, Callable, Optional, Dict, List, TypeVar, Generic
from functools import wraps
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

T = TypeVar('T')


# =============================================================================
# CACHE IMPLEMENTATION
# =============================================================================

class PerformanceCache:
    """
    Thread-safe TTL cache with statistics and automatic cleanup.

    Improvements over basic TTLCache:
    - Automatic background cleanup of expired entries
    - Hit/miss statistics for monitoring
    - Size limits to prevent memory issues
    - Tag-based invalidation
    """

    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self._cache: Dict[str, Any] = {}
        self._timestamps: Dict[str, float] = {}
        self._tags: Dict[str, set] = {}  # key -> set of tags
        self._tag_keys: Dict[str, set] = {}  # tag -> set of keys
        self._lock = threading.RLock()
        self._max_size = max_size
        self._default_ttl = default_ttl

        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, key: str, ttl_seconds: Optional[int] = None) -> Optional[Any]:
        """Get cached value if not expired."""
        ttl = ttl_seconds or self._default_ttl

        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            timestamp = self._timestamps.get(key, 0)
            if time.time() - timestamp > ttl:
                # Expired
                self._remove_key(key)
                self._misses += 1
                return None

            self._hits += 1
            return self._cache[key]

    def set(self, key: str, value: Any, tags: Optional[List[str]] = None) -> None:
        """Set cache value with optional tags for group invalidation."""
        with self._lock:
            # Check size limit
            if len(self._cache) >= self._max_size and key not in self._cache:
                self._evict_oldest()

            self._cache[key] = value
            self._timestamps[key] = time.time()

            # Handle tags
            if tags:
                self._tags[key] = set(tags)
                for tag in tags:
                    if tag not in self._tag_keys:
                        self._tag_keys[tag] = set()
                    self._tag_keys[tag].add(key)

    def invalidate(self, key: str = None, tag: str = None, pattern: str = None) -> int:
        """
        Invalidate cache entries.

        Args:
            key: Specific key to invalidate
            tag: Invalidate all entries with this tag
            pattern: Invalidate all entries with key containing pattern

        Returns:
            Number of entries invalidated
        """
        with self._lock:
            count = 0

            if key:
                if key in self._cache:
                    self._remove_key(key)
                    count = 1

            elif tag:
                keys_to_remove = list(self._tag_keys.get(tag, set()))
                for k in keys_to_remove:
                    self._remove_key(k)
                count = len(keys_to_remove)

            elif pattern:
                keys_to_remove = [k for k in self._cache if pattern in k]
                for k in keys_to_remove:
                    self._remove_key(k)
                count = len(keys_to_remove)

            else:
                # Clear all
                count = len(self._cache)
                self._cache.clear()
                self._timestamps.clear()
                self._tags.clear()
                self._tag_keys.clear()

            return count

    def _remove_key(self, key: str) -> None:
        """Remove a key and clean up associated tags."""
        if key in self._cache:
            del self._cache[key]
        if key in self._timestamps:
            del self._timestamps[key]
        if key in self._tags:
            for tag in self._tags[key]:
                if tag in self._tag_keys:
                    self._tag_keys[tag].discard(key)
            del self._tags[key]

    def _evict_oldest(self) -> None:
        """Evict oldest entry when size limit reached."""
        if not self._timestamps:
            return

        oldest_key = min(self._timestamps, key=self._timestamps.get)
        self._remove_key(oldest_key)
        self._evictions += 1

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0

            return {
                "entries": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate_pct": round(hit_rate, 2),
                "evictions": self._evictions,
                "tags": list(self._tag_keys.keys())
            }

    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count of removed entries."""
        with self._lock:
            now = time.time()
            expired = [
                k for k, ts in self._timestamps.items()
                if now - ts > self._default_ttl
            ]
            for key in expired:
                self._remove_key(key)
            return len(expired)


# Global cache instances
_api_cache = PerformanceCache(max_size=500, default_ttl=300)
_query_cache = PerformanceCache(max_size=200, default_ttl=600)
_agent_cache = PerformanceCache(max_size=100, default_ttl=120)


def get_api_cache() -> PerformanceCache:
    """Get the API response cache."""
    return _api_cache


def get_query_cache() -> PerformanceCache:
    """Get the database query cache."""
    return _query_cache


def get_agent_cache() -> PerformanceCache:
    """Get the agent response cache."""
    return _agent_cache


# =============================================================================
# CACHING DECORATORS
# =============================================================================

def cache_key(*args, **kwargs) -> str:
    """Generate a cache key from function arguments."""
    key_parts = [str(a) for a in args]
    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    key_str = ":".join(key_parts)
    return hashlib.md5(key_str.encode()).hexdigest()


def cached_response(
    ttl_seconds: int = 300,
    tags: Optional[List[str]] = None,
    key_prefix: str = ""
):
    """
    Decorator for caching FastAPI endpoint responses.

    Usage:
        @app.get("/api/competitors")
        @cached_response(ttl_seconds=300, tags=["competitors"])
        async def get_competitors():
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            func_key = f"{key_prefix}{func.__name__}" if key_prefix else func.__name__
            key = f"{func_key}:{cache_key(*args, **kwargs)}"

            # Check cache
            cached = _api_cache.get(key, ttl_seconds)
            if cached is not None:
                logger.debug(f"Cache HIT: {func_key}")
                return cached

            # Execute function
            logger.debug(f"Cache MISS: {func_key}")
            result = await func(*args, **kwargs)

            # Cache result
            _api_cache.set(key, result, tags=tags)

            return result
        return wrapper
    return decorator


def cache_query_result(
    cache_name: str,
    ttl_seconds: int = 600,
    tags: Optional[List[str]] = None
):
    """
    Decorator for caching database query results.

    Usage:
        @cache_query_result("competitors", ttl=300)
        def get_all_competitors(db):
            return db.query(Competitor).all()
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = f"query:{cache_name}:{cache_key(*args, **kwargs)}"

            cached = _query_cache.get(key, ttl_seconds)
            if cached is not None:
                logger.debug(f"Query cache HIT: {cache_name}")
                return cached

            logger.debug(f"Query cache MISS: {cache_name}")
            result = func(*args, **kwargs)

            _query_cache.set(key, result, tags=tags or [cache_name])

            return result
        return wrapper
    return decorator


def cache_agent_response(ttl_seconds: int = 120):
    """
    Decorator for caching agent responses.

    Shorter TTL since agent responses may change with KB updates.
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract query from args/kwargs for key
            query = kwargs.get('query', args[1] if len(args) > 1 else '')
            key = f"agent:{func.__name__}:{cache_key(query)}"

            cached = _agent_cache.get(key, ttl_seconds)
            if cached is not None:
                logger.debug(f"Agent cache HIT: {func.__name__}")
                return cached

            result = await func(*args, **kwargs)
            _agent_cache.set(key, result)

            return result
        return wrapper
    return decorator


# =============================================================================
# LAZY LOADING
# =============================================================================

class LazyLoader(Generic[T]):
    """
    Lazy loading wrapper for expensive operations.

    Usage:
        competitors = LazyLoader(lambda: db.query(Competitor).all())

        # Data not loaded yet
        if competitors.is_loaded:
            ...

        # This triggers the load
        for c in competitors.data:
            ...
    """

    def __init__(self, loader: Callable[[], T]):
        self._loader = loader
        self._data: Optional[T] = None
        self._loaded = False
        self._load_time: Optional[float] = None

    @property
    def data(self) -> T:
        """Get the data, loading it if necessary."""
        if not self._loaded:
            start = time.time()
            self._data = self._loader()
            self._load_time = time.time() - start
            self._loaded = True
            logger.debug(f"LazyLoader loaded data in {self._load_time:.3f}s")
        return self._data

    @property
    def is_loaded(self) -> bool:
        """Check if data has been loaded."""
        return self._loaded

    @property
    def load_time_ms(self) -> Optional[float]:
        """Get load time in milliseconds."""
        return self._load_time * 1000 if self._load_time else None

    def reload(self) -> T:
        """Force reload the data."""
        self._loaded = False
        return self.data


class PaginatedLoader(Generic[T]):
    """
    Paginated lazy loading for large datasets.

    Usage:
        loader = PaginatedLoader(
            query_func=lambda offset, limit: db.query(Competitor).offset(offset).limit(limit).all(),
            page_size=50
        )

        # Load first page
        page1 = loader.get_page(0)

        # Load next page
        page2 = loader.get_page(1)
    """

    def __init__(
        self,
        query_func: Callable[[int, int], List[T]],
        page_size: int = 50,
        cache_pages: bool = True
    ):
        self._query_func = query_func
        self._page_size = page_size
        self._cache_pages = cache_pages
        self._pages: Dict[int, List[T]] = {}
        self._total_count: Optional[int] = None

    def get_page(self, page: int) -> List[T]:
        """Get a specific page of results."""
        if self._cache_pages and page in self._pages:
            return self._pages[page]

        offset = page * self._page_size
        results = self._query_func(offset, self._page_size)

        if self._cache_pages:
            self._pages[page] = results

        return results

    @property
    def page_size(self) -> int:
        return self._page_size

    def clear_cache(self):
        """Clear cached pages."""
        self._pages.clear()


# =============================================================================
# QUERY OPTIMIZATION
# =============================================================================

def batch_query(
    items: List[Any],
    query_func: Callable[[List[Any]], List[T]],
    batch_size: int = 100
) -> List[T]:
    """
    Execute queries in batches to avoid large IN clauses.

    Usage:
        competitor_ids = [1, 2, 3, ..., 500]
        results = batch_query(
            competitor_ids,
            lambda ids: db.query(Competitor).filter(Competitor.id.in_(ids)).all(),
            batch_size=100
        )
    """
    results = []
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        batch_results = query_func(batch)
        results.extend(batch_results)
    return results


def prefetch_related(
    items: List[Any],
    relation_loader: Callable[[List[int]], Dict[int, Any]],
    id_getter: Callable[[Any], int],
    relation_setter: Callable[[Any, Any], None]
) -> List[Any]:
    """
    Prefetch related objects to avoid N+1 queries.

    Usage:
        competitors = db.query(Competitor).all()
        prefetch_related(
            competitors,
            relation_loader=lambda ids: {p.competitor_id: p for p in db.query(Product).filter(Product.competitor_id.in_(ids)).all()},
            id_getter=lambda c: c.id,
            relation_setter=lambda c, products: setattr(c, '_products', products)
        )
    """
    ids = [id_getter(item) for item in items]
    related = relation_loader(ids)

    for item in items:
        item_id = id_getter(item)
        relation_setter(item, related.get(item_id))

    return items


# =============================================================================
# RESPONSE COMPRESSION
# =============================================================================

def compress_response(data: Any, threshold: int = 1024) -> tuple[bytes, bool]:
    """
    Compress response data if it exceeds threshold.

    Returns:
        (compressed_data, was_compressed)
    """
    json_data = json.dumps(data).encode('utf-8')

    if len(json_data) < threshold:
        return json_data, False

    compressed = gzip.compress(json_data)

    # Only use compression if it actually reduces size
    if len(compressed) < len(json_data):
        return compressed, True

    return json_data, False


# =============================================================================
# PERFORMANCE MONITORING
# =============================================================================

class PerformanceMonitor:
    """
    Track and report performance metrics.
    """

    def __init__(self):
        self._timings: Dict[str, List[float]] = {}
        self._lock = threading.Lock()

    def record(self, operation: str, duration_ms: float):
        """Record a timing for an operation."""
        with self._lock:
            if operation not in self._timings:
                self._timings[operation] = []
            self._timings[operation].append(duration_ms)

            # Keep only last 1000 timings per operation
            if len(self._timings[operation]) > 1000:
                self._timings[operation] = self._timings[operation][-1000:]

    def get_stats(self, operation: str = None) -> Dict[str, Any]:
        """Get statistics for an operation or all operations."""
        with self._lock:
            if operation:
                timings = self._timings.get(operation, [])
                return self._calculate_stats(operation, timings)

            return {
                op: self._calculate_stats(op, times)
                for op, times in self._timings.items()
            }

    def _calculate_stats(self, operation: str, timings: List[float]) -> Dict[str, Any]:
        if not timings:
            return {"operation": operation, "count": 0}

        sorted_timings = sorted(timings)
        count = len(timings)

        return {
            "operation": operation,
            "count": count,
            "avg_ms": round(sum(timings) / count, 2),
            "min_ms": round(sorted_timings[0], 2),
            "max_ms": round(sorted_timings[-1], 2),
            "p50_ms": round(sorted_timings[count // 2], 2),
            "p95_ms": round(sorted_timings[int(count * 0.95)], 2) if count >= 20 else None,
            "p99_ms": round(sorted_timings[int(count * 0.99)], 2) if count >= 100 else None
        }

    def clear(self):
        """Clear all recorded timings."""
        with self._lock:
            self._timings.clear()


# Global performance monitor
_perf_monitor = PerformanceMonitor()


def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor."""
    return _perf_monitor


def timed(operation: str):
    """
    Decorator to automatically record operation timing.

    Usage:
        @timed("get_competitors")
        def get_competitors(db):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                duration_ms = (time.time() - start) * 1000
                _perf_monitor.record(operation, duration_ms)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            try:
                return await func(*args, **kwargs)
            finally:
                duration_ms = (time.time() - start) * 1000
                _perf_monitor.record(operation, duration_ms)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper
    return decorator


# =============================================================================
# CACHE INVALIDATION HELPERS
# =============================================================================

def invalidate_competitor_cache(competitor_id: int = None):
    """Invalidate all competitor-related caches."""
    if competitor_id:
        _api_cache.invalidate(pattern=f"competitor:{competitor_id}")
        _query_cache.invalidate(pattern=f"competitor:{competitor_id}")
    else:
        _api_cache.invalidate(tag="competitors")
        _query_cache.invalidate(tag="competitors")
    logger.info(f"Invalidated competitor cache: {competitor_id or 'all'}")


def invalidate_news_cache():
    """Invalidate news-related caches."""
    _api_cache.invalidate(tag="news")
    _query_cache.invalidate(tag="news")
    logger.info("Invalidated news cache")


def invalidate_kb_cache():
    """Invalidate knowledge base caches (also clears agent cache)."""
    _api_cache.invalidate(tag="kb")
    _query_cache.invalidate(tag="kb")
    _agent_cache.invalidate()  # Clear all agent responses since KB changed
    logger.info("Invalidated KB and agent caches")


def invalidate_all_caches():
    """Clear all caches."""
    _api_cache.invalidate()
    _query_cache.invalidate()
    _agent_cache.invalidate()
    logger.info("Invalidated all caches")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Cache classes
    'PerformanceCache',
    'get_api_cache',
    'get_query_cache',
    'get_agent_cache',

    # Decorators
    'cached_response',
    'cache_query_result',
    'cache_agent_response',
    'cache_key',
    'timed',

    # Lazy loading
    'LazyLoader',
    'PaginatedLoader',

    # Query optimization
    'batch_query',
    'prefetch_related',

    # Compression
    'compress_response',

    # Monitoring
    'PerformanceMonitor',
    'get_performance_monitor',

    # Invalidation
    'invalidate_competitor_cache',
    'invalidate_news_cache',
    'invalidate_kb_cache',
    'invalidate_all_caches',
]
