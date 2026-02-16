"""
Certify Intel v7.0 - Agent API Router
======================================

FastAPI router for AI agent endpoints.

Endpoints:
- POST /api/agents/query - Send query to orchestrator
- POST /api/agents/dashboard - Direct dashboard queries
- POST /api/agents/discovery - Run competitor discovery
- POST /api/agents/battlecard - Generate battlecard
- GET /api/agents/status - Agent system status
- GET /api/agents/cost - Cost tracking summary

All endpoints include:
- Cost tracking
- Citation validation
- Rate limiting (10/minute for queries, 30/minute for status)
- Audit logging
- Knowledge Base integration for RAG-powered responses
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Input sanitization for security
try:
    from input_sanitizer import get_sanitizer  # noqa: F401
    INPUT_SANITIZER_AVAILABLE = True
except ImportError:
    INPUT_SANITIZER_AVAILABLE = False

# Rate limiting
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    RATE_LIMITING_AVAILABLE = True
    limiter = Limiter(key_func=get_remote_address)
except ImportError:
    RATE_LIMITING_AVAILABLE = False
    limiter = None
    logger.warning("slowapi not installed - rate limiting disabled")

router = APIRouter(prefix="/api/agents", tags=["agents"])


# =============================================================================
# RATE LIMITING HELPER
# =============================================================================

def rate_limit(limit_string: str):
    """
    Rate limiting decorator that degrades gracefully if slowapi is unavailable.

    Args:
        limit_string: Rate limit like "10/minute" or "30/minute"

    Usage:
        @rate_limit("10/minute")
        async def my_endpoint(request: Request):
            ...
    """
    def decorator(func):
        if RATE_LIMITING_AVAILABLE and limiter:
            # Apply slowapi limiter
            return limiter.limit(limit_string)(func)
        else:
            # No-op if rate limiting not available
            return func
    return decorator


# =============================================================================
# KNOWLEDGE BASE DEPENDENCY
# =============================================================================

# Cached instances for performance (singleton pattern)
_kb_instance = None
_vs_instance = None


def get_knowledge_base():
    """
    Get or create the KnowledgeBase singleton.

    This ensures all agents share the same KB instance for consistency
    and to avoid re-initializing connections on each request.
    """
    global _kb_instance
    if _kb_instance is None:
        try:
            from knowledge_base import KnowledgeBase
            _kb_instance = KnowledgeBase()
            logger.info("KnowledgeBase initialized for agent router")
        except Exception as e:
            logger.warning(f"Could not initialize KnowledgeBase: {e}")
            _kb_instance = None
    return _kb_instance


def get_vector_store():
    """
    Get or create the VectorStore singleton.
    """
    global _vs_instance
    if _vs_instance is None:
        try:
            from vector_store import VectorStore
            _vs_instance = VectorStore()
            logger.info("VectorStore initialized for agent router")
        except Exception as e:
            logger.warning(f"Could not initialize VectorStore: {e}")
            _vs_instance = None
    return _vs_instance


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class AgentQueryRequest(BaseModel):
    """Request model for agent queries."""
    query: str = Field(..., min_length=1, max_length=2000, description="Natural language query")
    user_id: Optional[str] = Field(None, description="User ID for tracking")
    session_id: Optional[str] = Field(None, description="Session ID for conversation context")
    competitor_id: Optional[int] = Field(None, description="Specific competitor ID for context")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")


class AgentQueryResponse(BaseModel):
    """Response model for agent queries."""
    response: str = Field(..., description="Agent response text")
    agent: str = Field(..., description="Agent that handled the query")
    citations: List[Dict[str, Any]] = Field(default_factory=list, description="Source citations")
    cost_usd: float = Field(0.0, description="Cost of this query in USD")
    tokens_used: int = Field(0, description="Total tokens used")
    latency_ms: float = Field(0.0, description="Response latency in milliseconds")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class DiscoveryRequest(BaseModel):
    """Request model for discovery agent."""
    target_segments: List[str] = Field(default_factory=list, description="Target market segments")
    required_capabilities: List[str] = Field(default_factory=list, description="Required capabilities")
    geography: List[str] = Field(default_factory=list, description="Geographic focus")
    funding_stages: List[str] = Field(default_factory=list, description="Funding stage filters")
    min_employees: int = Field(0, description="Minimum employee count")
    max_employees: int = Field(0, description="Maximum employee count")
    max_candidates: int = Field(10, ge=1, le=50, description="Maximum candidates to return")
    exclusions: List[str] = Field(default_factory=list, description="Categories to exclude")


class BattlecardRequest(BaseModel):
    """Request model for battlecard agent."""
    competitor_id: int = Field(..., description="Competitor ID")
    battlecard_type: str = Field("full", description="Type: full, quick, objection_handler")
    include_news: bool = Field(True, description="Include recent news")
    include_talking_points: bool = Field(True, description="Include talking points")
    focus_dimensions: Optional[List[str]] = Field(None, description="Specific dimensions to focus on")


class CostSummaryResponse(BaseModel):
    """Response model for cost summary."""
    today_spend_usd: float
    daily_budget_usd: float
    remaining_budget_usd: float
    requests_today: int
    avg_cost_per_request: float
    model_breakdown: Dict[str, float]


class AgentStatusResponse(BaseModel):
    """Response model for agent status."""
    orchestrator_available: bool
    agents_available: List[str]
    vector_store_connected: bool
    ai_router_status: str
    langfuse_connected: bool


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/query", response_model=AgentQueryResponse)
@rate_limit("10/minute")
async def agent_query(request: Request, query_request: AgentQueryRequest):
    """
    Send a query to the agent orchestrator.

    The orchestrator routes the query to the most appropriate agent
    based on keywords and context.

    Rate limited: 10 requests per minute per IP.

    Security: All queries are sanitized for SQL injection, prompt injection,
    and other attack patterns before processing.

    Example queries:
    - "What are the top threats?" → Dashboard Agent
    - "Find telehealth competitors" → Discovery Agent
    - "Generate battlecard for Epic" → Battlecard Agent
    - "Latest news about Athenahealth" → News Agent
    """
    start_time = datetime.utcnow()

    # Input sanitization
    query = query_request.query
    if INPUT_SANITIZER_AVAILABLE:
        sanitizer = get_sanitizer()
        validation_result = sanitizer.validate(query)
        if not validation_result.valid:
            logger.warning(f"Blocked query: {validation_result.blocked_reason}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid query: {validation_result.blocked_reason}"
            )
        query = validation_result.sanitized

    try:
        from agents import run_agent_query

        # Extract context parameters including page-aware agent hints
        context = query_request.context or {}
        agent_hint = context.get("agent_hint")  # From chat widget page detection
        competitor_id = query_request.competitor_id or context.get("competitor_id")
        competitor_name = context.get("competitor_name")

        result = await run_agent_query(
            query=query,  # Use sanitized query
            user_id=query_request.user_id,
            session_id=query_request.session_id,
            competitor_id=competitor_id,
            competitor_name=competitor_name,
            agent_hint=agent_hint,
            knowledge_base_context=context.get("kb_context"),
            competitor_context=context.get("competitor_context")
        )

        latency = (datetime.utcnow() - start_time).total_seconds() * 1000

        return AgentQueryResponse(
            response=result.get("response", ""),
            agent=result.get("target_agent", "unknown"),
            citations=result.get("citations", []),
            cost_usd=result.get("total_cost_usd", 0.0),
            tokens_used=result.get("total_tokens", 0),
            latency_ms=latency,
            metadata={
                "route_confidence": result.get("route_confidence", 0.0),
                "agent_outputs": result.get("agent_outputs", {})
            }
        )

    except ImportError as e:
        logger.error(f"Agent orchestrator not available: {e}")
        raise HTTPException(
            status_code=503,
            detail="Agent orchestrator not available. Please install langgraph."
        )
    except Exception as e:
        logger.error(f"Agent query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Agent query failed. Please try again.")


@router.post("/dashboard", response_model=AgentQueryResponse)
@rate_limit("10/minute")
async def dashboard_query(request: Request, query_request: AgentQueryRequest):
    """
    Direct query to Dashboard Agent.

    Rate limited: 10 requests per minute per IP.

    Best for:
    - Executive summaries
    - Threat analysis
    - Key metrics
    - Overview reports

    Uses Knowledge Base for RAG-powered responses with citations.
    """
    # Input sanitization
    query = query_request.query
    if INPUT_SANITIZER_AVAILABLE:
        sanitizer = get_sanitizer()
        validation_result = sanitizer.validate(query)
        if not validation_result.valid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid query: {validation_result.blocked_reason}"
            )
        query = validation_result.sanitized

    try:
        from agents import DashboardAgent

        # Get KB and VectorStore for RAG integration
        kb = get_knowledge_base()
        vs = get_vector_store()

        agent = DashboardAgent(knowledge_base=kb, vector_store=vs)
        result = await agent.process(
            query=query,  # Use sanitized query
            context=query_request.context
        )

        return AgentQueryResponse(
            response=result.text,
            agent="dashboard",
            citations=[c.__dict__ if hasattr(c, '__dict__') else c for c in result.citations],
            cost_usd=result.cost_usd,
            tokens_used=result.tokens_used,
            latency_ms=result.latency_ms,
            metadata=result.metadata
        )

    except Exception as e:
        logger.error(f"Dashboard query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Dashboard query failed. Please try again.")


@router.post("/discovery", response_model=AgentQueryResponse)
@rate_limit("5/minute")
async def discovery_query(
    request: Request,
    discovery_request: DiscoveryRequest,
    background_tasks: BackgroundTasks
):
    """
    Run competitor discovery.

    Rate limited: 5 requests per minute per IP (resource intensive).

    Executes the 4-stage AI discovery pipeline:
    1. Search - Find candidates via web search
    2. Scrape - Deep content extraction
    3. Qualify - AI evaluation against criteria
    4. Analyze - Threat assessment

    Uses Knowledge Base for market context during qualification.
    Note: This can take several minutes for large searches.
    """
    start_time = datetime.utcnow()

    try:
        from agents import DiscoveryAgent

        # Get KB for market intelligence context
        kb = get_knowledge_base()
        vs = get_vector_store()

        agent = DiscoveryAgent(knowledge_base=kb, vector_store=vs)
        result = await agent.process(
            query="Run discovery with provided criteria",
            context={
                "target_segments": discovery_request.target_segments,
                "required_capabilities": discovery_request.required_capabilities,
                "geography": discovery_request.geography,
                "funding_stages": discovery_request.funding_stages,
                "min_employees": discovery_request.min_employees,
                "max_employees": discovery_request.max_employees,
                "max_candidates": discovery_request.max_candidates,
                "exclusions": discovery_request.exclusions
            }
        )

        return AgentQueryResponse(
            response=result.text,
            agent="discovery",
            citations=[c.__dict__ if hasattr(c, '__dict__') else c for c in result.citations],
            cost_usd=result.cost_usd,
            tokens_used=result.tokens_used,
            latency_ms=result.latency_ms,
            metadata=result.metadata
        )

    except Exception as e:
        logger.error(f"Discovery failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Discovery query failed. Please try again.")


@router.post("/battlecard", response_model=AgentQueryResponse)
@rate_limit("10/minute")
async def battlecard_query(request: Request, battlecard_request: BattlecardRequest):
    """
    Generate a competitive battlecard.

    Rate limited: 10 requests per minute per IP.

    Types:
    - full: Complete battlecard with all sections
    - quick: 1-page summary
    - objection_handler: Focused objection handling

    Uses Knowledge Base for competitor-specific intelligence.
    """
    try:
        from agents import BattlecardAgent
        from database import SessionLocal

        # Get KB for competitor intelligence
        kb = get_knowledge_base()
        vs = get_vector_store()

        db = SessionLocal()
        try:
            agent = BattlecardAgent(knowledge_base=kb, vector_store=vs, db_session=db)
            result = await agent.process(
                query=f"Generate {battlecard_request.battlecard_type} battlecard",
                context={
                    "competitor_id": battlecard_request.competitor_id,
                    "battlecard_type": battlecard_request.battlecard_type,
                    "include_news": battlecard_request.include_news,
                    "include_talking_points": battlecard_request.include_talking_points,
                    "focus_dimensions": battlecard_request.focus_dimensions
                }
            )

            return AgentQueryResponse(
                response=result.text,
                agent="battlecard",
                citations=[c.__dict__ if hasattr(c, '__dict__') else c for c in result.citations],
                cost_usd=result.cost_usd,
                tokens_used=result.tokens_used,
                latency_ms=result.latency_ms,
                metadata=result.metadata
            )
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Battlecard generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Battlecard generation failed. Please try again.")


@router.get("/status", response_model=AgentStatusResponse)
@rate_limit("30/minute")
async def agent_status(request: Request):
    """
    Get agent system status.

    Rate limited: 30 requests per minute per IP.

    Returns availability of all components including Knowledge Base.
    """
    status = AgentStatusResponse(
        orchestrator_available=False,
        agents_available=[],
        vector_store_connected=False,
        ai_router_status="unknown",
        langfuse_connected=False
    )

    # Check orchestrator
    try:
        from agents import get_orchestrator
        orch = get_orchestrator()
        status.orchestrator_available = orch is not None
    except (ImportError, Exception) as e:
        logger.debug(f"Orchestrator not available: {e}")

    # Check agents
    try:
        from agents import (  # noqa: F401 - import to check availability
            DashboardAgent, DiscoveryAgent, BattlecardAgent,
            NewsAgent, AnalyticsAgent, ValidationAgent, RecordsAgent
        )
        status.agents_available = [
            "dashboard", "discovery", "battlecard",
            "news", "analytics", "validation", "records"
        ]
    except (ImportError, Exception) as e:
        logger.debug(f"Some agents not available: {e}")

    # Check AI router (use singleton to avoid re-initializing on every status check)
    try:
        from ai_router import get_ai_router
        router_instance = get_ai_router()
        status.ai_router_status = "active" if router_instance else "unavailable"
    except (ImportError, Exception) as e:
        logger.debug(f"AI router not available: {e}")
        status.ai_router_status = "unavailable"

    # Check Langfuse
    try:
        from observability import get_langfuse
        langfuse = get_langfuse()
        status.langfuse_connected = langfuse is not None
    except (ImportError, Exception) as e:
        logger.debug(f"Langfuse not available: {e}")

    # Check Knowledge Base / Vector Store connection
    try:
        kb = get_knowledge_base()
        vs = get_vector_store()
        status.vector_store_connected = (kb is not None) or (vs is not None)
    except (ImportError, Exception) as e:
        logger.debug(f"KB/Vector store not available: {e}")

    return status


@router.get("/cost", response_model=CostSummaryResponse)
@rate_limit("30/minute")
async def cost_summary(request: Request):
    """
    Get AI cost tracking summary.

    Rate limited: 30 requests per minute per IP.

    Returns today's spending, budget, and breakdown by model.
    """
    try:
        from ai_router import get_ai_router

        router_instance = get_ai_router()
        tracker = router_instance.cost_tracker

        return CostSummaryResponse(
            today_spend_usd=tracker.get_today_spend(),
            daily_budget_usd=tracker.daily_budget_usd,
            remaining_budget_usd=tracker.daily_budget_usd - tracker.get_today_spend(),
            requests_today=len([u for u in tracker.usage_history if u.timestamp.date() == datetime.utcnow().date()]),
            avg_cost_per_request=tracker.get_today_spend() / max(1, len(tracker.usage_history)),
            model_breakdown=tracker.get_usage_summary().get("by_model", {})
        )

    except Exception as e:
        logger.error(f"Cost summary failed: {e}")
        return CostSummaryResponse(
            today_spend_usd=0.0,
            daily_budget_usd=50.0,
            remaining_budget_usd=50.0,
            requests_today=0,
            avg_cost_per_request=0.0,
            model_breakdown={}
        )


@router.post("/news", response_model=AgentQueryResponse)
@rate_limit("10/minute")
async def news_query(request: Request, query_request: AgentQueryRequest):
    """
    Query News Agent for real-time news and sentiment.

    Rate limited: 10 requests per minute per IP.

    Best for:
    - Competitor news monitoring
    - Sentiment analysis
    - Funding/acquisition alerts
    - Major event detection

    Uses Knowledge Base for historical context.
    """
    # Input sanitization
    query = query_request.query
    if INPUT_SANITIZER_AVAILABLE:
        sanitizer = get_sanitizer()
        validation_result = sanitizer.validate(query)
        if not validation_result.valid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid query: {validation_result.blocked_reason}"
            )
        query = validation_result.sanitized

    try:
        from agents import NewsAgent

        # Get KB for historical news context
        kb = get_knowledge_base()
        vs = get_vector_store()

        agent = NewsAgent(knowledge_base=kb, vector_store=vs)
        result = await agent.process(
            query=query,
            context=query_request.context
        )

        return AgentQueryResponse(
            response=result.text,
            agent="news",
            citations=[c.__dict__ if hasattr(c, '__dict__') else c for c in result.citations],
            cost_usd=result.cost_usd,
            tokens_used=result.tokens_used,
            latency_ms=result.latency_ms,
            metadata=result.data if result.data else {}
        )

    except Exception as e:
        logger.error(f"News query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="News query failed. Please try again.")


@router.post("/analytics", response_model=AgentQueryResponse)
@rate_limit("10/minute")
async def analytics_query(request: Request, query_request: AgentQueryRequest):
    """
    Query Analytics Agent for market analysis.

    Rate limited: 10 requests per minute per IP.

    Best for:
    - Executive summaries
    - Market positioning
    - Win/loss trends
    - Data-driven reports

    Uses Knowledge Base for strategic planning documents.
    """
    # Input sanitization
    query = query_request.query
    if INPUT_SANITIZER_AVAILABLE:
        sanitizer = get_sanitizer()
        validation_result = sanitizer.validate(query)
        if not validation_result.valid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid query: {validation_result.blocked_reason}"
            )
        query = validation_result.sanitized

    try:
        from agents import AnalyticsAgent

        # Get KB for strategic insights
        kb = get_knowledge_base()
        vs = get_vector_store()

        agent = AnalyticsAgent(knowledge_base=kb, vector_store=vs)
        result = await agent.process(
            query=query,
            context=query_request.context
        )

        return AgentQueryResponse(
            response=result.text,
            agent="analytics",
            citations=[c.__dict__ if hasattr(c, '__dict__') else c for c in result.citations],
            cost_usd=result.cost_usd,
            tokens_used=result.tokens_used,
            latency_ms=result.latency_ms,
            metadata=result.data if result.data else {}
        )

    except Exception as e:
        logger.error(f"Analytics query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Analytics query failed. Please try again.")


@router.post("/validation", response_model=AgentQueryResponse)
@rate_limit("10/minute")
async def validation_query(request: Request, query_request: AgentQueryRequest):
    """
    Query Validation Agent for data confidence scoring.

    Rate limited: 10 requests per minute per IP.

    Best for:
    - Data quality reports
    - Admiralty Code scoring
    - Low confidence data alerts
    - Source verification
    """
    # Input sanitization
    query = query_request.query
    if INPUT_SANITIZER_AVAILABLE:
        sanitizer = get_sanitizer()
        validation_result = sanitizer.validate(query)
        if not validation_result.valid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid query: {validation_result.blocked_reason}"
            )
        query = validation_result.sanitized

    try:
        from agents import ValidationAgent

        kb = get_knowledge_base()
        vs = get_vector_store()
        agent = ValidationAgent(knowledge_base=kb, vector_store=vs)
        result = await agent.process(
            query=query,
            context=query_request.context
        )

        return AgentQueryResponse(
            response=result.text,
            agent="validation",
            citations=[c.__dict__ if hasattr(c, '__dict__') else c for c in result.citations],
            cost_usd=result.cost_usd,
            tokens_used=result.tokens_used,
            latency_ms=result.latency_ms,
            metadata=result.data if result.data else {}
        )

    except Exception as e:
        logger.error(f"Validation query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Validation query failed. Please try again.")


@router.post("/records", response_model=AgentQueryResponse)
@rate_limit("10/minute")
async def records_query(request: Request, query_request: AgentQueryRequest):
    """
    Query Records Agent for change tracking and audit.

    Rate limited: 10 requests per minute per IP.

    Best for:
    - Change history
    - Activity logs
    - Audit reports
    - Who changed what
    """
    # Input sanitization
    query = query_request.query
    if INPUT_SANITIZER_AVAILABLE:
        sanitizer = get_sanitizer()
        validation_result = sanitizer.validate(query)
        if not validation_result.valid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid query: {validation_result.blocked_reason}"
            )
        query = validation_result.sanitized

    try:
        from agents import RecordsAgent

        kb = get_knowledge_base()
        vs = get_vector_store()
        agent = RecordsAgent(knowledge_base=kb, vector_store=vs)
        result = await agent.process(
            query=query,
            context=query_request.context
        )

        return AgentQueryResponse(
            response=result.text,
            agent="records",
            citations=[c.__dict__ if hasattr(c, '__dict__') else c for c in result.citations],
            cost_usd=result.cost_usd,
            tokens_used=result.tokens_used,
            latency_ms=result.latency_ms,
            metadata=result.data if result.data else {}
        )

    except Exception as e:
        logger.error(f"Records query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Records query failed. Please try again.")


@router.post("/knowledge-base/search")
async def kb_search(
    query: str,
    limit: int = 5,
    min_similarity: float = 0.7
):
    """
    Search the knowledge base.

    Returns relevant document chunks with similarity scores.
    """
    try:
        from knowledge_base import KnowledgeBase

        kb = KnowledgeBase()
        results = await kb.search(
            query=query,
            limit=limit,
            min_similarity=min_similarity
        )

        return {
            "query": query,
            "results": [
                {
                    "chunk_id": r.chunk_id,
                    "document_id": r.document_id,
                    "content": r.content,
                    "similarity": r.similarity,
                    "metadata": r.metadata
                }
                for r in results
            ],
            "count": len(results)
        }

    except Exception as e:
        logger.error(f"KB search failed: {e}")
        raise HTTPException(status_code=500, detail="Knowledge base search failed. Please try again.")


@router.post("/knowledge-base/context")
async def kb_context(
    query: str,
    max_chunks: int = 5,
    max_tokens: int = 4000
):
    """
    Get RAG context for a query.

    Returns formatted context with citations for use in prompts.
    """
    try:
        from knowledge_base import KnowledgeBase

        kb = KnowledgeBase()
        context = await kb.get_context_for_query(
            query=query,
            max_chunks=max_chunks,
            max_tokens=max_tokens
        )

        return context

    except Exception as e:
        logger.error(f"KB context failed: {e}")
        raise HTTPException(status_code=500, detail="Knowledge base context retrieval failed. Please try again.")
