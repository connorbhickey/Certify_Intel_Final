"""
Certify Intel v7.0 - Discovery Agent
=====================================

AI-powered competitor discovery with 4-stage pipeline.

This agent wraps the existing AIDiscoveryEngine to integrate with
the LangGraph orchestrator.

Stages:
1. Search: Gemini with Google Search grounding
2. Scrape: Firecrawl/Playwright for deep content
3. Qualify: AI evaluation against user criteria
4. Analyze: Threat assessment and scoring

Features:
- Integrates with existing discovery_engine.py
- Proper cost tracking through AI router
- Citation validation for all sources
- Deduplication against known competitors
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime

from .base_agent import BaseAgent, AgentResponse, Citation

logger = logging.getLogger(__name__)


@dataclass
class DiscoveryRequest:
    """Request parameters for discovery."""
    target_segments: List[str] = field(default_factory=list)
    required_capabilities: List[str] = field(default_factory=list)
    geography: List[str] = field(default_factory=list)
    funding_stages: List[str] = field(default_factory=list)
    min_employees: int = 0
    max_employees: int = 0
    exclusions: List[str] = field(default_factory=list)
    include_keywords: List[str] = field(default_factory=list)
    exclude_keywords: List[str] = field(default_factory=list)
    max_candidates: int = 10


class DiscoveryAgent(BaseAgent):
    """
    Discovery Agent - AI-powered competitor discovery.

    This agent handles:
    - Finding new competitors based on criteria
    - Qualifying candidates against user requirements
    - Threat analysis of discovered companies
    - Deduplication against existing database

    CRITICAL: All discovered candidates include sources and citations.

    v7.0 Enhancement: Integrated with KnowledgeBase RAG pipeline for:
    - Market research and trend context
    - Industry report insights
    - Historical competitive intelligence
    """

    def __init__(
        self,
        knowledge_base=None,
        vector_store=None,
        db_session=None,
        ai_router=None,
        min_similarity: float = 0.5
    ):
        super().__init__(
            agent_type="discovery",
            ai_router=ai_router,
            vector_store=vector_store
        )
        self.knowledge_base = knowledge_base
        self.vector_store = vector_store
        self.db_session = db_session
        self.ai_router = ai_router
        self.min_similarity = min_similarity
        self._discovery_engine = None

    def _get_discovery_engine(self):
        """Lazy-load the discovery engine."""
        if self._discovery_engine is None:
            try:
                from discovery_engine import AIDiscoveryEngine
                self._discovery_engine = AIDiscoveryEngine()
                logger.info("AIDiscoveryEngine initialized")
            except ImportError as e:
                logger.error(f"Failed to import AIDiscoveryEngine: {e}")
                raise
        return self._discovery_engine

    async def _get_knowledge_base_context(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Retrieve relevant market intelligence from knowledge base.

        This provides context for discovery including:
        - Market trends and industry reports
        - Competitive landscape insights
        - Technology stack information
        - Funding and M&A activity

        Returns:
            Dict with context, citations, and metadata
        """
        # Try KnowledgeBase first (preferred)
        if self.knowledge_base:
            try:
                filter_metadata = context.get("filter_metadata")

                result = await self.knowledge_base.get_context_for_query(
                    query=query,
                    max_chunks=5,
                    max_tokens=2000,  # Smaller for discovery
                    filter_metadata=filter_metadata
                )

                # Add source_type to citations
                for cit in result.get("citations", []):
                    cit["source_type"] = "knowledge_base"

                logger.info(f"KB context retrieved: {result.get('chunks_used', 0)} chunks")
                return result

            except Exception as e:
                logger.warning(f"KnowledgeBase retrieval failed: {e}")

        # Fallback to direct vector_store access
        if self.vector_store:
            try:
                results = await self.vector_store.search(
                    query=query,
                    limit=5,
                    min_similarity=self.min_similarity
                )

                if not results:
                    return {"context": "", "citations": [], "chunks_used": 0}

                # Build context manually
                context_parts = []
                citations = []

                for i, r in enumerate(results):
                    context_parts.append(f"[Source {i+1}]\n{r.content}")
                    citations.append({
                        "source_number": i + 1,
                        "document_id": r.document_id,
                        "chunk_id": str(r.chunk_id),
                        "section": r.metadata.get("section", "Unknown"),
                        "content_preview": r.content[:150] if r.content else "",
                        "similarity_score": round(r.similarity, 3),
                        "source_type": "knowledge_base"
                    })

                return {
                    "context": "\n\n".join(context_parts),
                    "citations": citations,
                    "chunks_used": len(results),
                    "total_tokens": sum(len(r.content) // 4 for r in results)
                }

            except Exception as e:
                logger.warning(f"VectorStore search failed: {e}")

        # No KB available - return empty context (discovery can still run)
        return {"context": "", "citations": [], "chunks_used": 0}

    async def process(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """
        Process a discovery request.

        Args:
            query: Natural language query (e.g., "Find telehealth competitors")
            context: Optional context with criteria, known_competitors, etc.

        Returns:
            AgentResponse with discovered candidates and citations

        v7.0 Enhancement:
            Now retrieves KB context for market intelligence before discovery.
        """
        context = context or {}
        start_time = datetime.utcnow()

        try:
            # Step 0: Get internal company context (Certify Health)
            internal_context = await self._get_internal_company_context()

            # Step 1: Get KB context for market intelligence
            kb_query = f"market trends competitors {query}"
            kb_result = await self._get_knowledge_base_context(kb_query, context)
            kb_context = kb_result.get("context", "")
            kb_citations = kb_result.get("citations", [])

            # Include internal company context for understanding our market position
            if internal_context.get("has_internal_data"):
                kb_context = internal_context.get("context", "") + "\n\n" + kb_context
                kb_citations = internal_context.get("citations", []) + kb_citations

            # Step 2: Parse the request
            request = self._parse_request(query, context)

            # Step 3: Get existing competitors for deduplication
            known_competitors = await self._get_known_competitors()

            # Step 4: Run discovery with KB context
            result = await self._run_discovery(request, known_competitors, kb_context)

            # Step 5: Build response with KB citations included
            return self._build_response(result, start_time, kb_citations)

        except Exception as e:
            logger.error(f"Discovery agent error: {e}", exc_info=True)
            return AgentResponse(
                text=f"Discovery failed: {str(e)}",
                citations=[],
                agent_type=self.agent_type,
                cost_usd=0.0,
                tokens_used=0,
                latency_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                metadata={"status": "error", "error": str(e)}
            )

    def _parse_request(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> DiscoveryRequest:
        """Parse query and context into a DiscoveryRequest."""
        query_lower = query.lower()

        # Extract from context if provided
        request = DiscoveryRequest(
            target_segments=context.get("target_segments", []),
            required_capabilities=context.get("required_capabilities", []),
            geography=context.get("geography", []),
            funding_stages=context.get("funding_stages", []),
            min_employees=context.get("min_employees", 0),
            max_employees=context.get("max_employees", 0),
            exclusions=context.get("exclusions", []),
            include_keywords=context.get("include_keywords", []),
            exclude_keywords=context.get("exclude_keywords", []),
            max_candidates=context.get("max_candidates", 10)
        )

        # Parse query for additional hints
        segment_keywords = {
            "telehealth": "telehealth",
            "hospital": "hospital",
            "ambulatory": "ambulatory",
            "urgent care": "urgent_care",
            "behavioral": "behavioral",
            "dental": "dental_dso",
            "laboratory": "lab",
            "long-term care": "ltc"
        }

        for keyword, segment in segment_keywords.items():
            if keyword in query_lower and segment not in request.target_segments:
                request.target_segments.append(segment)

        capability_keywords = {
            "patient experience": "pxp",
            "practice management": "pms",
            "revenue cycle": "rcm",
            "ehr": "ehr",
            "emr": "ehr",
            "payments": "payments",
            "biometric": "biometric",
            "ai scribe": "ai_scribe"
        }

        for keyword, cap in capability_keywords.items():
            if keyword in query_lower and cap not in request.required_capabilities:
                request.required_capabilities.append(cap)

        return request

    async def _get_known_competitors(self) -> List[Dict[str, Any]]:
        """Get list of known competitors for deduplication."""
        try:
            from database import SessionLocal, Competitor
            db = SessionLocal()

            competitors = db.query(Competitor).all()
            result = [
                {"name": c.name, "website": c.website}
                for c in competitors
            ]

            db.close()
            return result

        except Exception as e:
            logger.warning(f"Failed to get known competitors: {e}")
            return []

    async def _run_discovery(
        self,
        request: DiscoveryRequest,
        known_competitors: List[Dict[str, Any]],
        kb_context: str = ""
    ) -> Dict[str, Any]:
        """
        Run the discovery pipeline.

        Args:
            request: Discovery request parameters
            known_competitors: List of known competitors for deduplication
            kb_context: Market intelligence context from knowledge base

        Returns:
            Discovery results with candidates
        """
        try:
            from discovery_engine import QualificationCriteria

            engine = self._get_discovery_engine()

            # Set known competitors for deduplication
            engine.set_known_competitors(known_competitors)

            # Build qualification criteria
            criteria = QualificationCriteria(
                target_segments=request.target_segments,
                required_capabilities=request.required_capabilities,
                geography=request.geography,
                funding_stages=request.funding_stages,
                company_size={
                    "min_employees": request.min_employees,
                    "max_employees": request.max_employees
                } if request.min_employees or request.max_employees else {},
                exclusions=request.exclusions,
                custom_keywords={
                    "include": request.include_keywords,
                    "exclude": request.exclude_keywords
                }
            )

            # Run discovery with KB context for enhanced qualification
            result = await engine.run_discovery(
                criteria=criteria,
                max_candidates=request.max_candidates,
                timeout_seconds=600,  # 10 minute timeout
                market_context=kb_context  # Pass KB context
            )

            # Add KB context info to result
            result["kb_context_used"] = bool(kb_context)

            return result

        except ImportError:
            # Fallback: simple mock response
            logger.warning("Discovery engine not available, using mock")
            return {
                "status": "mock",
                "candidates": [],
                "total_found": 0,
                "stages_run": [],
                "processing_time_ms": 0,
                "message": "Discovery engine not available",
                "kb_context_used": bool(kb_context)
            }

    def _build_response(
        self,
        result: Dict[str, Any],
        start_time: datetime,
        kb_citations: List[Dict[str, Any]] = None
    ) -> AgentResponse:
        """
        Build the AgentResponse from discovery results.

        Args:
            result: Discovery pipeline results
            start_time: When processing started
            kb_citations: Citations from knowledge base context

        Returns:
            AgentResponse with text, citations, and metadata
        """
        kb_citations = kb_citations or []
        candidates = result.get("candidates", [])
        status = result.get("status", "unknown")

        # Build response text
        if not candidates:
            if status == "error":
                text = f"Discovery encountered an error: {result.get('error', 'Unknown error')}"
            else:
                text = ("No new competitors were discovered matching your criteria. "
                        "Try broadening your search parameters.")
        else:
            text = self._format_discovery_results(candidates)

        # Build citations from candidates
        citations = []

        # Add KB citations first (market intelligence sources)
        for kb_cit in kb_citations:
            citations.append(Citation(
                source_id=kb_cit.get("document_id", "kb"),
                source_type="knowledge_base",
                content=kb_cit.get("content_preview", "Market intelligence"),
                confidence=kb_cit.get("similarity_score", 0.7)
            ))

        # Add candidate citations
        for candidate in candidates:
            if isinstance(candidate, dict):
                name = candidate.get("name", "Unknown")
                url = candidate.get("url", "")
                source = candidate.get("search_source", "discovery")
            else:
                # Handle dataclass
                name = getattr(candidate, "name", "Unknown")
                url = getattr(candidate, "url", "")
                source = getattr(candidate, "search_source", "discovery")

            citations.append(Citation(
                source_id=url or name,
                source_type="discovered_competitor",
                content=f"Discovered via {source}",
                confidence=0.8
            ))

        latency = (datetime.utcnow() - start_time).total_seconds() * 1000

        return AgentResponse(
            text=text,
            citations=citations,
            agent_type=self.agent_type,
            cost_usd=result.get("total_cost_usd", 0.0),
            tokens_used=result.get("total_tokens", 0),
            latency_ms=latency,
            metadata={
                "status": status,
                "total_found": len(candidates),
                "stages_run": result.get("stages_run", []),
                "kb_context_used": result.get("kb_context_used", False),
                "kb_citations_count": len(kb_citations),
                "candidates": [
                    asdict(c) if hasattr(c, "__dataclass_fields__") else c
                    for c in candidates
                ]
            }
        )

    def _format_discovery_results(self, candidates: List) -> str:
        """Format discovery results as readable text."""
        parts = [
            "## Discovery Results\n",
            f"Found **{len(candidates)}** new competitor candidates:\n"
        ]

        for i, candidate in enumerate(candidates, 1):
            if isinstance(candidate, dict):
                name = candidate.get("name", "Unknown")
                url = candidate.get("url", "")
                threat = candidate.get("threat_level", "Unknown")
                score = candidate.get("qualification_score", 0)
                summary = candidate.get("ai_summary", "")
            else:
                name = getattr(candidate, "name", "Unknown")
                url = getattr(candidate, "url", "")
                threat = getattr(candidate, "threat_level", "Unknown")
                score = getattr(candidate, "qualification_score", 0)
                summary = getattr(candidate, "ai_summary", "")

            parts.append(f"### {i}. {name}")
            parts.append(f"- **URL:** {url}")
            parts.append(f"- **Threat Level:** {threat}")
            parts.append(f"- **Qualification Score:** {score}/100")

            if summary:
                parts.append(f"- **Summary:** {summary[:200]}...")

            parts.append("[Source: Discovery Pipeline]\n")

        parts.append("\n### Next Steps")
        parts.append("1. Review candidates and select those to add to tracking")
        parts.append("2. Run deep analysis on high-priority candidates")
        parts.append("3. Generate battlecards for new competitors")

        return "\n".join(parts)

    async def add_candidates_to_database(
        self,
        candidates: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Add discovered candidates to the competitor database.

        Args:
            candidates: List of candidate dictionaries

        Returns:
            Dictionary with added/skipped counts
        """
        try:
            from database import SessionLocal, Competitor
            db = SessionLocal()

            added = 0
            skipped = 0

            for candidate in candidates:
                name = candidate.get("name", "")
                url = candidate.get("url", "")

                if not name:
                    skipped += 1
                    continue

                # Check for duplicates
                existing = db.query(Competitor).filter(
                    (Competitor.name.ilike(f"%{name}%")) |
                    (Competitor.website == url)
                ).first()

                if existing:
                    skipped += 1
                    continue

                # Create new competitor
                new_comp = Competitor(
                    name=name,
                    website=url,
                    description=candidate.get("ai_summary", ""),
                    threat_level=self._threat_to_score(candidate.get("threat_level", "Low")),
                    discovery_source="ai_discovery",
                    created_at=datetime.utcnow()
                )

                db.add(new_comp)
                added += 1

            db.commit()
            db.close()

            return {
                "status": "success",
                "added": added,
                "skipped": skipped,
                "total": len(candidates)
            }

        except Exception as e:
            logger.error(f"Failed to add candidates: {e}")
            return {
                "status": "error",
                "error": str(e),
                "added": 0,
                "skipped": len(candidates)
            }

    def _threat_to_score(self, threat_level: str) -> int:
        """Convert threat level string to numeric score."""
        mapping = {
            "critical": 10,
            "high": 8,
            "medium": 5,
            "low": 3,
            "unknown": 1
        }
        return mapping.get(threat_level.lower(), 1)


# CLI testing
if __name__ == "__main__":
    import asyncio

    async def test():
        agent = DiscoveryAgent()

        # Test basic discovery
        response = await agent.process(
            "Find telehealth competitors with patient experience platforms",
            context={
                "target_segments": ["telehealth"],
                "required_capabilities": ["pxp"],
                "max_candidates": 5
            }
        )

        print("=== Discovery Test ===")
        print(f"Status: {response.metadata.get('status')}")
        print(f"Found: {response.metadata.get('total_found')} candidates")
        print(f"Response: {response.text[:500]}...")

    asyncio.run(test())
