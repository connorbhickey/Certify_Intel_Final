"""
Certify Intel v7.0 - LangGraph Agent Orchestrator
==================================================

Central orchestration for all AI agents using LangGraph StateGraph.

Features:
- Stateful multi-agent workflows
- Automatic persistence and checkpointing
- Conditional routing based on query type
- Citation validation on all outputs
- Cost tracking and budget enforcement

Architecture:
    User Query -> Route Query -> Selected Agent -> Citation Validator -> Response

Agents:
    - dashboard: Executive summaries, threat analysis
    - discovery: Competitor discovery and qualification
    - battlecard: Sales battlecard generation
    - news: News monitoring and sentiment
    - analytics: Market analysis and reporting
    - validation: Data validation with confidence scoring
    - records: Change tracking and audit logs
"""

import os
import logging
import threading
from typing import TypedDict, Annotated, Optional, Any, Dict, List
from datetime import datetime
import operator

logger = logging.getLogger(__name__)

# Try to import LangGraph - graceful fallback if not installed
try:
    from langgraph.graph import StateGraph, END
    from langgraph.checkpoint.memory import MemorySaver
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    logger.warning("LangGraph not installed. Agent orchestration disabled.")
    logger.warning("Install with: pip install langgraph langgraph-checkpoint")

# Try to import SqliteSaver for persistent checkpointing
try:
    from langgraph.checkpoint.sqlite import SqliteSaver
    SQLITE_SAVER_AVAILABLE = True
except ImportError:
    SQLITE_SAVER_AVAILABLE = False
    logger.info("SqliteSaver not available. Using MemorySaver for checkpointing.")


# =============================================================================
# STATE DEFINITION
# =============================================================================

class AgentState(TypedDict):
    """
    Shared state passed between LangGraph nodes.

    All agents read from and write to this state.
    """
    # Input
    user_query: str
    user_id: Optional[str]
    session_id: Optional[str]
    competitor_id: Optional[int]
    competitor_name: Optional[str]
    agent_hint: Optional[str]  # Hint from UI about which agent to prefer

    # Routing
    target_agent: str
    route_confidence: float

    # Context (accumulated by agents)
    messages: Annotated[List[Dict[str, Any]], operator.add]
    knowledge_base_context: List[Dict[str, Any]]
    competitor_context: List[Dict[str, Any]]

    # Output
    agent_outputs: Dict[str, Any]
    citations: List[Dict[str, Any]]
    final_response: str

    # Control flow
    task_complete: bool
    error: Optional[str]

    # Cost tracking
    total_cost_usd: float
    total_tokens: int


# =============================================================================
# ROUTING LOGIC
# =============================================================================

AGENT_KEYWORDS = {
    "dashboard": [
        "summary", "executive", "overview", "status", "threat", "threats",
        "top", "main", "key", "important", "highlight", "brief", "dashboard"
    ],
    "discovery": [
        "discover", "find new", "search for", "emerging", "identify",
        "qualification", "qualify", "scan for", "scout"
    ],
    "battlecard": [
        "battlecard", "sales", "compete", "win", "objection", "counter",
        "talking point", "pitch", "deal", "versus", "vs"
    ],
    "news": [
        "news", "article", "press", "announcement", "recent news", "latest news",
        "news about", "release", "mention", "media", "coverage", "headlines"
    ],
    "analytics": [
        "analytics", "analysis", "analyze", "report", "chart", "graph",
        "trend", "metric", "market share", "insight"
    ],
    "validation": [
        "validate", "verify", "confidence", "accuracy", "source", "trust",
        "reliable", "quality", "data quality", "verify this"
    ],
    "records": [
        "change log", "history", "log", "record", "track", "when was", "modified",
        "updated", "who changed", "audit trail", "timeline"
    ]
}


def route_query(query: str) -> tuple[str, float]:
    """
    Route query to the most appropriate agent.

    Returns (agent_name, confidence_score).
    """
    query_lower = query.lower()

    # Score each agent based on keyword matches
    scores = {}
    for agent, keywords in AGENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in query_lower)
        if score > 0:
            scores[agent] = score

    if not scores:
        # Default to dashboard for general queries
        return ("dashboard", 0.5)

    # Return highest scoring agent
    best_agent = max(scores, key=scores.get)
    max_score = scores[best_agent]

    # Normalize confidence (max possible is ~10 keywords)
    confidence = min(max_score / 3.0, 1.0)

    return (best_agent, confidence)


# =============================================================================
# KNOWLEDGE BASE HELPERS
# =============================================================================

# Cached KB instances for orchestrator nodes (thread-safe)
_orchestrator_kb = None
_orchestrator_vs = None
_kb_lock = threading.Lock()


def _get_kb_for_orchestrator():
    """Get KnowledgeBase instance for orchestrator nodes (thread-safe)."""
    global _orchestrator_kb
    if _orchestrator_kb is None:
        with _kb_lock:
            if _orchestrator_kb is None:
                try:
                    from knowledge_base import KnowledgeBase
                    _orchestrator_kb = KnowledgeBase()
                    logger.info("KnowledgeBase initialized for orchestrator")
                except Exception as e:
                    logger.warning(f"Could not initialize KnowledgeBase: {e}")
    return _orchestrator_kb


def _get_vs_for_orchestrator():
    """Get VectorStore instance for orchestrator nodes (thread-safe)."""
    global _orchestrator_vs
    if _orchestrator_vs is None:
        with _kb_lock:
            if _orchestrator_vs is None:
                try:
                    from vector_store import VectorStore
                    _orchestrator_vs = VectorStore()
                    logger.info("VectorStore initialized for orchestrator")
                except Exception as e:
                    logger.warning(f"Could not initialize VectorStore: {e}")
    return _orchestrator_vs


# =============================================================================
# NODE FUNCTIONS
# =============================================================================

async def route_query_node(state: AgentState) -> AgentState:
    """
    LangGraph node: Route query to appropriate agent.

    If an agent_hint is provided (from UI page context), it will be used
    as a boost to the routing decision, but not a hard override. This allows
    the chat to be context-aware while still respecting the query content.
    """
    query = state.get("user_query", "")
    agent_hint = state.get("agent_hint")

    # Route based on query content
    target_agent, confidence = route_query(query)

    # If an agent hint is provided and the confidence is low, prefer the hint
    if agent_hint and agent_hint in AGENT_KEYWORDS:
        if confidence < 0.6:
            # Low confidence on content-based routing, use the hint
            logger.info(f"Using agent_hint '{agent_hint}' due to low routing confidence ({confidence:.2f})")
            target_agent = agent_hint
            # Boost confidence slightly since we have context
            confidence = max(confidence, 0.5)
        elif target_agent != agent_hint:
            # Query routing was confident but different from hint - log for debugging
            logger.debug(f"Ignoring agent_hint '{agent_hint}' in favor of content-based routing to '{target_agent}'")

    logger.info(f"Routing query to {target_agent} (confidence: {confidence:.2f})")

    return {
        **state,
        "target_agent": target_agent,
        "route_confidence": confidence,
        "messages": [{"role": "system", "content": f"Routed to {target_agent}"}]
    }


async def dashboard_agent_node(state: AgentState) -> AgentState:
    """
    LangGraph node: Dashboard Agent - Executive summaries and threat analysis.
    """
    logger.info("Dashboard Agent processing...")

    try:
        from .dashboard_agent import DashboardAgent

        # Get KB for RAG integration
        kb = _get_kb_for_orchestrator()
        vs = _get_vs_for_orchestrator()

        # Create agent with KB
        agent = DashboardAgent(knowledge_base=kb, vector_store=vs)
        context = {
            "competitor_ids": [state.get("competitor_id")] if state.get("competitor_id") else [],
            "kb_context": state.get("knowledge_base_context", []),
            "competitor_context": state.get("competitor_context", [])
        }

        response = await agent.process(
            query=state.get("user_query", ""),
            context=context
        )

        # Convert citations to dict format
        citations = [
            {
                "source_id": c.source_id,
                "source_type": c.source_type,
                "content": c.content,
                "confidence": c.confidence
            }
            for c in response.citations
        ]

        return {
            **state,
            "agent_outputs": {"dashboard": {"summary": response.text, "metadata": response.metadata}},
            "final_response": response.text,
            "citations": citations,
            "total_cost_usd": state.get("total_cost_usd", 0) + response.cost_usd,
            "total_tokens": state.get("total_tokens", 0) + response.tokens_used,
            "messages": [{"role": "assistant", "content": response.text}],
            "task_complete": False  # Continue to citation validator
        }

    except Exception as e:
        logger.error(f"Dashboard agent error: {e}", exc_info=True)
        return {
            **state,
            "final_response": f"I encountered an error while processing your request: {str(e)}",
            "citations": [],
            "task_complete": True,
            "error": str(e)
        }


async def discovery_agent_node(state: AgentState) -> AgentState:
    """
    LangGraph node: Discovery Agent - Competitor discovery and qualification.
    """
    logger.info("Discovery Agent processing...")

    try:
        from .discovery_agent import DiscoveryAgent

        # Get KB for market intelligence
        kb = _get_kb_for_orchestrator()
        vs = _get_vs_for_orchestrator()

        agent = DiscoveryAgent(knowledge_base=kb, vector_store=vs)
        context = {
            "kb_context": state.get("knowledge_base_context", []),
            "competitor_context": state.get("competitor_context", [])
        }

        response = await agent.process(
            query=state.get("user_query", ""),
            context=context
        )

        citations = [
            {"source_id": c.source_id, "source_type": c.source_type, "content": c.content, "confidence": c.confidence}
            for c in response.citations
        ]

        return {
            **state,
            "agent_outputs": {"discovery": {"candidates": response.data or [], "summary": response.text}},
            "final_response": response.text,
            "citations": citations,
            "total_cost_usd": state.get("total_cost_usd", 0) + response.cost_usd,
            "total_tokens": state.get("total_tokens", 0) + response.tokens_used,
            "messages": [{"role": "assistant", "content": response.text}],
            "task_complete": False
        }

    except Exception as e:
        logger.error(f"Discovery agent error: {e}", exc_info=True)
        return {
            **state,
            "final_response": f"Discovery agent error: {str(e)}",
            "citations": [],
            "task_complete": True,
            "error": str(e)
        }


async def battlecard_agent_node(state: AgentState) -> AgentState:
    """
    LangGraph node: Battlecard Agent - Sales battlecard generation.
    """
    logger.info("Battlecard Agent processing...")

    try:
        from .battlecard_agent import BattlecardAgent

        # Get KB for competitor intelligence
        kb = _get_kb_for_orchestrator()
        vs = _get_vs_for_orchestrator()

        from database import SessionLocal
        db = SessionLocal()
        try:
            agent = BattlecardAgent(knowledge_base=kb, vector_store=vs, db_session=db)
            context = {
                "competitor_id": state.get("competitor_id"),
                "kb_context": state.get("knowledge_base_context", []),
                "competitor_context": state.get("competitor_context", [])
            }

            response = await agent.process(
                query=state.get("user_query", ""),
                context=context
            )

            citations = [
                {"source_id": c.source_id, "source_type": c.source_type, "content": c.content, "confidence": c.confidence}
                for c in response.citations
            ]

            return {
                **state,
                "agent_outputs": {"battlecard": {"content": response.text, "data": response.data}},
                "final_response": response.text,
                "citations": citations,
                "total_cost_usd": state.get("total_cost_usd", 0) + response.cost_usd,
                "total_tokens": state.get("total_tokens", 0) + response.tokens_used,
                "messages": [{"role": "assistant", "content": response.text}],
                "task_complete": False
            }
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Battlecard agent error: {e}", exc_info=True)
        return {
            **state,
            "final_response": f"Battlecard agent error: {str(e)}",
            "citations": [],
            "task_complete": True,
            "error": str(e)
        }


async def news_agent_node(state: AgentState) -> AgentState:
    """
    LangGraph node: News Agent - News monitoring and sentiment analysis.
    """
    logger.info("News Agent processing...")

    try:
        from .news_agent import NewsAgent

        # Get KB for historical context
        kb = _get_kb_for_orchestrator()
        vs = _get_vs_for_orchestrator()

        agent = NewsAgent(knowledge_base=kb, vector_store=vs)
        context = {
            "competitor_id": state.get("competitor_id"),
            "kb_context": state.get("knowledge_base_context", []),
            "competitor_context": state.get("competitor_context", [])
        }

        response = await agent.process(
            query=state.get("user_query", ""),
            context=context
        )

        citations = [
            {"source_id": c.source_id, "source_type": c.source_type, "content": c.content, "confidence": c.confidence}
            for c in response.citations
        ]

        return {
            **state,
            "agent_outputs": {"news": {"articles": response.data or [], "summary": response.text}},
            "final_response": response.text,
            "citations": citations,
            "total_cost_usd": state.get("total_cost_usd", 0) + response.cost_usd,
            "total_tokens": state.get("total_tokens", 0) + response.tokens_used,
            "messages": [{"role": "assistant", "content": response.text}],
            "task_complete": False
        }

    except Exception as e:
        logger.error(f"News agent error: {e}", exc_info=True)
        return {
            **state,
            "final_response": f"News agent error: {str(e)}",
            "citations": [],
            "task_complete": True,
            "error": str(e)
        }


async def analytics_agent_node(state: AgentState) -> AgentState:
    """
    LangGraph node: Analytics Agent - Market analysis and reporting.
    """
    logger.info("Analytics Agent processing...")

    try:
        from .analytics_agent import AnalyticsAgent

        # Get KB for strategic insights
        kb = _get_kb_for_orchestrator()
        vs = _get_vs_for_orchestrator()

        agent = AnalyticsAgent(knowledge_base=kb, vector_store=vs)
        context = {
            "competitor_id": state.get("competitor_id"),
            "kb_context": state.get("knowledge_base_context", []),
            "competitor_context": state.get("competitor_context", [])
        }

        response = await agent.process(
            query=state.get("user_query", ""),
            context=context
        )

        citations = [
            {"source_id": c.source_id, "source_type": c.source_type, "content": c.content, "confidence": c.confidence}
            for c in response.citations
        ]

        return {
            **state,
            "agent_outputs": {"analytics": {"charts": response.data or {}, "insights": response.text}},
            "final_response": response.text,
            "citations": citations,
            "total_cost_usd": state.get("total_cost_usd", 0) + response.cost_usd,
            "total_tokens": state.get("total_tokens", 0) + response.tokens_used,
            "messages": [{"role": "assistant", "content": response.text}],
            "task_complete": False
        }

    except Exception as e:
        logger.error(f"Analytics agent error: {e}", exc_info=True)
        return {
            **state,
            "final_response": f"Analytics agent error: {str(e)}",
            "citations": [],
            "task_complete": True,
            "error": str(e)
        }


async def validation_agent_node(state: AgentState) -> AgentState:
    """
    LangGraph node: Validation Agent - Data validation with confidence scoring.
    """
    logger.info("Validation Agent processing...")

    try:
        from .validation_agent import ValidationAgent

        kb = _get_kb_for_orchestrator()
        vs = _get_vs_for_orchestrator()
        agent = ValidationAgent(knowledge_base=kb, vector_store=vs)
        context = {
            "competitor_id": state.get("competitor_id"),
            "kb_context": state.get("knowledge_base_context", []),
            "competitor_context": state.get("competitor_context", [])
        }

        response = await agent.process(
            query=state.get("user_query", ""),
            context=context
        )

        citations = [
            {"source_id": c.source_id, "source_type": c.source_type, "content": c.content, "confidence": c.confidence}
            for c in response.citations
        ]

        return {
            **state,
            "agent_outputs": {"validation": {"confidence_scores": response.data or {}, "summary": response.text}},
            "final_response": response.text,
            "citations": citations,
            "total_cost_usd": state.get("total_cost_usd", 0) + response.cost_usd,
            "total_tokens": state.get("total_tokens", 0) + response.tokens_used,
            "messages": [{"role": "assistant", "content": response.text}],
            "task_complete": False
        }

    except Exception as e:
        logger.error(f"Validation agent error: {e}", exc_info=True)
        return {
            **state,
            "final_response": f"Validation agent error: {str(e)}",
            "citations": [],
            "task_complete": True,
            "error": str(e)
        }


async def records_agent_node(state: AgentState) -> AgentState:
    """
    LangGraph node: Records Agent - Change tracking and audit logs.
    """
    logger.info("Records Agent processing...")

    try:
        from .records_agent import RecordsAgent

        kb = _get_kb_for_orchestrator()
        vs = _get_vs_for_orchestrator()
        agent = RecordsAgent(knowledge_base=kb, vector_store=vs)
        context = {
            "competitor_id": state.get("competitor_id"),
            "kb_context": state.get("knowledge_base_context", []),
            "competitor_context": state.get("competitor_context", [])
        }

        response = await agent.process(
            query=state.get("user_query", ""),
            context=context
        )

        citations = [
            {"source_id": c.source_id, "source_type": c.source_type, "content": c.content, "confidence": c.confidence}
            for c in response.citations
        ]

        return {
            **state,
            "agent_outputs": {"records": {"changes": response.data or [], "summary": response.text}},
            "final_response": response.text,
            "citations": citations,
            "total_cost_usd": state.get("total_cost_usd", 0) + response.cost_usd,
            "total_tokens": state.get("total_tokens", 0) + response.tokens_used,
            "messages": [{"role": "assistant", "content": response.text}],
            "task_complete": False
        }

    except Exception as e:
        logger.error(f"Records agent error: {e}", exc_info=True)
        return {
            **state,
            "final_response": f"Records agent error: {str(e)}",
            "citations": [],
            "task_complete": True,
            "error": str(e)
        }


async def citation_validator_node(state: AgentState) -> AgentState:
    """
    LangGraph node: Validate citations in agent responses.

    CRITICAL: All agent outputs pass through this node to ensure
    no hallucinated citations.
    """
    logger.info("Citation Validator processing...")

    citations = state.get("citations", [])
    kb_context = state.get("knowledge_base_context", [])

    # Get valid source IDs from context
    valid_source_ids = {doc.get("id") for doc in kb_context}

    # Validate each citation
    invalid_citations = []
    for citation in citations:
        source_id = citation.get("source_id")
        if source_id and source_id not in valid_source_ids:
            if citation.get("source_type") != "competitor":  # Competitors validated separately
                invalid_citations.append(citation)

    if invalid_citations:
        logger.warning(f"Found {len(invalid_citations)} invalid citations")
        # Remove invalid citations from response
        valid_citations = [c for c in citations if c not in invalid_citations]
        return {
            **state,
            "citations": valid_citations,
            "task_complete": True,
            "messages": [{"role": "system", "content": f"Removed {len(invalid_citations)} invalid citations"}]
        }

    return {
        **state,
        "task_complete": True,
        "messages": [{"role": "system", "content": "Citations validated"}]
    }


# =============================================================================
# WORKFLOW DEFINITION
# =============================================================================

def determine_agent(state: AgentState) -> str:
    """Conditional edge function: return target agent name."""
    return state.get("target_agent", "dashboard")


def is_task_complete(state: AgentState) -> str:
    """Conditional edge function: check if task is complete."""
    if state.get("task_complete", False):
        return "end"
    return "route_query"


def get_checkpointer(use_sqlite: bool = True, db_path: str = None):
    """
    Get the appropriate checkpointer for LangGraph.

    Args:
        use_sqlite: If True, use SqliteSaver for persistence. Falls back to MemorySaver if unavailable.
        db_path: Path to SQLite database file. Defaults to langgraph_checkpoints.db in backend folder.

    Returns:
        Checkpointer instance (SqliteSaver or MemorySaver).
    """
    if use_sqlite and SQLITE_SAVER_AVAILABLE:
        if db_path is None:
            # Default to backend folder
            db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "langgraph_checkpoints.db")
        try:
            import sqlite3
            conn = sqlite3.connect(db_path, check_same_thread=False)
            checkpointer = SqliteSaver(conn)
            logger.info(f"Using SqliteSaver for LangGraph persistence: {db_path}")
            return checkpointer
        except Exception as e:
            logger.warning(f"Failed to initialize SqliteSaver: {e}. Falling back to MemorySaver.")

    logger.info("Using MemorySaver for LangGraph checkpointing (non-persistent)")
    return MemorySaver()


def build_orchestrator(use_sqlite_persistence: bool = True):
    """
    Build the LangGraph workflow.

    Args:
        use_sqlite_persistence: If True, use SqliteSaver for persistent checkpoints.
                               Set to False for in-memory only (faster but non-persistent).

    Returns compiled StateGraph with checkpointing.
    """
    if not LANGGRAPH_AVAILABLE:
        logger.error("Cannot build orchestrator - LangGraph not installed")
        return None

    # Create workflow
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("route_query", route_query_node)
    workflow.add_node("dashboard", dashboard_agent_node)
    workflow.add_node("discovery", discovery_agent_node)
    workflow.add_node("battlecard", battlecard_agent_node)
    workflow.add_node("news", news_agent_node)
    workflow.add_node("analytics", analytics_agent_node)
    workflow.add_node("validation", validation_agent_node)
    workflow.add_node("records", records_agent_node)
    workflow.add_node("citation_validator", citation_validator_node)

    # Set entry point
    workflow.set_entry_point("route_query")

    # Add conditional routing from route_query to agents
    workflow.add_conditional_edges(
        "route_query",
        determine_agent,
        {
            "dashboard": "dashboard",
            "discovery": "discovery",
            "battlecard": "battlecard",
            "news": "news",
            "analytics": "analytics",
            "validation": "validation",
            "records": "records"
        }
    )

    # All agents go to citation validator
    workflow.add_edge("dashboard", "citation_validator")
    workflow.add_edge("discovery", "citation_validator")
    workflow.add_edge("battlecard", "citation_validator")
    workflow.add_edge("news", "citation_validator")
    workflow.add_edge("analytics", "citation_validator")
    workflow.add_edge("validation", "citation_validator")
    workflow.add_edge("records", "citation_validator")

    # Citation validator goes to end or back to route (for multi-turn)
    workflow.add_conditional_edges(
        "citation_validator",
        is_task_complete,
        {
            "end": END,
            "route_query": "route_query"
        }
    )

    # Get checkpointer (SqliteSaver for persistence, MemorySaver as fallback)
    checkpointer = get_checkpointer(use_sqlite=use_sqlite_persistence)

    # Compile workflow
    app = workflow.compile(checkpointer=checkpointer)

    logger.info("LangGraph orchestrator built successfully")
    return app


# =============================================================================
# PUBLIC API
# =============================================================================

_orchestrator = None


def get_orchestrator():
    """
    Get or create the orchestrator instance.

    Returns compiled LangGraph workflow.
    """
    global _orchestrator

    if _orchestrator is None:
        _orchestrator = build_orchestrator()

    return _orchestrator


async def run_agent_query(
    query: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    competitor_id: Optional[int] = None,
    competitor_name: Optional[str] = None,
    agent_hint: Optional[str] = None,
    knowledge_base_context: Optional[List[Dict]] = None,
    competitor_context: Optional[List[Dict]] = None
) -> Dict[str, Any]:
    """
    Run a query through the agent orchestrator.

    Args:
        query: User's natural language query
        user_id: Optional user ID for tracking
        session_id: Optional session ID for tracking
        competitor_id: Optional competitor ID for context
        competitor_name: Optional competitor name for context
        agent_hint: Optional hint about which agent to prefer (from UI page context)
        knowledge_base_context: Optional pre-fetched KB context
        competitor_context: Optional pre-fetched competitor data

    Returns:
        Dict with response, citations, agent_outputs, and metadata
    """
    orchestrator = get_orchestrator()

    if orchestrator is None:
        return {
            "error": "Agent orchestrator not available. Please install langgraph.",
            "response": "I'm unable to process your request at this time."
        }

    # Build initial state
    initial_state = {
        "user_query": query,
        "user_id": user_id,
        "session_id": session_id,
        "competitor_id": competitor_id,
        "competitor_name": competitor_name,
        "agent_hint": agent_hint,
        "target_agent": "",
        "route_confidence": 0.0,
        "messages": [],
        "knowledge_base_context": knowledge_base_context or [],
        "competitor_context": competitor_context or [],
        "agent_outputs": {},
        "citations": [],
        "final_response": "",
        "task_complete": False,
        "error": None,
        "total_cost_usd": 0.0,
        "total_tokens": 0
    }

    # Create thread config for checkpointing
    config = {
        "configurable": {
            "thread_id": session_id or f"query_{datetime.utcnow().isoformat()}"
        }
    }

    # Run workflow
    result = await orchestrator.ainvoke(initial_state, config)

    return {
        "response": result.get("final_response", ""),
        "citations": result.get("citations", []),
        "agent_outputs": result.get("agent_outputs", {}),
        "target_agent": result.get("target_agent", ""),
        "route_confidence": result.get("route_confidence", 0.0),
        "total_cost_usd": result.get("total_cost_usd", 0.0),
        "total_tokens": result.get("total_tokens", 0)
    }


# =============================================================================
# CLI FOR TESTING
# =============================================================================

if __name__ == "__main__":
    import asyncio

    async def test():
        print("Testing Agent Orchestrator\n")

        # Test routing
        test_queries = [
            "What are the top threats to our business?",
            "Find new competitors in the healthcare space",
            "Generate a battlecard for Epic Systems",
            "What's the latest news about Athenahealth?",
            "Show me market share trends",
            "Verify the customer count for Cerner",
            "When was Phreesia's pricing last updated?"
        ]

        print("Query Routing Test:")
        print("-" * 50)
        for query in test_queries:
            agent, confidence = route_query(query)
            print(f"  '{query[:40]}...'")
            print(f"    -> {agent} (confidence: {confidence:.2f})")
            print()

        # Test full workflow (if LangGraph available)
        if LANGGRAPH_AVAILABLE:
            print("\nFull Workflow Test:")
            print("-" * 50)
            result = await run_agent_query(
                "What are the top 3 threats?",
                user_id="test_user",
                session_id="test_session"
            )
            print(f"Target Agent: {result.get('target_agent')}")
            print(f"Response: {result.get('response')[:200]}...")
        else:
            print("\nSkipping workflow test - LangGraph not installed")

    asyncio.run(test())
