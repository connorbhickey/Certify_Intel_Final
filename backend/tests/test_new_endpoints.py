"""
Certify Intel - Tests for New API Endpoints (v9.0 Sprint)

Tests for:
- AI cost analytics (GET /api/ai/cost/summary, GET /api/ai/cost/daily)
- Audit log search (GET /api/audit/logs)
- Password change (POST /api/auth/change-password)
- Competitor relationships (POST/GET /api/competitors/{id}/relationships)
"""

import os
import sys
import pytest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['TESTING'] = 'true'
os.environ['DATABASE_URL'] = 'sqlite:///./test_certify_intel.db'

pytestmark = pytest.mark.timeout(20)


# ==============================================================================
# Helper: login and get auth headers
# ==============================================================================

ADMIN_EMAIL = "[YOUR-ADMIN-EMAIL]"
ADMIN_PASSWORD = "[YOUR-ADMIN-PASSWORD]"


def _login(client):
    """Login with the seeded admin and return auth headers."""
    resp = client.post("/token", data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if resp.status_code != 200:
        return {}
    token = resp.json().get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# AI Cost Analytics Tests
# ==============================================================================

class TestAICostSummary:
    """Tests for GET /api/ai/cost/summary."""

    def test_cost_summary_returns_structure(self, test_client):
        """AI cost summary returns expected fields."""
        headers = _login(test_client)
        if not headers:
            pytest.skip("Login failed")

        resp = test_client.get("/api/ai/cost/summary", headers=headers)
        assert resp.status_code == 200
        data = resp.json()

        assert "total" in data
        assert "by_provider" in data
        assert "period" in data
        assert isinstance(data["total"], (int, float))
        assert isinstance(data["by_provider"], dict)
        assert data["period"] == "all_time"

    def test_cost_summary_requires_auth(self, test_client):
        """AI cost summary rejects unauthenticated requests."""
        resp = test_client.get("/api/ai/cost/summary")
        assert resp.status_code == 401


class TestAICostDaily:
    """Tests for GET /api/ai/cost/daily."""

    def test_cost_daily_returns_30_days(self, test_client):
        """Daily cost breakdown returns 30 days of data."""
        headers = _login(test_client)
        if not headers:
            pytest.skip("Login failed")

        resp = test_client.get("/api/ai/cost/daily", headers=headers)
        assert resp.status_code == 200
        data = resp.json()

        assert isinstance(data, list)
        assert len(data) == 30

        # Each entry has date, cost, calls
        entry = data[0]
        assert "date" in entry
        assert "cost" in entry
        assert "calls" in entry

    def test_cost_daily_requires_auth(self, test_client):
        """Daily cost breakdown rejects unauthenticated requests."""
        resp = test_client.get("/api/ai/cost/daily")
        assert resp.status_code == 401


# ==============================================================================
# Audit Log Search Tests
# ==============================================================================

class TestAuditLogSearch:
    """Tests for GET /api/audit/logs."""

    def test_audit_logs_basic(self, test_client):
        """Audit logs returns paginated structure."""
        headers = _login(test_client)
        if not headers:
            pytest.skip("Login failed")

        resp = test_client.get("/api/audit/logs", headers=headers)
        assert resp.status_code == 200
        data = resp.json()

        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "pages" in data
        assert isinstance(data["items"], list)
        assert data["page"] == 1

    def test_audit_logs_filtered_by_action(self, test_client):
        """Audit logs can be filtered by action type."""
        headers = _login(test_client)
        if not headers:
            pytest.skip("Login failed")

        resp = test_client.get("/api/audit/logs?action=login", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["items"], list)
        # All returned items should have action_type == "login" (or be empty)
        for item in data["items"]:
            assert item["action_type"] == "login"

    def test_audit_logs_paginated(self, test_client):
        """Audit logs supports pagination parameters."""
        headers = _login(test_client)
        if not headers:
            pytest.skip("Login failed")

        resp = test_client.get("/api/audit/logs?page=1&per_page=5", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        # Items should not exceed per_page
        assert len(data["items"]) <= 5

    def test_audit_logs_date_filter(self, test_client):
        """Audit logs can be filtered by date range."""
        headers = _login(test_client)
        if not headers:
            pytest.skip("Login failed")

        today = datetime.utcnow().strftime("%Y-%m-%d")
        resp = test_client.get(
            f"/api/audit/logs?start_date={today}&end_date={today}",
            headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["items"], list)

    def test_audit_logs_invalid_date(self, test_client):
        """Audit logs rejects invalid date format."""
        headers = _login(test_client)
        if not headers:
            pytest.skip("Login failed")

        resp = test_client.get("/api/audit/logs?start_date=not-a-date", headers=headers)
        assert resp.status_code == 400

    def test_audit_logs_requires_auth(self, test_client):
        """Audit logs rejects unauthenticated requests."""
        resp = test_client.get("/api/audit/logs")
        assert resp.status_code == 401


# ==============================================================================
# Password Change Tests
# ==============================================================================

class TestPasswordChange:
    """Tests for POST /api/auth/change-password."""

    def test_change_password_success(self, test_client):
        """Successfully change password and verify login with new password."""
        headers = _login(test_client)
        if not headers:
            pytest.skip("Login failed")

        new_pw = "NewSecurePassword123!"
        resp = test_client.post(
            "/api/auth/change-password",
            json={
                "old_password": ADMIN_PASSWORD,
                "new_password": new_pw,
                "confirm_password": new_pw,
            },
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Password changed successfully"

        # Verify login works with new password
        login_resp = test_client.post(
            "/token",
            data={"username": ADMIN_EMAIL, "password": new_pw}
        )
        assert login_resp.status_code == 200

        # Revert password back for other tests
        new_headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}
        revert_resp = test_client.post(
            "/api/auth/change-password",
            json={
                "old_password": new_pw,
                "new_password": ADMIN_PASSWORD,
                "confirm_password": ADMIN_PASSWORD,
            },
            headers=new_headers,
        )
        assert revert_resp.status_code == 200

    def test_change_password_wrong_old(self, test_client):
        """Reject password change when old password is wrong."""
        headers = _login(test_client)
        if not headers:
            pytest.skip("Login failed")

        resp = test_client.post(
            "/api/auth/change-password",
            json={
                "old_password": "definitelyWrongPassword",
                "new_password": "NewPassword123!",
                "confirm_password": "NewPassword123!",
            },
            headers=headers,
        )
        assert resp.status_code == 401
        assert "incorrect" in resp.json()["detail"].lower()

    def test_change_password_mismatch(self, test_client):
        """Reject password change when new password and confirmation don't match."""
        headers = _login(test_client)
        if not headers:
            pytest.skip("Login failed")

        resp = test_client.post(
            "/api/auth/change-password",
            json={
                "old_password": ADMIN_PASSWORD,
                "new_password": "NewPassword123!",
                "confirm_password": "DifferentPassword456!",
            },
            headers=headers,
        )
        assert resp.status_code == 400
        assert "match" in resp.json()["detail"].lower()

    def test_change_password_too_short(self, test_client):
        """Reject password change when new password is too short."""
        headers = _login(test_client)
        if not headers:
            pytest.skip("Login failed")

        resp = test_client.post(
            "/api/auth/change-password",
            json={
                "old_password": ADMIN_PASSWORD,
                "new_password": "short",
                "confirm_password": "short",
            },
            headers=headers,
        )
        assert resp.status_code == 400
        assert "8 characters" in resp.json()["detail"]

    def test_change_password_requires_auth(self, test_client):
        """Password change rejects unauthenticated requests."""
        resp = test_client.post(
            "/api/auth/change-password",
            json={
                "old_password": "old",
                "new_password": "newpassword1",
                "confirm_password": "newpassword1",
            },
        )
        assert resp.status_code == 401


# ==============================================================================
# Competitor Relationship Tests
# ==============================================================================

class TestCompetitorRelationships:
    """Tests for POST/GET /api/competitors/{id}/relationships."""

    def _ensure_two_competitors(self, test_client, headers):
        """Ensure at least two competitors exist, return their IDs."""
        resp = test_client.get("/api/competitors", headers=headers)
        if resp.status_code != 200:
            return None, None
        competitors = resp.json()
        if len(competitors) < 2:
            # Create two competitors
            for i in range(2 - len(competitors)):
                import uuid
                test_client.post(
                    "/api/competitors",
                    json={
                        "name": f"RelTest Competitor {uuid.uuid4().hex[:8]}",
                        "website": f"https://reltest-{uuid.uuid4().hex[:8]}.com",
                    },
                    headers=headers,
                )
            resp = test_client.get("/api/competitors", headers=headers)
            competitors = resp.json()

        return competitors[0]["id"], competitors[1]["id"]

    def test_create_relationship(self, test_client):
        """Create a competitor relationship."""
        headers = _login(test_client)
        if not headers:
            pytest.skip("Login failed")

        id_a, id_b = self._ensure_two_competitors(test_client, headers)
        if not id_a or not id_b:
            pytest.skip("Could not get two competitors")

        resp = test_client.post(
            f"/api/competitors/{id_a}/relationships",
            json={
                "related_id": id_b,
                "relationship_type": "partner",
                "notes": "Testing relationship creation",
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["competitor_id"] == id_a
        assert data["related_id"] == id_b
        assert data["relationship_type"] == "partner"

    def test_list_relationships(self, test_client):
        """List relationships for a competitor."""
        headers = _login(test_client)
        if not headers:
            pytest.skip("Login failed")

        id_a, id_b = self._ensure_two_competitors(test_client, headers)
        if not id_a or not id_b:
            pytest.skip("Could not get two competitors")

        resp = test_client.get(
            f"/api/competitors/{id_a}/relationships",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "relationships" in data
        assert "total" in data
        assert isinstance(data["relationships"], list)

    def test_create_relationship_invalid_type(self, test_client):
        """Reject invalid relationship type."""
        headers = _login(test_client)
        if not headers:
            pytest.skip("Login failed")

        id_a, id_b = self._ensure_two_competitors(test_client, headers)
        if not id_a or not id_b:
            pytest.skip("Could not get two competitors")

        resp = test_client.post(
            f"/api/competitors/{id_a}/relationships",
            json={
                "related_id": id_b,
                "relationship_type": "invalid_type",
            },
            headers=headers,
        )
        assert resp.status_code == 400

    def test_create_relationship_self_reference(self, test_client):
        """Reject self-referencing relationship."""
        headers = _login(test_client)
        if not headers:
            pytest.skip("Login failed")

        id_a, _ = self._ensure_two_competitors(test_client, headers)
        if not id_a:
            pytest.skip("Could not get competitor")

        resp = test_client.post(
            f"/api/competitors/{id_a}/relationships",
            json={
                "related_id": id_a,
                "relationship_type": "partner",
            },
            headers=headers,
        )
        assert resp.status_code == 400

    def test_create_relationship_nonexistent_competitor(self, test_client):
        """Reject relationship with nonexistent competitor."""
        headers = _login(test_client)
        if not headers:
            pytest.skip("Login failed")

        resp = test_client.post(
            "/api/competitors/999999/relationships",
            json={
                "related_id": 999998,
                "relationship_type": "partner",
            },
            headers=headers,
        )
        assert resp.status_code == 404

    def test_relationships_require_auth(self, test_client):
        """Relationship endpoints reject unauthenticated requests."""
        resp = test_client.get("/api/competitors/1/relationships")
        assert resp.status_code == 401

        resp = test_client.post(
            "/api/competitors/1/relationships",
            json={"related_id": 2, "relationship_type": "partner"},
        )
        assert resp.status_code == 401
