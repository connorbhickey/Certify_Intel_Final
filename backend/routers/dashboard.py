"""
Certify Intel - Dashboard Router

Endpoints:
- GET /api/dashboard/stats - Summary statistics for dashboard
- GET /api/dashboard/top-threats - Top 5 highest-threat competitors
- GET /api/dashboard/threat-trends - Weekly threat-level snapshots (90 days)
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from database import get_db, Competitor, ChangeLog
from dependencies import get_current_user, get_current_user_optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/stats")
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_optional)
):
    """Get summary statistics for dashboard."""
    competitors = db.query(Competitor).filter(
        Competitor.is_deleted == False  # noqa: E712
    ).all()

    stats = {
        "total_competitors": len(competitors),
        "active": len([c for c in competitors if c.status == "Active"]),
        "high_threat": len([
            c for c in competitors
            if c.threat_level and c.threat_level.upper() == "HIGH"
        ]),
        "medium_threat": len([
            c for c in competitors
            if c.threat_level and c.threat_level.upper() == "MEDIUM"
        ]),
        "low_threat": len([
            c for c in competitors
            if c.threat_level and c.threat_level.upper() == "LOW"
        ]),
        "last_updated": datetime.utcnow().isoformat()
    }

    return stats


@router.get("/top-threats")
async def get_top_threats(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Return top 5 highest-threat competitors for the dashboard."""
    from sqlalchemy import case

    # Sort with NULLs last: use case expression to push NULLs to bottom
    overlap_sort = case(
        (Competitor.product_overlap_score.is_(None), 0),
        else_=Competitor.product_overlap_score
    ).desc()

    # First get High-threat competitors sorted by product_overlap_score
    high_threats = db.query(Competitor).filter(
        Competitor.is_deleted == False,  # noqa: E712
        Competitor.threat_level.ilike("high")
    ).order_by(overlap_sort).limit(5).all()

    results = list(high_threats)

    # If fewer than 5 High-threat, fill with Medium-threat
    if len(results) < 5:
        remaining = 5 - len(results)
        existing_ids = [c.id for c in results]
        medium_query = db.query(Competitor).filter(
            Competitor.is_deleted == False,  # noqa: E712
            Competitor.threat_level.ilike("medium")
        )
        if existing_ids:
            medium_query = medium_query.filter(
                ~Competitor.id.in_(existing_ids)
            )
        medium_threats = medium_query.order_by(
            overlap_sort
        ).limit(remaining).all()
        results.extend(medium_threats)

    # If still fewer than 5, fill with Low-threat or any remaining
    if len(results) < 5:
        remaining = 5 - len(results)
        existing_ids = [c.id for c in results]
        low_query = db.query(Competitor).filter(
            Competitor.is_deleted == False,  # noqa: E712
        )
        if existing_ids:
            low_query = low_query.filter(
                ~Competitor.id.in_(existing_ids)
            )
        low_threats = low_query.order_by(
            overlap_sort
        ).limit(remaining).all()
        results.extend(low_threats)

    return {
        "top_threats": [
            {
                "id": c.id,
                "name": c.name,
                "threat_level": c.threat_level,
                "product_overlap_score": c.product_overlap_score,
                "market_focus_score": c.market_focus_score,
                "customer_count": c.customer_count,
                "base_price": c.base_price,
            }
            for c in results
        ],
        "count": len(results),
    }


@router.get("/threat-trends")
async def get_threat_trends(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Return weekly threat-level snapshots over the last 90 days.

    Shows cumulative competitor counts at each threat level per week.
    Uses current DB state and works backwards through ChangeLog to
    reconstruct historical snapshots.
    """
    try:
        from collections import defaultdict
        from sqlalchemy import func as sa_func

        cutoff = datetime.utcnow() - timedelta(days=90)
        now = datetime.utcnow()

        # 1. Current snapshot from actual competitor data
        current_counts = db.query(
            Competitor.threat_level, sa_func.count(Competitor.id)
        ).filter(
            Competitor.is_deleted == False,  # noqa: E712
            Competitor.status == "Active"
        ).group_by(Competitor.threat_level).all()

        current = {"high": 0, "medium": 0, "low": 0}
        for level, count in current_counts:
            key = (level or "Medium").strip().lower()
            if key in current:
                current[key] = count

        # 2. Get historical changes with both old and new values
        changes = db.query(ChangeLog).filter(
            ChangeLog.change_type == "threat_level",
            ChangeLog.detected_at >= cutoff,
            ChangeLog.new_value.isnot(None),
            ChangeLog.previous_value.isnot(None)
        ).order_by(ChangeLog.detected_at.desc()).all()

        # 3. Group changes by ISO week
        weekly_changes: Dict[str, list] = defaultdict(list)
        for change in changes:
            if not change.detected_at:
                continue
            iso_year, iso_week, _ = change.detected_at.isocalendar()
            wk = f"{iso_year}-W{iso_week:02d}"
            weekly_changes[wk].append(change)

        # 4. Generate all weeks from cutoff to now
        all_weeks = set()
        d = cutoff
        while d <= now:
            iso_year, iso_week, _ = d.isocalendar()
            all_weeks.add(f"{iso_year}-W{iso_week:02d}")
            d += timedelta(days=7)
        current_iso = now.isocalendar()
        all_weeks.add(f"{current_iso[0]}-W{current_iso[1]:02d}")
        sorted_weeks = sorted(all_weeks)

        # 5. Work backwards from current snapshot to reconstruct history
        snapshots: Dict[str, Dict[str, int]] = {}
        running = dict(current)

        for week in reversed(sorted_weeks):
            snapshots[week] = dict(running)
            # Undo this week's changes to get previous week's state
            if week in weekly_changes:
                for change in weekly_changes[week]:
                    new_level = (
                        change.new_value or ""
                    ).strip().lower()
                    prev_level = (
                        change.previous_value or ""
                    ).strip().lower()
                    if new_level in running:
                        running[new_level] = max(
                            0, running[new_level] - 1
                        )
                    if prev_level in running:
                        running[prev_level] += 1

        return {
            "labels": sorted_weeks,
            "high": [snapshots[w]["high"] for w in sorted_weeks],
            "medium": [snapshots[w]["medium"] for w in sorted_weeks],
            "low": [snapshots[w]["low"] for w in sorted_weeks],
        }
    except Exception as e:
        logger.error(f"Failed to fetch threat trends: {e}")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while fetching threat trends"
        )
