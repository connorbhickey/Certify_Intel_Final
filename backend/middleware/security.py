"""Security headers middleware for FastAPI.

Adds Content-Security-Policy, HSTS, X-Frame-Options, X-Content-Type-Options,
Referrer-Policy, Permissions-Policy, and X-XSS-Protection headers to all
responses.

Configurable via SECURITY_HEADERS_ENABLED env var (default: true).
"""

import logging
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)


def is_security_headers_enabled() -> bool:
    """Check if security headers middleware is enabled via env var."""
    return os.getenv("SECURITY_HEADERS_ENABLED", "true").lower() in ("true", "1", "yes")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses.

    Adds CSP, HSTS, X-Frame-Options, X-Content-Type-Options,
    Referrer-Policy, Permissions-Policy, and X-XSS-Protection.

    CSP allows:
    - Inline scripts/styles (required for SPA)
    - Chart.js from cdn.jsdelivr.net
    - Google Fonts from fonts.googleapis.com / fonts.gstatic.com
    - WebSocket connections (ws:/wss:) for real-time updates
    - Data URIs and blob: for images
    - External API connections for AI providers

    Disable via SECURITY_HEADERS_ENABLED=false in .env.
    """

    CSP_POLICY = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
        "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net data:; "
        "img-src 'self' data: https: blob:; "
        "connect-src 'self' https://api.openai.com https://generativelanguage.googleapis.com wss: ws:; "
        "frame-ancestors 'self'; "
        "form-action 'self'; "
        "base-uri 'self'"
    )

    def __init__(self, app, enabled: bool = True) -> None:
        super().__init__(app)
        self.enabled = enabled and is_security_headers_enabled()
        if not self.enabled:
            logger.info("SecurityHeadersMiddleware is DISABLED via SECURITY_HEADERS_ENABLED=false")

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        if not self.enabled:
            return response

        # Core security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        # Content Security Policy
        response.headers["Content-Security-Policy"] = self.CSP_POLICY

        # HSTS - only enable if using HTTPS (check X-Forwarded-Proto or scheme)
        forwarded_proto = request.headers.get("X-Forwarded-Proto", "")
        if forwarded_proto == "https" or request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response
