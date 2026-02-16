"""
HTTP metrics middleware for Certify Intel.

Tracks request count and duration per method/path/status.
Zero overhead when METRICS_ENABLED=false (default).
"""

import time
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect HTTP request metrics.

    Tracks total request count and request duration by method, path, and
    status code. When METRICS_ENABLED is false, the middleware passes
    through without any overhead.
    """

    # Paths to exclude from per-path metric labels to avoid high cardinality
    _SKIP_PATHS = frozenset({"/health", "/readiness", "/metrics", "/favicon.ico"})

    # Path prefixes that should be normalized (e.g., /api/competitors/123 -> /api/competitors/{id})
    _NORMALIZE_PREFIXES = (
        "/api/competitors/",
        "/api/chat/sessions/",
        "/api/ai/tasks/",
        "/api/news-feed/",
    )

    def _normalize_path(self, path: str) -> str:
        """Normalize paths with IDs to prevent high-cardinality labels."""
        for prefix in self._NORMALIZE_PREFIXES:
            if path.startswith(prefix):
                # Replace the ID segment with {id}
                rest = path[len(prefix):]
                if rest and "/" not in rest:
                    return prefix + "{id}"
                elif rest and "/" in rest:
                    parts = rest.split("/", 1)
                    return prefix + "{id}/" + parts[1]
        return path

    async def dispatch(self, request: Request, call_next):
        from metrics import METRICS_ENABLED, track_request

        if not METRICS_ENABLED:
            return await call_next(request)

        start = time.time()
        response = await call_next(request)
        duration = time.time() - start

        path = request.url.path
        if path not in self._SKIP_PATHS:
            normalized = self._normalize_path(path)
            track_request(request.method, normalized, response.status_code, duration)

        return response
