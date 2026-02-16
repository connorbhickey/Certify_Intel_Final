"""
Certify Intel - Prompt Resolution Utilities

Provides system prompt resolution with user-specific override support.
"""

import logging
from typing import Optional
from sqlalchemy.orm import Session

from database import SystemPrompt

logger = logging.getLogger(__name__)


def resolve_system_prompt(
    db: Session,
    user_id: Optional[int],
    prompt_key: Optional[str],
    default: str
) -> str:
    """Load a system prompt by key with user-specific override, or return default.

    Checks user-specific prompt first, then global prompt, then falls back
    to the provided default string.
    """
    if not prompt_key:
        return default
    # User-specific override
    p = db.query(SystemPrompt).filter(
        SystemPrompt.key == prompt_key,
        SystemPrompt.user_id == user_id
    ).first()
    if not p:
        # Global fallback
        p = db.query(SystemPrompt).filter(
            SystemPrompt.key == prompt_key,
            SystemPrompt.user_id == None  # noqa: E711
        ).first()
    return p.content if p else default
