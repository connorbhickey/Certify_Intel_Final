"""
Certify Intel - AI Cost Analytics, Audit Logs & Competitor Relationships Router

Endpoints:
- GET  /api/ai/cost/summary           - AI cost summary (total + by provider)
- GET  /api/ai/cost/daily              - Last 30 days daily cost breakdown
- GET  /api/audit/logs                 - Search/filter activity logs (paginated)
- POST /api/competitors/{id}/relationships - Add competitor relationship
- GET  /api/competitors/{id}/relationships - List competitor relationships
"""

import logging
import math
from datetime import datetime, timedelta, date
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, ActivityLog, Competitor, CompetitorRelationship
from dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["AI Cost & Audit"])


# =============================================================================
# Pydantic Models
# =============================================================================

class RelationshipCreate(BaseModel):
    related_id: int
    relationship_type: str  # parent, subsidiary, partner, competitor
    notes: Optional[str] = None


# =============================================================================
# AI Cost Endpoints
# =============================================================================

@router.get("/api/ai/cost/summary")
async def ai_cost_summary(current_user: dict = Depends(get_current_user)):
    """Get AI cost summary with totals by provider/model."""
    try:
        from ai_router import get_ai_router
        ai_router = get_ai_router()
        summary = ai_router.cost_tracker.get_usage_summary()

        # Group by provider from model names
        by_provider = {}
        for model_name, model_data in summary.get("by_model", {}).items():
            if "claude" in model_name or "opus" in model_name or "sonnet" in model_name or "haiku" in model_name:
                provider = "anthropic"
            elif "gpt" in model_name or "o1" in model_name or "o3" in model_name:
                provider = "openai"
            elif "gemini" in model_name:
                provider = "gemini"
            elif "deepseek" in model_name:
                provider = "deepseek"
            elif "llama" in model_name or "mistral" in model_name or "qwen" in model_name:
                provider = "ollama"
            else:
                provider = "other"

            if provider not in by_provider:
                by_provider[provider] = 0.0
            by_provider[provider] += model_data.get("cost", 0.0)

        return {
            "total": summary.get("total_cost_usd", 0.0),
            "total_requests": summary.get("total_requests", 0),
            "total_tokens_input": summary.get("total_tokens_input", 0),
            "total_tokens_output": summary.get("total_tokens_output", 0),
            "by_provider": by_provider,
            "by_model": summary.get("by_model", {}),
            "by_task": summary.get("by_task", {}),
            "daily_budget_usd": ai_router.cost_tracker.daily_budget_usd,
            "today_spend": ai_router.cost_tracker.get_today_spend(),
            "remaining_budget": ai_router.cost_tracker.get_remaining_budget(),
            "period": "all_time",
        }
    except Exception as e:
        logger.error(f"Error getting AI cost summary: {e}")
        return {
            "total": 0.0,
            "total_requests": 0,
            "total_tokens_input": 0,
            "total_tokens_output": 0,
            "by_provider": {"anthropic": 0.0, "openai": 0.0, "gemini": 0.0},
            "by_model": {},
            "by_task": {},
            "daily_budget_usd": 50.0,
            "today_spend": 0.0,
            "remaining_budget": 50.0,
            "period": "all_time",
        }


@router.get("/api/ai/cost/daily")
async def ai_cost_daily(current_user: dict = Depends(get_current_user)):
    """Get last 30 days of daily AI cost breakdown."""
    try:
        from ai_router import get_ai_router
        ai_router = get_ai_router()

        # Build daily breakdown from usage records
        today = date.today()
        daily_data = {}
        for i in range(30):
            d = today - timedelta(days=i)
            daily_data[d] = {"cost": 0.0, "calls": 0}

        for record in ai_router.cost_tracker._usage_records:
            record_date = record.timestamp.date()
            if record_date in daily_data:
                daily_data[record_date]["cost"] += record.cost_usd
                daily_data[record_date]["calls"] += 1

        # Convert to sorted list
        result = []
        for d in sorted(daily_data.keys()):
            result.append({
                "date": d.isoformat(),
                "cost": round(daily_data[d]["cost"], 6),
                "calls": daily_data[d]["calls"],
            })

        return result
    except Exception as e:
        logger.error(f"Error getting daily AI costs: {e}")
        today = date.today()
        return [
            {"date": (today - timedelta(days=i)).isoformat(), "cost": 0.0, "calls": 0}
            for i in range(29, -1, -1)
        ]


# =============================================================================
# Audit Log Endpoints
# =============================================================================

@router.get("/api/audit/logs")
async def search_audit_logs(
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=200, description="Items per page"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Search and filter activity logs with pagination."""
    try:
        query = db.query(ActivityLog)

        if user_id is not None:
            query = query.filter(ActivityLog.user_id == user_id)

        if action:
            query = query.filter(ActivityLog.action_type == action)

        if start_date:
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                query = query.filter(ActivityLog.created_at >= start_dt)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD.")

        if end_date:
            try:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
                query = query.filter(ActivityLog.created_at < end_dt)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD.")

        total = query.count()
        pages = max(1, math.ceil(total / per_page))
        offset = (page - 1) * per_page

        logs = (
            query
            .order_by(ActivityLog.created_at.desc())
            .offset(offset)
            .limit(per_page)
            .all()
        )

        items = []
        for log in logs:
            items.append({
                "id": log.id,
                "user_id": log.user_id,
                "user_email": log.user_email,
                "action_type": log.action_type,
                "action_details": log.action_details,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "pages": pages,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching audit logs: {e}")
        raise HTTPException(status_code=500, detail="Failed to search audit logs")


# =============================================================================
# Competitor Relationship Endpoints
# =============================================================================

VALID_RELATIONSHIP_TYPES = {"parent", "subsidiary", "partner", "competitor"}


@router.post("/api/competitors/{competitor_id}/relationships")
async def create_competitor_relationship(
    competitor_id: int,
    body: RelationshipCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a relationship between two competitors."""
    # Validate relationship type
    if body.relationship_type not in VALID_RELATIONSHIP_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid relationship_type. Must be one of: {', '.join(sorted(VALID_RELATIONSHIP_TYPES))}"
        )

    # Validate both competitors exist
    competitor = db.query(Competitor).filter(Competitor.id == competitor_id).first()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    related = db.query(Competitor).filter(Competitor.id == body.related_id).first()
    if not related:
        raise HTTPException(status_code=404, detail="Related competitor not found")

    if competitor_id == body.related_id:
        raise HTTPException(status_code=400, detail="Cannot create a relationship with itself")

    # Check for duplicate
    existing = (
        db.query(CompetitorRelationship)
        .filter(
            CompetitorRelationship.competitor_id == competitor_id,
            CompetitorRelationship.related_id == body.related_id,
            CompetitorRelationship.relationship_type == body.relationship_type,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Relationship already exists")

    try:
        relationship = CompetitorRelationship(
            competitor_id=competitor_id,
            related_id=body.related_id,
            relationship_type=body.relationship_type,
            notes=body.notes,
            created_by=current_user.get("email"),
        )
        db.add(relationship)
        db.commit()
        db.refresh(relationship)

        return {
            "id": relationship.id,
            "competitor_id": relationship.competitor_id,
            "related_id": relationship.related_id,
            "relationship_type": relationship.relationship_type,
            "notes": relationship.notes,
            "created_at": relationship.created_at.isoformat() if relationship.created_at else None,
            "created_by": relationship.created_by,
            "related_name": related.name,
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating competitor relationship: {e}")
        raise HTTPException(status_code=500, detail="Failed to create relationship")


@router.get("/api/competitors/{competitor_id}/relationships")
async def list_competitor_relationships(
    competitor_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all relationships for a competitor (both directions)."""
    # Validate competitor exists
    competitor = db.query(Competitor).filter(Competitor.id == competitor_id).first()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    try:
        # Get relationships where this competitor is on either side
        outgoing = (
            db.query(CompetitorRelationship)
            .filter(CompetitorRelationship.competitor_id == competitor_id)
            .all()
        )
        incoming = (
            db.query(CompetitorRelationship)
            .filter(CompetitorRelationship.related_id == competitor_id)
            .all()
        )

        results = []
        for rel in outgoing:
            related = db.query(Competitor).filter(Competitor.id == rel.related_id).first()
            results.append({
                "id": rel.id,
                "competitor_id": rel.competitor_id,
                "related_id": rel.related_id,
                "related_name": related.name if related else "Unknown",
                "relationship_type": rel.relationship_type,
                "direction": "outgoing",
                "notes": rel.notes,
                "created_at": rel.created_at.isoformat() if rel.created_at else None,
                "created_by": rel.created_by,
            })

        for rel in incoming:
            source = db.query(Competitor).filter(Competitor.id == rel.competitor_id).first()
            results.append({
                "id": rel.id,
                "competitor_id": rel.competitor_id,
                "related_id": rel.related_id,
                "related_name": source.name if source else "Unknown",
                "relationship_type": rel.relationship_type,
                "direction": "incoming",
                "notes": rel.notes,
                "created_at": rel.created_at.isoformat() if rel.created_at else None,
                "created_by": rel.created_by,
            })

        return {
            "competitor_id": competitor_id,
            "competitor_name": competitor.name,
            "relationships": results,
            "total": len(results),
        }
    except Exception as e:
        logger.error(f"Error listing competitor relationships: {e}")
        raise HTTPException(status_code=500, detail="Failed to list relationships")
