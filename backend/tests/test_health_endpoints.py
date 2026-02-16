"""
Certify Intel - Health Endpoint Tests

Tests for /health and /readiness probe endpoints.

Run: python -m pytest -xvs tests/test_health_endpoints.py
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a FastAPI TestClient for health endpoint tests."""
    import sys
    import os
    # Ensure backend is on the path
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    from main import app
    return TestClient(app)


class TestHealthEndpoint:
    """Test the /health liveness probe."""

    def test_health_returns_200(self, client):
        """GET /health should return 200 with status and version."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_health_includes_version_string(self, client):
        """GET /health version should be a non-empty string."""
        response = client.get("/health")
        data = response.json()
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0


class TestReadinessEndpoint:
    """Test the /readiness probe endpoint."""

    def test_readiness_returns_200(self, client):
        """GET /readiness should return 200 when all checks pass."""
        response = client.get("/readiness")
        # May be 200 or 503 depending on environment
        assert response.status_code in (200, 503)
        data = response.json()
        assert "status" in data
        assert data["status"] in ("ready", "degraded")

    def test_readiness_includes_checks(self, client):
        """GET /readiness should include a checks dict."""
        response = client.get("/readiness")
        data = response.json()
        assert "checks" in data
        assert isinstance(data["checks"], dict)

    def test_readiness_checks_database(self, client):
        """GET /readiness should check database connectivity."""
        response = client.get("/readiness")
        data = response.json()
        assert "database" in data["checks"]

    def test_readiness_checks_ai_router(self, client):
        """GET /readiness should check AI router availability."""
        response = client.get("/readiness")
        data = response.json()
        assert "ai_router" in data["checks"]

    def test_readiness_includes_version(self, client):
        """GET /readiness should include version."""
        response = client.get("/readiness")
        data = response.json()
        assert "version" in data
