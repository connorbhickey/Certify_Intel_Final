"""
Certify Intel - Auth & User Pydantic Schemas
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    last_login: Optional[datetime] = None
    created_at: Optional[datetime] = None


class UserInviteRequest(BaseModel):
    email: str
    role: str = "viewer"
    full_name: Optional[str] = None
