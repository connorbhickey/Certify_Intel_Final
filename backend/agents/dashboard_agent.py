"""
Certify Intel v7.0 - Dashboard Agent
====================================

Executive summary generation, threat analysis, and key metrics.

Features:
- Pulls data from knowledge base (RAG) and competitor database
- Generates executive summaries with proper citations
- Refuses to hallucinate when no data is available
- Tracks costs via AI router
- Integrates with KnowledgeBase for semantic search

Usage:
    from knowledge_base import KnowledgeBase
    from vector_store import VectorStore

    vector_store = VectorStore()
    kb = KnowledgeBase(vector_store=vector_store)
    agent = DashboardAgent(knowledge_base=kb)

    response = await agent.process(
        query="What are the top threats?",
        context={"competitor_ids": [1, 2, 3]}
    )
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from .base_agent import BaseAgent, AgentResponse, Citation

logger = logging.getLogger(__name__)


@dataclass
class ThreatSummary:
    """Summary of a competitive threat."""
    competitor_id: int
    competitor_name: str
    threat_level: str  # high, medium, low
    threat_score: float
    key_concerns: List[str]
    recent_moves: List[str]
    last_updated: datetime


@dataclass
class DashboardMetrics:
    """Key metrics for the dashboard."""
    total_competitors: int
    high_threat_count: int
    medium_threat_count: int
    low_threat_count: int
    recent_news_count: int
    data_freshness_days: float
    coverage_percentage: float


class DashboardAgent(BaseAgent):
    """
    Dashboard Agent - Executive summaries and threat analysis.

    This agent handles:
    - Executive summaries for leadership
    - Top threats identification
    - Key metrics aggregation
    - Trend analysis

    CRITICAL: This agent REFUSES to generate content without source data.
    All responses include proper citations.
    """

    def __init__(
        self,
        knowledge_base=None,
        vector_store=None,
        db_session=None,
        ai_router=None,
        max_competitors: int = 100,
        min_similarity: float = 0.5  # Lower default for better recall
    ):
        super().__init__(
            agent_type="dashboard",
            ai_router=ai_router,
            vector_store=vector_store
        )
        self.knowledge_base = knowledge_base
        self.vector_store = vector_store
        self.db_session = db_session
        self.ai_router = ai_router
        self.max_competitors = max_competitors
        self.min_similarity = min_similarity

    async def process(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """
        Process a dashboard query.

        Args:
            query: Natural language query (e.g., "What are the top threats?")
            context: Optional context with competitor_ids, date_range, etc.

        Returns:
            AgentResponse with summary, citations, and cost tracking
        """
        context = context or {}
        start_time = datetime.utcnow()

        try:
            # Step 1: Gather internal company context (Certify Health)
            internal_context = await self._get_internal_company_context()

            # Step 2: Use reconciliation engine if competitor_id provided, else KB context
            competitor_id = context.get("competitor_id")
            competitor_name = context.get("competitor_name", "")

            if competitor_id:
                # Use full reconciliation (KB + live data combined)
                kb_result = await self._get_reconciled_context(
                    competitor_id=competitor_id,
                    competitor_name=competitor_name,
                    query=query
                )
            else:
                # Fall back to KB context only
                kb_result = await self._get_knowledge_base_context(query, context)

            competitor_context = await self._get_competitor_context(context)

            # Merge internal context into KB result
            if internal_context.get("has_internal_data"):
                kb_result["internal_context"] = internal_context.get("context", "")
                kb_result["citations"] = kb_result.get("citations", []) + internal_context.get("citations", [])

            # Step 2: Check if we have enough data
            has_kb_data = kb_result.get("chunks_used", 0) > 0 or kb_result.get("context", "")
            has_competitor_data = len(competitor_context) > 0

            if not has_kb_data and not has_competitor_data:
                return AgentResponse(
                    text="I don't have information available to answer that question. "
                         "Please ensure relevant documents are uploaded to the knowledge base "
                         "or competitor data is available in the database.",
                    citations=[],
                    agent_type=self.agent_type,
                    cost_usd=0.0,
                    tokens_used=0,
                    latency_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                    metadata={"status": "no_data"}
                )

            # Step 3: Determine query type and generate response
            query_lower = query.lower()

            if any(kw in query_lower for kw in ["threat", "risk", "concern", "worry"]):
                return await self._generate_threat_summary(
                    query, kb_result, competitor_context, start_time
                )
            elif any(kw in query_lower for kw in ["summary", "overview", "brief", "executive"]):
                return await self._generate_executive_summary(
                    query, kb_result, competitor_context, start_time
                )
            elif any(kw in query_lower for kw in ["metric", "stat", "number", "count"]):
                return await self._generate_metrics_summary(
                    kb_result, competitor_context, start_time
                )
            else:
                # Default to executive summary
                return await self._generate_executive_summary(
                    query, kb_result, competitor_context, start_time
                )

        except Exception as e:
            logger.error(f"Dashboard agent error: {e}", exc_info=True)
            return AgentResponse(
                text=f"An error occurred while processing your request: {str(e)}",
                citations=[],
                agent_type=self.agent_type,
                cost_usd=0.0,
                tokens_used=0,
                latency_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                metadata={"status": "error", "error": str(e)}
            )

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
        # Try KnowledgeBase first (preferred)
        if self.knowledge_base:
            try:
                # Get filter metadata if provided in context
                filter_metadata = context.get("filter_metadata")

                # Temporarily override search method with lower similarity threshold
                original_search = self.knowledge_base.search

                async def search_with_threshold(*args, **kwargs):
                    kwargs['min_similarity'] = self.min_similarity
                    return await original_search(*args, **kwargs)

                self.knowledge_base.search = search_with_threshold

                result = await self.knowledge_base.get_context_for_query(
                    query=query,
                    max_chunks=5,
                    max_tokens=3000,
                    filter_metadata=filter_metadata
                )

                # Restore original search
                self.knowledge_base.search = original_search

                # Add source_type to each citation
                for cit in result.get("citations", []):
                    cit["source_type"] = "knowledge_base"

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
                        "content_preview": r.content[:150],
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
                logger.warning(f"Vector store search failed: {e}")

        return {"context": "", "citations": [], "chunks_used": 0}

    async def _get_competitor_context(
        self,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Retrieve competitor data from the database."""
        if not self.db_session:
            # Fallback: try to import and use sync session
            try:
                from database import SessionLocal, Competitor
                db = SessionLocal()

                competitor_ids = context.get("competitor_ids", [])

                if competitor_ids:
                    competitors = db.query(Competitor).filter(
                        Competitor.id.in_(competitor_ids)
                    ).limit(self.max_competitors).all()
                else:
                    # Get top competitors by threat level
                    competitors = db.query(Competitor).order_by(
                        Competitor.threat_level.desc()
                    ).limit(self.max_competitors).all()

                result = []
                for comp in competitors:
                    result.append({
                        "id": comp.id,
                        "name": comp.name,
                        "website": comp.website,
                        "threat_level": comp.threat_level,
                        "description": comp.notes,  # Fixed: Competitor model uses 'notes' not 'description'
                        "headquarters": comp.headquarters,
                        "estimated_revenue": comp.estimated_revenue,
                        "employee_count": comp.employee_count,
                        "products": comp.key_features,
                        "product_categories": comp.product_categories,
                        "target_segments": comp.target_segments,
                        "pricing_model": comp.pricing_model,
                        "source_type": "competitor_database"
                    })

                db.close()
                return result

            except Exception as e:
                logger.warning(f"Competitor database query failed: {e}")
                return []

        return []

    async def _generate_threat_summary(
        self,
        query: str,
        kb_result: Dict[str, Any],
        competitor_context: List[Dict],
        start_time: datetime
    ) -> AgentResponse:
        """Generate a threat analysis summary using RAG context."""

        # Build context for AI - use RAG context directly
        context_text = self._build_context_text(kb_result, competitor_context)

        # Generate using AI router or fallback
        if self.ai_router:
            from ai_router import TaskType

            prompt = f"""Based on the following competitive intelligence data, analyze the top threats.

CONTEXT:
{context_text}

USER QUESTION: {query}

INSTRUCTIONS:
1. Identify the top 3-5 competitive threats
2. For each threat, explain WHY it's a concern
3. Use [Source: X] citations for every claim
4. If data is insufficient, say so honestly
5. Focus on actionable insights

FORMAT:
## Top Competitive Threats

### 1. [Competitor Name] - [Threat Level]
- Key concern: [specific concern with citation]
- Recent activity: [what they've done recently]
- Recommended action: [what we should do]

[Continue for other threats...]

## Summary
[2-3 sentence executive summary]
"""

            response = await self.ai_router.generate(
                prompt=prompt,
                task_type=TaskType.ANALYSIS
            )

            response_text = response.get("text", "")
            cost = response.get("cost_usd", 0.0)
            tokens = response.get("tokens_total", 0)
        else:
            # Fallback: Generate structured response without AI
            response_text = self._generate_threat_fallback(competitor_context)
            cost = 0.0
            tokens = 0

        # Extract and validate citations - combine KB citations with extracted ones
        citations = self._build_citations(kb_result, competitor_context, response_text)

        latency = (datetime.utcnow() - start_time).total_seconds() * 1000

        return AgentResponse(
            text=response_text,
            citations=citations,
            agent_type=self.agent_type,
            cost_usd=cost,
            tokens_used=tokens,
            latency_ms=latency,
            metadata={
                "status": "success",
                "query_type": "threat_analysis",
                "competitors_analyzed": len(competitor_context),
                "kb_chunks_used": kb_result.get("chunks_used", 0)
            }
        )

    async def _generate_executive_summary(
        self,
        query: str,
        kb_result: Dict[str, Any],
        competitor_context: List[Dict],
        start_time: datetime
    ) -> AgentResponse:
        """Generate an executive summary using RAG context."""

        context_text = self._build_context_text(kb_result, competitor_context)

        if self.ai_router:
            from ai_router import TaskType

            prompt = f"""Generate a concise executive summary based on the following competitive intelligence.

CONTEXT:
{context_text}

USER QUESTION: {query}

INSTRUCTIONS:
1. Keep it brief (3-5 key points)
2. Focus on what executives need to know
3. Use [Source: X] citations for claims
4. Highlight any urgent items
5. End with recommended actions

FORMAT:
## Executive Summary

### Key Highlights
- [Point 1 with citation]
- [Point 2 with citation]
- [Point 3 with citation]

### Urgent Items
[Any time-sensitive information]

### Recommended Actions
1. [Action 1]
2. [Action 2]
"""

            response = await self.ai_router.generate(
                prompt=prompt,
                task_type=TaskType.SUMMARIZATION
            )

            response_text = response.get("text", "")
            cost = response.get("cost_usd", 0.0)
            tokens = response.get("tokens_total", 0)
        else:
            response_text = self._generate_summary_fallback(competitor_context)
            cost = 0.0
            tokens = 0

        citations = self._build_citations(kb_result, competitor_context, response_text)
        latency = (datetime.utcnow() - start_time).total_seconds() * 1000

        return AgentResponse(
            text=response_text,
            citations=citations,
            agent_type=self.agent_type,
            cost_usd=cost,
            tokens_used=tokens,
            latency_ms=latency,
            metadata={
                "status": "success",
                "query_type": "executive_summary",
                "competitors_analyzed": len(competitor_context),
                "kb_chunks_used": kb_result.get("chunks_used", 0)
            }
        )

    async def _generate_metrics_summary(
        self,
        kb_result: Dict[str, Any],
        competitor_context: List[Dict],
        start_time: datetime
    ) -> AgentResponse:
        """Generate a metrics summary without AI (pure data)."""

        # Calculate metrics from available data
        total = len(competitor_context)
        high_threat = sum(1 for c in competitor_context if str(c.get("threat_level", "")).lower() == "high")
        medium_threat = sum(1 for c in competitor_context if str(c.get("threat_level", "")).lower() == "medium")
        low_threat = sum(1 for c in competitor_context if str(c.get("threat_level", "")).lower() == "low")
        kb_chunks = kb_result.get("chunks_used", 0)

        metrics = DashboardMetrics(
            total_competitors=total,
            high_threat_count=high_threat,
            medium_threat_count=medium_threat,
            low_threat_count=low_threat,
            recent_news_count=0,  # Would need news data
            data_freshness_days=0.0,  # Would calculate from last_updated
            coverage_percentage=100.0 if total > 0 else 0.0
        )

        response_text = f"""## Dashboard Metrics

### Knowledge Base
- **Documents Available:** {kb_chunks} relevant chunks found
- **Total Tokens:** {kb_result.get('total_tokens', 0)}

### Competitor Overview
- **Total Competitors Tracked:** {metrics.total_competitors}
- **High Threat:** {metrics.high_threat_count} competitors
- **Medium Threat:** {metrics.medium_threat_count} competitors
- **Low Threat:** {metrics.low_threat_count} competitors

### Data Quality
- **Coverage:** {metrics.coverage_percentage:.1f}%

[Source: Internal Database & Knowledge Base]
"""

        citations = [
            Citation(
                source_id="internal_database",
                source_type="database",
                content="Metrics from internal database and knowledge base",
                confidence=1.0
            )
        ]

        latency = (datetime.utcnow() - start_time).total_seconds() * 1000

        return AgentResponse(
            text=response_text,
            citations=citations,
            agent_type=self.agent_type,
            cost_usd=0.0,
            tokens_used=0,
            latency_ms=latency,
            metadata={
                "status": "success",
                "query_type": "metrics",
                "metrics": {
                    "total_competitors": metrics.total_competitors,
                    "high_threat": metrics.high_threat_count,
                    "medium_threat": metrics.medium_threat_count,
                    "low_threat": metrics.low_threat_count
                }
            }
        )

    def _build_context_text(
        self,
        kb_result: Dict[str, Any],
        competitor_context: List[Dict]
    ) -> str:
        """
        Build context text for AI prompts.

        Args:
            kb_result: Result from KnowledgeBase.get_context_for_query()
            competitor_context: List of competitor data dicts

        Returns:
            Formatted context string for AI prompt
        """
        parts = []

        # Add internal company context (Certify Health) first
        internal_context = kb_result.get("internal_context", "")
        if internal_context:
            parts.append("### Our Company (Certify Health)")
            parts.append(internal_context)
            parts.append("")  # Blank line separator

        # Add knowledge base context (already formatted from RAG pipeline)
        kb_context = kb_result.get("context", "")
        if kb_context:
            parts.append("### Knowledge Base Documents")
            parts.append(kb_context)

        # Add competitor context
        if competitor_context:
            parts.append("\n### Competitor Data")
            for comp in competitor_context:
                parts.append(f"\n[Source: {comp.get('name', 'Unknown')}]")
                parts.append(f"- Threat Level: {comp.get('threat_level', 'N/A')}")
                if comp.get('notes'):
                    parts.append(f"- Description: {comp.get('notes', 'N/A')[:200]}")
                if comp.get('estimated_revenue'):
                    parts.append(f"- Revenue: {comp.get('estimated_revenue')}")
                if comp.get('employee_count'):
                    parts.append(f"- Employees: {comp.get('employee_count')}")

        return "\n".join(parts)

    def _build_citations(
        self,
        kb_result: Dict[str, Any],
        competitor_context: List[Dict],
        response_text: str
    ) -> List[Citation]:
        """
        Build citations from KB results and competitor context.

        Args:
            kb_result: Result from KnowledgeBase with citations
            competitor_context: Competitor data
            response_text: Generated response (for extracting additional refs)

        Returns:
            List of Citation objects
        """
        citations = []

        # Add KB citations directly
        for cit in kb_result.get("citations", []):
            citations.append(Citation(
                source_id=cit.get("document_id", "unknown"),
                source_type="knowledge_base",
                content=cit.get("content_preview", ""),
                confidence=cit.get("similarity_score", 0.8)
            ))

        # Add competitor citations
        for comp in competitor_context:
            if comp.get("name", "").lower() in response_text.lower():
                citations.append(Citation(
                    source_id=str(comp.get("id", "")),
                    source_type="competitor",
                    content=f"{comp.get('name')}: {comp.get('notes', '')[:100]}",
                    confidence=1.0
                ))

        return citations

    def _extract_citations(
        self,
        response_text: str,
        kb_context: List[Dict],
        competitor_context: List[Dict]
    ) -> List[Citation]:
        """Extract and validate citations from response text."""
        import re

        citations = []

        # Find all [Source: X] patterns
        pattern = r'\[Source:?\s*([^\]]+)\]'
        matches = re.findall(pattern, response_text, re.IGNORECASE)

        # Build valid source lookup
        valid_sources = {}

        for i, doc in enumerate(kb_context, 1):
            valid_sources[f"KB-{i}"] = {
                "id": doc.get("id"),
                "type": "knowledge_base",
                "content": doc.get("content", "")[:100]
            }

        for comp in competitor_context:
            valid_sources[comp.get("name", "").lower()] = {
                "id": str(comp.get("id")),
                "type": "competitor",
                "content": comp.get("notes", "")[:100]
            }

        valid_sources["competitor database"] = {
            "id": "database",
            "type": "database",
            "content": "Internal competitor database"
        }

        # Validate and create citations
        for match in matches:
            match_lower = match.lower().strip()

            # Check if it's a valid source
            for source_key, source_data in valid_sources.items():
                if source_key.lower() in match_lower or match_lower in source_key.lower():
                    citations.append(Citation(
                        source_id=source_data["id"],
                        source_type=source_data["type"],
                        content=source_data["content"],
                        confidence=0.9
                    ))
                    break

        return citations

    def _generate_threat_fallback(self, competitor_context: List[Dict]) -> str:
        """Generate threat summary without AI."""
        if not competitor_context:
            return "No competitor data available for threat analysis."

        # Sort by threat level (High > Medium > Low)
        _threat_order = {"high": 3, "medium": 2, "low": 1}
        sorted_comps = sorted(
            competitor_context,
            key=lambda x: _threat_order.get(str(x.get("threat_level", "")).lower(), 0),
            reverse=True
        )[:5]

        parts = ["## Top Competitive Threats\n"]

        for i, comp in enumerate(sorted_comps, 1):
            threat_label = str(comp.get("threat_level", "Low")).capitalize()
            if threat_label not in ("High", "Medium", "Low"):
                threat_label = "Low"

            parts.append(f"### {i}. {comp.get('name', 'Unknown')} - {threat_label} Threat")
            parts.append(f"- Threat Score: {comp.get('threat_level', 'N/A')}/10")
            if comp.get('notes'):
                parts.append(f"- Overview: {comp.get('notes')[:150]}...")
            parts.append(f"[Source: {comp.get('name', 'Unknown')}]\n")

        return "\n".join(parts)

    def _generate_summary_fallback(self, competitor_context: List[Dict]) -> str:
        """Generate executive summary without AI."""
        if not competitor_context:
            return "No competitor data available for summary."

        total = len(competitor_context)
        high_threat = [c for c in competitor_context if str(c.get("threat_level", "")).lower() == "high"]

        parts = [
            "## Executive Summary\n",
            "### Key Highlights",
            f"- Tracking {total} competitors in the competitive landscape [Source: Competitor Database]"
        ]

        if high_threat:
            names = ", ".join(c.get("name", "Unknown") for c in high_threat[:3])
            parts.append(f"- High-threat competitors: {names} [Source: Competitor Database]")

        parts.append("\n### Recommended Actions")
        parts.append("1. Review high-threat competitor activities weekly")
        parts.append("2. Update competitive intelligence data regularly")

        return "\n".join(parts)


# CLI testing
if __name__ == "__main__":
    import asyncio

    async def test():
        agent = DashboardAgent()

        # Test with no data
        response = await agent.process("What are the top threats?")
        print("=== No Data Test ===")
        print(response.text[:200])
        print(f"Citations: {len(response.citations)}")
        print()

        # Test with mock context
        response = await agent.process(
            "Give me an executive summary",
            context={"competitor_ids": [1, 2, 3]}
        )
        print("=== With Context Test ===")
        print(response.text[:500])
        print(f"Citations: {len(response.citations)}")

    asyncio.run(test())
