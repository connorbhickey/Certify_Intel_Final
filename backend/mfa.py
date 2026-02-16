"""
Certify Intel - Multi-Factor Authentication (TOTP)

Provides TOTP-based MFA using pyotp (RFC 6238).
Backup codes use PBKDF2-HMAC-SHA256 for secure storage.

Usage:
    from mfa import generate_mfa_secret, verify_totp, generate_backup_codes
"""
import hashlib
import json
import logging
import secrets
import string
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import pyotp
    PYOTP_AVAILABLE = True
except ImportError:
    PYOTP_AVAILABLE = False
    logger.warning("pyotp not installed. MFA features disabled. Run: pip install pyotp")

APP_NAME = "Certify Intel"


def generate_mfa_secret() -> str:
    """Generate a random base32 secret for TOTP."""
    if not PYOTP_AVAILABLE:
        raise RuntimeError("pyotp is required for MFA. Run: pip install pyotp")
    return pyotp.random_base32()


def get_totp_uri(secret: str, user_email: str) -> str:
    """Generate an otpauth:// provisioning URI for QR code scanning."""
    if not PYOTP_AVAILABLE:
        raise RuntimeError("pyotp is required for MFA")
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=user_email, issuer_name=APP_NAME)


def verify_totp(secret: str, code: str) -> bool:
    """Verify a 6-digit TOTP code. Allows 1 window of drift (30s)."""
    if not PYOTP_AVAILABLE:
        return False
    if not code or not secret:
        return False
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


def generate_backup_codes(count: int = 10) -> List[str]:
    """Generate a list of random 8-character alphanumeric backup codes."""
    chars = string.ascii_uppercase + string.digits
    codes = []
    for _ in range(count):
        code = ''.join(secrets.choice(chars) for _ in range(8))
        codes.append(code)
    return codes


def hash_backup_code(code: str) -> str:
    """Hash a backup code using PBKDF2-HMAC-SHA256 with a random salt."""
    salt = secrets.token_bytes(16)
    hashed = hashlib.pbkdf2_hmac(
        "sha256", code.upper().encode(), salt, 100_000
    ).hex()
    return f"{salt.hex()}${hashed}"


def verify_backup_code(
    code: str,
    hashed_codes_json: str,
) -> Tuple[bool, Optional[str]]:
    """
    Verify a backup code against the stored hashed codes.
    Returns (is_valid, updated_hashed_codes_json).
    If valid, the used code is removed from the list.
    """
    if not code or not hashed_codes_json:
        return False, hashed_codes_json

    try:
        hashed_codes = json.loads(hashed_codes_json)
    except (json.JSONDecodeError, TypeError):
        return False, hashed_codes_json

    code_upper = code.upper()

    for i, stored_hash in enumerate(hashed_codes):
        try:
            salt_hex, expected_hash = stored_hash.split("$", 1)
            salt = bytes.fromhex(salt_hex)
            computed = hashlib.pbkdf2_hmac(
                "sha256", code_upper.encode(), salt, 100_000
            ).hex()
            if secrets.compare_digest(computed, expected_hash):
                # Remove used code
                remaining = hashed_codes[:i] + hashed_codes[i + 1:]
                return True, json.dumps(remaining)
        except (ValueError, TypeError):
            continue

    return False, hashed_codes_json
