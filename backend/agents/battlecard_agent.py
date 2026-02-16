"""
Certify Intel v7.0 - Battlecard Agent
======================================

Sales-ready competitive battlecard generation.

This agent wraps the existing BattlecardGenerator to integrate with
the LangGraph orchestrator.

Features:
- Full battlecards with all 9 dimensions
- Quick reference cards for fast lookups
- Objection handlers for specific scenarios
- AI-powered content enhancement with citations
- Cost tracking through AI router

Battlecard Types:
- full: Complete battlecard with all sections
- quick: 1-page summary for fast lookups
- objection_handler: Focused objection handling
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from .base_agent import BaseAgent, AgentResponse, Citation

logger = logging.getLogger(__name__)


@dataclass
class BattlecardRequest:
    """Request parameters for battlecard generation."""
    competitor_id: int
    competitor_name: str = ""
    battlecard_type: str = "full"  # full, quick, objection_handler
    focus_dimensions: List[str] = None
    include_news: bool = True
    include_talking_points: bool = True


class BattlecardAgent(BaseAgent):
    """
    Battlecard Agent - Sales-ready competitive battlecards.

    This agent handles:
    - Generating battlecards for specific competitors
    - Enhancing content with AI-powered insights
    - Including proper citations from knowledge base
    - Tracking costs through AI router

    CRITICAL: All battlecard content is sourced from real data.

    v7.0 Enhancement: Integrated with KnowledgeBase RAG pipeline for:
    - Competitor-specific intelligence from uploaded documents
    - Recent news and analyst reports
    - Product comparisons and feature analysis
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
            agent_type="battlecard",
            ai_router=ai_router,
            vector_store=vector_store
        )
        self.knowledge_base = knowledge_base
        self.vector_store = vector_store
        self.db_session = db_session
        self.ai_router = ai_router
        self.min_similarity = min_similarity
        self._generator = None

    def _get_generator(self):
        """Lazy-load the battlecard generator."""
        if self._generator is None:
            try:
                from battlecard_generator import BattlecardGenerator
                self._generator = BattlecardGenerator(self.db_session)
                logger.info("BattlecardGenerator initialized")
            except ImportError as e:
                logger.warning(f"BattlecardGenerator not available: {e}")
        return self._generator

    async def process(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """
        Process a battlecard request.

        Args:
            query: Natural language query (e.g., "Generate battlecard for Epic")
            context: Optional context with competitor_id, type, etc.

        Returns:
            AgentResponse with battlecard content and citations
        """
        context = context or {}
        start_time = datetime.utcnow()

        try:
            # Get internal company context (Certify Health) for comparison
            internal_context = await self._get_internal_company_context()

            # Parse the request
            request = self._parse_request(query, context)

            # Validate competitor exists
            competitor = await self._get_competitor(request.competitor_id)

            if not competitor:
                return AgentResponse(
                    text=f"Could not find competitor with ID {request.competitor_id}. "
                         "Please provide a valid competitor ID or name.",
                    citations=[],
                    agent_type=self.agent_type,
                    cost_usd=0.0,
                    tokens_used=0,
                    latency_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                    metadata={"status": "not_found"}
                )

            # Use reconciliation engine for competitor-specific battlecards (KB + live data)
            if request.competitor_id:
                kb_context = await self._get_reconciled_context(
                    competitor_id=request.competitor_id,
                    competitor_name=competitor.get("name", ""),
                    query=f"battlecard competitive analysis {competitor.get('name', '')}"
                )
            else:
                # Fallback to KB-only context
                kb_context = await self._get_kb_context(competitor.get("name", ""))

            # Merge internal company context into KB context for battlecard generation
            if internal_context.get("has_internal_data"):
                kb_context["internal_context"] = internal_context.get("context", "")
                kb_context["citations"] = kb_context.get("citations", []) + internal_context.get("citations", [])

            # Generate battlecard
            battlecard = await self._generate_battlecard(
                request, competitor, kb_context
            )

            return self._build_response(battlecard, competitor, kb_context, start_time)

        except Exception as e:
            logger.error(f"Battlecard agent error: {e}", exc_info=True)
            return AgentResponse(
                text=f"Battlecard generation failed: {str(e)}",
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
    ) -> BattlecardRequest:
        """Parse query and context into a BattlecardRequest."""
        query_lower = query.lower()

        # Determine battlecard type from query
        battlecard_type = "full"
        if "quick" in query_lower or "summary" in query_lower:
            battlecard_type = "quick"
        elif "objection" in query_lower:
            battlecard_type = "objection_handler"

        # Get competitor ID from context or try to parse from query
        competitor_id = context.get("competitor_id", 0)
        competitor_name = context.get("competitor_name", "")

        # If no ID, try to find by name in query
        if not competitor_id and not competitor_name:
            # Extract potential competitor name from query
            # e.g., "Generate battlecard for Epic Systems"
            for keyword in ["for ", "about ", "on "]:
                if keyword in query_lower:
                    idx = query_lower.index(keyword) + len(keyword)
                    competitor_name = query[idx:].strip()
                    break

        return BattlecardRequest(
            competitor_id=competitor_id,
            competitor_name=competitor_name,
            battlecard_type=context.get("battlecard_type", battlecard_type),
            focus_dimensions=context.get("focus_dimensions"),
            include_news=context.get("include_news", True),
            include_talking_points=context.get("include_talking_points", True)
        )

    async def _get_competitor(self, competitor_id: int) -> Optional[Dict[str, Any]]:
        """Get competitor from database."""
        try:
            from database import SessionLocal, Competitor
            db = SessionLocal()

            if competitor_id:
                comp = db.query(Competitor).filter(Competitor.id == competitor_id).first()
            else:
                db.close()
                return None

            if not comp:
                db.close()
                return None

            result = {
                "id": comp.id,
                "name": comp.name,
                "website": comp.website,
                "description": comp.notes,  # Fixed: Competitor model uses 'notes' not 'description'
                "threat_level": comp.threat_level,
                "headquarters": comp.headquarters,
                "employee_count": comp.employee_count,
                "estimated_revenue": comp.estimated_revenue,
                "key_features": comp.key_features,
                "products": comp.product_categories,
                "target_segments": comp.target_segments,
                "pricing_model": comp.pricing_model,
                "certifications": comp.certifications,
                "integration_partners": comp.integration_partners
            }

            db.close()
            return result

        except Exception as e:
            logger.error(f"Failed to get competitor: {e}")
            return None

    async def _get_kb_context(self, competitor_name: str) -> Dict[str, Any]:
        """
        Get knowledge base context for competitor.

        Uses KnowledgeBase RAG pipeline for semantic search.

        Args:
            competitor_name: Name of the competitor to search for

        Returns:
            Dict with context, citations, and metadata
        """
        if not competitor_name:
            return {"context": "", "citations": [], "chunks_used": 0}

        # Build search query for competitor-specific intelligence
        query = f"{competitor_name} competitive intelligence products features pricing"

        # Try KnowledgeBase first (preferred)
        if self.knowledge_base:
            try:
                result = await self.knowledge_base.get_context_for_query(
                    query=query,
                    max_chunks=5,
                    max_tokens=3000
                )

                # Add source_type to citations
                for cit in result.get("citations", []):
                    cit["source_type"] = "knowledge_base"

                logger.info(f"KB context for {competitor_name}: {result.get('chunks_used', 0)} chunks")
                return result

            except Exception as e:
                logger.warning(f"KnowledgeBase retrieval failed for {competitor_name}: {e}")

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
                logger.warning(f"VectorStore search failed for {competitor_name}: {e}")

        # No KB available - return empty context
        return {"context": "", "citations": [], "chunks_used": 0}

    async def _generate_battlecard(
        self,
        request: BattlecardRequest,
        competitor: Dict[str, Any],
        kb_context: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate the battlecard content."""

        generator = self._get_generator()

        if generator:
            # Use existing generator
            try:
                battlecard = generator.generate(
                    competitor_id=request.competitor_id,
                    battlecard_type=request.battlecard_type,
                    include_news=request.include_news
                )
                return battlecard.to_dict() if hasattr(battlecard, "to_dict") else battlecard
            except Exception as e:
                logger.warning(f"Generator failed, using fallback: {e}")

        # Fallback: Build battlecard from available data
        return self._build_fallback_battlecard(request, competitor, kb_context)

    def _build_fallback_battlecard(
        self,
        request: BattlecardRequest,
        competitor: Dict[str, Any],
        kb_context: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build a battlecard without the generator."""

        name = competitor.get("name", "Unknown")

        # Build sections based on type
        sections = []

        # Quick Facts (always included)
        sections.append({
            "section_id": "quick_facts",
            "title": "Quick Facts",
            "content": {
                "name": name,
                "website": competitor.get("website", "N/A"),
                "headquarters": competitor.get("headquarters", "N/A"),
                "employees": competitor.get("employee_count", "N/A"),
                "revenue": competitor.get("estimated_revenue", "N/A"),
                "threat_level": competitor.get("threat_level", "N/A")
            }
        })

        # Key Differentiators (derived from key_features)
        differentiators = competitor.get("key_features", "")
        if differentiators:
            sections.append({
                "section_id": "key_differentiators",
                "title": "Key Differentiators",
                "content": differentiators.split(",") if isinstance(differentiators, str) else differentiators
            })

        # Strengths & Weaknesses (weaknesses not available in schema, using empty list)
        sections.append({
            "section_id": "strengths_weaknesses",
            "title": "Strengths & Weaknesses",
            "content": {
                "strengths": competitor.get("key_features", "").split(",") if competitor.get("key_features") else [],
                "weaknesses": []  # Not in Competitor model schema
            }
        })

        # Notes/Overview (using 'notes' field from Competitor model)
        if competitor.get("notes"):
            sections.append({
                "section_id": "overview",
                "title": "Company Overview",
                "content": competitor.get("notes")
            })

        # Knowledge Base Insights (now using Dict format from RAG pipeline)
        kb_citations = kb_context.get("citations", []) if isinstance(kb_context, dict) else kb_context
        kb_text = kb_context.get("context", "") if isinstance(kb_context, dict) else ""

        if kb_citations or kb_text:
            insights = []
            for cit in kb_citations[:3]:
                insights.append({
                    "source": cit.get("document_id", cit.get("id", "Unknown")),
                    "section": cit.get("section", ""),
                    "content": cit.get("content_preview", "")[:200] + "..."
                })
            sections.append({
                "section_id": "kb_insights",
                "title": "Knowledge Base Insights",
                "content": insights
            })

        return {
            "competitor_id": request.competitor_id,
            "competitor_name": name,
            "battlecard_type": request.battlecard_type,
            "title": f"{name} - Competitive Battlecard",
            "sections": sections,
            "generated_at": datetime.utcnow().isoformat(),
            "metadata": {
                "source": "fallback_generator",
                "kb_chunks_used": kb_context.get("chunks_used", 0) if isinstance(kb_context, dict) else len(kb_context)
            }
        }

    def _build_response(
        self,
        battlecard: Dict[str, Any],
        competitor: Dict[str, Any],
        kb_context: Dict[str, Any],
        start_time: datetime
    ) -> AgentResponse:
        """
        Build the AgentResponse from battlecard data.

        Args:
            battlecard: Generated battlecard content
            competitor: Competitor database record
            kb_context: Knowledge base context (Dict with context, citations, chunks_used)
            start_time: When processing started

        Returns:
            AgentResponse with battlecard, citations, and metadata
        """
        # Format battlecard as readable text
        text = self._format_battlecard(battlecard)

        # Build citations
        citations = [
            Citation(
                source_id=str(competitor.get("id", "unknown")),
                source_type="competitor_database",
                content=f"Competitor data for {competitor.get('name', 'Unknown')}",
                confidence=1.0
            )
        ]

        # Add KB citations (now using Dict format from RAG pipeline)
        kb_citations = kb_context.get("citations", []) if isinstance(kb_context, dict) else kb_context
        for cit in kb_citations:
            citations.append(Citation(
                source_id=cit.get("document_id", cit.get("id", "unknown")),
                source_type="knowledge_base",
                content=cit.get("content_preview", "")[:100],
                confidence=cit.get("similarity_score", 0.8)
            ))

        latency = (datetime.utcnow() - start_time).total_seconds() * 1000

        return AgentResponse(
            text=text,
            citations=citations,
            agent_type=self.agent_type,
            cost_usd=0.0,
            tokens_used=0,
            latency_ms=latency,
            metadata={
                "status": "success",
                "battlecard_type": battlecard.get("battlecard_type"),
                "competitor_id": battlecard.get("competitor_id"),
                "sections_count": len(battlecard.get("sections", [])),
                "kb_chunks_used": kb_context.get("chunks_used", 0) if isinstance(kb_context, dict) else 0,
                "battlecard": battlecard  # Full battlecard data
            }
        )

    def _format_battlecard(self, battlecard: Dict[str, Any]) -> str:
        """Format battlecard as readable markdown text."""
        parts = [
            f"# {battlecard.get('title', 'Competitive Battlecard')}\n",
            f"*Generated: {battlecard.get('generated_at', 'N/A')}*\n",
            f"*Type: {battlecard.get('battlecard_type', 'full')}*\n"
        ]

        for section in battlecard.get("sections", []):
            title = section.get("title", "Section")
            content = section.get("content", "")

            parts.append(f"\n## {title}\n")

            if isinstance(content, dict):
                for key, value in content.items():
                    if isinstance(value, list):
                        parts.append(f"**{key.replace('_', ' ').title()}:**")
                        for item in value:
                            parts.append(f"- {item}")
                    else:
                        parts.append(f"**{key.replace('_', ' ').title()}:** {value}")
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        parts.append(f"- {item.get('content', item)}")
                    else:
                        parts.append(f"- {item}")
            else:
                parts.append(str(content))

        parts.append("\n---")
        parts.append("[Source: Competitor Database, Knowledge Base]")

        return "\n".join(parts)


# CLI testing
if __name__ == "__main__":
    import asyncio

    async def test():
        agent = BattlecardAgent()

        # Test with competitor ID
        response = await agent.process(
            "Generate a quick battlecard for competitor",
            context={"competitor_id": 1}
        )

        print("=== Battlecard Test ===")
        print(f"Status: {response.metadata.get('status')}")
        print(f"Response:\n{response.text[:1000]}...")
        print(f"Citations: {len(response.citations)}")

    asyncio.run(test())
