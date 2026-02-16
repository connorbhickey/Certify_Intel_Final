"""
Certify Intel - Win/Loss Router

Endpoints:
- GET  /api/win-loss - Get all win/loss deals
- POST /api/win-loss - Create a new win/loss deal
"""

import logging
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from schemas.common import WinLossCreate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/win-loss", tags=["Win/Loss"])


@router.get("")
def get_win_loss_deals(db: Session = Depends(get_db)):
    """Get all win/loss deals (v7.1.5: added deal_size alias for frontend compatibility)."""
    from database import WinLossDeal

    deals = db.query(WinLossDeal).order_by(WinLossDeal.deal_date.desc()).all()

    # Serialize with deal_size as alias for deal_value
    result = []
    for deal in deals:
        deal_dict = {
            "id": deal.id,
            "user_id": deal.user_id,
            "competitor_id": deal.competitor_id,
            "competitor_name": deal.competitor_name,
            "outcome": deal.outcome,
            "deal_value": deal.deal_value,
            "deal_size": deal.deal_value,  # Frontend expects deal_size
            "deal_date": deal.deal_date.isoformat() if deal.deal_date else None,
            "customer_name": deal.customer_name,
            "customer_size": deal.customer_size,
            "reason": deal.reason,
            "sales_rep": deal.sales_rep,
            "notes": deal.notes
        }
        result.append(deal_dict)

    return result


@router.post("")
def create_win_loss_deal(deal: WinLossCreate, db: Session = Depends(get_db)):
    """FEAT-003: Log a new win/loss deal with dimension correlation."""
    from database import WinLossDeal

    # Parse deal date
    deal_date = None
    if deal.deal_date:
        try:
            deal_date = datetime.strptime(deal.deal_date, "%Y-%m-%d")
        except ValueError:
            deal_date = datetime.utcnow()
    else:
        deal_date = datetime.utcnow()

    new_deal = WinLossDeal(
        competitor_id=deal.competitor_id,
        competitor_name=deal.competitor_name,
        outcome=deal.outcome,
        deal_value=deal.deal_value,
        deal_date=deal_date,
        customer_name=deal.customer_name,
        customer_size=deal.customer_size,
        reason=deal.reason,
        sales_rep=deal.sales_rep,
        notes=deal.notes
    )

    # FEAT-003: Store key dimension in notes if not null
    if deal.key_dimension:
        dimension_note = f"[KEY_DIMENSION:{deal.key_dimension}]"
        new_deal.notes = f"{dimension_note} {new_deal.notes or ''}"

    db.add(new_deal)
    db.commit()
    return {"status": "success", "id": new_deal.id}
