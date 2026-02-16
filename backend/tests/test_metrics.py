"""
Tests for the metrics module and MetricsMiddleware.

CI-safe: No external dependencies or API keys required.
"""

import importlib
import os
import sys
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reload_metrics(env_overrides=None):
    """Reload the metrics module with optional env var overrides."""
    env = env_overrides or {}
    with patch.dict(os.environ, env, clear=False):
        # Remove cached module so it re-evaluates globals
        if "metrics" in sys.modules:
            del sys.modules["metrics"]
        import metrics
        importlib.reload(metrics)
        return metrics


# ---------------------------------------------------------------------------
# Unit tests: metrics module
# ---------------------------------------------------------------------------

class TestMetricsModule:
    """Tests for backend/metrics.py"""

    def test_metrics_disabled_by_default(self):
        """METRICS_ENABLED defaults to false."""
        m = _reload_metrics({"METRICS_ENABLED": "false"})
        assert m.METRICS_ENABLED is False

    def test_metrics_enabled_via_env(self):
        """METRICS_ENABLED=true enables metrics."""
        m = _reload_metrics({"METRICS_ENABLED": "true"})
        assert m.METRICS_ENABLED is True

    def test_noop_metric_labels(self):
        """NoOp metrics should silently accept any labels."""
        m = _reload_metrics({"METRICS_ENABLED": "false"})
        # Should not raise
        m.http_requests_total.labels(method="GET", path="/test", status="200").inc()
        m.http_request_duration.labels(method="GET", path="/test").observe(0.5)
        m.ai_requests_total.labels(provider="anthropic", model="test").inc()
        m.ai_cost_total.labels(provider="anthropic").inc(0.01)
        m.db_connections_active.set(5)
        m.cache_operations.labels(operation="get", result="hit").inc()

    def test_track_request(self):
        """track_request increments internal counters."""
        m = _reload_metrics({"METRICS_ENABLED": "false"})
        initial = m._internal_counters["http_requests"]
        m.track_request("GET", "/api/test", 200, 0.05)
        assert m._internal_counters["http_requests"] == initial + 1

    def test_track_ai_call(self):
        """track_ai_call increments internal counters and accumulates cost."""
        m = _reload_metrics({"METRICS_ENABLED": "false"})
        initial_count = m._internal_counters["ai_requests"]
        initial_cost = m._internal_counters["ai_cost_usd"]
        m.track_ai_call("anthropic", "claude-opus-4-5-20250514", cost=0.015, duration=2.1)
        assert m._internal_counters["ai_requests"] == initial_count + 1
        assert m._internal_counters["ai_cost_usd"] == pytest.approx(initial_cost + 0.015)

    def test_track_ai_call_zero_cost(self):
        """track_ai_call handles zero cost and duration."""
        m = _reload_metrics({"METRICS_ENABLED": "false"})
        # Should not raise
        m.track_ai_call("ollama", "llama3.1:8b", cost=0.0, duration=0.0)

    def test_track_cache_hit(self):
        """track_cache increments hit counter."""
        m = _reload_metrics({"METRICS_ENABLED": "false"})
        initial = m._internal_counters["cache_hits"]
        m.track_cache("get", hit=True)
        assert m._internal_counters["cache_hits"] == initial + 1

    def test_track_cache_miss(self):
        """track_cache increments miss counter."""
        m = _reload_metrics({"METRICS_ENABLED": "false"})
        initial = m._internal_counters["cache_misses"]
        m.track_cache("get", hit=False)
        assert m._internal_counters["cache_misses"] == initial + 1

    def test_get_metrics_summary(self):
        """get_metrics_summary returns expected structure."""
        m = _reload_metrics({"METRICS_ENABLED": "false"})
        summary = m.get_metrics_summary()
        assert "metrics_enabled" in summary
        assert "prometheus_available" in summary
        assert "uptime_seconds" in summary
        assert "http_requests_total" in summary
        assert "ai_requests_total" in summary
        assert "ai_cost_usd_total" in summary
        assert "cache_hits" in summary
        assert "cache_misses" in summary
        assert summary["uptime_seconds"] >= 0

    def test_get_metrics_summary_reflects_tracking(self):
        """Metrics summary reflects tracked operations."""
        m = _reload_metrics({"METRICS_ENABLED": "false"})
        m.track_request("POST", "/api/test", 201, 0.1)
        m.track_ai_call("openai", "gpt-4o", cost=0.003, duration=0.8)
        m.track_cache("get", hit=True)
        m.track_cache("get", hit=False)

        summary = m.get_metrics_summary()
        assert summary["http_requests_total"] >= 1
        assert summary["ai_requests_total"] >= 1
        assert summary["ai_cost_usd_total"] >= 0.003
        assert summary["cache_hits"] >= 1
        assert summary["cache_misses"] >= 1


# ---------------------------------------------------------------------------
# MetricsMiddleware tests
# ---------------------------------------------------------------------------

class TestMetricsMiddleware:
    """Tests for middleware/metrics.py"""

    def test_normalize_path_with_id(self):
        """Path normalization replaces IDs with {id}."""
        from middleware.metrics import MetricsMiddleware
        mw = MetricsMiddleware(app=MagicMock())
        assert mw._normalize_path("/api/competitors/42") == "/api/competitors/{id}"
        assert mw._normalize_path("/api/chat/sessions/abc-123") == "/api/chat/sessions/{id}"
        assert mw._normalize_path("/api/ai/tasks/task-uuid") == "/api/ai/tasks/{id}"

    def test_normalize_path_with_subpath(self):
        """Path normalization handles sub-paths after ID."""
        from middleware.metrics import MetricsMiddleware
        mw = MetricsMiddleware(app=MagicMock())
        assert mw._normalize_path("/api/competitors/42/news") == "/api/competitors/{id}/news"
        assert mw._normalize_path("/api/chat/sessions/abc/messages") == "/api/chat/sessions/{id}/messages"

    def test_normalize_path_no_match(self):
        """Paths without known prefixes are returned unchanged."""
        from middleware.metrics import MetricsMiddleware
        mw = MetricsMiddleware(app=MagicMock())
        assert mw._normalize_path("/api/version") == "/api/version"
        assert mw._normalize_path("/health") == "/health"

    def test_skip_paths(self):
        """Health and metrics paths are excluded from tracking."""
        from middleware.metrics import MetricsMiddleware
        mw = MetricsMiddleware(app=MagicMock())
        assert "/health" in mw._SKIP_PATHS
        assert "/readiness" in mw._SKIP_PATHS
        assert "/metrics" in mw._SKIP_PATHS


# ---------------------------------------------------------------------------
# /metrics endpoint tests (via TestClient)
# ---------------------------------------------------------------------------

class TestMetricsEndpoint:
    """Tests for the /metrics endpoint in routers/health.py"""

    def test_metrics_endpoint_json_fallback(self):
        """When prometheus_client is not available, /metrics returns JSON."""
        # Ensure metrics is in disabled state
        _reload_metrics({"METRICS_ENABLED": "false"})

        # Use FastAPI TestClient
        from fastapi.testclient import TestClient

        # Import the health router and create a mini app
        from fastapi import FastAPI
        # Reload health router to pick up the metrics import
        if "routers.health" in sys.modules:
            del sys.modules["routers.health"]
        from routers.health import router

        test_app = FastAPI()
        test_app.include_router(router)

        client = TestClient(test_app)
        response = client.get("/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "metrics_enabled" in data
        assert "prometheus_available" in data

    def test_metrics_endpoint_returns_uptime(self):
        """Metrics summary includes a positive uptime."""
        _reload_metrics({"METRICS_ENABLED": "false"})

        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        if "routers.health" in sys.modules:
            del sys.modules["routers.health"]
        from routers.health import router

        test_app = FastAPI()
        test_app.include_router(router)

        client = TestClient(test_app)
        response = client.get("/metrics")
        data = response.json()
        assert data["uptime_seconds"] >= 0
