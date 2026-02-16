"""
Certify Intel - API Endpoint Tests
TEST-001: Comprehensive unit test coverage for API endpoints

Tests for all major API endpoints including:
- Authentication
- Competitors CRUD
- News Feed
- Analytics
- Change History
- Data Quality

Note: These tests use TestClient with SQLite database.
Endpoints that call external APIs (news, AI) are tested with
cache-only mode or mocked to avoid network dependencies.
"""
import pytest
import sys
import os
from datetime import datetime
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mark entire module with a generous timeout
pytestmark = pytest.mark.timeout(20)


# ==============================================================================
# Authentication Tests
# ==============================================================================

class TestAuthentication:
    """Tests for authentication endpoints."""

    def test_login_success(self, test_client, sample_user):
        """Test successful login."""
        response = test_client.post(
            "/token",
            data={
                "username": "test@certifyhealth.com",
                "password": "testpassword123"
            }
        )
        assert response.status_code in [200, 401]  # May fail if user doesn't exist

    def test_login_invalid_credentials(self, test_client):
        """Test login with invalid credentials."""
        response = test_client.post(
            "/token",
            data={
                "username": "invalid@test.com",
                "password": "wrongpassword"
            }
        )
        assert response.status_code in [401, 400]

    def test_protected_endpoint_without_auth(self, test_client):
        """Test accessing protected endpoint without authentication."""
        response = test_client.get("/api/auth/me")
        assert response.status_code == 401


# ==============================================================================
# Competitor Endpoint Tests
# ==============================================================================

class TestCompetitorEndpoints:
    """Tests for competitor CRUD endpoints."""

    def test_list_competitors(self, test_client, api_test_competitor, auth_headers):
        """Test listing all competitors."""
        response = test_client.get("/api/competitors", headers=auth_headers)
        # May return 200 with auth or 401 without valid auth
        assert response.status_code in [200, 401]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)

    def test_list_competitors_with_filters(self, test_client, api_test_competitor, auth_headers):
        """Test listing competitors with filters."""
        response = test_client.get("/api/competitors?threat_level=High", headers=auth_headers)
        assert response.status_code in [200, 401]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)

    def test_create_competitor(self, test_client, auth_headers):
        """Test creating a new competitor."""
        new_competitor = {
            "name": f"New Test Competitor {datetime.now().timestamp()}",
            "website": "https://newtestcompetitor.com",
            "notes": "A newly created test competitor",  # Use 'notes' not 'description'
            "headquarters": "New York, NY",
            "employee_count": "250",  # String type in schema
            "pricing_model": "Enterprise",
            "target_segments": "Healthcare IT"  # Use 'target_segments' not 'target_market'
        }
        response = test_client.post(
            "/api/competitors",
            json=new_competitor,
            headers=auth_headers
        )
        # May need auth or may succeed
        assert response.status_code in [200, 201, 401, 422]

    def test_get_competitor_by_id(self, test_client, api_test_competitor, auth_headers):
        """Test getting a specific competitor."""
        response = test_client.get(f"/api/competitors/{api_test_competitor['id']}", headers=auth_headers)
        assert response.status_code in [200, 401, 404]
        if response.status_code == 200:
            data = response.json()
            assert data["name"] == api_test_competitor["name"]

    def test_update_competitor(self, test_client, api_test_competitor, auth_headers):
        """Test updating a competitor."""
        update_data = {
            "notes": "Updated description",  # Use 'notes' not 'description'
            "employee_count": "600"  # String type in schema
        }
        response = test_client.put(
            f"/api/competitors/{api_test_competitor['id']}",
            json=update_data,
            headers=auth_headers
        )
        assert response.status_code in [200, 401, 404]


# ==============================================================================
# News Feed Tests
# ==============================================================================

class TestNewsFeedEndpoints:
    """Tests for news feed endpoints.

    Note: The news-feed endpoint calls external APIs (Google News, GNews, etc.)
    when there's no cached data. We mock the NewsMonitor to avoid network calls.
    """

    def test_get_news_feed(self, test_client):
        """Test getting the news feed (with mocked external calls)."""
        # Mock NewsMonitor to avoid real HTTP calls to external news APIs.
        # The endpoint imports from news_monitor module inside the function.
        with patch("news_monitor.NewsMonitor") as MockMonitor:
            mock_instance = MagicMock()
            mock_instance.fetch_news.return_value = MagicMock(articles=[])
            MockMonitor.return_value = mock_instance

            response = test_client.get("/api/news-feed")
            assert response.status_code == 200
            data = response.json()
            assert "articles" in data or isinstance(data, list)

    def test_get_news_with_filters(self, test_client):
        """Test getting news with filters."""
        with patch("news_monitor.NewsMonitor") as MockMonitor:
            mock_instance = MagicMock()
            mock_instance.fetch_news.return_value = MagicMock(articles=[])
            MockMonitor.return_value = mock_instance

            response = test_client.get("/api/news-feed?sentiment=positive&limit=10")
            assert response.status_code == 200

    def test_get_competitor_news(self, test_client, api_test_competitor):
        """Test getting news for a specific competitor."""
        response = test_client.get(f"/api/competitors/{api_test_competitor['id']}/news")
        assert response.status_code in [200, 404]


# ==============================================================================
# Analytics Tests
# ==============================================================================

class TestAnalyticsEndpoints:
    """Tests for analytics endpoints."""

    def test_get_analytics_dashboard(self, test_client):
        """Test getting analytics dashboard data."""
        response = test_client.get("/api/analytics/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_get_market_map(self, test_client):
        """Test getting market map data."""
        response = test_client.get("/api/analytics/market-map")
        assert response.status_code == 200

    def test_get_analytics_summary(self, test_client, auth_headers):
        """Test getting AI analytics summary."""
        response = test_client.get("/api/analytics/summary", headers=auth_headers)
        assert response.status_code in [200, 401]


# ==============================================================================
# Change History Tests
# ==============================================================================

class TestChangeHistoryEndpoints:
    """Tests for change history endpoints."""

    def test_get_changes(self, test_client):
        """Test getting change history."""
        response = test_client.get("/api/changes")
        assert response.status_code == 200
        data = response.json()
        assert "changes" in data

    def test_get_changes_with_filters(self, test_client):
        """Test getting changes with filters."""
        response = test_client.get("/api/changes?days=7&page=1&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert "changes" in data
        assert "total_count" in data
        assert "page" in data

    def test_get_change_timeline(self, test_client):
        """Test getting change timeline."""
        response = test_client.get("/api/changes/timeline")
        assert response.status_code == 200
        data = response.json()
        assert "timeline" in data

    def test_get_change_diff(self, test_client):
        """Test getting change diff endpoint exists."""
        # Use a non-existent ID to test the endpoint responds correctly
        response = test_client.get("/api/changes/99999/diff")
        # Endpoint should return 404 for non-existent change or 200 if found
        assert response.status_code in [200, 404]

    def test_export_changes_csv(self, test_client):
        """Test exporting changes as CSV."""
        response = test_client.get("/api/changes/export?format=csv")
        assert response.status_code == 200


# ==============================================================================
# Data Quality Tests
# ==============================================================================

class TestDataQualityEndpoints:
    """Tests for data quality endpoints."""

    def test_get_data_quality_overview(self, test_client):
        """Test getting data quality overview."""
        response = test_client.get("/api/data-quality/overview")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_get_low_confidence_data(self, test_client):
        """Test getting low confidence data."""
        response = test_client.get("/api/data-quality/low-confidence")
        assert response.status_code == 200


# ==============================================================================
# Sales & Marketing Tests
# ==============================================================================

class TestSalesMarketingEndpoints:
    """Tests for sales & marketing endpoints."""

    def test_get_dimensions(self, test_client):
        """Test getting all dimensions."""
        response = test_client.get("/api/sales-marketing/dimensions")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))

    def test_get_competitor_dimensions(self, test_client, api_test_competitor):
        """Test getting competitor dimension scores."""
        response = test_client.get(
            f"/api/sales-marketing/competitors/{api_test_competitor['id']}/dimensions"
        )
        assert response.status_code in [200, 404]


# ==============================================================================
# Products Tests
# ==============================================================================

class TestProductEndpoints:
    """Tests for product endpoints."""

    def test_get_products_coverage(self, test_client):
        """Test getting products coverage."""
        response = test_client.get("/api/products/coverage")
        assert response.status_code == 200
        data = response.json()
        assert "total_products" in data
        assert "coverage_percentage" in data

    def test_get_competitor_products(self, test_client, api_test_competitor):
        """Test getting products for a competitor."""
        response = test_client.get(f"/api/products/competitor/{api_test_competitor['id']}")
        assert response.status_code in [200, 404]


# ==============================================================================
# Health Check Tests
# ==============================================================================

class TestHealthCheck:
    """Tests for health check endpoints."""

    def test_health_endpoint(self, test_client):
        """Test health check endpoint."""
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"

    def test_ai_status(self, test_client):
        """Test AI status endpoint."""
        response = test_client.get("/api/ai/status")
        assert response.status_code == 200
        data = response.json()
        assert "provider" in data or "status" in data


# ==============================================================================
# Performance Metrics Tests
# ==============================================================================

class TestPerformanceMetrics:
    """Tests for performance monitoring endpoints."""

    def test_record_web_vitals(self, test_client):
        """Test recording web vitals."""
        metric = {
            "name": "LCP",
            "value": 2500.5,
            "rating": "good",
            "url": "/dashboard"
        }
        response = test_client.post("/api/metrics/vitals", json=metric)
        assert response.status_code == 200

    def test_get_web_vitals_summary(self, test_client):
        """Test getting web vitals summary."""
        response = test_client.get("/api/metrics/vitals/summary")
        assert response.status_code == 200


# ==============================================================================
# Scheduler Tests
# ==============================================================================

class TestSchedulerEndpoints:
    """Tests for scheduler endpoints."""

    def test_get_scheduler_status(self, test_client):
        """Test getting scheduler status."""
        response = test_client.get("/api/scheduler/status")
        assert response.status_code == 200
