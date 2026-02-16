"""
Certify Intel - Security Headers Middleware Tests

Tests for SecurityHeadersMiddleware (middleware/security.py):
- All required security headers present on responses
- CSP policy allows required CDN resources
- HSTS only added for HTTPS requests
- Middleware can be disabled via SECURITY_HEADERS_ENABLED env var
"""
import os
import sys
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pytestmark = pytest.mark.timeout(20)


class TestSecurityHeadersPresence:
    """Verify all required security headers are present."""

    def test_x_content_type_options(self, test_client):
        response = test_client.get("/health")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"

    def test_x_frame_options(self, test_client):
        response = test_client.get("/health")
        assert response.headers.get("X-Frame-Options") == "DENY"

    def test_x_xss_protection(self, test_client):
        response = test_client.get("/health")
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"

    def test_referrer_policy(self, test_client):
        response = test_client.get("/health")
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_permissions_policy(self, test_client):
        response = test_client.get("/health")
        policy = response.headers.get("Permissions-Policy")
        assert "camera=()" in policy
        assert "microphone=()" in policy
        assert "geolocation=()" in policy

    def test_csp_present(self, test_client):
        response = test_client.get("/health")
        csp = response.headers.get("Content-Security-Policy")
        assert csp is not None
        assert "default-src 'self'" in csp


class TestCSPPolicy:
    """Verify CSP allows required external resources."""

    def test_csp_allows_jsdelivr_scripts(self, test_client):
        response = test_client.get("/health")
        csp = response.headers.get("Content-Security-Policy")
        assert "https://cdn.jsdelivr.net" in csp

    def test_csp_allows_google_fonts_styles(self, test_client):
        response = test_client.get("/health")
        csp = response.headers.get("Content-Security-Policy")
        assert "https://fonts.googleapis.com" in csp

    def test_csp_allows_google_fonts_files(self, test_client):
        response = test_client.get("/health")
        csp = response.headers.get("Content-Security-Policy")
        assert "https://fonts.gstatic.com" in csp

    def test_csp_allows_inline_scripts(self, test_client):
        """SPA requires inline scripts."""
        response = test_client.get("/health")
        csp = response.headers.get("Content-Security-Policy")
        assert "'unsafe-inline'" in csp

    def test_csp_allows_websocket(self, test_client):
        """Real-time updates use WebSocket."""
        response = test_client.get("/health")
        csp = response.headers.get("Content-Security-Policy")
        assert "ws:" in csp or "wss:" in csp

    def test_csp_allows_data_uri_images(self, test_client):
        response = test_client.get("/health")
        csp = response.headers.get("Content-Security-Policy")
        assert "data:" in csp


class TestHSTS:
    """Verify HSTS behavior."""

    def test_no_hsts_over_http(self, test_client):
        """HSTS should not be added for HTTP requests."""
        response = test_client.get("/health")
        # TestClient uses http by default
        assert "Strict-Transport-Security" not in response.headers

    def test_hsts_with_forwarded_proto(self, test_client):
        """HSTS should be added when X-Forwarded-Proto is https."""
        response = test_client.get("/health", headers={"X-Forwarded-Proto": "https"})
        hsts = response.headers.get("Strict-Transport-Security")
        assert hsts is not None
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts


class TestSecurityMiddlewareConfig:
    """Verify middleware configurability."""

    def test_middleware_module_importable(self):
        """Middleware can be imported from the module."""
        from middleware.security import SecurityHeadersMiddleware
        assert SecurityHeadersMiddleware is not None

    def test_is_security_headers_enabled_default(self):
        """Default should be enabled (true)."""
        from middleware.security import is_security_headers_enabled
        with patch.dict(os.environ, {}, clear=False):
            # Remove SECURITY_HEADERS_ENABLED if set
            os.environ.pop("SECURITY_HEADERS_ENABLED", None)
            assert is_security_headers_enabled() is True

    def test_is_security_headers_enabled_false(self):
        """Can be disabled via env var."""
        from middleware.security import is_security_headers_enabled
        with patch.dict(os.environ, {"SECURITY_HEADERS_ENABLED": "false"}):
            assert is_security_headers_enabled() is False

    def test_is_security_headers_enabled_true(self):
        """Explicitly enabled."""
        from middleware.security import is_security_headers_enabled
        with patch.dict(os.environ, {"SECURITY_HEADERS_ENABLED": "true"}):
            assert is_security_headers_enabled() is True
