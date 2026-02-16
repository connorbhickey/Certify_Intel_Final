"""
Certify Intel v7.0 - News Agent
================================

Agent specialized for real-time news monitoring and sentiment analysis.
Integrates with:
- NewsMonitor for multi-source news fetching
- ML sentiment analysis (FinBERT)
- SEC EDGAR for regulatory filings
- USPTO for patent news

Features:
- Real-time news search with sentiment
- Major event detection (funding, M&A, launches)
- Competitor news aggregation
- Dimension tagging for Sales & Marketing
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import asdict

from .base_agent import BaseAgent, AgentResponse, Citation

logger = logging.getLogger(__name__)


class NewsAgent(BaseAgent):
    """
    Agent for real-time news monitoring and sentiment analysis.

    Capabilities:
    - Search news for specific competitors
    - Aggregate news across all competitors
    - Filter by sentiment, date range, event type
    - Get major events (funding, acquisitions, etc.)
    - Patent and SEC filing monitoring

    v7.0 Enhancement: Integrated with KnowledgeBase RAG pipeline for:
    - Historical news context from uploaded documents
    - Background company information for news relevance
    - Regulatory filing context
    """

    def __init__(
        self,
        knowledge_base=None,
        vector_store=None,
        ai_router=None,
        min_similarity: float = 0.5
    ):
        super().__init__(
            agent_type="news",
            ai_router=ai_router,
            vector_store=vector_store
        )
        self.knowledge_base = knowledge_base
        self.vector_store = vector_store
        self.ai_router = ai_router
        self.min_similarity = min_similarity
        self._news_monitor = None
        self._initialize_monitor()

    def _initialize_monitor(self):
        """Initialize NewsMonitor with lazy loading."""
        try:
            from news_monitor import NewsMonitor
            self._news_monitor = NewsMonitor()
            logger.info("NewsMonitor initialized successfully")
        except ImportError as e:
            logger.warning(f"NewsMonitor not available: {e}")
            self._news_monitor = None

    async def _get_knowledge_base_context(
        self,
        query: str,
        competitor_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Retrieve background context from knowledge base.

        This provides historical context for news interpretation:
        - Previous company announcements
        - Regulatory history
        - Product launch history
        - Market positioning context

        Args:
            query: The news search query
            competitor_name: Optional competitor name for targeted search

        Returns:
            Dict with context, citations, and metadata
        """
        # Build search query
        if competitor_name:
            kb_query = f"{competitor_name} news history announcements regulatory"
        else:
            kb_query = f"healthcare technology news {query}"

        # Try KnowledgeBase first (preferred)
        if self.knowledge_base:
            try:
                result = await self.knowledge_base.get_context_for_query(
                    query=kb_query,
                    max_chunks=3,  # Smaller for news context
                    max_tokens=1500
                )

                # Add source_type to citations
                for cit in result.get("citations", []):
                    cit["source_type"] = "knowledge_base"

                logger.info(f"KB context for news: {result.get('chunks_used', 0)} chunks")
                return result

            except Exception as e:
                logger.warning(f"KnowledgeBase retrieval failed: {e}")

        # Fallback to direct vector_store access
        if self.vector_store:
            try:
                results = await self.vector_store.search(
                    query=kb_query,
                    limit=3,
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
        Process a news-related query.

        Supported queries:
        - "Latest news for [competitor]"
        - "What's the sentiment for [competitor]?"
        - "Recent funding announcements"
        - "Major events this week"
        - "News about [topic] in healthcare AI"

        Args:
            query: Natural language query about news
            context: Optional context with filters:
                - competitor_id: Specific competitor ID
                - competitor_name: Competitor name to search
                - days: Number of days to look back (default 7)
                - sentiment_filter: "positive", "negative", "neutral"
                - event_type: "funding", "acquisition", "product_launch", etc.
                - limit: Max articles to return

        Returns:
            AgentResponse with news summary and citations
        """
        start_time = datetime.utcnow()
        context = context or {}

        try:
            # Parse query to determine action
            query_lower = query.lower()

            # Extract parameters from context or query
            competitor_name = context.get("competitor_name")
            competitor_id = context.get("competitor_id")
            days = context.get("days", 7)
            sentiment_filter = context.get("sentiment_filter")
            event_type = context.get("event_type")
            limit = context.get("limit", 10)

            # Detect competitor name from query if not in context
            if not competitor_name and not competitor_id:
                competitor_name = self._extract_competitor_from_query(query)

            # Determine query type
            if any(word in query_lower for word in ["funding", "raised", "investment"]):
                event_type = event_type or "funding"
            elif any(word in query_lower for word in ["acquired", "acquisition", "merger"]):
                event_type = event_type or "acquisition"
            elif any(word in query_lower for word in ["launch", "released", "announces"]):
                event_type = event_type or "product_launch"

            # Step 0: Get internal company context (Certify Health)
            internal_context = await self._get_internal_company_context()

            # Step 1: Use reconciliation engine if competitor_id provided
            if competitor_id:
                kb_result = await self._get_reconciled_context(
                    competitor_id=competitor_id,
                    competitor_name=competitor_name or "",
                    query=f"news history {query}"
                )
            else:
                kb_result = await self._get_knowledge_base_context(query, competitor_name)

            kb_citations = kb_result.get("citations", [])

            # Merge internal context citations
            if internal_context.get("has_internal_data"):
                kb_result["internal_context"] = internal_context.get("context", "")
                kb_citations = kb_citations + internal_context.get("citations", [])

            # Step 2: Fetch news
            if self._news_monitor:
                articles, news_citations = await self._fetch_news(
                    competitor_name=competitor_name,
                    competitor_id=competitor_id,
                    days=days,
                    sentiment_filter=sentiment_filter,
                    event_type=event_type,
                    limit=limit
                )
            else:
                articles = []
                news_citations = []

            # Step 3: Combine citations (KB first, then news)
            all_citations = []

            # Add KB citations
            for kb_cit in kb_citations:
                all_citations.append(Citation(
                    source_id=kb_cit.get("document_id", "kb"),
                    source_type="knowledge_base",
                    content=kb_cit.get("content_preview", "Background context"),
                    confidence=kb_cit.get("similarity_score", 0.7)
                ))

            # Add news citations
            all_citations.extend(news_citations)

            # Step 4: Generate response text with KB context
            response_text = self._generate_news_summary(
                query=query,
                articles=articles,
                competitor_name=competitor_name,
                event_type=event_type,
                sentiment_filter=sentiment_filter,
                kb_context=kb_result.get("context", "")
            )

            latency = (datetime.utcnow() - start_time).total_seconds() * 1000

            return AgentResponse(
                text=response_text,
                citations=all_citations,
                agent_type=self.agent_type,
                data={
                    "articles": [self._article_to_dict(a) for a in articles],
                    "total_count": len(articles),
                    "sentiment_breakdown": self._get_sentiment_breakdown(articles),
                    "query_params": {
                        "competitor": competitor_name,
                        "days": days,
                        "event_type": event_type,
                        "sentiment_filter": sentiment_filter
                    },
                    "kb_chunks_used": kb_result.get("chunks_used", 0)
                },
                cost_usd=0.0,  # News fetching is free
                latency_ms=latency,
                tokens_used=0
            )

        except Exception as e:
            logger.error(f"News agent error: {e}")
            latency = (datetime.utcnow() - start_time).total_seconds() * 1000

            return AgentResponse(
                text=f"I encountered an error fetching news: {str(e)}. Please try again.",
                citations=[],
                agent_type=self.agent_type,
                data={"error": str(e)},
                latency_ms=latency
            )

    async def _fetch_news(
        self,
        competitor_name: Optional[str] = None,
        competitor_id: Optional[int] = None,
        days: int = 7,
        sentiment_filter: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 10
    ) -> tuple:
        """
        Fetch news articles and create citations.

        Returns:
            Tuple of (articles, citations)
        """
        articles = []
        citations = []

        if not self._news_monitor:
            return articles, citations

        try:
            # Get competitor name if we have ID
            if competitor_id and not competitor_name:
                competitor_name = await self._get_competitor_name(competitor_id)

            if competitor_name:
                # Fetch news for specific competitor
                digest = self._news_monitor.get_competitor_news(
                    company_name=competitor_name,
                    days=days
                )
                if digest:
                    articles = digest.articles
            else:
                # Fetch aggregated news from database cache
                articles = await self._get_cached_news(days=days, limit=limit * 2)

            # Apply filters
            if sentiment_filter:
                articles = [a for a in articles if a.sentiment == sentiment_filter]

            if event_type:
                articles = [a for a in articles if a.event_type == event_type]

            # Limit results
            articles = articles[:limit]

            # Create citations
            for i, article in enumerate(articles):
                citations.append(Citation(
                    source_id=f"news_{i+1}",
                    source_type="news",
                    content=f"{article.title} ({article.source})",
                    confidence=0.9 if article.is_major_event else 0.8,
                    url=article.url
                ))

        except Exception as e:
            logger.error(f"Error fetching news: {e}")

        return articles, citations

    async def _get_competitor_name(self, competitor_id: int) -> Optional[str]:
        """Get competitor name from database."""
        try:
            from database import SessionLocal, Competitor
            db = SessionLocal()
            competitor = db.query(Competitor).filter(Competitor.id == competitor_id).first()
            db.close()
            return competitor.name if competitor else None
        except Exception as e:
            logger.error(f"Error getting competitor name: {e}")
            return None

    async def _get_cached_news(self, days: int = 7, limit: int = 20) -> List:
        """Get news from database cache."""
        articles = []
        try:
            from database import SessionLocal, NewsArticleCache
            from datetime import timedelta as td

            db = SessionLocal()
            cutoff = datetime.utcnow() - td(days=days)

            cached = db.query(NewsArticleCache).filter(
                NewsArticleCache.published_at >= cutoff
            ).order_by(
                NewsArticleCache.published_at.desc()
            ).limit(limit).all()

            db.close()

            # Convert to NewsArticle format
            from news_monitor import NewsArticle
            for item in cached:
                articles.append(NewsArticle(
                    title=item.title,
                    url=item.url,
                    source=item.source,
                    published_date=item.published_at.isoformat() if item.published_at else "",
                    snippet=item.snippet or "",
                    sentiment=item.sentiment or "neutral",
                    is_major_event=item.is_major_event or False,
                    event_type=item.event_type
                ))

        except Exception as e:
            logger.error(f"Error getting cached news: {e}")

        return articles

    def _extract_competitor_from_query(self, query: str) -> Optional[str]:
        """Extract competitor name from query using patterns."""
        patterns = [
            r"news (?:for|about|on) ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'s news",
            r"what's happening (?:with|at) ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        ]

        import re
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _generate_news_summary(
        self,
        query: str,
        articles: List,
        competitor_name: Optional[str],
        event_type: Optional[str],
        sentiment_filter: Optional[str],
        kb_context: str = ""
    ) -> str:
        """
        Generate natural language summary of news.

        Args:
            query: Original user query
            articles: List of news articles
            competitor_name: Competitor being searched
            event_type: Type of event filter
            sentiment_filter: Sentiment filter applied
            kb_context: Background context from knowledge base

        Returns:
            Formatted summary string
        """
        if not articles:
            subject = competitor_name or "the requested topic"
            # Include KB context even if no news found
            if kb_context:
                return (
                    f"I couldn't find any recent news articles about {subject}. "
                    f"However, here's some background context from the knowledge base:\n\n"
                    f"{kb_context[:500]}..."
                )
            return (
                f"I couldn't find any recent news articles about {subject}. "
                "This could mean there hasn't been significant news coverage recently, "
                "or the competitor name may need to be verified."
            )

        # Build summary
        parts = []

        # Opening with KB context if available
        if competitor_name:
            parts.append(f"Here's what I found about **{competitor_name}**:")
        elif event_type:
            parts.append(f"Here are recent **{event_type.replace('_', ' ')}** announcements:")
        else:
            parts.append("Here's the latest news:")

        # Add KB background context if available
        if kb_context:
            parts.append("")
            parts.append("**Background Context:**")
            parts.append(kb_context[:300] + "..." if len(kb_context) > 300 else kb_context)

        parts.append("")

        # Sentiment overview
        breakdown = self._get_sentiment_breakdown(articles)
        if breakdown:
            sentiment_parts = []
            if breakdown.get("positive", 0) > 0:
                sentiment_parts.append(f"{breakdown['positive']} positive")
            if breakdown.get("negative", 0) > 0:
                sentiment_parts.append(f"{breakdown['negative']} negative")
            if breakdown.get("neutral", 0) > 0:
                sentiment_parts.append(f"{breakdown['neutral']} neutral")

            if sentiment_parts:
                parts.append(f"**Sentiment**: {', '.join(sentiment_parts)}")
                parts.append("")

        # Major events first
        major_events = [a for a in articles if a.is_major_event]
        if major_events:
            parts.append("**Major Events:**")
            for i, article in enumerate(major_events[:3], 1):
                event_tag = f" [{article.event_type}]" if article.event_type else ""
                src_idx = articles.index(article) + 1
                parts.append(f"{i}. {article.title}{event_tag} [Source: news_{src_idx}]")
            parts.append("")

        # Recent headlines
        non_major = [a for a in articles if not a.is_major_event][:5]
        if non_major:
            parts.append("**Recent Headlines:**")
            for i, article in enumerate(non_major, len(major_events) + 1):
                sentiment_map = {"positive": "+", "negative": "-", "neutral": "="}
                sentiment_icon = sentiment_map.get(article.sentiment, "")
                src_idx = articles.index(article) + 1
                parts.append(
                    f"- {sentiment_icon} {article.title} ({article.source}) "
                    f"[Source: news_{src_idx}]"
                )

        return "\n".join(parts)

    def _get_sentiment_breakdown(self, articles: List) -> Dict[str, int]:
        """Get sentiment counts from articles."""
        breakdown = {"positive": 0, "negative": 0, "neutral": 0}
        for article in articles:
            sentiment = getattr(article, "sentiment", "neutral")
            if sentiment in breakdown:
                breakdown[sentiment] += 1
        return breakdown

    def _article_to_dict(self, article) -> Dict[str, Any]:
        """Convert article to dictionary."""
        try:
            return asdict(article)
        except Exception:
            return {
                "title": getattr(article, "title", ""),
                "url": getattr(article, "url", ""),
                "source": getattr(article, "source", ""),
                "published_date": getattr(article, "published_date", ""),
                "sentiment": getattr(article, "sentiment", "neutral"),
                "is_major_event": getattr(article, "is_major_event", False),
                "event_type": getattr(article, "event_type", None)
            }

    # Additional methods for specific news types

    async def get_funding_news(self, days: int = 30, limit: int = 10) -> AgentResponse:
        """Get recent funding announcements."""
        return await self.process(
            "Show recent funding announcements",
            context={"event_type": "funding", "days": days, "limit": limit}
        )

    async def get_competitor_sentiment(self, competitor_name: str, days: int = 7) -> AgentResponse:
        """Get sentiment analysis for a specific competitor."""
        return await self.process(
            f"What's the sentiment for {competitor_name}?",
            context={"competitor_name": competitor_name, "days": days}
        )

    async def get_major_events(self, days: int = 7) -> AgentResponse:
        """Get all major events across competitors."""
        return await self.process(
            "What are the major events this week?",
            context={"days": days, "limit": 20}
        )
