"""
Certify Intel - Authentication Router

Endpoints:
- POST /token - Login and get access + refresh tokens
- GET  /api/auth/me - Get current user info
- POST /api/auth/refresh - Refresh access token
- POST /api/auth/logout - Revoke refresh token on logout
- POST /api/auth/register - Register a new user account
- POST /api/auth/mfa/setup - Generate MFA secret + provisioning URI
- POST /api/auth/mfa/enable - Verify TOTP code to confirm MFA setup
- POST /api/auth/mfa/disable - Disable MFA with password confirmation
- POST /api/auth/mfa/backup-codes - Regenerate backup codes
"""

import json  # noqa: F401 - used in MFA endpoints below
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, User
from dependencies import oauth2_scheme, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Authentication"])


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserRegisterRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None


class MFAVerifyRequest(BaseModel):
    code: str


class MFADisableRequest(BaseModel):
    password: str


class MFALoginRequest(BaseModel):
    mfa_token: str
    mfa_code: str


@router.post("/token")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Login and get access + refresh tokens. Supports MFA two-step flow."""
    from extended_features import auth_manager

    user = auth_manager.authenticate_user(
        db, form_data.username, form_data.password
    )
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Check if MFA is enabled
    if getattr(user, 'mfa_enabled', False) and user.mfa_secret:
        # Issue a temporary MFA token (short-lived, cannot access API)
        mfa_token = auth_manager.create_access_token(
            data={
                "sub": user.email,
                "role": user.role,
                "mfa_pending": True,
            },
            expires_delta=__import__('datetime').timedelta(minutes=5)
        )
        return {
            "mfa_required": True,
            "mfa_token": mfa_token,
            "token_type": "bearer",
        }

    # No MFA - issue full tokens
    access_token = auth_manager.create_access_token(
        data={"sub": user.email, "role": user.role}
    )
    refresh_token = auth_manager.create_refresh_token(db, user.id)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 15 * 60,
        "user": {
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role
        }
    }


@router.post("/api/auth/mfa/verify-login")
async def mfa_verify_login(
    request: MFALoginRequest,
    db: Session = Depends(get_db)
):
    """Complete MFA login by verifying TOTP code with the temporary MFA token."""
    from extended_features import auth_manager
    from mfa import verify_totp, verify_backup_code

    # Verify the MFA token
    payload = auth_manager.verify_token(request.mfa_token)
    if not payload or not payload.get("mfa_pending"):
        raise HTTPException(
            status_code=401, detail="Invalid or expired MFA token"
        )

    user = db.query(User).filter(
        User.email == payload.get("sub")
    ).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")

    # Try TOTP code first
    code_valid = verify_totp(user.mfa_secret, request.mfa_code)

    # If TOTP fails, try backup code
    if not code_valid and user.mfa_backup_codes:
        code_valid, updated_codes = verify_backup_code(
            request.mfa_code, user.mfa_backup_codes
        )
        if code_valid:
            user.mfa_backup_codes = updated_codes
            db.commit()

    if not code_valid:
        raise HTTPException(
            status_code=401, detail="Invalid MFA code"
        )

    # MFA verified - issue full tokens
    access_token = auth_manager.create_access_token(
        data={"sub": user.email, "role": user.role}
    )
    refresh_token = auth_manager.create_refresh_token(db, user.id)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 15 * 60,
        "user": {
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role
        }
    }


@router.get("/api/auth/me")
async def get_current_user_info(token: str = Depends(oauth2_scheme)):
    """Get current user info."""
    from extended_features import auth_manager

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = auth_manager.verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    if payload.get("mfa_pending"):
        raise HTTPException(
            status_code=401, detail="MFA verification required"
        )

    return {"email": payload.get("sub"), "role": payload.get("role")}


@router.post("/api/auth/refresh")
async def refresh_access_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Exchange a valid refresh token for a new access + refresh token pair."""
    from database import User
    from extended_features import auth_manager

    token_record = auth_manager.validate_refresh_token(db, request.refresh_token)
    if not token_record:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    # Look up the user
    user = db.query(User).filter(User.id == token_record.user_id).first()
    if not user or not user.is_active:
        auth_manager.revoke_refresh_token(db, request.refresh_token)
        raise HTTPException(status_code=401, detail="User not found or inactive")

    # Revoke the old refresh token (rotation)
    auth_manager.revoke_refresh_token(db, request.refresh_token)

    # Issue new tokens
    new_access_token = auth_manager.create_access_token(
        data={"sub": user.email, "role": user.role}
    )
    new_refresh_token = auth_manager.create_refresh_token(db, user.id)

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "expires_in": 15 * 60
    }


@router.post("/api/auth/logout")
async def logout_user(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Revoke a refresh token on logout."""
    from extended_features import auth_manager

    auth_manager.revoke_refresh_token(db, request.refresh_token)
    return {"status": "ok", "message": "Logged out successfully"}


@router.post("/api/auth/register")
async def register_user(request: UserRegisterRequest, db: Session = Depends(get_db)):
    """Register a new user account."""
    from database import User
    from extended_features import auth_manager
    import re

    # Check if email already exists
    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Validate email format
    if not re.match(r"[^@]+@[^@]+\.[^@]+", request.email):
        raise HTTPException(status_code=400, detail="Invalid email format")

    # Validate password strength (minimum 8 characters)
    if len(request.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    # Create user with default "viewer" role
    new_user = auth_manager.create_user(
        db,
        email=request.email,
        password=request.password,
        full_name=request.full_name or "",
        role="viewer"
    )

    return {
        "message": "Account created successfully. You can now log in.",
        "email": new_user.email,
        "role": new_user.role
    }


# ==============================================================================
# MFA Endpoints
# ==============================================================================


@router.post("/api/auth/mfa/setup")
async def mfa_setup(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Generate a new MFA secret and provisioning URI for QR code scanning."""
    from mfa import generate_mfa_secret, get_totp_uri

    user = db.query(User).filter(
        User.id == current_user.get("id")
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if getattr(user, 'mfa_enabled', False):
        raise HTTPException(
            status_code=400, detail="MFA is already enabled"
        )

    secret = generate_mfa_secret()
    uri = get_totp_uri(secret, user.email)

    # Store the secret temporarily (not enabled until verified)
    user.mfa_secret = secret
    db.commit()

    return {
        "secret": secret,
        "provisioning_uri": uri,
        "message": "Scan the QR code, then verify with a TOTP code"
    }


@router.post("/api/auth/mfa/enable")
async def mfa_enable(
    request: MFAVerifyRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Verify a TOTP code to confirm MFA setup and enable it."""
    from mfa import (
        verify_totp, generate_backup_codes,
        hash_backup_code
    )

    user = db.query(User).filter(
        User.id == current_user.get("id")
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.mfa_secret:
        raise HTTPException(
            status_code=400,
            detail="Call /api/auth/mfa/setup first"
        )

    if getattr(user, 'mfa_enabled', False):
        raise HTTPException(
            status_code=400, detail="MFA is already enabled"
        )

    if not verify_totp(user.mfa_secret, request.code):
        raise HTTPException(
            status_code=400, detail="Invalid TOTP code"
        )

    # Generate backup codes
    backup_codes = generate_backup_codes(10)
    hashed_codes = [hash_backup_code(c) for c in backup_codes]

    user.mfa_enabled = True
    user.mfa_backup_codes = json.dumps(hashed_codes)
    db.commit()

    return {
        "message": "MFA enabled successfully",
        "backup_codes": backup_codes,
        "warning": "Save these backup codes. They will not be shown again."
    }


@router.post("/api/auth/mfa/disable")
async def mfa_disable(
    request: MFADisableRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Disable MFA. Requires password confirmation."""
    from extended_features import auth_manager

    user = db.query(User).filter(
        User.id == current_user.get("id")
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not getattr(user, 'mfa_enabled', False):
        raise HTTPException(
            status_code=400, detail="MFA is not enabled"
        )

    # Verify password
    if not auth_manager.verify_password(
        request.password, user.hashed_password
    ):
        raise HTTPException(status_code=401, detail="Invalid password")

    user.mfa_enabled = False
    user.mfa_secret = None
    user.mfa_backup_codes = None
    db.commit()

    return {"message": "MFA disabled successfully"}


@router.post("/api/auth/mfa/backup-codes")
async def mfa_regenerate_backup_codes(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Regenerate backup codes. Requires MFA to be enabled."""
    from mfa import generate_backup_codes, hash_backup_code

    user = db.query(User).filter(
        User.id == current_user.get("id")
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not getattr(user, 'mfa_enabled', False):
        raise HTTPException(
            status_code=400, detail="MFA is not enabled"
        )

    backup_codes = generate_backup_codes(10)
    hashed_codes = [hash_backup_code(c) for c in backup_codes]
    user.mfa_backup_codes = json.dumps(hashed_codes)
    db.commit()

    return {
        "backup_codes": backup_codes,
        "warning": "Save these backup codes. They will not be shown again."
    }


@router.get("/api/auth/mfa/status")
async def mfa_status(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Check if MFA is enabled for the current user."""
    user = db.query(User).filter(
        User.id == current_user.get("id")
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    backup_count = 0
    if getattr(user, 'mfa_backup_codes', None):
        try:
            backup_count = len(json.loads(user.mfa_backup_codes))
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "mfa_enabled": getattr(user, 'mfa_enabled', False),
        "backup_codes_remaining": backup_count
    }


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
    confirm_password: str


@router.post("/api/auth/change-password")
async def change_password(
    request: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Change the current user's password."""
    from extended_features import auth_manager

    # Validate new_password == confirm_password
    if request.new_password != request.confirm_password:
        raise HTTPException(status_code=400, detail="New password and confirmation do not match")

    # Validate minimum length
    if len(request.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")

    user = db.query(User).filter(User.id == current_user.get("id")).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify old password
    if not auth_manager.verify_password(request.old_password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    # Hash and update
    user.hashed_password = auth_manager.hash_password(request.new_password)
    db.commit()

    return {"message": "Password changed successfully"}
