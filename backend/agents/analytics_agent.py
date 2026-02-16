"""
Certify Intel v7.0 - Analytics Agent
======================================

Agent specialized for analytics, executive summaries, and strategic insights.
Generates data-driven reports with full citation support.

Features:
- Executive summary generation
- Threat analysis with scoring
- Market positioning analysis
- Win/loss trend analysis
- Strategic recommendations

All outputs include citations to source data.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from .base_agent import BaseAgent, AgentResponse, Citation

logger = logging.getLogger(__name__)


class AnalyticsAgent(BaseAgent):
    """
    Agent for analytics, summaries, and strategic insights.

    Capabilities:
    - Generate executive summaries with live data
    - Analyze threat levels and trends
    - Create market positioning reports
    - Synthesize win/loss data
    - Provide strategic recommendations

    v7.0 Enhancement: Integrated with KnowledgeBase RAG pipeline for:
    - Market research and analyst reports
    - Strategic planning documents
    - Competitive benchmark data
    - Historical trend analysis
    """

    def __init__(
        self,
        knowledge_base=None,
        vector_store=None,
        ai_router=None,
        min_similarity: float = 0.5
    ):
        super().__init__(
            agent_type="analytics",
            ai_router=ai_router,
            vector_store=vector_store
        )
        self.knowledge_base = knowledge_base
        self.vector_store = vector_store
        self.ai_router = ai_router
        self.min_similarity = min_similarity
        self._db = None

    def _get_db(self):
        """Get database session."""
        if not self._db:
            try:
                from database import SessionLocal
                self._db = SessionLocal()
            except Exception as e:
                logger.error(f"Database connection error: {e}")
        return self._db

    def _close_db(self):
        """Close database session."""
        if self._db:
            self._db.close()
            self._db = None

    async def _get_knowledge_base_context(
        self,
        query: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Retrieve strategic context from knowledge base.

        This provides research and analysis context:
        - Market research reports
        - Analyst reports and benchmarks
        - Strategic planning documents
        - Industry trends and forecasts

        Args:
            query: The analytics query
            context: Optional additional context

        Returns:
            Dict with context, citations, and metadata
        """
        context = context or {}

        # Build search query based on analysis type
        kb_query = f"market analysis strategic insights trends {query}"

        # Try KnowledgeBase first (preferred)
        if self.knowledge_base:
            try:
                filter_metadata = context.get("filter_metadata")

                result = await self.knowledge_base.get_context_for_query(
                    query=kb_query,
                    max_chunks=5,
                    max_tokens=3000,
                    filter_metadata=filter_metadata
                )

                # Add source_type to citations
                for cit in result.get("citations", []):
                    cit["source_type"] = "knowledge_base"

                logger.info(f"KB context for analytics: {result.get('chunks_used', 0)} chunks")
                return result

            except Exception as e:
                logger.warning(f"KnowledgeBase retrieval failed: {e}")

        # Fallback to direct vector_store access
        if self.vector_store:
            try:
                results = await self.vector_store.search(
                    query=kb_query,
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

        # No KB available - return empty context
        return {"context": "", "citations": [], "chunks_used": 0}

    async def process(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """
        Process an analytics query.

        Supported queries:
        - "Generate executive summary"
        - "What are the top threats?"
        - "Analyze market positioning"
        - "Win/loss trends this quarter"
        - "Strategic recommendations for [competitor]"

        Args:
            query: Natural language analytics query
            context: Optional context with parameters:
                - report_type: "executive", "threat", "market", "winloss"
                - competitor_id: For competitor-specific analysis
                - time_period: "week", "month", "quarter", "year"
                - include_recommendations: bool

        Returns:
            AgentResponse with analytics and citations
        """
        start_time = datetime.utcnow()
        context = context or {}

        try:
            query_lower = query.lower()

            # Step 0: Get internal company context (Certify Health)
            internal_context = await self._get_internal_company_context()

            # Step 1: Use reconciliation engine if competitor_id provided
            competitor_id = context.get("competitor_id")
            competitor_name = context.get("competitor_name", "")

            if competitor_id:
                # Use full reconciliation for competitor-specific analytics
                kb_result = await self._get_reconciled_context(
                    competitor_id=competitor_id,
                    competitor_name=competitor_name,
                    query=query
                )
            else:
                # Fall back to KB context only for general analytics
                kb_result = await self._get_knowledge_base_context(query, context)

            # Merge internal context into KB result for analytics
            if internal_context.get("has_internal_data"):
                kb_result["internal_context"] = internal_context.get("context", "")
                kb_result["citations"] = kb_result.get("citations", []) + internal_context.get("citations", [])

            # Determine report type and pass query + KB context
            if any(w in query_lower for w in ["executive", "summary", "overview", "brief"]):
                return await self._generate_executive_summary(query, context, start_time, kb_result)
            elif any(w in query_lower for w in ["threat", "risk", "danger"]):
                return await self._analyze_threats(query, context, start_time, kb_result)
            elif any(w in query_lower for w in ["market", "position", "landscape"]):
                return await self._analyze_market_positioning(query, context, start_time, kb_result)
            elif any(w in query_lower for w in ["win", "loss", "deal"]):
                return await self._analyze_win_loss(query, context, start_time, kb_result)
            elif any(w in query_lower for w in ["recommend", "strategy", "action"]):
                return await self._generate_recommendations(query, context, start_time, kb_result)
            else:
                # Default to executive summary
                return await self._generate_executive_summary(query, context, start_time, kb_result)

        except Exception as e:
            logger.error(f"Analytics agent error: {e}")
            latency = (datetime.utcnow() - start_time).total_seconds() * 1000

            return AgentResponse(
                text=f"I encountered an error generating analytics: {str(e)}",
                citations=[],
                agent_type=self.agent_type,
                data={"error": str(e)},
                latency_ms=latency
            )
        finally:
            self._close_db()

    async def _generate_executive_summary(
        self,
        query: str,
        context: Dict[str, Any],
        start_time: datetime,
        kb_result: Dict[str, Any] = None
    ) -> AgentResponse:
        """
        Generate comprehensive executive summary.

        Args:
            query: Original user query
            context: Additional context parameters
            start_time: When processing started
            kb_result: Knowledge base context (Dict with context, citations, chunks_used)

        Returns:
            AgentResponse with executive summary and citations
        """
        kb_result = kb_result or {"context": "", "citations": [], "chunks_used": 0}
        citations = []
        data = {}

        try:
            db = self._get_db()
            if not db:
                raise Exception("Database not available")

            from database import Competitor, NewsArticleCache, WinLossDeal

            # Gather data for summary
            competitors = db.query(Competitor).all()
            total_competitors = len(competitors)

            # Threat analysis
            high_threats = [c for c in competitors if getattr(c, 'threat_level', '') == 'High']
            medium_threats = [c for c in competitors if getattr(c, 'threat_level', '') == 'Medium']

            # Recent news
            week_ago = datetime.utcnow() - timedelta(days=7)
            recent_news = db.query(NewsArticleCache).filter(
                NewsArticleCache.published_at >= week_ago
            ).count()

            # Recent wins/losses
            try:
                recent_deals = db.query(WinLossDeal).filter(
                    WinLossDeal.created_at >= week_ago
                ).all()
                wins = len([d for d in recent_deals if d.outcome == 'win'])
                losses = len([d for d in recent_deals if d.outcome == 'loss'])
            except Exception:
                wins, losses = 0, 0

            # Build citations
            citations.append(Citation(
                source_id="competitor_db",
                source_type="competitor_database",
                content=f"{total_competitors} competitors tracked",
                confidence=1.0
            ))

            citations.append(Citation(
                source_id="threat_analysis",
                source_type="competitor_database",
                content=f"{len(high_threats)} high-threat competitors identified",
                confidence=0.95
            ))

            if recent_news > 0:
                citations.append(Citation(
                    source_id="news_cache",
                    source_type="news",
                    content=f"{recent_news} news articles from past week",
                    confidence=0.9
                ))

            # Generate summary text
            parts = []
            parts.append("## Executive Summary\n")
            parts.append(f"**Competitive Landscape Overview** (as of {datetime.utcnow().strftime('%B %d, %Y')})\n")

            # Key metrics
            parts.append("### Key Metrics")
            parts.append(f"- **Total Competitors Tracked**: {total_competitors} [Source: competitor_db]")
            parts.append(f"- **High-Threat Competitors**: {len(high_threats)} [Source: threat_analysis]")
            parts.append(f"- **Medium-Threat Competitors**: {len(medium_threats)}")
            parts.append(f"- **News Articles (7 days)**: {recent_news} [Source: news_cache]")

            if wins > 0 or losses > 0:
                win_rate = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0
                parts.append(f"- **Win Rate (7 days)**: {win_rate:.1f}% ({wins}W / {losses}L)")
            parts.append("")

            # Top threats
            if high_threats:
                parts.append("### Top Threats")
                for i, threat in enumerate(high_threats[:5], 1):
                    parts.append(f"{i}. **{threat.name}** - {getattr(threat, 'headquarters', 'Location unknown')}")
                parts.append("")

            # Recent major events
            major_events = db.query(NewsArticleCache).filter(
                NewsArticleCache.published_at >= week_ago,
                NewsArticleCache.is_major_event.is_(True)
            ).limit(5).all()

            if major_events:
                parts.append("### Recent Major Events")
                for i, event in enumerate(major_events, 1):
                    event_type = event.event_type or "news"
                    parts.append(f"{i}. [{event_type.upper()}] {event.title}")
                    citations.append(Citation(
                        source_id=f"event_{i}",
                        source_type="news",
                        content=event.title[:100],
                        confidence=0.9,
                        url=event.url
                    ))
                parts.append("")

            # Recommendations
            parts.append("### Recommended Actions")
            if len(high_threats) > 5:
                parts.append("- **Priority**: Review battlecards for top 5 high-threat competitors")
            if recent_news < 10:
                parts.append("- **Action**: Consider refreshing news data for broader coverage")
            if losses > wins:
                parts.append("- **Focus**: Analyze recent losses to identify competitive gaps")
            parts.append("- **Ongoing**: Monitor funding announcements for emerging threats")

            # Add KB strategic context if available
            kb_context = kb_result.get("context", "")
            kb_citations = kb_result.get("citations", [])

            if kb_context:
                parts.append("")
                parts.append("### Strategic Context (from Knowledge Base)")
                parts.append(kb_context[:500] + "..." if len(kb_context) > 500 else kb_context)

            # Add KB citations
            for kb_cit in kb_citations:
                citations.append(Citation(
                    source_id=kb_cit.get("document_id", "kb"),
                    source_type="knowledge_base",
                    content=kb_cit.get("content_preview", "Strategic context"),
                    confidence=kb_cit.get("similarity_score", 0.7)
                ))

            # Store data
            data = {
                "total_competitors": total_competitors,
                "high_threats": len(high_threats),
                "medium_threats": len(medium_threats),
                "recent_news": recent_news,
                "wins": wins,
                "losses": losses,
                "top_threats": [{"name": c.name, "id": c.id} for c in high_threats[:5]],
                "kb_chunks_used": kb_result.get("chunks_used", 0)
            }

            latency = (datetime.utcnow() - start_time).total_seconds() * 1000

            return AgentResponse(
                text="\n".join(parts),
                citations=citations,
                agent_type=self.agent_type,
                data=data,
                latency_ms=latency
            )

        except Exception as e:
            logger.error(f"Error generating executive summary: {e}")
            raise

    async def _analyze_threats(
        self,
        query: str,
        context: Dict[str, Any],
        start_time: datetime,
        kb_result: Dict[str, Any] = None
    ) -> AgentResponse:
        """Analyze threat levels and trends with KB context."""
        kb_result = kb_result or {"context": "", "citations": [], "chunks_used": 0}
        citations = []

        try:
            db = self._get_db()
            if not db:
                raise Exception("Database not available")

            from database import Competitor

            competitors = db.query(Competitor).all()

            # Group by threat level
            threat_groups = {
                "Critical": [],
                "High": [],
                "Medium": [],
                "Low": [],
                "Unknown": []
            }

            for c in competitors:
                level = getattr(c, 'threat_level', 'Unknown') or 'Unknown'
                if level in threat_groups:
                    threat_groups[level].append(c)
                else:
                    threat_groups["Unknown"].append(c)

            # Build response
            parts = []
            parts.append("## Threat Analysis Report\n")

            for level in ["Critical", "High", "Medium", "Low"]:
                group = threat_groups[level]
                if group:
                    parts.append(f"### {level} Threat ({len(group)} competitors)")
                    for c in group[:5]:
                        funding = getattr(c, 'funding_amount', None) or "Unknown"
                        parts.append(f"- **{c.name}**: Funding ${funding}")

                        citations.append(Citation(
                            source_id=f"competitor_{c.id}",
                            source_type="competitor_database",
                            content=f"{c.name} - {level} threat",
                            confidence=0.9
                        ))
                    if len(group) > 5:
                        parts.append(f"  _...and {len(group) - 5} more_")
                    parts.append("")

            latency = (datetime.utcnow() - start_time).total_seconds() * 1000

            return AgentResponse(
                text="\n".join(parts),
                citations=citations,
                agent_type=self.agent_type,
                data={
                    "threat_counts": {k: len(v) for k, v in threat_groups.items()},
                    "total_analyzed": len(competitors)
                },
                latency_ms=latency
            )

        except Exception as e:
            logger.error(f"Error analyzing threats: {e}")
            raise

    async def _analyze_market_positioning(
        self,
        query: str,
        context: Dict[str, Any],
        start_time: datetime,
        kb_result: Dict[str, Any] = None
    ) -> AgentResponse:
        """Analyze market positioning of competitors with KB context."""
        kb_result = kb_result or {"context": "", "citations": [], "chunks_used": 0}
        citations = []

        try:
            db = self._get_db()
            if not db:
                raise Exception("Database not available")

            from database import Competitor

            competitors = db.query(Competitor).all()

            # Group by segment
            segments = {}
            for c in competitors:
                segment = getattr(c, 'target_market', 'Other') or 'Other'
                if segment not in segments:
                    segments[segment] = []
                segments[segment].append(c)

            # Build response
            parts = []
            parts.append("## Market Positioning Analysis\n")
            parts.append(f"Analyzing {len(competitors)} competitors across {len(segments)} segments.\n")

            for segment, comps in sorted(segments.items(), key=lambda x: -len(x[1]))[:8]:
                parts.append(f"### {segment} ({len(comps)} competitors)")

                top_comps = sorted(comps, key=lambda c: getattr(c, 'estimated_customers', 0) or 0, reverse=True)[:3]
                for c in top_comps:
                    customers = getattr(c, 'estimated_customers', 'Unknown')
                    parts.append(f"- **{c.name}**: ~{customers} customers")

                    citations.append(Citation(
                        source_id=f"market_{c.id}",
                        source_type="competitor_database",
                        content=f"{c.name} in {segment} segment",
                        confidence=0.85
                    ))
                parts.append("")

            latency = (datetime.utcnow() - start_time).total_seconds() * 1000

            return AgentResponse(
                text="\n".join(parts),
                citations=citations,
                agent_type=self.agent_type,
                data={
                    "segments": {k: len(v) for k, v in segments.items()},
                    "total_competitors": len(competitors)
                },
                latency_ms=latency
            )

        except Exception as e:
            logger.error(f"Error analyzing market positioning: {e}")
            raise

    async def _analyze_win_loss(
        self,
        query: str,
        context: Dict[str, Any],
        start_time: datetime,
        kb_result: Dict[str, Any] = None
    ) -> AgentResponse:
        """Analyze win/loss trends with KB context."""
        kb_result = kb_result or {"context": "", "citations": [], "chunks_used": 0}
        citations = []
        period = context.get("time_period", "quarter")

        try:
            db = self._get_db()
            if not db:
                raise Exception("Database not available")

            from database import WinLossDeal, Competitor

            # Determine date range
            if period == "week":
                cutoff = datetime.utcnow() - timedelta(days=7)
            elif period == "month":
                cutoff = datetime.utcnow() - timedelta(days=30)
            else:  # quarter
                cutoff = datetime.utcnow() - timedelta(days=90)

            deals = db.query(WinLossDeal).filter(
                WinLossDeal.created_at >= cutoff
            ).all()

            wins = [d for d in deals if d.outcome == 'win']
            losses = [d for d in deals if d.outcome == 'loss']

            # Build response
            parts = []
            parts.append(f"## Win/Loss Analysis ({period.capitalize()})\n")

            if not deals:
                parts.append("No win/loss data available for this period.")
            else:
                total = len(deals)
                win_rate = len(wins) / total * 100 if total > 0 else 0

                parts.append("### Summary")
                parts.append(f"- **Total Deals**: {total}")
                parts.append(f"- **Wins**: {len(wins)}")
                parts.append(f"- **Losses**: {len(losses)}")
                parts.append(f"- **Win Rate**: {win_rate:.1f}%")
                parts.append("")

                # Top competitors we lost to
                if losses:
                    parts.append("### Top Competitors We Lost To")
                    loss_counts = {}
                    for d in losses:
                        comp_id = d.competitor_id
                        if comp_id:
                            loss_counts[comp_id] = loss_counts.get(comp_id, 0) + 1

                    for comp_id, count in sorted(loss_counts.items(), key=lambda x: -x[1])[:5]:
                        comp = db.query(Competitor).filter(Competitor.id == comp_id).first()
                        if comp:
                            parts.append(f"- **{comp.name}**: {count} losses")

                            citations.append(Citation(
                                source_id=f"loss_{comp_id}",
                                source_type="winloss",
                                content=f"Lost {count} deals to {comp.name}",
                                confidence=1.0
                            ))

            latency = (datetime.utcnow() - start_time).total_seconds() * 1000

            return AgentResponse(
                text="\n".join(parts),
                citations=citations,
                agent_type=self.agent_type,
                data={
                    "wins": len(wins),
                    "losses": len(losses),
                    "win_rate": len(wins) / len(deals) * 100 if deals else 0,
                    "period": period
                },
                latency_ms=latency
            )

        except Exception as e:
            logger.error(f"Error analyzing win/loss: {e}")
            raise

    async def _generate_recommendations(
        self,
        query: str,
        context: Dict[str, Any],
        start_time: datetime,
        kb_result: Dict[str, Any] = None
    ) -> AgentResponse:
        """Generate strategic recommendations with KB context."""
        kb_result = kb_result or {"context": "", "citations": [], "chunks_used": 0}
        citations = []

        try:
            db = self._get_db()
            if not db:
                raise Exception("Database not available")

            from database import Competitor, NewsArticleCache

            # Gather data for recommendations
            competitors = db.query(Competitor).all()
            high_threats = [c for c in competitors if getattr(c, 'threat_level', '') == 'High']

            week_ago = datetime.utcnow() - timedelta(days=7)
            funding_news = db.query(NewsArticleCache).filter(
                NewsArticleCache.published_at >= week_ago,
                NewsArticleCache.event_type == 'funding'
            ).all()

            # Build recommendations
            parts = []
            parts.append("## Strategic Recommendations\n")

            parts.append("### Immediate Actions (This Week)")

            if high_threats:
                top_threat = high_threats[0]
                parts.append(f"1. **Update battlecard for {top_threat.name}** - Highest threat competitor")
                citations.append(Citation(
                    source_id="rec_1",
                    source_type="competitor_database",
                    content=f"{top_threat.name} identified as top threat",
                    confidence=0.95
                ))

            if funding_news:
                parts.append(
                    f"2. **Monitor {len(funding_news)} recent funding announcements** "
                    "- New resources enable expansion"
                )
                for news in funding_news[:2]:
                    citations.append(Citation(
                        source_id=f"funding_{news.id}",
                        source_type="news",
                        content=news.title[:80],
                        confidence=0.9,
                        url=news.url
                    ))

            parts.append("3. **Review sales talking points** - Ensure team has latest competitive data")
            parts.append("")

            parts.append("### Medium-Term (This Month)")
            parts.append("1. Conduct deep-dive analysis on top 3 threats")
            parts.append("2. Update product comparison matrices")
            parts.append("3. Schedule competitive intelligence training")
            parts.append("")

            parts.append("### Strategic (This Quarter)")
            parts.append("1. Develop counter-positioning for emerging threats")
            parts.append("2. Build relationships with analyst firms")
            parts.append("3. Create competitive win playbooks")

            latency = (datetime.utcnow() - start_time).total_seconds() * 1000

            return AgentResponse(
                text="\n".join(parts),
                citations=citations,
                agent_type=self.agent_type,
                data={
                    "high_threats_count": len(high_threats),
                    "funding_news_count": len(funding_news)
                },
                latency_ms=latency
            )

        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            raise
