"""
Certify Intel v7.0 - AI Agents Package
======================================

LangGraph-orchestrated specialized agents for competitive intelligence.

Agents:
    - DashboardAgent: Executive summaries, threat analysis
    - DiscoveryAgent: Competitor discovery and qualification
    - BattlecardAgent: Sales battlecard generation
    - NewsAgent: News monitoring and sentiment analysis
    - AnalyticsAgent: Market analysis and reporting
    - ValidationAgent: Data validation with confidence scoring (Admiralty Code)
    - RecordsAgent: Change tracking and audit logs

Usage:
    from agents import get_orchestrator, run_agent_query

    result = await run_agent_query(
        query="What are the top threats?",
        user_id="user123"
    )
"""

from .orchestrator import (
    AgentState,
    get_orchestrator,
    run_agent_query,
    route_query
)

from .base_agent import (
    BaseAgent,
    AgentResponse,
    Citation,
    CitationError,
    BudgetExceededError
)

from .dashboard_agent import DashboardAgent
from .discovery_agent import DiscoveryAgent
from .battlecard_agent import BattlecardAgent
from .news_agent import NewsAgent
from .analytics_agent import AnalyticsAgent
from .validation_agent import ValidationAgent
from .records_agent import RecordsAgent

__all__ = [
    # Orchestrator
    "AgentState",
    "get_orchestrator",
    "run_agent_query",
    "route_query",

    # Base classes
    "BaseAgent",
    "AgentResponse",
    "Citation",
    "CitationError",
    "BudgetExceededError",

    # Agents
    "DashboardAgent",
    "DiscoveryAgent",
    "BattlecardAgent",
    "NewsAgent",
    "AnalyticsAgent",
    "ValidationAgent",
    "RecordsAgent"
]
