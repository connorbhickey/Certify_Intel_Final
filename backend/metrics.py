"""
Certify Intel - Prometheus Metrics Module

Provides application metrics with two backends:
- Prometheus: Full histogram/counter/gauge metrics (requires prometheus_client)
- No-op fallback: Zero-overhead stubs when prometheus_client is not installed

All metrics default to OFF (METRICS_ENABLED=false). Zero overhead when disabled.

Usage:
    from metrics import track_request, track_ai_call, track_cache
    track_request("GET", "/api/competitors", 200, 0.045)
    track_ai_call("anthropic", "claude-opus-4-5-20250514", cost=0.012, duration=1.5)
    track_cache("get", hit=True)
"""

import os
import time
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

METRICS_ENABLED = os.environ.get("METRICS_ENABLED", "false").lower() == "true"

# Try to import prometheus_client
try:
    from prometheus_client import (
        Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    CONTENT_TYPE_LATEST = "text/plain"

    def generate_latest():
        return b""


class _NoOpMetric:
    """No-op metric that silently discards all operations."""

    def labels(self, *args, **kwargs):
        return self

    def inc(self, amount=1):
        pass

    def dec(self, amount=1):
        pass

    def observe(self, amount):
        pass

    def set(self, value):
        pass


if PROMETHEUS_AVAILABLE and METRICS_ENABLED:
    logger.info("Prometheus metrics enabled")

    # HTTP metrics
    http_requests_total = Counter(
        "http_requests_total",
        "Total HTTP requests",
        ["method", "path", "status"]
    )
    http_request_duration = Histogram(
        "http_request_duration_seconds",
        "HTTP request duration in seconds",
        ["method", "path"],
        buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
    )

    # AI metrics
    ai_requests_total = Counter(
        "ai_requests_total",
        "Total AI API calls",
        ["provider", "model"]
    )
    ai_cost_total = Counter(
        "ai_cost_dollars_total",
        "Total AI API cost in dollars",
        ["provider"]
    )
    ai_request_duration = Histogram(
        "ai_request_duration_seconds",
        "AI request duration in seconds",
        ["provider", "model"],
        buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)
    )

    # Database metrics
    db_connections_active = Gauge(
        "db_connections_active",
        "Active database connections"
    )

    # Cache metrics
    cache_operations = Counter(
        "cache_operations_total",
        "Cache operations",
        ["operation", "result"]
    )
else:
    if METRICS_ENABLED and not PROMETHEUS_AVAILABLE:
        logger.warning(
            "METRICS_ENABLED=true but prometheus_client not installed. "
            "Install with: pip install prometheus_client"
        )

    http_requests_total = _NoOpMetric()
    http_request_duration = _NoOpMetric()
    ai_requests_total = _NoOpMetric()
    ai_cost_total = _NoOpMetric()
    ai_request_duration = _NoOpMetric()
    db_connections_active = _NoOpMetric()
    cache_operations = _NoOpMetric()


# --- Convenience functions ---

# In-memory counters for the JSON fallback summary
_internal_counters: Dict[str, Any] = {
    "http_requests": 0,
    "ai_requests": 0,
    "ai_cost_usd": 0.0,
    "cache_hits": 0,
    "cache_misses": 0,
    "started_at": time.time(),
}


def track_request(method: str, path: str, status: int, duration: float) -> None:
    """Track an HTTP request."""
    http_requests_total.labels(method=method, path=path, status=str(status)).inc()
    http_request_duration.labels(method=method, path=path).observe(duration)
    _internal_counters["http_requests"] += 1


def track_ai_call(
    provider: str, model: str, cost: float = 0.0, duration: float = 0.0
) -> None:
    """Track an AI API call."""
    ai_requests_total.labels(provider=provider, model=model).inc()
    if cost > 0:
        ai_cost_total.labels(provider=provider).inc(cost)
    if duration > 0:
        ai_request_duration.labels(provider=provider, model=model).observe(duration)
    _internal_counters["ai_requests"] += 1
    _internal_counters["ai_cost_usd"] += cost


def track_cache(operation: str, hit: bool = True) -> None:
    """Track a cache operation."""
    cache_operations.labels(
        operation=operation, result="hit" if hit else "miss"
    ).inc()
    if hit:
        _internal_counters["cache_hits"] += 1
    else:
        _internal_counters["cache_misses"] += 1


def get_metrics_summary() -> Dict[str, Any]:
    """Return a JSON summary of metrics (used when Prometheus is not available)."""
    uptime = time.time() - _internal_counters["started_at"]
    return {
        "metrics_enabled": METRICS_ENABLED,
        "prometheus_available": PROMETHEUS_AVAILABLE,
        "uptime_seconds": round(uptime, 1),
        "http_requests_total": _internal_counters["http_requests"],
        "ai_requests_total": _internal_counters["ai_requests"],
        "ai_cost_usd_total": round(_internal_counters["ai_cost_usd"], 6),
        "cache_hits": _internal_counters["cache_hits"],
        "cache_misses": _internal_counters["cache_misses"],
    }
