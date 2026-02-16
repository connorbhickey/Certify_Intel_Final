"""
Certify Intel - MFA (Multi-Factor Authentication) Tests

Tests for TOTP-based MFA including:
- MFA setup flow (generate secret + provisioning URI)
- MFA enable with TOTP verification
- MFA login two-step flow
- MFA disable with password confirmation
- Backup codes generation and verification
- MFA-pending token rejection
"""
import pytest
import sys
import os
import hashlib
import secrets
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pytestmark = pytest.mark.timeout(20)


def _create_test_user(session):
    """Create a test user and return (user, raw_password)."""
    from database import User

    password = "TestPassword123!"
    salt = secrets.token_bytes(32)
    pw_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt, 600_000
    ).hex()
    hashed = f"{salt.hex()}${pw_hash}"
    unique = str(uuid.uuid4())[:8]

    user = User(
        email=f"mfa-test-{unique}@certifyintel.com",
        hashed_password=hashed,
        full_name="MFA Test User",
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


def _get_auth_headers(client, email, password):
    """Login and return auth headers."""
    data = _login(client, email, password)
    return {"Authorization": f"Bearer {data['access_token']}"}


# ==============================================================================
# MFA Module Unit Tests
# ==============================================================================

class TestMFAModule:
    """Tests for mfa.py utility functions."""

    def test_generate_secret(self):
        from mfa import generate_mfa_secret
        secret = generate_mfa_secret()
        assert len(secret) == 32  # Base32 encoded

    def test_get_totp_uri(self):
        from mfa import generate_mfa_secret, get_totp_uri
        secret = generate_mfa_secret()
        uri = get_totp_uri(secret, "test@example.com")
        assert uri.startswith("otpauth://totp/")
        assert "Certify%20Intel" in uri
        assert "test%40example.com" in uri

    def test_verify_totp_valid(self):
        import pyotp
        from mfa import verify_totp
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        code = totp.now()
        assert verify_totp(secret, code) is True

    def test_verify_totp_invalid(self):
        import pyotp
        from mfa import verify_totp
        secret = pyotp.random_base32()
        assert verify_totp(secret, "000000") is False

    def test_verify_totp_empty(self):
        from mfa import verify_totp
        assert verify_totp("", "") is False
        assert verify_totp(None, None) is False

    def test_generate_backup_codes(self):
        from mfa import generate_backup_codes
        codes = generate_backup_codes(10)
        assert len(codes) == 10
        assert all(len(c) == 8 for c in codes)
        # All unique
        assert len(set(codes)) == 10

    def test_hash_and_verify_backup_code(self):
        import json
        from mfa import (
            generate_backup_codes, hash_backup_code,
            verify_backup_code
        )
        codes = generate_backup_codes(3)
        hashed = [hash_backup_code(c) for c in codes]
        hashed_json = json.dumps(hashed)

        # Verify first code
        valid, remaining = verify_backup_code(codes[0], hashed_json)
        assert valid is True
        remaining_list = json.loads(remaining)
        assert len(remaining_list) == 2

        # Same code should fail now (already consumed)
        valid2, _ = verify_backup_code(codes[0], remaining)
        assert valid2 is False

        # Other codes still work
        valid3, _ = verify_backup_code(codes[1], remaining)
        assert valid3 is True

    def test_backup_code_case_insensitive(self):
        import json
        from mfa import hash_backup_code, verify_backup_code
        code = "ABCD1234"
        hashed = [hash_backup_code(code)]
        hashed_json = json.dumps(hashed)

        valid, _ = verify_backup_code("abcd1234", hashed_json)
        assert valid is True


# ==============================================================================
# MFA Endpoint Integration Tests
# ==============================================================================

class TestMFASetup:
    """Tests for MFA setup endpoints."""

    def test_mfa_setup_returns_secret_and_uri(self, test_client):
        """MFA setup should return a secret and provisioning URI."""
        from tests.conftest import TestingSessionLocal
        session = TestingSessionLocal()
        try:
            user, password = _create_test_user(session)
            headers = _get_auth_headers(test_client, user.email, password)

            response = test_client.post(
                "/api/auth/mfa/setup", headers=headers
            )
            assert response.status_code == 200
            data = response.json()
            assert "secret" in data
            assert "provisioning_uri" in data
            assert data["provisioning_uri"].startswith("otpauth://")
        finally:
            session.close()

    def test_mfa_setup_twice_fails_when_enabled(self, test_client):
        """Cannot setup MFA again if already enabled."""
        from tests.conftest import TestingSessionLocal
        import pyotp
        session = TestingSessionLocal()
        try:
            user, password = _create_test_user(session)
            headers = _get_auth_headers(test_client, user.email, password)

            # Setup MFA
            setup_resp = test_client.post(
                "/api/auth/mfa/setup", headers=headers
            )
            secret = setup_resp.json()["secret"]

            # Enable MFA
            totp = pyotp.TOTP(secret)
            test_client.post(
                "/api/auth/mfa/enable",
                json={"code": totp.now()},
                headers=headers
            )

            # Try setup again
            response = test_client.post(
                "/api/auth/mfa/setup", headers=headers
            )
            assert response.status_code == 400
        finally:
            session.close()


class TestMFAEnable:
    """Tests for MFA enable endpoint."""

    def test_enable_with_valid_code(self, test_client):
        """Enabling MFA with correct TOTP code should succeed."""
        from tests.conftest import TestingSessionLocal
        import pyotp
        session = TestingSessionLocal()
        try:
            user, password = _create_test_user(session)
            headers = _get_auth_headers(test_client, user.email, password)

            # Setup
            setup_resp = test_client.post(
                "/api/auth/mfa/setup", headers=headers
            )
            secret = setup_resp.json()["secret"]

            # Enable
            totp = pyotp.TOTP(secret)
            response = test_client.post(
                "/api/auth/mfa/enable",
                json={"code": totp.now()},
                headers=headers
            )
            assert response.status_code == 200
            data = response.json()
            assert "backup_codes" in data
            assert len(data["backup_codes"]) == 10
        finally:
            session.close()

    def test_enable_with_invalid_code(self, test_client):
        """Enabling MFA with wrong code should fail."""
        from tests.conftest import TestingSessionLocal
        session = TestingSessionLocal()
        try:
            user, password = _create_test_user(session)
            headers = _get_auth_headers(test_client, user.email, password)

            # Setup
            test_client.post("/api/auth/mfa/setup", headers=headers)

            # Enable with bad code
            response = test_client.post(
                "/api/auth/mfa/enable",
                json={"code": "000000"},
                headers=headers
            )
            assert response.status_code == 400
        finally:
            session.close()


class TestMFALogin:
    """Tests for MFA two-step login flow."""

    def test_login_requires_mfa_when_enabled(self, test_client):
        """Login should return mfa_required when MFA is enabled."""
        from tests.conftest import TestingSessionLocal
        import pyotp
        session = TestingSessionLocal()
        try:
            user, password = _create_test_user(session)
            headers = _get_auth_headers(test_client, user.email, password)

            # Setup + enable MFA
            setup_resp = test_client.post(
                "/api/auth/mfa/setup", headers=headers
            )
            secret = setup_resp.json()["secret"]
            totp = pyotp.TOTP(secret)
            test_client.post(
                "/api/auth/mfa/enable",
                json={"code": totp.now()},
                headers=headers
            )

            # Login again -- should get mfa_required
            login_resp = test_client.post(
                "/token",
                data={
                    "username": user.email,
                    "password": password
                }
            )
            assert login_resp.status_code == 200
            data = login_resp.json()
            assert data.get("mfa_required") is True
            assert "mfa_token" in data
            assert "access_token" not in data
        finally:
            session.close()

    def test_mfa_verify_login_completes_auth(self, test_client):
        """Verifying MFA code with mfa_token should complete login."""
        from tests.conftest import TestingSessionLocal
        import pyotp
        session = TestingSessionLocal()
        try:
            user, password = _create_test_user(session)
            headers = _get_auth_headers(test_client, user.email, password)

            # Setup + enable MFA
            setup_resp = test_client.post(
                "/api/auth/mfa/setup", headers=headers
            )
            secret = setup_resp.json()["secret"]
            totp = pyotp.TOTP(secret)
            test_client.post(
                "/api/auth/mfa/enable",
                json={"code": totp.now()},
                headers=headers
            )

            # Login step 1
            login_resp = test_client.post(
                "/token",
                data={
                    "username": user.email,
                    "password": password
                }
            )
            mfa_token = login_resp.json()["mfa_token"]

            # Login step 2 - verify MFA
            verify_resp = test_client.post(
                "/api/auth/mfa/verify-login",
                json={
                    "mfa_token": mfa_token,
                    "mfa_code": totp.now()
                }
            )
            assert verify_resp.status_code == 200
            data = verify_resp.json()
            assert "access_token" in data
            assert "refresh_token" in data
        finally:
            session.close()

    def test_mfa_pending_token_cannot_access_api(self, test_client):
        """MFA-pending token should be rejected by protected endpoints."""
        from tests.conftest import TestingSessionLocal
        import pyotp
        session = TestingSessionLocal()
        try:
            user, password = _create_test_user(session)
            headers = _get_auth_headers(test_client, user.email, password)

            # Setup + enable MFA
            setup_resp = test_client.post(
                "/api/auth/mfa/setup", headers=headers
            )
            secret = setup_resp.json()["secret"]
            totp = pyotp.TOTP(secret)
            test_client.post(
                "/api/auth/mfa/enable",
                json={"code": totp.now()},
                headers=headers
            )

            # Login step 1 (get MFA-pending token)
            login_resp = test_client.post(
                "/token",
                data={
                    "username": user.email,
                    "password": password
                }
            )
            mfa_token = login_resp.json()["mfa_token"]

            # Try to access API with MFA-pending token
            me_resp = test_client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {mfa_token}"}
            )
            assert me_resp.status_code == 401
        finally:
            session.close()


class TestMFADisable:
    """Tests for MFA disable endpoint."""

    def test_disable_with_correct_password(self, test_client):
        """Disabling MFA with correct password should succeed."""
        from tests.conftest import TestingSessionLocal
        import pyotp
        session = TestingSessionLocal()
        try:
            user, password = _create_test_user(session)
            headers = _get_auth_headers(test_client, user.email, password)

            # Setup + enable MFA
            setup_resp = test_client.post(
                "/api/auth/mfa/setup", headers=headers
            )
            secret = setup_resp.json()["secret"]
            totp = pyotp.TOTP(secret)
            test_client.post(
                "/api/auth/mfa/enable",
                json={"code": totp.now()},
                headers=headers
            )

            # Disable MFA
            response = test_client.post(
                "/api/auth/mfa/disable",
                json={"password": password},
                headers=headers
            )
            assert response.status_code == 200

            # Login should no longer require MFA
            login_resp = test_client.post(
                "/token",
                data={
                    "username": user.email,
                    "password": password
                }
            )
            data = login_resp.json()
            assert "access_token" in data
            assert data.get("mfa_required") is not True
        finally:
            session.close()

    def test_disable_with_wrong_password(self, test_client):
        """Disabling MFA with wrong password should fail."""
        from tests.conftest import TestingSessionLocal
        import pyotp
        session = TestingSessionLocal()
        try:
            user, password = _create_test_user(session)
            headers = _get_auth_headers(test_client, user.email, password)

            # Setup + enable MFA
            setup_resp = test_client.post(
                "/api/auth/mfa/setup", headers=headers
            )
            secret = setup_resp.json()["secret"]
            totp = pyotp.TOTP(secret)
            test_client.post(
                "/api/auth/mfa/enable",
                json={"code": totp.now()},
                headers=headers
            )

            # Try to disable with wrong password
            response = test_client.post(
                "/api/auth/mfa/disable",
                json={"password": "wrongpassword"},
                headers=headers
            )
            assert response.status_code == 401
        finally:
            session.close()


class TestMFAStatus:
    """Tests for MFA status endpoint."""

    def test_status_when_disabled(self, test_client):
        """MFA status should show disabled by default."""
        from tests.conftest import TestingSessionLocal
        session = TestingSessionLocal()
        try:
            user, password = _create_test_user(session)
            headers = _get_auth_headers(test_client, user.email, password)

            response = test_client.get(
                "/api/auth/mfa/status", headers=headers
            )
            assert response.status_code == 200
            data = response.json()
            assert data["mfa_enabled"] is False
            assert data["backup_codes_remaining"] == 0
        finally:
            session.close()

    def test_status_when_enabled(self, test_client):
        """MFA status should show enabled with backup code count."""
        from tests.conftest import TestingSessionLocal
        import pyotp
        session = TestingSessionLocal()
        try:
            user, password = _create_test_user(session)
            headers = _get_auth_headers(test_client, user.email, password)

            # Setup + enable MFA
            setup_resp = test_client.post(
                "/api/auth/mfa/setup", headers=headers
            )
            secret = setup_resp.json()["secret"]
            totp = pyotp.TOTP(secret)
            test_client.post(
                "/api/auth/mfa/enable",
                json={"code": totp.now()},
                headers=headers
            )

            response = test_client.get(
                "/api/auth/mfa/status", headers=headers
            )
            assert response.status_code == 200
            data = response.json()
            assert data["mfa_enabled"] is True
            assert data["backup_codes_remaining"] == 10
        finally:
            session.close()
