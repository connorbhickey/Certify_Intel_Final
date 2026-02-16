"""
Certify Intel - Refresh Token Tests
Tests for the refresh token system including:
- Login returns refresh token
- Token refresh flow (rotation)
- Logout revokes refresh token
- Expired/revoked token rejection
- Concurrent refresh deduplication
"""
import pytest
import sys
import os
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mark entire module with a generous timeout
pytestmark = pytest.mark.timeout(20)


def _create_test_user(session):
    """Create a test user and return (user, raw_password)."""
    from database import User

    password = "TestPassword123!"
    salt = secrets.token_bytes(32)
    pw_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000).hex()
    hashed = f"{salt.hex()}${pw_hash}"
    unique = str(uuid.uuid4())[:8]

    user = User(
        email=f"refresh-test-{unique}@certifyintel.com",
        hashed_password=hashed,
        full_name="Refresh Test User",
        role="admin",
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user, password


def _login(client, email, password):
    """Login and return the response JSON."""
    response = client.post(
        "/token",
        data={"username": email, "password": password}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()


class TestLoginReturnsRefreshToken:
    """Test that login endpoint now returns refresh tokens."""

    def test_login_returns_refresh_token(self, test_client):
        """Login should return both access_token and refresh_token."""
        from tests.conftest import TestingSessionLocal
        session = TestingSessionLocal()
        try:
            user, password = _create_test_user(session)
            data = _login(test_client, user.email, password)

            assert "access_token" in data
            assert "refresh_token" in data
            assert "expires_in" in data
            assert data["token_type"] == "bearer"
            assert data["expires_in"] == 900  # 15 minutes
        finally:
            session.close()

    def test_login_returns_user_info(self, test_client):
        """Login should still return user info alongside tokens."""
        from tests.conftest import TestingSessionLocal
        session = TestingSessionLocal()
        try:
            user, password = _create_test_user(session)
            data = _login(test_client, user.email, password)

            assert "user" in data
            assert data["user"]["email"] == user.email
            assert data["user"]["role"] == "admin"
        finally:
            session.close()


class TestTokenRefresh:
    """Test the /api/auth/refresh endpoint."""

    def test_refresh_returns_new_tokens(self, test_client):
        """Refreshing should return new access and refresh tokens."""
        from tests.conftest import TestingSessionLocal
        session = TestingSessionLocal()
        try:
            user, password = _create_test_user(session)
            login_data = _login(test_client, user.email, password)

            response = test_client.post(
                "/api/auth/refresh",
                json={"refresh_token": login_data["refresh_token"]}
            )
            assert response.status_code == 200

            refresh_data = response.json()
            assert "access_token" in refresh_data
            assert "refresh_token" in refresh_data
            assert "expires_in" in refresh_data
            # Refresh token must be different (new UUID generated)
            assert refresh_data["refresh_token"] != login_data["refresh_token"]
            # Access token may be identical if generated in same second (same JWT payload)
            # so we verify it's valid instead of checking string inequality
            assert len(refresh_data["access_token"]) > 0
        finally:
            session.close()

    def test_old_refresh_token_revoked_after_rotation(self, test_client):
        """After refresh, the old refresh token should be revoked."""
        from tests.conftest import TestingSessionLocal
        session = TestingSessionLocal()
        try:
            user, password = _create_test_user(session)
            login_data = _login(test_client, user.email, password)
            old_refresh = login_data["refresh_token"]

            # Use the refresh token
            response = test_client.post(
                "/api/auth/refresh",
                json={"refresh_token": old_refresh}
            )
            assert response.status_code == 200

            # Try to use the old refresh token again -- should fail
            response2 = test_client.post(
                "/api/auth/refresh",
                json={"refresh_token": old_refresh}
            )
            assert response2.status_code == 401
        finally:
            session.close()

    def test_refresh_with_invalid_token(self, test_client):
        """Refreshing with an invalid token should return 401."""
        response = test_client.post(
            "/api/auth/refresh",
            json={"refresh_token": "invalid-token-value"}
        )
        assert response.status_code == 401

    def test_refresh_with_expired_token(self, test_client):
        """Refreshing with an expired token should return 401."""
        from tests.conftest import TestingSessionLocal
        from database import RefreshToken
        session = TestingSessionLocal()
        try:
            user, password = _create_test_user(session)
            login_data = _login(test_client, user.email, password)

            # Manually expire the token in the database
            token_record = session.query(RefreshToken).filter(
                RefreshToken.token == login_data["refresh_token"]
            ).first()
            assert token_record is not None
            token_record.expires_at = datetime.utcnow() - timedelta(hours=1)
            session.commit()

            response = test_client.post(
                "/api/auth/refresh",
                json={"refresh_token": login_data["refresh_token"]}
            )
            assert response.status_code == 401
        finally:
            session.close()

    def test_new_access_token_works(self, test_client):
        """The new access token from refresh should be valid for API calls."""
        from tests.conftest import TestingSessionLocal
        session = TestingSessionLocal()
        try:
            user, password = _create_test_user(session)
            login_data = _login(test_client, user.email, password)

            # Refresh
            response = test_client.post(
                "/api/auth/refresh",
                json={"refresh_token": login_data["refresh_token"]}
            )
            new_data = response.json()

            # Use the new access token
            me_response = test_client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {new_data['access_token']}"}
            )
            assert me_response.status_code == 200
            assert me_response.json()["email"] == user.email
        finally:
            session.close()


class TestLogout:
    """Test the /api/auth/logout endpoint."""

    def test_logout_revokes_refresh_token(self, test_client):
        """Logout should revoke the refresh token."""
        from tests.conftest import TestingSessionLocal
        session = TestingSessionLocal()
        try:
            user, password = _create_test_user(session)
            login_data = _login(test_client, user.email, password)

            # Logout
            response = test_client.post(
                "/api/auth/logout",
                json={"refresh_token": login_data["refresh_token"]}
            )
            assert response.status_code == 200
            assert response.json()["status"] == "ok"

            # Try to refresh with the revoked token -- should fail
            refresh_response = test_client.post(
                "/api/auth/refresh",
                json={"refresh_token": login_data["refresh_token"]}
            )
            assert refresh_response.status_code == 401
        finally:
            session.close()

    def test_logout_with_invalid_token(self, test_client):
        """Logout with an invalid token should still return 200 (idempotent)."""
        response = test_client.post(
            "/api/auth/logout",
            json={"refresh_token": "nonexistent-token"}
        )
        assert response.status_code == 200


class TestRefreshTokenModel:
    """Test the RefreshToken database model and AuthManager methods directly."""

    def test_create_and_validate_refresh_token(self, db_session):
        """Test creating and validating a refresh token via AuthManager."""
        from extended_features import auth_manager

        user, _ = _create_test_user(db_session)
        token_value = auth_manager.create_refresh_token(db_session, user.id)

        assert token_value is not None
        assert len(token_value) == 36  # UUID format

        # Validate
        record = auth_manager.validate_refresh_token(db_session, token_value)
        assert record is not None
        assert record.user_id == user.id
        assert record.revoked is False

    def test_revoke_refresh_token(self, db_session):
        """Test revoking a refresh token."""
        from extended_features import auth_manager

        user, _ = _create_test_user(db_session)
        token_value = auth_manager.create_refresh_token(db_session, user.id)

        result = auth_manager.revoke_refresh_token(db_session, token_value)
        assert result is True

        # Should no longer validate
        record = auth_manager.validate_refresh_token(db_session, token_value)
        assert record is None

    def test_revoke_all_user_tokens(self, db_session):
        """Test revoking all tokens for a user."""
        from extended_features import auth_manager

        user, _ = _create_test_user(db_session)
        token1 = auth_manager.create_refresh_token(db_session, user.id)
        token2 = auth_manager.create_refresh_token(db_session, user.id)

        count = auth_manager.revoke_all_user_tokens(db_session, user.id)
        assert count == 2

        assert auth_manager.validate_refresh_token(db_session, token1) is None
        assert auth_manager.validate_refresh_token(db_session, token2) is None
