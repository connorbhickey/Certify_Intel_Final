"""
Certify Intel - Shared FastAPI Dependencies

Centralizes authentication dependencies and utility functions
used across multiple routers and main.py.
"""

import logging
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from database import get_db, User, ActivityLog

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """Verify JWT token and return current user with ID. Raises 401 if invalid/missing."""
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    from extended_features import auth_manager

    payload = auth_manager.verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Reject MFA-pending tokens (partial auth, cannot access API)
    if payload.get("mfa_pending"):
        raise HTTPException(status_code=401, detail="MFA verification required")

    user = db.query(User).filter(User.email == payload.get("sub")).first()
    user_id = user.id if user else None

    return {"id": user_id, "email": payload.get("sub"), "role": payload.get("role")}


async def get_current_user_optional(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """Verify JWT token and return current user, or None if not authenticated. Does not raise errors."""
    if not token:
        return None

    from extended_features import auth_manager

    payload = auth_manager.verify_token(token)
    if not payload:
        return None

    user = db.query(User).filter(User.email == payload.get("sub")).first()
    user_id = user.id if user else None

    return {"id": user_id, "email": payload.get("sub"), "role": payload.get("role")}


def log_activity(
    db: Session,
    user_email: str,
    user_id: int,
    action_type: str,
    action_details: str = None
):
    """Log a user activity to the activity_logs table (shared across all users)."""
    import json
    activity = ActivityLog(
        user_id=user_id,
        user_email=user_email,
        action_type=action_type,
        action_details=(
            action_details if isinstance(action_details, str)
            else json.dumps(action_details) if action_details
            else None
        )
    )
    db.add(activity)
    db.commit()
    return activity
