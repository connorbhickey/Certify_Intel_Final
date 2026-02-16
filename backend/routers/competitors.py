"""
Certify Intel - Competitors CRUD Router

Core CRUD endpoints for competitor management:
- GET    /api/competitors - List all competitors
- GET    /api/competitors/{id} - Get competitor details
- POST   /api/competitors - Create new competitor
- PUT    /api/competitors/{id} - Update competitor
- DELETE /api/competitors/{id} - Soft-delete competitor
- POST   /api/competitors/{id}/correct - Manual data correction
"""

import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from database import (
    get_db, SessionLocal, Competitor, DataSource, DataChangeHistory,
)
from dependencies import get_current_user, get_current_user_optional, log_activity
from constants import KNOWN_TICKERS
from schemas.competitors import (
    CompetitorCreate, CompetitorResponse, CorrectionRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/competitors", tags=["Competitors"])


def _lookup_ticker_dynamically(company_name: str) -> dict:
    """
    Try to find ticker symbol for a company using yfinance.
    Returns dict with symbol, exchange, name or None values if not found.
    """
    try:
        import yfinance as yf
        search_terms = [
            company_name,
            company_name.replace(" ", ""),
            company_name.split()[0] if " " in company_name else company_name
        ]

        for term in search_terms:
            try:
                ticker = yf.Ticker(term)
                info = ticker.info
                if info and info.get('symbol') and info.get('shortName'):
                    exchange = info.get('exchange', 'UNKNOWN')
                    exchange_map = {
                        'NMS': 'NASDAQ', 'NGM': 'NASDAQ', 'NCM': 'NASDAQ',
                        'NYQ': 'NYSE', 'NYSE': 'NYSE', 'PCX': 'NYSE ARCA'
                    }
                    return {
                        "symbol": info.get('symbol'),
                        "exchange": exchange_map.get(exchange, exchange),
                        "name": info.get('shortName') or info.get('longName')
                    }
            except (KeyError, AttributeError, Exception):
                continue
        return None
    except Exception as e:
        logger.warning(f"Dynamic ticker lookup failed for {company_name}: {e}")
        return None


@router.get("", response_model=List[CompetitorResponse])
async def list_competitors(
    status: Optional[str] = None,
    threat_level: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_optional)
):
    query = db.query(Competitor).filter(Competitor.is_deleted == False)  # noqa: E712
    if status:
        query = query.filter(Competitor.status == status)
    if threat_level:
        query = query.filter(Competitor.threat_level == threat_level)
    competitors = query.offset(skip).limit(limit).all()
    return competitors


@router.get("/{competitor_id}", response_model=CompetitorResponse)
async def get_competitor(
    competitor_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    competitor = db.query(Competitor).filter(
        Competitor.id == competitor_id,
        Competitor.is_deleted == False  # noqa: E712
    ).first()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")
    return competitor


@router.post("", response_model=CompetitorResponse)
async def create_competitor(
    competitor: CompetitorCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    db_competitor = Competitor(**competitor.model_dump())

    # Auto-classify Public/Private
    comp_lower = db_competitor.name.lower()
    ticker_info = None

    if comp_lower in KNOWN_TICKERS:
        ticker_info = KNOWN_TICKERS[comp_lower]
    else:
        ticker_info = _lookup_ticker_dynamically(db_competitor.name)

    if ticker_info and ticker_info.get("symbol"):
        db_competitor.is_public = True
        db_competitor.ticker_symbol = ticker_info["symbol"]
        db_competitor.stock_exchange = ticker_info.get("exchange", "UNKNOWN")
        logger.info(
            f"[AUTO-DETECT] {db_competitor.name} identified as public: "
            f"{ticker_info['symbol']} on {ticker_info.get('exchange')}"
        )
    elif ticker_info and ticker_info.get("symbol") is None:
        db_competitor.is_public = False
        logger.info(
            f"[AUTO-DETECT] {db_competitor.name} identified as private company"
        )

    db.add(db_competitor)
    db.commit()
    db.refresh(db_competitor)

    user_email = current_user.get("email", "unknown")
    log_activity(
        db, user_email, current_user.get("id"),
        "competitor_create",
        {"competitor_id": db_competitor.id, "competitor_name": db_competitor.name}
    )

    # v6.3.9: Auto-trigger AI source discovery for new competitor (background)
    # v8.3.0: Also run data verification + URL refinement after discovery
    async def trigger_source_discovery_and_verification(comp_id: int):
        import asyncio as _asyncio

        # Step 1: Source discovery
        try:
            from source_discovery_engine import get_source_discovery_engine
            engine = get_source_discovery_engine()
            await _asyncio.wait_for(
                engine.discover_sources_for_competitor(comp_id, max_fields=30),
                timeout=120.0,
            )
            logger.info(f"Source discovery completed for competitor {comp_id}")
        except _asyncio.TimeoutError:
            logger.warning(
                f"Source discovery timed out for competitor {comp_id}"
            )
        except Exception as e:
            logger.warning(
                f"Auto source discovery failed for competitor {comp_id}: {e}"
            )

        # Step 2: Data quality verification (v8.3.0)
        try:
            from source_discovery_engine import get_source_discovery_engine
            engine = get_source_discovery_engine()
            result = await _asyncio.wait_for(
                engine.verify_sources_for_competitor(comp_id),
                timeout=120.0,
            )
            corrected = result.get("fields_corrected", 0)
            verified = result.get("fields_correct", 0)
            logger.info(
                f"Auto-verification for competitor {comp_id}: "
                f"{verified} correct, {corrected} corrected"
            )
        except _asyncio.TimeoutError:
            logger.warning(
                f"Auto verification timed out for competitor {comp_id}"
            )
        except Exception as e:
            logger.warning(
                f"Auto verification failed for competitor {comp_id}: {e}"
            )

        # Step 3: URL refinement (v8.3.0)
        try:
            from url_refinement_engine import refine_source_url
            verify_db = SessionLocal()
            try:
                comp = verify_db.query(Competitor).filter(
                    Competitor.id == comp_id
                ).first()
                if comp:
                    sources = verify_db.query(DataSource).filter(
                        DataSource.competitor_id == comp_id,
                        DataSource.source_url.isnot(None),
                    ).all()
                    for src in sources:
                        try:
                            refined = await _asyncio.wait_for(
                                refine_source_url(
                                    competitor_name=comp.name,
                                    website=comp.website or "",
                                    field_name=src.field_name,
                                    current_value=src.current_value,
                                    current_url=src.source_url,
                                ),
                                timeout=15.0,
                            )
                            if refined.source_page_url:
                                src.source_page_url = refined.source_page_url
                                src.source_anchor_text = (
                                    refined.source_anchor_text
                                )
                                src.source_section = refined.source_section
                                src.deep_link_url = refined.deep_link_url
                                src.url_status = refined.url_status
                                src.last_url_verified = datetime.utcnow()
                        except (_asyncio.TimeoutError, Exception):
                            pass
                    verify_db.commit()
                    logger.info(
                        f"URL refinement completed for competitor {comp_id}"
                    )
            finally:
                verify_db.close()
        except Exception as e:
            logger.warning(
                f"Auto URL refinement failed for competitor {comp_id}: {e}"
            )

    background_tasks.add_task(
        trigger_source_discovery_and_verification, db_competitor.id
    )

    return db_competitor


@router.put("/{competitor_id}", response_model=CompetitorResponse)
async def update_competitor(
    competitor_id: int,
    competitor: CompetitorCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    db_competitor = db.query(Competitor).filter(
        Competitor.id == competitor_id
    ).first()
    if not db_competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    changes_made = []
    user_email = current_user.get("email", "unknown")

    for key, value in competitor.model_dump().items():
        old_value = getattr(db_competitor, key, None)
        if str(old_value) != str(value) and value is not None:
            changes_made.append({
                "field": key,
                "old_value": str(old_value) if old_value else None,
                "new_value": str(value)
            })
            change_record = DataChangeHistory(
                competitor_id=competitor_id,
                competitor_name=db_competitor.name,
                field_name=key,
                old_value=str(old_value) if old_value else None,
                new_value=str(value),
                changed_by=user_email,
                change_reason="Manual update via UI"
            )
            db.add(change_record)

        setattr(db_competitor, key, value)

    db_competitor.last_updated = datetime.utcnow()

    if changes_made:
        log_activity(
            db, user_email, current_user.get("id"),
            "competitor_update",
            {
                "competitor_id": competitor_id,
                "competitor_name": db_competitor.name,
                "changes_count": len(changes_made)
            }
        )

    db.commit()
    db.refresh(db_competitor)
    return db_competitor


@router.delete("/{competitor_id}")
async def delete_competitor(
    competitor_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    db_competitor = db.query(Competitor).filter(
        Competitor.id == competitor_id
    ).first()
    if not db_competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    competitor_name = db_competitor.name
    db_competitor.is_deleted = True

    user_email = current_user.get("email", "unknown")
    log_activity(
        db, user_email, current_user.get("id"),
        "competitor_delete",
        {"competitor_id": competitor_id, "competitor_name": competitor_name}
    )

    db.commit()
    return {"message": "Competitor deleted", "deleted_by": user_email}


@router.post("/{competitor_id}/correct")
async def correct_competitor_data(
    competitor_id: int,
    correction: CorrectionRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Manually correct a data point and lock it to prevent overwrite."""
    competitor = db.query(Competitor).filter(
        Competitor.id == competitor_id
    ).first()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    if not hasattr(competitor, correction.field):
        raise HTTPException(
            status_code=400, detail=f"Invalid field: {correction.field}"
        )

    old_value = getattr(competitor, correction.field)

    setattr(competitor, correction.field, correction.new_value)
    competitor.last_updated = datetime.utcnow()

    source = db.query(DataSource).filter(
        DataSource.competitor_id == competitor_id,
        DataSource.field_name == correction.field
    ).first()

    if source:
        source.source_type = "manual"
        source.entered_by = current_user.get("email", "unknown")
        source.updated_at = datetime.utcnow()
    else:
        new_source = DataSource(
            competitor_id=competitor_id,
            field_name=correction.field,
            source_type="manual",
            source_url=correction.source_url,
            entered_by=current_user.get("email", "unknown"),
            verified_at=datetime.utcnow()
        )
        db.add(new_source)

    history = DataChangeHistory(
        competitor_id=competitor_id,
        competitor_name=competitor.name,
        field_name=correction.field,
        old_value=str(old_value) if old_value else None,
        new_value=correction.new_value,
        source_url=correction.source_url,
        changed_by=current_user.get("email", "unknown"),
        change_reason=correction.reason
    )
    db.add(history)

    db.commit()
    db.refresh(competitor)

    return {
        "message": "Correction applied successfully",
        "competitor": competitor
    }
