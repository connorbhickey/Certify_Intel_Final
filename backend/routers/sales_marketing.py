"""
Certify Intel - Sales & Marketing Module API Routes (v5.0.7)
FastAPI router for competitive dimension management and sales enablement.

Provides 30+ endpoints for:
- Dimension score management (CRUD)
- Battlecard generation
- Competitor comparison
- Talking points management
- News dimension tagging
- Analytics and trends
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import json
import io

from database import SessionLocal, get_db, Competitor
from sales_marketing_module import (
    SalesMarketingModule,
    DimensionID,
    DIMENSION_METADATA,
    SCORE_LABELS
)
from dimension_analyzer import DimensionAnalyzer
from battlecard_generator import BattlecardGenerator, BATTLECARD_TEMPLATES

router = APIRouter(prefix="/api/sales-marketing", tags=["Sales & Marketing"])


# ============== Pydantic Models ==============

class DimensionScoreUpdate(BaseModel):
    """Request model for updating a dimension score."""
    dimension_id: str = Field(..., description="One of the 9 dimension IDs")
    score: int = Field(..., ge=1, le=5, description="Score from 1-5")
    evidence: str = Field(..., description="Supporting evidence for the score")
    source: str = Field(default="manual", description="Source: manual, ai, news, review")
    confidence: str = Field(default="medium", description="Confidence: low, medium, high")


class BattlecardRequest(BaseModel):
    """Request model for generating a battlecard."""
    competitor_id: int
    battlecard_type: str = Field(default="full", description="full, quick, or objection_handler")
    focus_dimensions: Optional[List[str]] = Field(default=None, description="Optional list of dimension IDs to emphasize")
    deal_context: Optional[str] = Field(default=None, description="Optional deal-specific context")
    session_id: Optional[int] = Field(default=None, description="Optional chat session ID for persistence")
    conversation_history: Optional[list] = Field(default=None, description="Optional prior conversation messages")


class TalkingPointCreate(BaseModel):
    """Request model for creating a talking point."""
    competitor_id: int
    dimension_id: str
    point_type: str = Field(..., description="strength, weakness, objection, or counter")
    content: str
    context: Optional[str] = None


class TalkingPointEffectivenessUpdate(BaseModel):
    """Request model for updating talking point effectiveness."""
    effectiveness_score: int = Field(..., ge=1, le=5)


class NewsTagRequest(BaseModel):
    """Request model for tagging news with a dimension."""
    news_url: str
    news_title: str
    competitor_id: int
    dimension_id: str
    relevance_score: float = Field(..., ge=0, le=1)
    news_snippet: Optional[str] = None
    sentiment: Optional[str] = None


class BulkDimensionUpdate(BaseModel):
    """Request model for bulk dimension updates."""
    competitor_id: int
    dimensions: List[DimensionScoreUpdate]


# ============== Dimension Endpoints ==============

@router.get("/dimensions")
async def list_dimensions():
    """
    Get all 9 competitive dimensions with metadata.

    Returns dimension IDs, names, descriptions, deal impact, and scoring guides.
    """
    return {
        "dimensions": [
            {
                "id": dim_id.value,
                "name": meta["name"],
                "short_name": meta["short_name"],
                "icon": meta["icon"],
                "description": meta["description"],
                "deal_impact": meta["deal_impact"],
                "keywords": meta["keywords"],
                "score_guide": meta["score_guide"]
            }
            for dim_id, meta in DIMENSION_METADATA.items()
        ],
        "score_labels": SCORE_LABELS
    }


@router.get("/dimensions/{dimension_id}")
async def get_dimension_detail(dimension_id: str):
    """Get detailed information about a specific dimension."""
    try:
        dim = DimensionID(dimension_id)
        meta = DIMENSION_METADATA[dim]
        return {
            "id": dim.value,
            **meta
        }
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Dimension '{dimension_id}' not found")


@router.get("/competitors/{competitor_id}/dimensions")
async def get_competitor_dimensions(
    competitor_id: int,
    db=Depends(get_db)
):
    """
    Get dimension profile for a competitor.

    Returns all 9 dimension scores, strengths, weaknesses, and overall score.
    """
    module = SalesMarketingModule(db)
    profile = module.get_dimension_profile(competitor_id)

    if not profile:
        raise HTTPException(status_code=404, detail=f"Competitor {competitor_id} not found")

    return profile.to_dict()


@router.put("/competitors/{competitor_id}/dimensions/{dimension_id}")
async def update_dimension_score(
    competitor_id: int,
    dimension_id: str,
    update: DimensionScoreUpdate,
    user_email: str = Query(default="system@certifyhealth.com"),
    db=Depends(get_db)
):
    """
    Update a dimension score with evidence.

    Creates audit trail in dimension history.
    """
    module = SalesMarketingModule(db)

    try:
        success = module.update_dimension_score(
            competitor_id=competitor_id,
            dimension_id=dimension_id,
            score=update.score,
            evidence=update.evidence,
            user_email=user_email,
            source=update.source,
            confidence=update.confidence
        )

        if not success:
            raise HTTPException(status_code=404, detail=f"Competitor {competitor_id} not found")

        return {
            "success": True,
            "message": f"Dimension {dimension_id} updated to score {update.score}",
            "competitor_id": competitor_id,
            "dimension_id": dimension_id,
            "new_score": update.score
        }

    except ValueError as e:
        logger.error(f"Dimension update validation error: {e}")
        raise HTTPException(status_code=400, detail="Invalid dimension score update. Check your input values.")


@router.post("/competitors/{competitor_id}/dimensions/bulk-update")
async def bulk_update_dimensions(
    competitor_id: int,
    updates: List[DimensionScoreUpdate],
    user_email: str = Query(default="system@certifyhealth.com"),
    db=Depends(get_db)
):
    """Update multiple dimension scores at once."""
    module = SalesMarketingModule(db)
    results = []

    for update in updates:
        try:
            success = module.update_dimension_score(
                competitor_id=competitor_id,
                dimension_id=update.dimension_id,
                score=update.score,
                evidence=update.evidence,
                user_email=user_email,
                source=update.source,
                confidence=update.confidence
            )
            results.append({
                "dimension_id": update.dimension_id,
                "success": success,
                "score": update.score
            })
        except Exception as e:
            logger.error(f"Bulk dimension update failed for dim {update.dimension_id}: {e}")
            results.append({
                "dimension_id": update.dimension_id,
                "success": False,
                "error": "Update failed"
            })

    return {
        "competitor_id": competitor_id,
        "updates": results,
        "successful": sum(1 for r in results if r.get("success")),
        "failed": sum(1 for r in results if not r.get("success"))
    }


@router.get("/competitors/{competitor_id}/dimensions/history")
async def get_dimension_history(
    competitor_id: int,
    dimension_id: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    db=Depends(get_db)
):
    """
    Get dimension score change history.

    Optionally filter by specific dimension.
    """
    module = SalesMarketingModule(db)
    history = module.get_dimension_history(
        competitor_id=competitor_id,
        dimension_id=dimension_id,
        limit=limit
    )

    return {
        "competitor_id": competitor_id,
        "filter_dimension": dimension_id,
        "history": history,
        "count": len(history)
    }


@router.post("/competitors/{competitor_id}/dimensions/ai-suggest")
async def ai_suggest_dimensions(
    competitor_id: int,
    prompt_key: Optional[str] = None,
    db=Depends(get_db)
):
    """
    Get AI-suggested dimension scores based on all available data.

    Uses existing competitor data, news, and reviews to suggest scores.
    Supports prompt_key for user-customizable AI prompts.
    """
    competitor = db.query(Competitor).filter(
        Competitor.id == competitor_id,
        Competitor.is_deleted == False
    ).first()

    if not competitor:
        raise HTTPException(status_code=404, detail=f"Competitor {competitor_id} not found")

    analyzer = DimensionAnalyzer()
    suggestions = analyzer.suggest_dimension_scores(
        competitor_id=competitor_id,
        competitor_name=competitor.name,
        db_session=db,
        prompt_key=prompt_key
    )

    return {
        "competitor_id": competitor_id,
        "competitor_name": competitor.name,
        "suggestions": suggestions,
        "note": "These are AI-generated suggestions. Review and adjust before saving."
    }


# ============== Battlecard Endpoints ==============

@router.get("/battlecards/templates")
async def get_battlecard_templates():
    """Get available battlecard templates."""
    return {
        "templates": [
            {
                "type": template_type,
                "name": template["name"],
                "description": template["description"],
                "sections": template["sections"]
            }
            for template_type, template in BATTLECARD_TEMPLATES.items()
        ]
    }


@router.post("/battlecards/generate")
async def generate_battlecard(
    request: BattlecardRequest,
    user_email: str = Query(default="system@certifyhealth.com"),
    save: bool = Query(default=True, description="Save battlecard to database"),
    db=Depends(get_db)
):
    """
    Generate a new battlecard for a competitor.

    Returns the complete battlecard with all sections based on template type.
    """
    generator = BattlecardGenerator(db)

    try:
        # Prepend conversation history as deal_context if provided
        deal_ctx = request.deal_context or ""
        if request.conversation_history and isinstance(request.conversation_history, list):
            history_text = "\n".join(
                f"[{m.get('role', 'user').upper()}]: {m.get('content', '')}"
                for m in request.conversation_history[-10:]
            )
            history_block = f"Previous conversation:\n{history_text}"
            deal_ctx = f"{deal_ctx}\n\n{history_block}" if deal_ctx else history_block

        battlecard = generator.generate_battlecard(
            competitor_id=request.competitor_id,
            battlecard_type=request.battlecard_type,
            focus_dimensions=request.focus_dimensions,
            deal_context=deal_ctx if deal_ctx else None
        )

        result = battlecard.to_dict()

        # Enhance template battlecard with AI strategic insights
        try:
            from ai_router import get_ai_router, TaskType

            router = get_ai_router()
            comp = db.query(Competitor).filter(
                Competitor.id == request.competitor_id
            ).first()
            comp_name = comp.name if comp else f"Competitor #{request.competitor_id}"

            # Build context from the template result
            template_sections = json.dumps(
                result.get("sections", {}), default=str
            )[:3000]

            ai_prompt = (
                f"You are enhancing a sales battlecard for competing against "
                f"{comp_name}. The template data below is based on verified "
                f"database records. Add strategic insights and competitive "
                f"recommendations based ONLY on the provided data.\n\n"
                f"Template Data:\n{template_sections}\n\n"
                f"Deal Context: {deal_ctx or 'None'}\n\n"
                f"Provide a concise 'AI Strategic Insights' section with "
                f"3-5 actionable recommendations for the sales team."
            )

            ai_result = await router.generate(
                prompt=ai_prompt,
                task_type=TaskType.BATTLECARD,
                system_prompt=(
                    "You are Certify Health's competitive strategy advisor. "
                    "Generate actionable sales insights based SOLELY on the "
                    "verified intelligence data provided. Do NOT fabricate, "
                    "estimate, or assume any data points. If data is not "
                    "available, state 'No verified data available for this metric.'"
                ),
                max_tokens=800,
                temperature=0.3,
            )

            ai_insights = ai_result.get("response", "")
            if ai_insights:
                result["ai_strategic_insights"] = ai_insights
                result["ai_enhanced"] = True
                result["ai_model"] = ai_result.get("model", "unknown")
        except Exception as ai_err:
            import logging as _ai_log2
            _ai_log2.getLogger(__name__).warning(f"AI enhancement for battlecard skipped: {ai_err}")
            result["ai_enhanced"] = False

        if save:
            battlecard_id = generator.save_battlecard(battlecard, user_email)
            result["id"] = battlecard_id
            result["saved"] = True

        # Persist to chat session if session_id provided
        if request.session_id:
            try:
                from database import ChatSession, ChatMessage
                user_msg = ChatMessage(
                    session_id=request.session_id,
                    role="user",
                    content=(
                        f"Generate {request.battlecard_type} battlecard"
                        f" for competitor #{request.competitor_id}"
                    ),
                )
                db.add(user_msg)
                ai_msg = ChatMessage(
                    session_id=request.session_id,
                    role="assistant",
                    content=json.dumps(result, default=str)[:4000],
                    metadata_json=json.dumps({
                        "endpoint": "sm_battlecard_generate"
                    }),
                )
                db.add(ai_msg)
                session_obj = db.query(ChatSession).filter(
                    ChatSession.id == request.session_id
                ).first()
                if session_obj:
                    session_obj.updated_at = datetime.utcnow()
                db.commit()
            except Exception as save_err:
                import logging as _log
                _log.getLogger(__name__).warning(
                    f"Failed to save SM battlecard to chat: {save_err}"
                )

        result["session_id"] = request.session_id
        return result

    except ValueError as e:
        logger.error(f"Battlecard generation validation error: {e}")
        raise HTTPException(status_code=400, detail="Invalid battlecard request. Check your input parameters.")


@router.get("/battlecards/{battlecard_id}")
async def get_battlecard(
    battlecard_id: int,
    db=Depends(get_db)
):
    """Get a specific saved battlecard."""
    generator = BattlecardGenerator(db)
    battlecard = generator.get_battlecard(battlecard_id)

    if not battlecard:
        raise HTTPException(status_code=404, detail=f"Battlecard {battlecard_id} not found")

    return battlecard


@router.get("/competitors/{competitor_id}/battlecards")
async def list_competitor_battlecards(
    competitor_id: int,
    db=Depends(get_db)
):
    """List all battlecards for a competitor."""
    generator = BattlecardGenerator(db)
    battlecards = generator.list_battlecards(competitor_id)

    return {
        "competitor_id": competitor_id,
        "battlecards": battlecards,
        "count": len(battlecards)
    }


@router.get("/battlecards/{battlecard_id}/pdf")
async def export_battlecard_pdf(
    battlecard_id: int,
    db=Depends(get_db)
):
    """Export battlecard as PDF."""
    generator = BattlecardGenerator(db)
    pdf_bytes = generator.export_to_pdf(battlecard_id)

    if not pdf_bytes:
        raise HTTPException(status_code=404, detail="Battlecard not found or PDF export failed")

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=battlecard_{battlecard_id}.pdf"}
    )


@router.get("/battlecards/{battlecard_id}/markdown")
async def export_battlecard_markdown(
    battlecard_id: int,
    db=Depends(get_db)
):
    """Export battlecard as Markdown."""
    generator = BattlecardGenerator(db)
    bc_data = generator.get_battlecard(battlecard_id)

    if not bc_data:
        raise HTTPException(status_code=404, detail=f"Battlecard {battlecard_id} not found")

    # Reconstruct the battlecard object for markdown conversion
    from battlecard_generator import BattlecardSection, GeneratedBattlecard

    content = bc_data.get("content", {})
    if isinstance(content, str):
        content = json.loads(content)

    sections = [
        BattlecardSection(
            section_id=s["section_id"],
            title=s["title"],
            content=s["content"]
        )
        for s in content.get("sections", [])
    ]

    battlecard = GeneratedBattlecard(
        competitor_id=content.get("competitor_id", 0),
        competitor_name=content.get("competitor_name", "Unknown"),
        battlecard_type=content.get("battlecard_type", "full"),
        title=content.get("title", "Battlecard"),
        sections=sections,
        generated_at=datetime.fromisoformat(content.get("generated_at", datetime.utcnow().isoformat())),
        metadata=content.get("metadata", {})
    )

    markdown = battlecard.to_markdown()

    return Response(
        content=markdown,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=battlecard_{battlecard_id}.md"}
    )


# ============== Comparison Endpoints ==============

@router.post("/compare/dimensions")
async def compare_dimensions(
    competitor_ids: List[int],
    db=Depends(get_db)
):
    """
    Compare multiple competitors across all dimensions.

    Returns dimension scores for each competitor for radar chart display.
    """
    if len(competitor_ids) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 competitors to compare")

    if len(competitor_ids) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 competitors can be compared")

    module = SalesMarketingModule(db)
    comparison = module.get_dimension_comparison(competitor_ids)

    return comparison


@router.get("/compare/{competitor_id}/vs-certify")
async def compare_vs_certify(
    competitor_id: int,
    db=Depends(get_db)
):
    """
    Compare competitor dimensions against Certify Health.

    Certify Health scores are configured defaults representing our positioning.
    """
    module = SalesMarketingModule(db)
    competitor_profile = module.get_dimension_profile(competitor_id)

    if not competitor_profile:
        raise HTTPException(status_code=404, detail=f"Competitor {competitor_id} not found")

    # Certify Health's self-assessment scores (these could be configurable)
    certify_scores = {
        "product_packaging": 5,  # Fully modular
        "integration_depth": 5,  # Deep EHR integrations
        "support_service": 4,    # Strong support
        "retention_stickiness": 4,
        "user_adoption": 4,
        "implementation_ttv": 5,  # Fast go-live
        "reliability_enterprise": 4,
        "pricing_flexibility": 5,  # Transparent pricing
        "reporting_analytics": 4
    }

    comparison = {
        "competitor": {
            "id": competitor_profile.competitor_id,
            "name": competitor_profile.competitor_name,
            "scores": {
                dim_id: (dim_score.score if dim_score else None)
                for dim_id, dim_score in competitor_profile.dimensions.items()
            }
        },
        "certify_health": {
            "name": "Certify Health",
            "scores": certify_scores
        },
        "advantages": [],
        "challenges": []
    }

    # Calculate advantages and challenges
    for dim_id, certify_score in certify_scores.items():
        comp_score = competitor_profile.dimensions.get(dim_id)
        comp_score_val = comp_score.score if comp_score else None

        meta = DIMENSION_METADATA.get(DimensionID(dim_id), {})

        if comp_score_val and comp_score_val < certify_score:
            comparison["advantages"].append({
                "dimension": meta.get("name", dim_id),
                "certify_score": certify_score,
                "competitor_score": comp_score_val,
                "gap": certify_score - comp_score_val
            })
        elif comp_score_val and comp_score_val > certify_score:
            comparison["challenges"].append({
                "dimension": meta.get("name", dim_id),
                "certify_score": certify_score,
                "competitor_score": comp_score_val,
                "gap": comp_score_val - certify_score
            })

    return comparison


# ============== Talking Points Endpoints ==============

@router.get("/competitors/{competitor_id}/talking-points")
async def get_talking_points(
    competitor_id: int,
    dimension_id: Optional[str] = None,
    point_type: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    db=Depends(get_db)
):
    """
    Get talking points for sales conversations.

    Filter by dimension and/or point type (strength, weakness, objection, counter).
    """
    module = SalesMarketingModule(db)
    points = module.get_talking_points(
        competitor_id=competitor_id,
        dimension_id=dimension_id,
        point_type=point_type,
        limit=limit
    )

    return {
        "competitor_id": competitor_id,
        "filters": {
            "dimension_id": dimension_id,
            "point_type": point_type
        },
        "talking_points": points,
        "count": len(points)
    }


@router.post("/talking-points")
async def create_talking_point(
    point: TalkingPointCreate,
    user_email: str = Query(default="system@certifyhealth.com"),
    db=Depends(get_db)
):
    """Create a new talking point."""
    module = SalesMarketingModule(db)

    try:
        point_id = module.create_talking_point(
            competitor_id=point.competitor_id,
            dimension_id=point.dimension_id,
            point_type=point.point_type,
            content=point.content,
            context=point.context,
            user_email=user_email
        )

        return {
            "success": True,
            "id": point_id,
            "message": "Talking point created"
        }

    except ValueError as e:
        logger.error(f"Talking point creation validation error: {e}")
        raise HTTPException(status_code=400, detail="Invalid talking point data. Check your input values.")


@router.put("/talking-points/{point_id}/effectiveness")
async def update_talking_point_effectiveness(
    point_id: int,
    update: TalkingPointEffectivenessUpdate,
    db=Depends(get_db)
):
    """Update effectiveness score for a talking point (from win/loss feedback)."""
    module = SalesMarketingModule(db)

    try:
        success = module.update_talking_point_effectiveness(
            point_id=point_id,
            effectiveness_score=update.effectiveness_score
        )

        if not success:
            raise HTTPException(status_code=404, detail=f"Talking point {point_id} not found")

        return {
            "success": True,
            "point_id": point_id,
            "new_effectiveness_score": update.effectiveness_score
        }

    except ValueError as e:
        logger.error(f"Effectiveness update validation error: {e}")
        raise HTTPException(status_code=400, detail="Invalid effectiveness score. Check your input values.")


@router.delete("/talking-points/{point_id}")
async def delete_talking_point(
    point_id: int,
    db=Depends(get_db)
):
    """Soft delete a talking point."""
    from database import TalkingPoint

    point = db.query(TalkingPoint).filter(TalkingPoint.id == point_id).first()
    if not point:
        raise HTTPException(status_code=404, detail=f"Talking point {point_id} not found")

    point.is_active = False
    db.commit()

    return {"success": True, "message": f"Talking point {point_id} deleted"}


# ============== News Dimension Tagging ==============

@router.get("/news/by-dimension/{dimension_id}")
async def get_news_by_dimension(
    dimension_id: str,
    competitor_id: Optional[int] = None,
    days: int = Query(default=30, le=365),
    limit: int = Query(default=50, le=200),
    db=Depends(get_db)
):
    """
    Get news articles tagged with a specific dimension.

    Filter by competitor and date range.
    """
    module = SalesMarketingModule(db)

    try:
        news = module.get_news_by_dimension(
            dimension_id=dimension_id,
            competitor_id=competitor_id,
            days=days,
            limit=limit
        )

        return {
            "dimension_id": dimension_id,
            "dimension_name": DIMENSION_METADATA.get(DimensionID(dimension_id), {}).get("name"),
            "filters": {
                "competitor_id": competitor_id,
                "days": days
            },
            "articles": news,
            "count": len(news)
        }

    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid dimension_id: {dimension_id}")


@router.post("/news/tag-dimension")
async def tag_news_dimension(
    tag: NewsTagRequest,
    user_email: str = Query(default="ai"),
    db=Depends(get_db)
):
    """Manually tag a news article with a dimension."""
    module = SalesMarketingModule(db)

    try:
        tag_id = module.tag_news_with_dimension(
            news_url=tag.news_url,
            news_title=tag.news_title,
            competitor_id=tag.competitor_id,
            dimension_id=tag.dimension_id,
            relevance_score=tag.relevance_score,
            tagged_by=user_email,
            news_snippet=tag.news_snippet,
            sentiment=tag.sentiment
        )

        return {
            "success": True,
            "id": tag_id,
            "message": "News article tagged with dimension"
        }

    except ValueError as e:
        logger.error(f"News dimension tag validation error: {e}")
        raise HTTPException(status_code=400, detail="Invalid news tag data. Check your input values.")


@router.post("/news/auto-tag/{competitor_id}")
async def auto_tag_news(
    competitor_id: int,
    days: int = Query(default=7, le=30),
    db=Depends(get_db)
):
    """
    Auto-tag recent news articles with dimensions using AI.

    Analyzes articles and tags them with relevant dimensions.
    """
    from database import Competitor

    competitor = db.query(Competitor).filter(
        Competitor.id == competitor_id,
        Competitor.is_deleted == False
    ).first()

    if not competitor:
        raise HTTPException(status_code=404, detail=f"Competitor {competitor_id} not found")

    # v5.0.7: Full integration with news_monitor.py
    try:
        from news_monitor import NewsMonitor

        monitor = NewsMonitor(tag_dimensions=True)
        digest = monitor.fetch_news(competitor.name, days=days)

        # Store tags in database
        tags_stored = 0
        if hasattr(monitor, 'store_dimension_tags'):
            tags_stored = monitor.store_dimension_tags(
                articles=digest.articles,
                competitor_id=competitor_id,
                db_session=db
            )

        # Count articles by dimension
        dimension_counts = {}
        for article in digest.articles:
            if article.dimension_tags:
                for tag in article.dimension_tags:
                    dim_id = tag["dimension_id"]
                    dimension_counts[dim_id] = dimension_counts.get(dim_id, 0) + 1

        return {
            "success": True,
            "competitor_id": competitor_id,
            "competitor_name": competitor.name,
            "days": days,
            "total_articles": digest.total_count,
            "articles_tagged": len([a for a in digest.articles if a.dimension_tags]),
            "tags_stored": tags_stored,
            "dimension_breakdown": dimension_counts,
            "sentiment_breakdown": digest.sentiment_breakdown
        }

    except ImportError:
        return {
            "success": False,
            "competitor_id": competitor_id,
            "competitor_name": competitor.name,
            "days": days,
            "error": "NewsMonitor not available. Install news monitoring dependencies."
        }


# ============== Analytics Endpoints ==============

@router.get("/analytics/dimension-trends")
async def get_dimension_trends(
    competitor_id: Optional[int] = None,
    dimension_id: Optional[str] = None,
    days: int = Query(default=90, le=365),
    db=Depends(get_db)
):
    """
    Get dimension score trends over time.

    Shows how dimension scores have changed for tracking improvements/declines.
    """
    from database import CompetitorDimensionHistory
    from datetime import timedelta

    cutoff = datetime.utcnow() - timedelta(days=days)

    query = db.query(CompetitorDimensionHistory).filter(
        CompetitorDimensionHistory.changed_at >= cutoff
    )

    if competitor_id:
        query = query.filter(CompetitorDimensionHistory.competitor_id == competitor_id)
    if dimension_id:
        query = query.filter(CompetitorDimensionHistory.dimension_id == dimension_id)

    history = query.order_by(CompetitorDimensionHistory.changed_at.asc()).all()

    # Group by dimension
    trends = {}
    for h in history:
        if h.dimension_id not in trends:
            trends[h.dimension_id] = {
                "dimension_name": DIMENSION_METADATA.get(DimensionID(h.dimension_id), {}).get("name"),
                "data_points": []
            }

        trends[h.dimension_id]["data_points"].append({
            "date": h.changed_at.isoformat(),
            "score": h.new_score,
            "competitor_id": h.competitor_id
        })

    return {
        "filters": {
            "competitor_id": competitor_id,
            "dimension_id": dimension_id,
            "days": days
        },
        "trends": trends
    }


@router.get("/analytics/win-loss-by-dimension")
async def get_win_loss_by_dimension(
    days: int = Query(default=90, le=365),
    db=Depends(get_db)
):
    """
    Analyze win/loss correlation with dimensions.

    Shows which dimensions correlate with winning or losing deals.
    """
    from database import WinLossDeal, CompetitorDimensionHistory
    from datetime import timedelta

    cutoff = datetime.utcnow() - timedelta(days=days)

    # Get recent deals
    deals = db.query(WinLossDeal).filter(
        WinLossDeal.deal_date >= cutoff
    ).all()

    # For each deal, get dimension scores at time of deal
    analysis = {
        "wins": {},
        "losses": {},
        "total_deals": len(deals)
    }

    for deal in deals:
        # Get dimension scores for this competitor around deal time
        scores = db.query(CompetitorDimensionHistory).filter(
            CompetitorDimensionHistory.competitor_id == deal.competitor_id,
            CompetitorDimensionHistory.changed_at <= deal.deal_date
        ).order_by(CompetitorDimensionHistory.changed_at.desc()).all()

        # Get most recent score per dimension
        latest_scores = {}
        for score in scores:
            if score.dimension_id not in latest_scores:
                latest_scores[score.dimension_id] = score.new_score

        outcome = "wins" if deal.outcome == "win" else "losses"

        for dim_id, score in latest_scores.items():
            if dim_id not in analysis[outcome]:
                analysis[outcome][dim_id] = {
                    "dimension_name": DIMENSION_METADATA.get(DimensionID(dim_id), {}).get("name"),
                    "scores": [],
                    "avg_score": 0
                }
            analysis[outcome][dim_id]["scores"].append(score)

    # Calculate averages
    for outcome in ["wins", "losses"]:
        for dim_id, data in analysis[outcome].items():
            if data["scores"]:
                data["avg_score"] = sum(data["scores"]) / len(data["scores"])
                data["deal_count"] = len(data["scores"])
            del data["scores"]  # Don't return raw scores

    return analysis


@router.get("/analytics/dimension-coverage")
async def get_dimension_coverage(
    db=Depends(get_db)
):
    """
    Get dimension scoring coverage across all competitors.

    Shows which competitors have been scored and which dimensions are missing.
    """
    competitors = db.query(Competitor).filter(Competitor.is_deleted == False).all()

    coverage = {
        "total_competitors": len(competitors),
        "fully_scored": 0,
        "partially_scored": 0,
        "not_scored": 0,
        "by_dimension": {},
        "competitors": []
    }

    # Initialize dimension counters
    for dim_id in DimensionID:
        coverage["by_dimension"][dim_id.value] = {
            "name": DIMENSION_METADATA[dim_id]["name"],
            "scored_count": 0,
            "percentage": 0
        }

    for comp in competitors:
        scored_dims = []
        for dim_id in DimensionID:
            score = getattr(comp, f"dim_{dim_id.value}_score", None)
            if score is not None:
                scored_dims.append(dim_id.value)
                coverage["by_dimension"][dim_id.value]["scored_count"] += 1

        if len(scored_dims) == 9:
            coverage["fully_scored"] += 1
        elif len(scored_dims) > 0:
            coverage["partially_scored"] += 1
        else:
            coverage["not_scored"] += 1

        coverage["competitors"].append({
            "id": comp.id,
            "name": comp.name,
            "scored_dimensions": len(scored_dims),
            "missing_dimensions": [d.value for d in DimensionID if d.value not in scored_dims]
        })

    # Calculate percentages
    for dim_id in DimensionID:
        count = coverage["by_dimension"][dim_id.value]["scored_count"]
        coverage["by_dimension"][dim_id.value]["percentage"] = round(
            (count / len(competitors)) * 100 if competitors else 0, 1
        )

    return coverage


@router.get("/analytics/sales-priority-matrix")
async def get_sales_priority_matrix(
    db=Depends(get_db)
):
    """
    Get sales priority matrix based on threat level and dimension weaknesses.

    Helps sales teams prioritize which competitors to focus on.
    """
    competitors = db.query(Competitor).filter(Competitor.is_deleted == False).all()

    matrix = {
        "high_priority": [],
        "medium_priority": [],
        "low_priority": [],
        "not_assessed": []
    }

    for comp in competitors:
        # Count weaknesses (score <= 2)
        weaknesses = []
        strengths = []

        for dim_id in DimensionID:
            score = getattr(comp, f"dim_{dim_id.value}_score", None)
            if score is not None:
                if score <= 2:
                    weaknesses.append(dim_id.value)
                elif score >= 4:
                    strengths.append(dim_id.value)

        comp_data = {
            "id": comp.id,
            "name": comp.name,
            "threat_level": comp.threat_level,
            "overall_score": comp.dim_overall_score,
            "weakness_count": len(weaknesses),
            "strength_count": len(strengths),
            "weaknesses": weaknesses,
            "strengths": strengths
        }

        # Prioritization logic
        if not weaknesses and not strengths:
            matrix["not_assessed"].append(comp_data)
        elif comp.threat_level == "High" and len(weaknesses) > 0:
            matrix["high_priority"].append(comp_data)
        elif comp.threat_level in ["High", "Medium"] or len(weaknesses) >= 3:
            matrix["medium_priority"].append(comp_data)
        else:
            matrix["low_priority"].append(comp_data)

    # Sort each category
    for category in matrix.values():
        category.sort(key=lambda x: (x["weakness_count"], -x.get("overall_score", 0)), reverse=True)

    return matrix


# ============== Phase 5: AI Enhancement Endpoints (v5.0.7) ==============

@router.post("/competitors/{competitor_id}/auto-score-reviews")
async def auto_score_from_reviews(
    competitor_id: int,
    apply_scores: bool = Query(default=False, description="Apply suggested scores to competitor"),
    user_email: str = Query(default="ai"),
    db=Depends(get_db)
):
    """
    Analyze customer reviews and suggest dimension scores.

    Parses review text for dimension signals and suggests scores based on sentiment.
    """
    competitor = db.query(Competitor).filter(
        Competitor.id == competitor_id,
        Competitor.is_deleted == False
    ).first()

    if not competitor:
        raise HTTPException(status_code=404, detail=f"Competitor {competitor_id} not found")

    analyzer = DimensionAnalyzer()
    module = SalesMarketingModule(db)

    # Collect reviews from multiple sources (G2, Glassdoor data if stored)
    reviews = []

    # Check for stored review data in DataSource
    from database import DataSource
    review_sources = db.query(DataSource).filter(
        DataSource.competitor_id == competitor_id,
        DataSource.field_name.in_(['g2_reviews', 'glassdoor_reviews', 'capterra_reviews'])
    ).all()

    for source in review_sources:
        if source.current_value:
            reviews.append({
                "text": source.current_value,
                "rating": 4.0,  # Default rating if not stored
                "source": source.field_name
            })

    # Also analyze any stored key customer feedback
    if competitor.key_customers:
        reviews.append({
            "text": competitor.key_customers,
            "rating": 4.0,
            "source": "key_customers"
        })

    if not reviews:
        return {
            "competitor_id": competitor_id,
            "competitor_name": competitor.name,
            "message": "No reviews found to analyze. Add review data first.",
            "suggestions": {}
        }

    # Analyze all reviews for dimension signals
    aggregated_signals = {}

    for review in reviews:
        signals = analyzer.analyze_review_dimensions(
            review_text=review["text"],
            review_rating=review["rating"],
            competitor_name=competitor.name
        )

        for dim_id, score in signals.items():
            if dim_id not in aggregated_signals:
                aggregated_signals[dim_id] = []
            aggregated_signals[dim_id].append(score)

    # Calculate average scores per dimension
    suggestions = {}
    for dim_id, scores in aggregated_signals.items():
        avg_score = round(sum(scores) / len(scores))
        avg_score = max(1, min(5, avg_score))  # Clamp to 1-5

        dim_meta = DIMENSION_METADATA.get(DimensionID(dim_id), {})
        suggestions[dim_id] = {
            "suggested_score": avg_score,
            "based_on_reviews": len(scores),
            "dimension_name": dim_meta.get("name", dim_id),
            "confidence": "medium" if len(scores) >= 3 else "low"
        }

    # Optionally apply scores
    applied = []
    if apply_scores and suggestions:
        for dim_id, data in suggestions.items():
            try:
                module.update_dimension_score(
                    competitor_id=competitor_id,
                    dimension_id=dim_id,
                    score=data["suggested_score"],
                    evidence=f"Auto-scored from {data['based_on_reviews']} review(s)",
                    user_email=user_email,
                    source="review_analysis",
                    confidence=data["confidence"]
                )
                applied.append(dim_id)
            except Exception as e:
                print(f"Failed to apply score for {dim_id}: {e}")

    return {
        "competitor_id": competitor_id,
        "competitor_name": competitor.name,
        "reviews_analyzed": len(reviews),
        "suggestions": suggestions,
        "applied": applied if apply_scores else [],
        "message": f"Applied {len(applied)} dimension scores" if apply_scores else "Suggestions generated (not applied)"
    }


@router.post("/competitors/{competitor_id}/auto-update-from-news")
async def auto_update_from_news(
    competitor_id: int,
    days: int = Query(default=30, le=90),
    apply_updates: bool = Query(default=False, description="Apply evidence updates"),
    user_email: str = Query(default="ai"),
    db=Depends(get_db)
):
    """
    Analyze recent news and update dimension evidence.

    Fetches news, classifies by dimension, and optionally updates evidence fields.
    """
    competitor = db.query(Competitor).filter(
        Competitor.id == competitor_id,
        Competitor.is_deleted == False
    ).first()

    if not competitor:
        raise HTTPException(status_code=404, detail=f"Competitor {competitor_id} not found")

    # Try to import and use NewsMonitor
    try:
        from news_monitor import NewsMonitor
        monitor = NewsMonitor(tag_dimensions=True)
        digest = monitor.fetch_news(competitor.name, days=days)

        # Store dimension tags if fetched
        if hasattr(monitor, 'store_dimension_tags'):
            tags_stored = monitor.store_dimension_tags(
                articles=digest.articles,
                competitor_id=competitor_id,
                db_session=db
            )
    except ImportError:
        return {
            "error": "NewsMonitor not available",
            "message": "Install news monitoring dependencies"
        }

    # Aggregate dimension evidence from tagged articles
    dimension_articles = {}
    for article in digest.articles:
        if article.dimension_tags:
            for tag in article.dimension_tags:
                dim_id = tag["dimension_id"]
                if dim_id not in dimension_articles:
                    dimension_articles[dim_id] = []
                dimension_articles[dim_id].append({
                    "title": article.title,
                    "sentiment": article.sentiment,
                    "date": article.published_date,
                    "confidence": tag["confidence"]
                })

    # Generate evidence summaries
    evidence_updates = {}
    analyzer = DimensionAnalyzer()

    for dim_id, articles in dimension_articles.items():
        if not articles:
            continue

        dim_meta = DIMENSION_METADATA.get(DimensionID(dim_id), {})

        # Build evidence summary
        positive = sum(1 for a in articles if a["sentiment"] == "positive")
        negative = sum(1 for a in articles if a["sentiment"] == "negative")

        summary = f"Based on {len(articles)} recent news articles. "
        if positive > negative:
            summary += f"Generally positive coverage ({positive} positive, {negative} negative)."
        elif negative > positive:
            summary += f"Some concerning coverage ({negative} negative, {positive} positive)."
        else:
            summary += f"Mixed coverage ({positive} positive, {negative} negative)."

        # Add recent headline
        if articles:
            summary += f" Recent: \"{articles[0]['title'][:100]}...\""

        evidence_updates[dim_id] = {
            "dimension_name": dim_meta.get("name", dim_id),
            "article_count": len(articles),
            "sentiment_summary": {
                "positive": positive,
                "negative": negative,
                "neutral": len(articles) - positive - negative
            },
            "evidence_summary": summary
        }

    # Optionally apply evidence updates
    module = SalesMarketingModule(db)
    applied = []

    if apply_updates and evidence_updates:
        for dim_id, data in evidence_updates.items():
            try:
                # Get current score or keep None
                current_score = getattr(competitor, f"dim_{dim_id}_score", None)

                if current_score:
                    # Update only the evidence, keep the score
                    setattr(competitor, f"dim_{dim_id}_evidence", data["evidence_summary"])
                    setattr(competitor, f"dim_{dim_id}_updated", datetime.utcnow())
                    applied.append(dim_id)

            except Exception as e:
                print(f"Failed to update evidence for {dim_id}: {e}")

        db.commit()

    return {
        "competitor_id": competitor_id,
        "competitor_name": competitor.name,
        "days_analyzed": days,
        "total_articles": digest.total_count,
        "articles_with_dimensions": sum(len(a) for a in dimension_articles.values()),
        "dimension_coverage": list(dimension_articles.keys()),
        "evidence_updates": evidence_updates,
        "applied": applied if apply_updates else [],
        "tags_stored": tags_stored if 'tags_stored' in locals() else 0,
        "message": f"Updated evidence for {len(applied)} dimensions" if apply_updates else "Analysis complete (not applied)"
    }
