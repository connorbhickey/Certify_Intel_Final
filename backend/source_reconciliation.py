"""
Source Reconciliation Engine for Certify Intel v7.1

Merges Knowledge Base data with live/scraped data using temporal + authority scoring.
Handles conflict detection, resolution, and provides unified data context for agents.

Key Features:
- Authority-based source hierarchy (SEC > Client Upload > API > Scrape > News)
- Temporal freshness scoring with decay
- Automatic conflict detection (>20% difference flags for review)
- Unified reconciled context for agent consumption
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union
import logging

logger = logging.getLogger(__name__)


@dataclass
class SourceRecord:
    """Represents a single data source (KB or live)."""
    value: str
    source_type: str  # sec_filing, client_provided, kb_extraction, website_scrape, etc.
    source_id: int
    source_origin: str  # "kb" or "live"
    confidence: float = 0.0
    data_as_of_date: Optional[datetime] = None
    extracted_at: Optional[datetime] = None
    is_verified: bool = False
    document_id: Optional[str] = None  # For KB sources
    chunk_id: Optional[int] = None
    source_url: Optional[str] = None
    source_name: Optional[str] = None


@dataclass
class ReconciliationResult:
    """Result of reconciling multiple data sources for a single field."""
    field_name: str
    best_value: Optional[str]
    confidence_score: int  # 0-100
    confidence_level: str  # high, moderate, low
    sources_used: List[SourceRecord]
    conflicts: List[Dict[str, Any]]
    needs_review: bool
    reconciliation_method: str  # authority, freshness, agreement, manual
    notes: str = ""


@dataclass
class UnifiedContext:
    """Unified data context combining KB and live sources."""
    competitor_id: int
    competitor_name: str
    reconciled_fields: Dict[str, ReconciliationResult]
    kb_context: str  # Formatted KB context for RAG
    kb_citations: List[Dict[str, Any]]
    live_data: Dict[str, Any]  # Current database values
    conflicts_summary: List[Dict[str, Any]]
    freshness_summary: Dict[str, Any]
    total_sources: int
    kb_sources: int
    live_sources: int


class SourceReconciliationEngine:
    """
    Engine for reconciling data from multiple sources (KB and live).

    Uses a composite scoring algorithm:
    Score = Authority_Base - Freshness_Penalty * Confidence_Multiplier + Verification_Bonus

    Authority Hierarchy (highest to lowest):
    1. SEC Filing (100) - Legal documents, audited
    2. Client Provided (90) - User-uploaded KB docs
    3. API Verified (85) - Structured API data
    4. KLAS Report (80) - Industry analyst
    5. Manual Verified (75) - Human-verified
    6. KB Extraction (70) - AI-extracted from KB
    7. Discovery Scrape (60) - Discovery agent results
    8. Website Scrape (50) - Marketing content
    9. News Article (40) - Press/news
    10. Unknown (10) - Unattributed
    """

    # Authority hierarchy (highest to lowest)
    SOURCE_AUTHORITY = {
        "sec_filing": 100,
        "client_provided": 90,
        "api_verified": 85,
        "klas_report": 80,
        "definitive_hc": 80,
        "manual_verified": 75,
        "kb_extraction": 70,
        "discovery_scrape": 60,
        "website_scrape": 50,
        "news_article": 40,
        "linkedin_estimate": 35,
        "crunchbase": 35,
        "glassdoor": 30,
        "unknown": 10,
    }

    # Freshness decay rate (points lost per 30 days)
    FRESHNESS_DECAY_RATE = 5

    # Maximum freshness penalty
    MAX_FRESHNESS_PENALTY = 30

    # Conflict threshold (difference requiring human review)
    CONFLICT_THRESHOLD_NUMERIC = 0.20  # 20% difference for numeric values
    CONFLICT_THRESHOLD_STRING = 0.85  # 85% similarity required for strings

    def __init__(
        self,
        db_session=None,
        knowledge_base=None,
        vector_store=None
    ):
        """
        Initialize the reconciliation engine.

        Args:
            db_session: SQLAlchemy database session
            knowledge_base: KnowledgeBase instance for RAG context
            vector_store: VectorStore instance for semantic search
        """
        self.db = db_session
        self.kb = knowledge_base
        self.vector_store = vector_store

    async def reconcile_field(
        self,
        competitor_id: int,
        field_name: str,
        kb_sources: List[SourceRecord],
        live_sources: List[SourceRecord]
    ) -> ReconciliationResult:
        """
        Reconcile a single field from multiple sources.

        Algorithm:
        1. Score each source using authority + freshness + confidence
        2. Sort by score (highest first)
        3. Check for conflicts between top sources
        4. Return best value with conflict flags

        Args:
            competitor_id: ID of the competitor
            field_name: Name of the field (e.g., "customer_count")
            kb_sources: List of KB extraction sources
            live_sources: List of live/scraped sources

        Returns:
            ReconciliationResult with best value and conflict information
        """
        all_sources = []

        # Score KB sources
        for source in kb_sources:
            score = self._calculate_source_score(source)
            source.confidence = score
            all_sources.append(source)

        # Score live sources
        for source in live_sources:
            score = self._calculate_source_score(source)
            source.confidence = score
            all_sources.append(source)

        # Sort by score (highest first)
        all_sources.sort(key=lambda x: x.confidence, reverse=True)

        if not all_sources:
            return ReconciliationResult(
                field_name=field_name,
                best_value=None,
                confidence_score=0,
                confidence_level="low",
                sources_used=[],
                conflicts=[],
                needs_review=True,
                reconciliation_method="none",
                notes="No sources available for this field"
            )

        # Get best source
        best = all_sources[0]

        # Check for conflicts with other high-scoring sources
        conflicts = []
        for source in all_sources[1:]:
            # Only check sources within 20% of top score
            if source.confidence >= best.confidence * 0.8:
                is_conflict, diff = self._check_conflict(best.value, source.value)
                if is_conflict:
                    conflicts.append({
                        "source": {
                            "type": source.source_type,
                            "origin": source.source_origin,
                            "value": source.value,
                            "score": source.confidence,
                            "date": source.data_as_of_date.isoformat() if source.data_as_of_date else None
                        },
                        "best_source": {
                            "type": best.source_type,
                            "origin": best.source_origin,
                            "value": best.value,
                            "score": best.confidence
                        },
                        "difference": diff,
                        "difference_type": "numeric" if isinstance(diff, float) else "string"
                    })

        # Determine if human review needed
        needs_review = len(conflicts) > 0 and any(
            c["difference"] > self.CONFLICT_THRESHOLD_NUMERIC
            if c["difference_type"] == "numeric"
            else c["difference"] < self.CONFLICT_THRESHOLD_STRING
            for c in conflicts
        )

        # Determine confidence level
        confidence_score = int(best.confidence)
        if confidence_score >= 70:
            confidence_level = "high"
        elif confidence_score >= 40:
            confidence_level = "moderate"
        else:
            confidence_level = "low"

        # Determine reconciliation method
        if best.source_type in ["sec_filing", "client_provided", "api_verified"]:
            method = "authority"
        elif best.is_verified:
            method = "manual"
        elif len(all_sources) > 1 and all(
            self._values_match(best.value, s.value) for s in all_sources[:3]
        ):
            method = "agreement"
        else:
            method = "freshness"

        return ReconciliationResult(
            field_name=field_name,
            best_value=best.value,
            confidence_score=confidence_score,
            confidence_level=confidence_level,
            sources_used=all_sources[:5],  # Top 5 sources
            conflicts=conflicts,
            needs_review=needs_review,
            reconciliation_method=method,
            notes=f"Selected from {len(all_sources)} sources"
        )

    async def reconcile_all_fields(
        self,
        competitor_id: int,
        kb_extractions: List[Dict[str, Any]],
        live_data_sources: List[Dict[str, Any]],
        fields: Optional[List[str]] = None
    ) -> Dict[str, ReconciliationResult]:
        """
        Reconcile all fields for a competitor.

        Args:
            competitor_id: ID of the competitor
            kb_extractions: List of KB extraction records
            live_data_sources: List of DataSource records
            fields: Optional list of specific fields to reconcile

        Returns:
            Dict mapping field names to ReconciliationResult
        """
        # Group sources by field
        kb_by_field: Dict[str, List[SourceRecord]] = {}
        live_by_field: Dict[str, List[SourceRecord]] = {}

        for ext in kb_extractions:
            field = ext.get("field_name")
            if fields and field not in fields:
                continue

            source = SourceRecord(
                value=ext.get("extracted_value", ""),
                source_type="kb_extraction",
                source_id=ext.get("id", 0),
                source_origin="kb",
                data_as_of_date=ext.get("data_as_of_date"),
                is_verified=ext.get("status") == "verified",
                document_id=ext.get("document_id"),
                chunk_id=ext.get("chunk_id")
            )

            if field not in kb_by_field:
                kb_by_field[field] = []
            kb_by_field[field].append(source)

        for ds in live_data_sources:
            field = ds.get("field_name")
            if fields and field not in fields:
                continue

            source = SourceRecord(
                value=ds.get("current_value", ""),
                source_type=ds.get("source_type", "unknown"),
                source_id=ds.get("id", 0),
                source_origin="live",
                data_as_of_date=ds.get("data_as_of_date"),
                extracted_at=ds.get("extracted_at"),
                is_verified=ds.get("is_verified", False),
                source_url=ds.get("source_url"),
                source_name=ds.get("source_name")
            )

            if field not in live_by_field:
                live_by_field[field] = []
            live_by_field[field].append(source)

        # Get all unique fields
        all_fields = set(kb_by_field.keys()) | set(live_by_field.keys())

        # Reconcile each field
        results = {}
        for field in all_fields:
            kb_sources = kb_by_field.get(field, [])
            live_sources = live_by_field.get(field, [])

            result = await self.reconcile_field(
                competitor_id=competitor_id,
                field_name=field,
                kb_sources=kb_sources,
                live_sources=live_sources
            )
            results[field] = result

        return results

    async def get_unified_context(
        self,
        competitor_id: int,
        competitor_name: str,
        query: Optional[str] = None,
        fields: Optional[List[str]] = None
    ) -> UnifiedContext:
        """
        Get unified context combining KB and live data for agent consumption.

        This is the main method agents should use instead of separate KB/database queries.

        Args:
            competitor_id: ID of the competitor
            competitor_name: Name of the competitor
            query: Optional query for KB semantic search
            fields: Optional list of specific fields to include

        Returns:
            UnifiedContext with reconciled data and KB context
        """
        # Get KB context via semantic search
        kb_context = ""
        kb_citations = []

        if self.kb and query:
            try:
                kb_result = await self._get_kb_context_async(
                    query=query,
                    competitor_filter={"competitor": competitor_name}
                )
                kb_context = kb_result.get("context", "")
                kb_citations = kb_result.get("citations", [])
            except Exception as e:
                logger.warning(f"Failed to get KB context: {e}")

        # Get KB extractions from database
        kb_extractions = await self._get_kb_extractions(competitor_id)

        # Get live data sources from database
        live_sources = await self._get_live_sources(competitor_id)

        # Get current competitor data
        live_data = await self._get_competitor_data(competitor_id)

        # Reconcile all fields
        reconciled = await self.reconcile_all_fields(
            competitor_id=competitor_id,
            kb_extractions=kb_extractions,
            live_data_sources=live_sources,
            fields=fields
        )

        # Build conflicts summary
        conflicts_summary = []
        for field, result in reconciled.items():
            if result.conflicts:
                conflicts_summary.append({
                    "field": field,
                    "best_value": result.best_value,
                    "conflicts": result.conflicts,
                    "needs_review": result.needs_review
                })

        # Build freshness summary
        freshness_summary = {
            "oldest_kb_date": None,
            "newest_kb_date": None,
            "oldest_live_date": None,
            "newest_live_date": None,
            "stale_fields": []
        }

        for field, result in reconciled.items():
            for source in result.sources_used:
                date = source.data_as_of_date or source.extracted_at
                if date:
                    if source.source_origin == "kb":
                        if not freshness_summary["oldest_kb_date"] or date < freshness_summary["oldest_kb_date"]:
                            freshness_summary["oldest_kb_date"] = date
                        if not freshness_summary["newest_kb_date"] or date > freshness_summary["newest_kb_date"]:
                            freshness_summary["newest_kb_date"] = date
                    else:
                        if not freshness_summary["oldest_live_date"] or date < freshness_summary["oldest_live_date"]:
                            freshness_summary["oldest_live_date"] = date
                        if not freshness_summary["newest_live_date"] or date > freshness_summary["newest_live_date"]:
                            freshness_summary["newest_live_date"] = date

                    # Check for stale data (> 90 days old)
                    if date < datetime.utcnow() - timedelta(days=90):
                        freshness_summary["stale_fields"].append(field)

        return UnifiedContext(
            competitor_id=competitor_id,
            competitor_name=competitor_name,
            reconciled_fields=reconciled,
            kb_context=kb_context,
            kb_citations=kb_citations,
            live_data=live_data,
            conflicts_summary=conflicts_summary,
            freshness_summary=freshness_summary,
            total_sources=len(kb_extractions) + len(live_sources),
            kb_sources=len(kb_extractions),
            live_sources=len(live_sources)
        )

    def _calculate_source_score(self, source: SourceRecord) -> float:
        """
        Calculate composite source score.

        Score = Authority_Base - Freshness_Penalty * Confidence_Multiplier + Verification_Bonus
        """
        # Base authority score (0-100)
        authority = self.SOURCE_AUTHORITY.get(source.source_type, 10)

        # Freshness penalty
        reference_date = source.data_as_of_date or source.extracted_at or datetime.utcnow()
        days_old = (datetime.utcnow() - reference_date).days
        freshness_penalty = min(
            (days_old // 30) * self.FRESHNESS_DECAY_RATE,
            self.MAX_FRESHNESS_PENALTY
        )

        # Start with authority minus freshness penalty
        score = authority - freshness_penalty

        # Confidence multiplier (0.5-1.0 based on original confidence if available)
        if source.confidence > 0:
            confidence_multiplier = 0.5 + (source.confidence / 200)  # Scale 0-100 to 0.5-1.0
            score *= confidence_multiplier

        # Verification bonus
        if source.is_verified:
            score += 10

        return max(0, min(100, score))

    def _check_conflict(
        self,
        value1: str,
        value2: str
    ) -> Tuple[bool, Union[float, str]]:
        """
        Check if two values represent conflicting data.

        Returns:
            Tuple of (is_conflict, difference_measure)
        """
        # Try numeric comparison
        num1 = self._extract_number(value1)
        num2 = self._extract_number(value2)

        if num1 is not None and num2 is not None:
            # Numeric comparison
            if max(num1, num2) == 0:
                return num1 != num2, 1.0 if num1 != num2 else 0.0

            diff = abs(num1 - num2) / max(num1, num2)
            return diff > self.CONFLICT_THRESHOLD_NUMERIC, diff

        # String comparison using simple similarity
        similarity = self._string_similarity(value1, value2)
        return similarity < self.CONFLICT_THRESHOLD_STRING, similarity

    def _values_match(self, value1: str, value2: str) -> bool:
        """Check if two values are essentially the same."""
        is_conflict, _ = self._check_conflict(value1, value2)
        return not is_conflict

    def _extract_number(self, value: str) -> Optional[float]:
        """Extract numeric value from string."""
        if not value:
            return None

        # Remove common formatting
        cleaned = re.sub(r'[,$%+]', '', str(value).strip())

        # Handle ranges (take midpoint)
        range_match = re.match(r'(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)', cleaned)
        if range_match:
            low, high = float(range_match.group(1)), float(range_match.group(2))
            return (low + high) / 2

        # Handle suffixes (K, M, B)
        suffix_match = re.match(r'(\d+(?:\.\d+)?)\s*([KMB])', cleaned, re.IGNORECASE)
        if suffix_match:
            num = float(suffix_match.group(1))
            suffix = suffix_match.group(2).upper()
            multipliers = {'K': 1_000, 'M': 1_000_000, 'B': 1_000_000_000}
            return num * multipliers.get(suffix, 1)

        # Try direct conversion
        try:
            return float(cleaned)
        except ValueError:
            return None

    def _string_similarity(self, s1: str, s2: str) -> float:
        """Calculate simple string similarity (0-1)."""
        if not s1 or not s2:
            return 0.0

        s1_lower = s1.lower().strip()
        s2_lower = s2.lower().strip()

        if s1_lower == s2_lower:
            return 1.0

        # Simple word overlap similarity
        words1 = set(s1_lower.split())
        words2 = set(s2_lower.split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    async def _get_kb_context_async(
        self,
        query: str,
        competitor_filter: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Get KB context via semantic search."""
        if not self.kb:
            return {"context": "", "citations": []}

        try:
            # Try using the knowledge base's get_context_for_query method
            if hasattr(self.kb, 'get_context_for_query'):
                return self.kb.get_context_for_query(
                    query=query,
                    max_chunks=5,
                    max_tokens=3000,
                    metadata_filter=competitor_filter
                )
        except Exception as e:
            logger.warning(f"KB context retrieval failed: {e}")

        return {"context": "", "citations": []}

    async def _get_kb_extractions(self, competitor_id: int) -> List[Dict[str, Any]]:
        """Get KB extractions for a competitor from database."""
        if not self.db:
            return []

        try:
            from database import KBDataExtraction
            from sqlalchemy import select

            # Use sync query since database.py uses sync SQLAlchemy
            extractions = self.db.query(KBDataExtraction).filter(
                KBDataExtraction.competitor_id == competitor_id,
                KBDataExtraction.status != "rejected"
            ).all()

            return [
                {
                    "id": e.id,
                    "document_id": e.document_id,
                    "chunk_id": e.chunk_id,
                    "field_name": e.field_name,
                    "extracted_value": e.extracted_value,
                    "extraction_confidence": e.extraction_confidence,
                    "data_as_of_date": e.data_as_of_date,
                    "document_date": e.document_date,
                    "status": e.status
                }
                for e in extractions
            ]
        except Exception as e:
            logger.warning(f"Failed to get KB extractions: {e}")
            return []

    async def _get_live_sources(self, competitor_id: int) -> List[Dict[str, Any]]:
        """Get live data sources for a competitor from database."""
        if not self.db:
            return []

        try:
            from database import DataSource

            sources = self.db.query(DataSource).filter(
                DataSource.competitor_id == competitor_id
            ).all()

            return [
                {
                    "id": s.id,
                    "field_name": s.field_name,
                    "current_value": s.current_value,
                    "source_type": s.source_type,
                    "source_url": s.source_url,
                    "source_name": s.source_name,
                    "data_as_of_date": s.data_as_of_date,
                    "extracted_at": s.extracted_at,
                    "is_verified": s.is_verified,
                    "confidence_score": s.confidence_score
                }
                for s in sources
            ]
        except Exception as e:
            logger.warning(f"Failed to get live sources: {e}")
            return []

    async def _get_competitor_data(self, competitor_id: int) -> Dict[str, Any]:
        """Get current competitor data from database."""
        if not self.db:
            return {}

        try:
            from database import Competitor

            comp = self.db.query(Competitor).filter(
                Competitor.id == competitor_id
            ).first()

            if not comp:
                return {}

            # Return key fields
            return {
                "id": comp.id,
                "name": comp.name,
                "website": comp.website,
                "headquarters": comp.headquarters,
                "employee_count": comp.employee_count,
                "founded_year": comp.founded_year,
                "total_funding": comp.total_funding,
                "annual_revenue": comp.annual_revenue,
                "customer_count": comp.customer_count,
                "threat_level": comp.threat_level,
                "last_updated": comp.last_updated.isoformat() if comp.last_updated else None
            }
        except Exception as e:
            logger.warning(f"Failed to get competitor data: {e}")
            return {}


# Convenience function for quick reconciliation
async def reconcile_competitor_data(
    competitor_id: int,
    competitor_name: str,
    db_session,
    knowledge_base=None,
    query: Optional[str] = None
) -> UnifiedContext:
    """
    Convenience function to get unified context for a competitor.

    Args:
        competitor_id: ID of the competitor
        competitor_name: Name of the competitor
        db_session: SQLAlchemy database session
        knowledge_base: Optional KnowledgeBase instance
        query: Optional query for KB semantic search

    Returns:
        UnifiedContext with reconciled data
    """
    engine = SourceReconciliationEngine(
        db_session=db_session,
        knowledge_base=knowledge_base
    )

    return await engine.get_unified_context(
        competitor_id=competitor_id,
        competitor_name=competitor_name,
        query=query
    )
