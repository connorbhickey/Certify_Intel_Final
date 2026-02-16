"""
Certify Intel v7.0 - Validation Agent
======================================

Agent specialized for data validation and confidence scoring using the
Admiralty Code framework.

Features:
- Validate competitor data fields
- Calculate confidence scores
- Identify low-confidence data needing verification
- Track data sources and corroboration
- Provide validation reports with citations

Admiralty Code Reference:
- Source Reliability: A-F scale
- Information Credibility: 1-6 scale
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from .base_agent import BaseAgent, AgentResponse, Citation

logger = logging.getLogger(__name__)


class ValidationAgent(BaseAgent):
    """
    Agent for data validation and confidence scoring.

    Capabilities:
    - Validate individual competitor fields
    - Calculate composite confidence scores
    - Identify data needing verification
    - Provide source attribution
    - Generate validation reports
    """

    def __init__(self, knowledge_base=None, vector_store=None, ai_router=None):
        super().__init__(
            agent_type="validation",
            ai_router=ai_router,
            vector_store=vector_store
        )
        self.knowledge_base = knowledge_base
        self.vector_store = vector_store
        self.ai_router = ai_router
        self._scorer = None
        self._initialize_scorer()

    def _initialize_scorer(self):
        """Initialize confidence scoring module."""
        try:
            from confidence_scoring import (
                calculate_confidence_score,
                SOURCE_TYPE_DEFAULTS,
                RELIABILITY_DESCRIPTIONS,
                CREDIBILITY_DESCRIPTIONS
            )
            self._scorer = calculate_confidence_score
            self._source_types = SOURCE_TYPE_DEFAULTS
            self._reliability_desc = RELIABILITY_DESCRIPTIONS
            self._credibility_desc = CREDIBILITY_DESCRIPTIONS
            logger.info("Confidence scoring initialized")
        except ImportError as e:
            logger.warning(f"Confidence scoring not available: {e}")
            self._scorer = None

    async def _get_knowledge_base_context(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Retrieve relevant documents from the knowledge base using RAG.

        Returns:
            Dict with context, citations, and metadata
        """
        if self.knowledge_base:
            try:
                filter_metadata = context.get("filter_metadata")
                result = await self.knowledge_base.get_context_for_query(
                    query=query,
                    max_chunks=5,
                    max_tokens=3000,
                    filter_metadata=filter_metadata
                )
                for cit in result.get("citations", []):
                    cit["source_type"] = "knowledge_base"
                return result
            except Exception as e:
                logger.warning(f"KB context retrieval failed: {e}")

        if self.vector_store:
            try:
                chunks = await self.vector_store.search(query, limit=5)
                context_text = "\n\n".join(c.get("content", "") for c in chunks)
                return {
                    "context": context_text,
                    "citations": [
                        {
                            "source_id": c.get("id", ""),
                            "source_type": "vector_store",
                            "content": c.get("content", "")[:200]
                        }
                        for c in chunks
                    ],
                    "chunks_found": len(chunks)
                }
            except Exception as e:
                logger.warning(f"Vector store search failed: {e}")

        return {"context": "", "citations": [], "chunks_found": 0}

    async def process(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """
        Process a validation query.

        Supported queries:
        - "Validate data for [competitor]"
        - "What's the confidence for [field]?"
        - "Show low confidence data"
        - "Verify [competitor] funding"
        - "Data quality report"

        Args:
            query: Natural language validation query
            context: Optional context with parameters:
                - competitor_id: Specific competitor to validate
                - field_name: Specific field to check
                - min_confidence: Threshold for filtering (0-100)

        Returns:
            AgentResponse with validation results and citations
        """
        start_time = datetime.utcnow()
        context = context or {}

        try:
            query_lower = query.lower()

            # Determine action
            if any(w in query_lower for w in ["low confidence", "needs verification", "unverified"]):
                return await self._get_low_confidence_data(context, start_time)
            elif any(w in query_lower for w in ["quality", "overview", "report"]):
                return await self._generate_quality_report(context, start_time)
            elif "competitor" in query_lower or context.get("competitor_id"):
                return await self._validate_competitor(context, start_time)
            else:
                return await self._generate_quality_report(context, start_time)

        except Exception as e:
            logger.error(f"Validation agent error: {e}")
            latency = (datetime.utcnow() - start_time).total_seconds() * 1000

            return AgentResponse(
                text=f"I encountered an error during validation: {str(e)}",
                citations=[],
                agent_type=self.agent_type,
                data={"error": str(e)},
                latency_ms=latency
            )

    async def _validate_competitor(
        self,
        context: Dict[str, Any],
        start_time: datetime
    ) -> AgentResponse:
        """Validate all data for a specific competitor."""
        citations = []
        competitor_id = context.get("competitor_id")

        db = None
        try:
            from database import SessionLocal, Competitor, DataSource

            db = SessionLocal()

            # Get competitor
            if competitor_id:
                competitor = db.query(Competitor).filter(Competitor.id == competitor_id).first()
            else:
                # Get first competitor for demo
                competitor = db.query(Competitor).first()

            if not competitor:
                return AgentResponse(
                    text="No competitor found to validate.",
                    citations=[],
                    agent_type=self.agent_type,
                    latency_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
                )

            # Get data sources for this competitor
            sources = db.query(DataSource).filter(
                DataSource.competitor_id == competitor.id
            ).all()

            # Build validation results
            parts = []
            parts.append(f"## Data Validation Report: {competitor.name}\n")

            # Key fields to validate
            fields_to_check = [
                ("name", competitor.name),
                ("website", getattr(competitor, "website", None)),
                ("headquarters", getattr(competitor, "headquarters", None)),
                ("estimated_customers", getattr(competitor, "estimated_customers", None)),
                ("funding_amount", getattr(competitor, "funding_amount", None)),
                ("employee_count", getattr(competitor, "employee_count", None)),
                ("target_market", getattr(competitor, "target_market", None)),
                ("threat_level", getattr(competitor, "threat_level", None)),
            ]

            # Calculate confidence for each field
            field_scores = []
            for field_name, value in fields_to_check:
                if value is not None:
                    # Find source for this field
                    field_source = next(
                        (s for s in sources if s.field_name == field_name),
                        None
                    )

                    if field_source and self._scorer:
                        result = self._scorer(
                            source_type=field_source.source_type or "unknown",
                            corroborating_sources=field_source.corroborating_count or 0,
                            data_age_days=self._get_age_days(field_source.last_verified)
                        )
                        score = result.score
                        level = result.level
                    else:
                        # Default scoring for fields without source
                        score = 50
                        level = "moderate"

                    field_scores.append({
                        "field": field_name,
                        "value": str(value)[:50],
                        "score": score,
                        "level": level
                    })

            # Summary
            avg_score = sum(f["score"] for f in field_scores) / len(field_scores) if field_scores else 0
            high_conf = len([f for f in field_scores if f["score"] >= 70])
            low_conf = len([f for f in field_scores if f["score"] < 50])

            parts.append("### Summary")
            parts.append(f"- **Average Confidence**: {avg_score:.0f}/100")
            parts.append(f"- **High Confidence Fields**: {high_conf}")
            parts.append(f"- **Low Confidence Fields**: {low_conf}")
            parts.append(f"- **Data Sources**: {len(sources)}")
            parts.append("")

            # Field breakdown
            parts.append("### Field Confidence Scores")
            for fs in sorted(field_scores, key=lambda x: x["score"]):
                icon = "✅" if fs["score"] >= 70 else "⚠️" if fs["score"] >= 50 else "❌"
                parts.append(f"- {icon} **{fs['field']}**: {fs['score']}/100 ({fs['level']})")

                citations.append(Citation(
                    source_id=f"field_{fs['field']}",
                    source_type="validation",
                    content=f"{fs['field']}: {fs['value']}",
                    confidence=fs["score"] / 100
                ))

            # Recommendations
            if low_conf > 0:
                parts.append("")
                parts.append("### Recommendations")
                parts.append(f"- Verify {low_conf} low-confidence field(s)")
                parts.append("- Add corroborating sources where possible")
                parts.append("- Update stale data (>30 days old)")

            latency = (datetime.utcnow() - start_time).total_seconds() * 1000

            return AgentResponse(
                text="\n".join(parts),
                citations=citations,
                agent_type=self.agent_type,
                data={
                    "competitor_id": competitor.id,
                    "competitor_name": competitor.name,
                    "avg_confidence": avg_score,
                    "field_scores": field_scores,
                    "sources_count": len(sources)
                },
                latency_ms=latency
            )

        except Exception as e:
            logger.error(f"Error validating competitor: {e}")
            raise
        finally:
            if db:
                db.close()

    async def _get_low_confidence_data(
        self,
        context: Dict[str, Any],
        start_time: datetime
    ) -> AgentResponse:
        """Get all data with low confidence scores."""
        citations = []
        min_confidence = context.get("min_confidence", 50)

        db = None
        try:
            from database import SessionLocal, Competitor, DataSource

            db = SessionLocal()

            # Get all data sources with low confidence
            sources = db.query(DataSource).filter(
                DataSource.confidence_score < min_confidence
            ).order_by(
                DataSource.confidence_score.asc()
            ).limit(20).all()

            parts = []
            parts.append("## Low Confidence Data Report\n")
            parts.append(f"Showing data with confidence below {min_confidence}/100.\n")

            if not sources:
                parts.append("No low-confidence data found.")
            else:
                parts.append(f"**Found {len(sources)} items needing verification:**\n")

                for source in sources:
                    competitor = db.query(Competitor).filter(
                        Competitor.id == source.competitor_id
                    ).first()
                    comp_name = competitor.name if competitor else "Unknown"

                    score = source.confidence_score or 0
                    icon = "❌" if score < 30 else "⚠️"

                    parts.append(f"- {icon} **{comp_name}** - `{source.field_name}`: {score}/100")
                    parts.append(f"  - Source: {source.source_type or 'unknown'}")
                    parts.append(f"  - Last verified: {source.last_verified or 'Never'}")

                    citations.append(Citation(
                        source_id=f"lowconf_{source.id}",
                        source_type="validation",
                        content=f"{comp_name}.{source.field_name}",
                        confidence=score / 100
                    ))

            latency = (datetime.utcnow() - start_time).total_seconds() * 1000

            return AgentResponse(
                text="\n".join(parts),
                citations=citations,
                agent_type=self.agent_type,
                data={
                    "low_confidence_count": len(sources),
                    "threshold": min_confidence
                },
                latency_ms=latency
            )

        except Exception as e:
            logger.error(f"Error getting low confidence data: {e}")
            raise
        finally:
            if db:
                db.close()

    async def _generate_quality_report(
        self,
        context: Dict[str, Any],
        start_time: datetime
    ) -> AgentResponse:
        """Generate overall data quality report."""
        citations = []

        db = None
        try:
            from database import SessionLocal, Competitor, DataSource

            db = SessionLocal()

            # Get stats
            total_competitors = db.query(Competitor).count()
            total_sources = db.query(DataSource).count()

            # Confidence distribution
            high_conf = db.query(DataSource).filter(DataSource.confidence_score >= 70).count()
            med_conf = db.query(DataSource).filter(
                DataSource.confidence_score >= 50,
                DataSource.confidence_score < 70
            ).count()
            low_conf = db.query(DataSource).filter(DataSource.confidence_score < 50).count()

            # Calculate average
            if total_sources > 0:
                from sqlalchemy import func
                avg_result = db.query(func.avg(DataSource.confidence_score)).scalar()
                avg_score = float(avg_result) if avg_result else 50.0
            else:
                avg_score = 0.0

            parts = []
            parts.append("## Data Quality Report\n")

            # Overview
            parts.append("### Overview")
            parts.append(f"- **Total Competitors**: {total_competitors}")
            parts.append(f"- **Total Data Sources**: {total_sources}")
            parts.append(f"- **Average Confidence**: {avg_score:.1f}/100")
            parts.append("")

            # Confidence distribution
            parts.append("### Confidence Distribution")
            if total_sources > 0:
                high_pct = high_conf / total_sources * 100
                med_pct = med_conf / total_sources * 100
                low_pct = low_conf / total_sources * 100
                parts.append(f"- High (70-100): {high_conf} ({high_pct:.1f}%)")
                parts.append(f"- Medium (50-69): {med_conf} ({med_pct:.1f}%)")
                parts.append(f"- Low (<50): {low_conf} ({low_pct:.1f}%)")
            else:
                parts.append("- High: 0")
                parts.append("- Medium: 0")
                parts.append("- Low: 0")
            parts.append("")

            # Quality grade
            if avg_score >= 80:
                grade = "A"
                grade_desc = "Excellent"
            elif avg_score >= 70:
                grade = "B"
                grade_desc = "Good"
            elif avg_score >= 60:
                grade = "C"
                grade_desc = "Acceptable"
            elif avg_score >= 50:
                grade = "D"
                grade_desc = "Needs Improvement"
            else:
                grade = "F"
                grade_desc = "Poor"

            parts.append(f"### Quality Grade: **{grade}** ({grade_desc})")
            parts.append("")

            # Recommendations
            parts.append("### Recommendations")
            if low_conf > 0:
                parts.append(f"1. Verify {low_conf} low-confidence data points")
            if avg_score < 70:
                parts.append("2. Add more corroborating sources")
            parts.append("3. Schedule regular data refresh")
            parts.append("4. Review stale data (>30 days)")

            # Add citations
            citations.append(Citation(
                source_id="quality_report",
                source_type="validation",
                content=f"Data quality grade: {grade}",
                confidence=avg_score / 100
            ))

            latency = (datetime.utcnow() - start_time).total_seconds() * 1000

            return AgentResponse(
                text="\n".join(parts),
                citations=citations,
                agent_type=self.agent_type,
                data={
                    "total_competitors": total_competitors,
                    "total_sources": total_sources,
                    "avg_confidence": avg_score,
                    "grade": grade,
                    "distribution": {
                        "high": high_conf,
                        "medium": med_conf,
                        "low": low_conf
                    }
                },
                latency_ms=latency
            )

        except Exception as e:
            logger.error(f"Error generating quality report: {e}")
            raise
        finally:
            if db:
                db.close()

    def _get_age_days(self, last_verified: Optional[datetime]) -> int:
        """Calculate age in days since last verification."""
        if not last_verified:
            return 365  # Assume very old if never verified
        delta = datetime.utcnow() - last_verified
        return delta.days

    # Convenience methods

    async def validate_field(
        self,
        competitor_id: int,
        field_name: str
    ) -> AgentResponse:
        """Validate a specific field."""
        return await self.process(
            f"Validate {field_name}",
            context={"competitor_id": competitor_id, "field_name": field_name}
        )

    async def get_quality_overview(self) -> AgentResponse:
        """Get overall data quality overview."""
        return await self.process("Data quality report")
