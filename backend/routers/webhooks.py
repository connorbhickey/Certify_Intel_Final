"""
Certify Intel - Webhooks Router

Endpoints:
- POST /api/webhooks/{webhook_id}/test - Send a test event to a webhook
- GET  /api/webhooks/events - List available webhook event types
- GET  /api/webhooks - Get all configured webhooks
- POST /api/webhooks - Configure a new webhook
- DELETE /api/webhooks/{id} - Delete (deactivate) a webhook
"""

import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from schemas.common import WebhookCreate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])


@router.post("/{webhook_id}/test")
def test_webhook(webhook_id: str):
    """Send a test event to a webhook."""
    try:
        from webhooks import get_webhook_manager

        manager = get_webhook_manager()
        return manager.test_webhook(webhook_id)

    except Exception:
        return {"success": False, "error": "An unexpected error occurred"}


@router.get("/events")
def list_webhook_events():
    """List available webhook event types."""
    from webhooks import WebhookManager
    return {"event_types": WebhookManager.EVENT_TYPES}


@router.get("")
def get_webhooks(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get all configured webhooks."""
    from database import WebhookConfig
    return db.query(WebhookConfig).filter(WebhookConfig.is_active == True).all()  # noqa: E712


@router.post("")
def create_webhook(
    webhook: WebhookCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Configure a new webhook."""
    from database import WebhookConfig
    new_hook = WebhookConfig(
        name=webhook.name,
        url=webhook.url,
        event_types=webhook.event_types
    )
    db.add(new_hook)
    db.commit()
    return {"status": "success", "id": new_hook.id}


@router.delete("/{id}")
def delete_webhook(id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Delete a webhook."""
    from database import WebhookConfig
    hook = db.query(WebhookConfig).filter(WebhookConfig.id == id).first()
    if hook:
        hook.is_active = False
        db.commit()
    return {"status": "success"}
