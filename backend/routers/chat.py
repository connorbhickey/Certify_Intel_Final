"""
Certify Intel - Chat Sessions Router

Endpoints:
- GET    /api/chat/sessions - List active chat sessions for current user
- GET    /api/chat/sessions/by-context/{page_context} - Get session by page context
- GET    /api/chat/sessions/{session_id}/messages - Get messages for a session
- POST   /api/chat/sessions - Create new chat session
- POST   /api/chat/sessions/{session_id}/messages - Add message to session
- DELETE /api/chat/sessions/{session_id} - Soft-delete a chat session
"""

import json
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from database import get_db, ChatSession, ChatMessage
from dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["Chat"])


@router.get("/sessions")
async def list_chat_sessions(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """List active chat sessions for the current user, sorted by most recent."""
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")

    sessions = db.query(ChatSession).filter(
        ChatSession.user_id == user_id,
        ChatSession.is_active == True  # noqa: E712
    ).order_by(ChatSession.updated_at.desc()).all()

    return {
        "sessions": [
            {
                "id": s.id,
                "page_context": s.page_context,
                "competitor_id": s.competitor_id,
                "title": s.title,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
            for s in sessions
        ]
    }


@router.get("/sessions/by-context/{page_context}")
async def get_session_by_context(
    page_context: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get the active chat session for a specific page context and current user."""
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")

    session = db.query(ChatSession).filter(
        ChatSession.user_id == user_id,
        ChatSession.page_context == page_context,
        ChatSession.is_active == True  # noqa: E712
    ).order_by(ChatSession.updated_at.desc()).first()

    if not session:
        return {"session": None}

    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session.id
    ).order_by(ChatMessage.created_at.asc()).all()

    return {
        "session": {
            "id": session.id,
            "page_context": session.page_context,
            "competitor_id": session.competitor_id,
            "title": session.title,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "metadata_json": m.metadata_json,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in messages
            ],
        }
    }


@router.get("/sessions/{session_id}/messages")
async def get_chat_messages(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get all messages for a chat session (must belong to current user)."""
    user_id = current_user.get("id")

    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == user_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at.asc()).all()

    return {
        "session_id": session_id,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "metadata_json": m.metadata_json,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


@router.post("/sessions")
async def create_chat_session(
    request: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create a new chat session."""
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")

    page_context = request.get("page_context", "general")
    competitor_id = request.get("competitor_id")
    title = request.get("title")

    session = ChatSession(
        user_id=user_id,
        page_context=page_context,
        competitor_id=competitor_id,
        title=title,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return {
        "id": session.id,
        "page_context": session.page_context,
        "competitor_id": session.competitor_id,
        "title": session.title,
        "created_at": session.created_at.isoformat() if session.created_at else None,
    }


@router.post("/sessions/{session_id}/messages")
async def add_chat_message(
    session_id: int,
    request: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Add a message to an existing chat session."""
    user_id = current_user.get("id")

    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == user_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    role = request.get("role", "user")
    content = request.get("content", "")
    metadata_json = request.get("metadata_json")

    if not content:
        raise HTTPException(
            status_code=400, detail="Message content is required"
        )

    # Auto-generate title from first user message if session has no title
    if not session.title and role == "user":
        session.title = content[:80] + ("..." if len(content) > 80 else "")

    msg = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        metadata_json=metadata_json if isinstance(metadata_json, str) else (
            json.dumps(metadata_json) if metadata_json else None
        ),
    )
    db.add(msg)

    # Touch session updated_at
    session.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(msg)

    return {
        "id": msg.id,
        "session_id": session_id,
        "role": msg.role,
        "content": msg.content,
        "metadata_json": msg.metadata_json,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


@router.delete("/sessions/{session_id}")
async def delete_chat_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Soft-delete a chat session (set is_active=False)."""
    user_id = current_user.get("id")

    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == user_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.is_active = False
    db.commit()

    return {"success": True, "session_id": session_id}
