"""
Certify Intel - Sales & Marketing Module (v5.0.7)
Core logic for competitive dimension management and sales enablement.

This module provides:
- 9 Competitive Evaluation Dimensions with scoring (1-5)
- Dimension profile management for competitors
- Talking points and objection handling
- Integration with existing competitor data

The 9 Dimensions:
1. Product Modules & Packaging
2. Interoperability & Integration Depth
3. Customer Support & Service Model
4. Retention & Product Stickiness
5. User Adoption & Ease of Use
6. Implementation Effort & Time to Value
7. Reliability & Enterprise Readiness
8. Pricing Model & Commercial Flexibility
9. Reporting & Analytics Capability
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass, field, asdict
from enum import Enum
import json
import logging

logger = logging.getLogger(__name__)


# ============== Dimension Definitions ==============

class DimensionID(str, Enum):
    """The 9 competitive evaluation dimensions."""
    PRODUCT_PACKAGING = "product_packaging"
    INTEGRATION_DEPTH = "integration_depth"
    SUPPORT_SERVICE = "support_service"
    RETENTION_STICKINESS = "retention_stickiness"
    USER_ADOPTION = "user_adoption"
    IMPLEMENTATION_TTV = "implementation_ttv"
    RELIABILITY_ENTERPRISE = "reliability_enterprise"
    PRICING_FLEXIBILITY = "pricing_flexibility"
    REPORTING_ANALYTICS = "reporting_analytics"


DIMENSION_METADATA = {
    DimensionID.PRODUCT_PACKAGING: {
        "name": "Product Modules & Packaging",
        "short_name": "Packaging",
        "icon": "📦",
        "description": "Modular vs bundled purchasing, module gaps, suite lock-in",
        "deal_impact": "Buyers often reject forced bundles and overbuy risk",
        "keywords": ["bundle", "module", "package", "suite", "pricing tier", "add-on", "modular", "all-in-one"],
        "review_signals": ["forced to buy", "only needed", "too many features", "nickel and dime", "bloated"],
        "score_guide": {
            1: "Forces bundled purchase, no modularity, significant overbuy risk",
            2: "Limited modularity, some forced bundling, hidden module costs",
            3: "Moderate modularity, some flexibility in purchasing",
            4: "Good modularity, most modules available separately",
            5: "Fully modular, buy only what you need, transparent packaging"
        }
    },
    DimensionID.INTEGRATION_DEPTH: {
        "name": "Interoperability & Integration Depth",
        "short_name": "Integration",
        "icon": "🔗",
        "description": "Number and depth of EHR/EMR integrations, API maturity, workflow embed",
        "deal_impact": "Broad, proven integration coverage reduces friction and becomes a standalone differentiator",
        "keywords": ["integration", "API", "EHR", "EMR", "Epic", "Cerner", "interoperability", "HL7", "FHIR", "webhook"],
        "review_signals": ["integrates with", "connects to", "API", "data sync", "workflow", "seamless"],
        "score_guide": {
            1: "No/minimal integrations, proprietary systems only",
            2: "Few integrations, limited API, manual data transfer required",
            3: "Basic integrations with major EHRs, functional API",
            4: "Strong integration ecosystem, mature API, good documentation",
            5: "Deep bidirectional integrations, certified Epic/Cerner partner, modern FHIR API"
        }
    },
    DimensionID.SUPPORT_SERVICE: {
        "name": "Customer Support & Service Model",
        "short_name": "Support",
        "icon": "🎧",
        "description": "Responsiveness, implementation partnership, services depth",
        "deal_impact": "Support quality often drives outcomes more than features",
        "keywords": ["support", "service", "help desk", "customer success", "account manager", "response time", "SLA"],
        "review_signals": ["support team", "responsive", "helpful", "slow to respond", "ticket", "wait time"],
        "score_guide": {
            1: "Poor support, long wait times, unresponsive, no dedicated contacts",
            2: "Basic support, slow response, limited availability",
            3: "Adequate support, reasonable response times, standard SLAs",
            4: "Good support, dedicated CSM, proactive communication",
            5: "Exceptional support, 24/7 availability, strategic partnership model"
        }
    },
    DimensionID.RETENTION_STICKINESS: {
        "name": "Retention & Product Stickiness",
        "short_name": "Retention",
        "icon": "🔒",
        "description": "Renewal strength, switching costs, embedded operational value",
        "deal_impact": "Sticky products persist because they deliver durable value",
        "keywords": ["retention", "churn", "renewal", "switching cost", "contract", "lock-in", "sticky"],
        "review_signals": ["hard to leave", "switching", "contract", "renewal", "years using", "trapped"],
        "score_guide": {
            1: "High churn, easy to switch away, low embedded value",
            2: "Moderate churn, some switching friction, limited stickiness",
            3: "Average retention, reasonable switching costs",
            4: "Strong retention, good embedded value, meaningful switching costs",
            5: "Very high retention, deeply embedded, strategic relationship"
        }
    },
    DimensionID.USER_ADOPTION: {
        "name": "User Adoption & Ease of Use",
        "short_name": "Adoption",
        "icon": "👥",
        "description": "Workflow fit, training burden, sustained usage evidence",
        "deal_impact": "Adoption determines whether value materializes",
        "keywords": ["adoption", "ease of use", "user-friendly", "training", "onboarding", "intuitive", "UX"],
        "review_signals": ["easy to use", "intuitive", "learning curve", "training", "staff adoption", "clunky"],
        "score_guide": {
            1: "Very difficult to use, extensive training required, low adoption",
            2: "Steep learning curve, significant training investment needed",
            3: "Moderate ease of use, standard training requirements",
            4: "User-friendly, minimal training, good adoption rates",
            5: "Extremely intuitive, self-service, high sustained adoption"
        }
    },
    DimensionID.IMPLEMENTATION_TTV: {
        "name": "Implementation & Time to Value",
        "short_name": "Implementation",
        "icon": "⏱️",
        "description": "Deployment timelines, services requirements, go-live consistency",
        "deal_impact": "Strong implementation creates faster time-to-value",
        "keywords": ["implementation", "deployment", "go-live", "timeline", "onboarding", "setup", "TTV"],
        "review_signals": ["implementation", "go-live", "weeks", "months", "delayed", "on time", "quick start"],
        "score_guide": {
            1: "Very long implementation (6+ months), frequent delays, high risk",
            2: "Long implementation (3-6 months), some delays common",
            3: "Average implementation (1-3 months), generally on schedule",
            4: "Fast implementation (2-4 weeks), reliable go-live",
            5: "Rapid deployment (days), self-service setup, immediate value"
        }
    },
    DimensionID.RELIABILITY_ENTERPRISE: {
        "name": "Reliability & Enterprise Readiness",
        "short_name": "Reliability",
        "icon": "🏢",
        "description": "Uptime, operational consistency, scalability, maturity at enterprise volume",
        "deal_impact": "Operational systems require dependable performance at scale",
        "keywords": ["uptime", "reliability", "scalability", "enterprise", "downtime", "outage", "performance", "SLA"],
        "review_signals": ["downtime", "reliable", "crashes", "slow", "enterprise", "scale", "outage"],
        "score_guide": {
            1: "Frequent outages, poor performance, not enterprise-ready",
            2: "Occasional reliability issues, limited scalability",
            3: "Generally reliable, adequate for mid-market",
            4: "Very reliable, strong uptime SLAs, good scalability",
            5: "Enterprise-grade, 99.9%+ uptime, proven at scale"
        }
    },
    DimensionID.PRICING_FLEXIBILITY: {
        "name": "Pricing Model & Commercial Flexibility",
        "short_name": "Pricing",
        "icon": "💰",
        "description": "Pricing transparency, modularity, hidden cost drivers",
        "deal_impact": "Commercial structure shapes buyer confidence and ROI",
        "keywords": ["pricing", "cost", "fee", "contract", "transparent", "hidden", "ROI", "flexible"],
        "review_signals": ["expensive", "affordable", "hidden fees", "pricing", "cost", "value", "worth it"],
        "score_guide": {
            1: "Opaque pricing, many hidden fees, inflexible terms",
            2: "Confusing pricing, some hidden costs, rigid contracts",
            3: "Standard pricing model, reasonable transparency",
            4: "Clear pricing, flexible terms, good value proposition",
            5: "Fully transparent, flexible commercial terms, strong ROI"
        }
    },
    DimensionID.REPORTING_ANALYTICS: {
        "name": "Reporting & Analytics Capability",
        "short_name": "Analytics",
        "icon": "📊",
        "description": "Operational dashboards, module-level performance visibility, exportable data",
        "deal_impact": "Buyers need surfaced data for ongoing performance improvement",
        "keywords": ["reporting", "analytics", "dashboard", "metrics", "data", "export", "insights", "BI"],
        "review_signals": ["reports", "dashboard", "analytics", "metrics", "visibility", "data", "insights"],
        "score_guide": {
            1: "Minimal reporting, no dashboards, data locked in system",
            2: "Basic reports, limited customization, poor data access",
            3: "Standard reporting, some dashboards, basic exports",
            4: "Good analytics, customizable dashboards, data export",
            5: "Advanced analytics, real-time dashboards, full API data access"
        }
    }
}

# Score labels for display
SCORE_LABELS = {
    1: "Major Weakness",
    2: "Weakness",
    3: "Neutral",
    4: "Strength",
    5: "Major Strength"
}


# ============== Data Classes ==============

@dataclass
class DimensionScore:
    """A single dimension score for a competitor."""
    dimension_id: str
    score: int  # 1-5
    evidence: str
    source: str = "manual"  # manual, ai, news, review
    confidence: str = "medium"  # low, medium, high
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension_id": self.dimension_id,
            "score": self.score,
            "score_label": SCORE_LABELS.get(self.score, "Unknown"),
            "evidence": self.evidence,
            "source": self.source,
            "confidence": self.confidence,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


@dataclass
class CompetitorDimensionProfile:
    """Complete dimension profile for a competitor."""
    competitor_id: int
    competitor_name: str
    dimensions: Dict[str, DimensionScore]
    overall_score: float
    strengths: List[str]  # dimension_ids where score >= 4
    weaknesses: List[str]  # dimension_ids where score <= 2
    sales_priority: str  # high, medium, low

    def to_dict(self) -> Dict[str, Any]:
        return {
            "competitor_id": self.competitor_id,
            "competitor_name": self.competitor_name,
            "dimensions": {k: v.to_dict() for k, v in self.dimensions.items()},
            "overall_score": round(self.overall_score, 2) if self.overall_score else None,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "sales_priority": self.sales_priority,
            "scored_count": len([d for d in self.dimensions.values() if d.score]),
            "total_dimensions": len(DimensionID)
        }


# ============== Core Module ==============

class SalesMarketingModule:
    """
    Core module for sales and marketing competitive intelligence.
    Manages dimension scoring, profiles, and talking points.
    """

    def __init__(self, db_session):
        """Initialize with a database session."""
        self.db = db_session

    def get_all_dimensions(self) -> List[Dict[str, Any]]:
        """Get metadata for all 9 competitive dimensions."""
        return [
            {
                "id": dim_id.value,
                "name": meta["name"],
                "short_name": meta["short_name"],
                "icon": meta["icon"],
                "description": meta["description"],
                "deal_impact": meta["deal_impact"],
                "score_guide": meta["score_guide"]
            }
            for dim_id, meta in DIMENSION_METADATA.items()
        ]

    def get_dimension_profile(self, competitor_id: int) -> Optional[CompetitorDimensionProfile]:
        """Get complete dimension profile for a competitor."""
        from database import Competitor

        competitor = self.db.query(Competitor).filter(
            Competitor.id == competitor_id,
            Competitor.is_deleted == False
        ).first()

        if not competitor:
            return None

        # Build dimension scores from competitor fields
        dimensions = {}
        for dim_id in DimensionID:
            score_field = f"dim_{dim_id.value}_score"
            evidence_field = f"dim_{dim_id.value}_evidence"
            updated_field = f"dim_{dim_id.value}_updated"

            score = getattr(competitor, score_field, None)
            evidence = getattr(competitor, evidence_field, None)
            updated = getattr(competitor, updated_field, None)

            if score is not None:
                dimensions[dim_id.value] = DimensionScore(
                    dimension_id=dim_id.value,
                    score=score,
                    evidence=evidence or "",
                    updated_at=updated or datetime.utcnow()
                )

        # Calculate aggregate metrics
        scores = [d.score for d in dimensions.values() if d.score]
        overall_score = sum(scores) / len(scores) if scores else 0.0

        strengths = [d.dimension_id for d in dimensions.values() if d.score and d.score >= 4]
        weaknesses = [d.dimension_id for d in dimensions.values() if d.score and d.score <= 2]

        # Determine sales priority based on threat level and weaknesses
        if competitor.threat_level == "High" and len(weaknesses) > 0:
            sales_priority = "high"
        elif competitor.threat_level == "Medium" or len(weaknesses) > 2:
            sales_priority = "medium"
        else:
            sales_priority = "low"

        return CompetitorDimensionProfile(
            competitor_id=competitor_id,
            competitor_name=competitor.name,
            dimensions=dimensions,
            overall_score=overall_score,
            strengths=strengths,
            weaknesses=weaknesses,
            sales_priority=sales_priority
        )

    def update_dimension_score(
        self,
        competitor_id: int,
        dimension_id: str,
        score: int,
        evidence: str,
        user_email: str,
        source: str = "manual",
        confidence: str = "medium"
    ) -> bool:
        """
        Update a dimension score with audit trail.

        Args:
            competitor_id: Target competitor ID
            dimension_id: One of the 9 dimension IDs
            score: 1-5 rating
            evidence: Supporting evidence text
            user_email: Who made this update
            source: manual, ai, news, review
            confidence: low, medium, high

        Returns:
            True if successful
        """
        from database import Competitor, CompetitorDimensionHistory

        # Validate dimension
        if dimension_id not in [d.value for d in DimensionID]:
            raise ValueError(f"Invalid dimension_id: {dimension_id}")

        # Validate score
        if not 1 <= score <= 5:
            raise ValueError(f"Score must be 1-5, got: {score}")

        competitor = self.db.query(Competitor).filter(
            Competitor.id == competitor_id,
            Competitor.is_deleted == False
        ).first()

        if not competitor:
            return False

        # Get current score for history
        score_field = f"dim_{dimension_id}_score"
        old_score = getattr(competitor, score_field, None)

        # Update competitor dimension fields
        setattr(competitor, score_field, score)
        setattr(competitor, f"dim_{dimension_id}_evidence", evidence)
        setattr(competitor, f"dim_{dimension_id}_updated", datetime.utcnow())

        # Recalculate overall score
        self._recalculate_overall_score(competitor)

        # Create history record
        history = CompetitorDimensionHistory(
            competitor_id=competitor_id,
            dimension_id=dimension_id,
            old_score=old_score,
            new_score=score,
            evidence=evidence,
            source=source,
            confidence=confidence,
            changed_by=user_email,
            changed_at=datetime.utcnow()
        )
        self.db.add(history)

        competitor.last_updated = datetime.utcnow()
        self.db.commit()

        logger.info(f"Updated dimension {dimension_id} for competitor {competitor_id}: {old_score} -> {score}")
        return True

    def _recalculate_overall_score(self, competitor) -> None:
        """Recalculate overall dimension score and sales priority."""
        scores = []
        weaknesses = 0

        for dim_id in DimensionID:
            score = getattr(competitor, f"dim_{dim_id.value}_score", None)
            if score is not None:
                scores.append(score)
                if score <= 2:
                    weaknesses += 1

        if scores:
            competitor.dim_overall_score = sum(scores) / len(scores)
        else:
            competitor.dim_overall_score = None

        # Update sales priority
        if competitor.threat_level == "High" and weaknesses > 0:
            competitor.dim_sales_priority = "High"
        elif competitor.threat_level == "Medium" or weaknesses > 2:
            competitor.dim_sales_priority = "Medium"
        else:
            competitor.dim_sales_priority = "Low"

    def get_dimension_history(
        self,
        competitor_id: int,
        dimension_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get dimension score change history."""
        from database import CompetitorDimensionHistory

        query = self.db.query(CompetitorDimensionHistory).filter(
            CompetitorDimensionHistory.competitor_id == competitor_id
        )

        if dimension_id:
            query = query.filter(CompetitorDimensionHistory.dimension_id == dimension_id)

        history = query.order_by(CompetitorDimensionHistory.changed_at.desc()).limit(limit).all()

        return [
            {
                "id": h.id,
                "dimension_id": h.dimension_id,
                "dimension_name": DIMENSION_METADATA.get(DimensionID(h.dimension_id), {}).get("name", h.dimension_id),
                "old_score": h.old_score,
                "old_score_label": SCORE_LABELS.get(h.old_score) if h.old_score else None,
                "new_score": h.new_score,
                "new_score_label": SCORE_LABELS.get(h.new_score),
                "evidence": h.evidence,
                "source": h.source,
                "confidence": h.confidence,
                "changed_by": h.changed_by,
                "changed_at": h.changed_at.isoformat()
            }
            for h in history
        ]

    def get_dimension_comparison(
        self,
        competitor_ids: List[int]
    ) -> Dict[str, Any]:
        """Compare multiple competitors across all dimensions."""
        from database import Competitor

        competitors = self.db.query(Competitor).filter(
            Competitor.id.in_(competitor_ids),
            Competitor.is_deleted == False
        ).all()

        result = {
            "competitors": [],
            "dimensions": list(DimensionID),
            "dimension_names": {d.value: DIMENSION_METADATA[d]["name"] for d in DimensionID}
        }

        for comp in competitors:
            comp_data = {
                "id": comp.id,
                "name": comp.name,
                "threat_level": comp.threat_level,
                "overall_score": comp.dim_overall_score,
                "dimensions": {}
            }

            for dim_id in DimensionID:
                score = getattr(comp, f"dim_{dim_id.value}_score", None)
                evidence = getattr(comp, f"dim_{dim_id.value}_evidence", None)
                comp_data["dimensions"][dim_id.value] = {
                    "score": score,
                    "score_label": SCORE_LABELS.get(score) if score else None,
                    "evidence": evidence
                }

            result["competitors"].append(comp_data)

        return result

    def get_talking_points(
        self,
        competitor_id: int,
        dimension_id: Optional[str] = None,
        point_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get talking points for sales conversations."""
        from database import TalkingPoint

        query = self.db.query(TalkingPoint).filter(
            TalkingPoint.competitor_id == competitor_id,
            TalkingPoint.is_active == True
        )

        if dimension_id:
            query = query.filter(TalkingPoint.dimension_id == dimension_id)
        if point_type:
            query = query.filter(TalkingPoint.point_type == point_type)

        points = query.order_by(
            TalkingPoint.effectiveness_score.desc().nullslast(),
            TalkingPoint.usage_count.desc()
        ).limit(limit).all()

        return [
            {
                "id": p.id,
                "competitor_id": p.competitor_id,
                "dimension_id": p.dimension_id,
                "dimension_name": DIMENSION_METADATA.get(DimensionID(p.dimension_id), {}).get("name"),
                "point_type": p.point_type,
                "content": p.content,
                "context": p.context,
                "effectiveness_score": p.effectiveness_score,
                "usage_count": p.usage_count,
                "created_by": p.created_by,
                "created_at": p.created_at.isoformat()
            }
            for p in points
        ]

    def create_talking_point(
        self,
        competitor_id: int,
        dimension_id: str,
        point_type: str,
        content: str,
        context: Optional[str],
        user_email: str
    ) -> int:
        """Create a new talking point."""
        from database import TalkingPoint

        if dimension_id not in [d.value for d in DimensionID]:
            raise ValueError(f"Invalid dimension_id: {dimension_id}")
        if point_type not in ["strength", "weakness", "objection", "counter"]:
            raise ValueError(f"Invalid point_type: {point_type}")

        point = TalkingPoint(
            competitor_id=competitor_id,
            dimension_id=dimension_id,
            point_type=point_type,
            content=content,
            context=context,
            created_by=user_email,
            created_at=datetime.utcnow()
        )

        self.db.add(point)
        self.db.commit()

        return point.id

    def update_talking_point_effectiveness(
        self,
        point_id: int,
        effectiveness_score: int
    ) -> bool:
        """Update effectiveness score for a talking point (from win/loss feedback)."""
        from database import TalkingPoint

        if not 1 <= effectiveness_score <= 5:
            raise ValueError("Effectiveness score must be 1-5")

        point = self.db.query(TalkingPoint).filter(TalkingPoint.id == point_id).first()
        if not point:
            return False

        point.effectiveness_score = effectiveness_score
        point.usage_count += 1
        self.db.commit()

        return True

    def get_news_by_dimension(
        self,
        dimension_id: str,
        competitor_id: Optional[int] = None,
        days: int = 30,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get news articles tagged with a specific dimension."""
        from database import DimensionNewsTag
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(days=days)

        query = self.db.query(DimensionNewsTag).filter(
            DimensionNewsTag.dimension_id == dimension_id,
            DimensionNewsTag.tagged_at >= cutoff
        )

        if competitor_id:
            query = query.filter(DimensionNewsTag.competitor_id == competitor_id)

        tags = query.order_by(DimensionNewsTag.tagged_at.desc()).limit(limit).all()

        return [
            {
                "id": t.id,
                "news_url": t.news_url,
                "news_title": t.news_title,
                "news_snippet": t.news_snippet,
                "competitor_id": t.competitor_id,
                "dimension_id": t.dimension_id,
                "dimension_name": DIMENSION_METADATA.get(DimensionID(t.dimension_id), {}).get("name"),
                "relevance_score": t.relevance_score,
                "sentiment": t.sentiment,
                "tagged_at": t.tagged_at.isoformat(),
                "tagged_by": t.tagged_by,
                "is_validated": t.is_validated
            }
            for t in tags
        ]

    def tag_news_with_dimension(
        self,
        news_url: str,
        news_title: str,
        competitor_id: int,
        dimension_id: str,
        relevance_score: float,
        tagged_by: str,
        news_snippet: Optional[str] = None,
        sentiment: Optional[str] = None
    ) -> int:
        """Tag a news article with a dimension."""
        from database import DimensionNewsTag

        if dimension_id not in [d.value for d in DimensionID]:
            raise ValueError(f"Invalid dimension_id: {dimension_id}")

        tag = DimensionNewsTag(
            news_url=news_url,
            news_title=news_title,
            news_snippet=news_snippet,
            competitor_id=competitor_id,
            dimension_id=dimension_id,
            relevance_score=relevance_score,
            sentiment=sentiment,
            tagged_by=tagged_by,
            tagged_at=datetime.utcnow()
        )

        self.db.add(tag)
        self.db.commit()

        return tag.id


# ============== Utility Functions ==============

def get_dimension_metadata(dimension_id: str) -> Optional[Dict[str, Any]]:
    """Get metadata for a specific dimension."""
    try:
        dim = DimensionID(dimension_id)
        return DIMENSION_METADATA.get(dim)
    except ValueError:
        return None


def get_score_label(score: int) -> str:
    """Get human-readable label for a score."""
    return SCORE_LABELS.get(score, "Unknown")


def calculate_dimension_match(
    text: str,
    dimension_id: str
) -> Tuple[bool, float]:
    """
    Check if text relates to a dimension based on keywords.
    Returns (is_match, confidence_score).
    """
    meta = get_dimension_metadata(dimension_id)
    if not meta:
        return False, 0.0

    text_lower = text.lower()
    keywords = meta.get("keywords", [])
    review_signals = meta.get("review_signals", [])

    all_signals = keywords + review_signals
    matches = sum(1 for signal in all_signals if signal.lower() in text_lower)

    if matches == 0:
        return False, 0.0

    confidence = min(matches / 3, 1.0)  # Cap at 1.0
    return True, confidence
