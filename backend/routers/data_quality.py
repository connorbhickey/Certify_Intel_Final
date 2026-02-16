"""
Certify Intel - Data Quality Router

Endpoints:
- GET  /api/data-quality/completeness - Field-by-field completeness statistics
- GET  /api/data-quality/scores - Quality scores for all competitors
- GET  /api/data-quality/stale - Competitors with stale data
- POST /api/data-quality/verify/{competitor_id} - Mark data as verified
- GET  /api/data-quality/completeness/{competitor_id} - Per-competitor completeness
- GET  /api/data-quality/low-confidence - Data below confidence threshold
- GET  /api/data-quality/confidence-distribution - Confidence level distribution
- POST /api/data-quality/recalculate-confidence - Recalculate all confidence scores
- GET  /api/data-quality/overview - Comprehensive data quality dashboard
"""

import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from database import get_db, Competitor, DataSource
from confidence_scoring import (
    calculate_confidence_score, calculate_data_staleness,
    get_source_type_description,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/data-quality", tags=["Data Quality"])


# Field list used for completeness calculations
COMPETITOR_DATA_FIELDS = [
    "name", "website", "status", "threat_level", "pricing_model",
    "base_price", "price_unit", "product_categories", "key_features",
    "integration_partners", "certifications", "target_segments",
    "customer_size_focus", "geographic_focus", "customer_count",
    "customer_acquisition_rate", "key_customers", "g2_rating",
    "employee_count", "employee_growth_rate", "year_founded",
    "headquarters", "funding_total", "latest_round", "pe_vc_backers",
    "website_traffic", "social_following", "recent_launches",
    "news_mentions", "is_public", "ticker_symbol", "stock_exchange"
]


def calculate_quality_score(competitor) -> int:
    """Calculate data quality score (0-100) based on field completeness."""
    filled_fields = 0
    for field in COMPETITOR_DATA_FIELDS:
        value = getattr(competitor, field, None)
        if value is not None and str(value).strip() not in [
            "", "None", "Unknown", "N/A"
        ]:
            filled_fields += 1
    return int((filled_fields / len(COMPETITOR_DATA_FIELDS)) * 100)


def _get_confidence_by_source_type(sources: list) -> dict:
    """Helper to group confidence scores by source type."""
    by_type = {}
    for s in sources:
        source_type = s.source_type or "unknown"
        if source_type not in by_type:
            by_type[source_type] = {
                "count": 0, "total_score": 0, "scores": []
            }
        by_type[source_type]["count"] += 1
        if s.confidence_score is not None:
            by_type[source_type]["total_score"] += s.confidence_score
            by_type[source_type]["scores"].append(s.confidence_score)

    result = {}
    for source_type, data in by_type.items():
        avg = round(
            data["total_score"] / len(data["scores"]), 1
        ) if data["scores"] else 0
        result[source_type] = {
            "count": data["count"],
            "average_confidence": avg,
            "description": get_source_type_description(source_type)
        }
    return result


@router.get("/completeness")
def get_data_completeness(db: Session = Depends(get_db)):
    """Get field-by-field completeness statistics across all competitors."""
    competitors = db.query(Competitor).filter(
        Competitor.is_deleted == False  # noqa: E712
    ).all()
    total = len(competitors)

    if total == 0:
        return {
            "total_competitors": 0, "fields": [],
            "overall_completeness": 0
        }

    field_stats = []
    for field in COMPETITOR_DATA_FIELDS:
        filled = 0
        for comp in competitors:
            value = getattr(comp, field, None)
            if value is not None and str(value).strip() not in [
                "", "None", "Unknown", "N/A"
            ]:
                filled += 1
        completeness = round((filled / total) * 100, 1)
        field_stats.append({
            "field": field,
            "filled": filled,
            "total": total,
            "completeness_percent": completeness
        })

    # Sort by completeness ascending (least complete first)
    field_stats.sort(key=lambda x: x["completeness_percent"])

    overall = round(
        sum(f["completeness_percent"] for f in field_stats)
        / len(field_stats), 1
    )

    return {
        "total_competitors": total,
        "total_fields": len(COMPETITOR_DATA_FIELDS),
        "overall_completeness": overall,
        "fields": field_stats
    }


@router.get("/scores")
def get_quality_scores(db: Session = Depends(get_db)):
    """Get quality scores for all competitors."""
    competitors = db.query(Competitor).filter(
        Competitor.is_deleted == False  # noqa: E712
    ).all()

    scores = []
    for comp in competitors:
        score = calculate_quality_score(comp)
        scores.append({
            "id": comp.id,
            "name": comp.name,
            "score": score,
            "tier": (
                "Excellent" if score >= 80
                else "Good" if score >= 60
                else "Fair" if score >= 40
                else "Poor"
            )
        })

    scores.sort(key=lambda x: x["score"], reverse=True)

    avg_score = round(
        sum(s["score"] for s in scores) / len(scores), 1
    ) if scores else 0

    return {
        "average_score": avg_score,
        "total_competitors": len(scores),
        "scores": scores
    }


@router.get("/stale")
def get_stale_records(days: int = 30, db: Session = Depends(get_db)):
    """Get competitors with data older than specified days."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    competitors = db.query(Competitor).filter(
        Competitor.is_deleted == False  # noqa: E712
    ).all()

    stale = []
    fresh = []
    for comp in competitors:
        check_date = (
            comp.last_verified_at or comp.last_updated or comp.created_at
        )
        if check_date and check_date < cutoff:
            days_old = (datetime.utcnow() - check_date).days
            stale.append({
                "id": comp.id,
                "name": comp.name,
                "last_verified": (
                    check_date.isoformat() if check_date else None
                ),
                "days_old": days_old
            })
        else:
            fresh.append({"id": comp.id, "name": comp.name})

    stale.sort(key=lambda x: x["days_old"], reverse=True)

    return {
        "threshold_days": days,
        "stale_count": len(stale),
        "fresh_count": len(fresh),
        "stale_records": stale,
        "fresh_records": fresh[:10]
    }


@router.post("/verify/{competitor_id}")
def verify_competitor_data(
    competitor_id: int, db: Session = Depends(get_db)
):
    """Mark a competitor's data as verified."""
    competitor = db.query(Competitor).filter(
        Competitor.id == competitor_id
    ).first()
    if not competitor:
        raise HTTPException(
            status_code=404, detail="Competitor not found"
        )

    competitor.last_verified_at = datetime.utcnow()
    competitor.data_quality_score = calculate_quality_score(competitor)
    db.commit()

    return {
        "success": True,
        "competitor_id": competitor_id,
        "name": competitor.name,
        "verified_at": competitor.last_verified_at.isoformat(),
        "quality_score": competitor.data_quality_score
    }


@router.get("/completeness/{competitor_id}")
def get_competitor_completeness(
    competitor_id: int, db: Session = Depends(get_db)
):
    """Get field-by-field completeness for a specific competitor."""
    competitor = db.query(Competitor).filter(
        Competitor.id == competitor_id
    ).first()
    if not competitor:
        raise HTTPException(
            status_code=404, detail="Competitor not found"
        )

    fields = []
    for field in COMPETITOR_DATA_FIELDS:
        value = getattr(competitor, field, None)
        has_value = value is not None and str(value).strip() not in [
            "", "None", "Unknown", "N/A"
        ]
        fields.append({
            "field": field,
            "has_value": has_value,
            "value": str(value)[:100] if value else None
        })

    filled = sum(1 for f in fields if f["has_value"])

    return {
        "competitor_id": competitor_id,
        "name": competitor.name,
        "filled_fields": filled,
        "total_fields": len(COMPETITOR_DATA_FIELDS),
        "completeness_percent": round(
            (filled / len(COMPETITOR_DATA_FIELDS)) * 100, 1
        ),
        "fields": fields
    }


@router.get("/low-confidence")
def get_low_confidence_data(
    threshold: int = 40, db: Session = Depends(get_db)
):
    """Get all data points below confidence threshold for review."""
    sources = db.query(DataSource).filter(
        DataSource.confidence_score < threshold
    ).order_by(DataSource.confidence_score).all()

    by_competitor = {}
    for s in sources:
        comp_id = s.competitor_id
        if comp_id not in by_competitor:
            competitor = db.query(Competitor).filter(
                Competitor.id == comp_id
            ).first()
            by_competitor[comp_id] = {
                "competitor_id": comp_id,
                "competitor_name": (
                    competitor.name if competitor else "Unknown"
                ),
                "fields": []
            }
        by_competitor[comp_id]["fields"].append({
            "field": s.field_name,
            "value": s.current_value,
            "confidence_score": s.confidence_score or 0,
            "confidence_level": s.confidence_level or "low",
            "source_type": s.source_type,
            "reason": (
                f"Low confidence ({s.confidence_score or 0}/100) "
                f"from {s.source_type or 'unknown source'}"
            )
        })

    return {
        "threshold": threshold,
        "total_low_confidence": len(sources),
        "competitors_affected": len(by_competitor),
        "data": list(by_competitor.values())
    }


@router.get("/confidence-distribution")
def get_confidence_distribution(db: Session = Depends(get_db)):
    """Get distribution of confidence levels across all data."""
    sources = db.query(DataSource).all()

    high = len([
        s for s in sources if (s.confidence_score or 0) >= 70
    ])
    moderate = len([
        s for s in sources if 40 <= (s.confidence_score or 0) < 70
    ])
    low = len([
        s for s in sources if (s.confidence_score or 0) < 40
    ])
    unscored = len([
        s for s in sources if s.confidence_score is None
    ])

    return {
        "total_data_points": len(sources),
        "distribution": {
            "high": {
                "count": high,
                "percentage": round(
                    high / len(sources) * 100, 1
                ) if sources else 0
            },
            "moderate": {
                "count": moderate,
                "percentage": round(
                    moderate / len(sources) * 100, 1
                ) if sources else 0
            },
            "low": {
                "count": low,
                "percentage": round(
                    low / len(sources) * 100, 1
                ) if sources else 0
            },
            "unscored": {
                "count": unscored,
                "percentage": round(
                    unscored / len(sources) * 100, 1
                ) if sources else 0
            }
        },
        "by_source_type": _get_confidence_by_source_type(sources)
    }


@router.post("/recalculate-confidence")
def recalculate_all_confidence_scores(db: Session = Depends(get_db)):
    """Recalculate confidence scores for all data sources."""
    sources = db.query(DataSource).all()
    updated_count = 0

    for source in sources:
        if source.source_type:
            staleness = calculate_data_staleness(
                source.extracted_at or datetime.utcnow(),
                source.data_as_of_date
            )
            confidence_result = calculate_confidence_score(
                source_type=source.source_type,
                source_reliability=source.source_reliability,
                information_credibility=source.information_credibility,
                corroborating_sources=source.corroborating_sources or 0,
                data_age_days=staleness
            )
            source.confidence_score = confidence_result.score
            source.confidence_level = confidence_result.level
            source.staleness_days = staleness
            updated_count += 1

    db.commit()

    return {
        "success": True,
        "message": (
            f"Recalculated confidence for {updated_count} data sources"
        ),
        "updated_count": updated_count
    }


@router.get("/overview")
def get_data_quality_overview(db: Session = Depends(get_db)):
    """Comprehensive data quality overview with confidence metrics.

    OPTIMIZED: Uses SQL aggregates instead of O(n^2) Python loops.
    """
    from sqlalchemy import func, case, and_

    total_competitors = db.query(Competitor).filter(
        Competitor.is_deleted == False  # noqa: E712
    ).count()

    stale_threshold = datetime.utcnow() - timedelta(days=90)

    stats = db.query(
        func.count(DataSource.id).label('total'),
        func.sum(case(
            (DataSource.confidence_score >= 70, 1), else_=0
        )).label('high'),
        func.sum(case(
            (and_(
                DataSource.confidence_score >= 40,
                DataSource.confidence_score < 70
            ), 1), else_=0
        )).label('moderate'),
        func.sum(case(
            (and_(
                DataSource.confidence_score < 40,
                DataSource.confidence_score.isnot(None)
            ), 1), else_=0
        )).label('low'),
        func.sum(case(
            (DataSource.confidence_score.is_(None), 1), else_=0
        )).label('unscored'),
        func.sum(case(
            (DataSource.is_verified == True, 1), else_=0  # noqa: E712
        )).label('verified'),
        func.sum(case(
            (and_(
                DataSource.extracted_at.isnot(None),
                DataSource.extracted_at < stale_threshold
            ), 1), else_=0
        )).label('stale'),
        func.avg(DataSource.confidence_score).label('avg_confidence')
    ).first()

    total_data_points = stats.total or 0
    high_confidence = stats.high or 0
    moderate_confidence = stats.moderate or 0
    low_confidence = stats.low or 0
    unscored = stats.unscored or 0
    verified_count = stats.verified or 0
    stale_count = stats.stale or 0

    verification_rate = round(
        (verified_count / total_data_points) * 100, 1
    ) if total_data_points > 0 else 0
    staleness_rate = round(
        (stale_count / total_data_points) * 100, 1
    ) if total_data_points > 0 else 0

    # Key field coverage
    key_fields = [
        "customer_count", "base_price", "pricing_model",
        "employee_count", "year_founded", "key_features"
    ]

    field_stats_rows = db.query(
        DataSource.field_name,
        func.count(DataSource.id).label('total'),
        func.sum(case((and_(
            DataSource.current_value.isnot(None),
            DataSource.current_value != '',
            DataSource.current_value != 'N/A',
            DataSource.current_value != 'Unknown'
        ), 1), else_=0)).label('populated'),
        func.avg(DataSource.confidence_score).label('avg_confidence')
    ).filter(
        DataSource.field_name.in_(key_fields)
    ).group_by(DataSource.field_name).all()

    field_coverage = {}
    field_stats_dict = {f.field_name: f for f in field_stats_rows}
    for field in key_fields:
        if field in field_stats_dict:
            f = field_stats_dict[field]
            field_coverage[field] = {
                "populated": f.populated or 0,
                "total": total_competitors,
                "percentage": round(
                    (f.populated / total_competitors) * 100, 1
                ) if total_competitors > 0 else 0,
                "avg_confidence": round(f.avg_confidence or 0, 1)
            }
        else:
            field_coverage[field] = {
                "populated": 0,
                "total": total_competitors,
                "percentage": 0,
                "avg_confidence": 0
            }

    # Source type breakdown
    source_breakdown = db.query(
        func.coalesce(
            DataSource.source_type, 'unknown'
        ).label('source_type'),
        func.count(DataSource.id).label('count'),
        func.avg(DataSource.confidence_score).label('avg_confidence')
    ).group_by(
        func.coalesce(DataSource.source_type, 'unknown')
    ).all()

    source_type_counts = {
        row.source_type: {
            "count": row.count,
            "avg_confidence": round(row.avg_confidence or 0, 1)
        }
        for row in source_breakdown
    }

    # Per-competitor quality scores
    competitor_stats = db.query(
        Competitor.id,
        Competitor.name,
        func.count(DataSource.id).label('total_fields'),
        func.avg(DataSource.confidence_score).label('avg_confidence'),
        func.sum(case(
            (DataSource.is_verified == True, 1), else_=0  # noqa: E712
        )).label('verified_count'),
        func.sum(case(
            (DataSource.confidence_score >= 70, 1), else_=0
        )).label('high_confidence_count'),
        func.sum(case(
            (DataSource.confidence_score < 40, 1), else_=0
        )).label('low_confidence_count')
    ).outerjoin(
        DataSource, DataSource.competitor_id == Competitor.id
    ).filter(
        Competitor.is_deleted == False  # noqa: E712
    ).group_by(
        Competitor.id, Competitor.name
    ).having(
        func.count(DataSource.id) > 0
    ).order_by(
        func.avg(DataSource.confidence_score).desc()
    ).limit(15).all()

    competitor_scores = []
    for c in competitor_stats:
        avg_conf = c.avg_confidence or 0
        quality_tier = (
            "Excellent" if avg_conf >= 70
            else "Good" if avg_conf >= 50
            else "Fair" if avg_conf >= 30
            else "Poor"
        )
        competitor_scores.append({
            "id": c.id,
            "name": c.name,
            "total_fields": c.total_fields or 0,
            "avg_confidence": round(avg_conf, 1),
            "verified_count": c.verified_count or 0,
            "high_confidence_count": c.high_confidence_count or 0,
            "low_confidence_count": c.low_confidence_count or 0,
            "quality_tier": quality_tier
        })

    needs_attention = {
        "low_confidence_count": low_confidence,
        "stale_count": stale_count,
        "unverified_count": total_data_points - verified_count,
        "unscored_count": unscored
    }

    return {
        "total_competitors": total_competitors,
        "total_data_points": total_data_points,
        "confidence_distribution": {
            "high": {
                "count": high_confidence,
                "percentage": round(
                    high_confidence / total_data_points * 100, 1
                ) if total_data_points else 0
            },
            "moderate": {
                "count": moderate_confidence,
                "percentage": round(
                    moderate_confidence / total_data_points * 100, 1
                ) if total_data_points else 0
            },
            "low": {
                "count": low_confidence,
                "percentage": round(
                    low_confidence / total_data_points * 100, 1
                ) if total_data_points else 0
            },
            "unscored": {
                "count": unscored,
                "percentage": round(
                    unscored / total_data_points * 100, 1
                ) if total_data_points else 0
            }
        },
        "verification_rate": verification_rate,
        "staleness_rate": staleness_rate,
        "field_coverage": field_coverage,
        "source_type_breakdown": source_type_counts,
        "competitor_scores": competitor_scores,
        "needs_attention": needs_attention,
        "generated_at": datetime.utcnow().isoformat()
    }
