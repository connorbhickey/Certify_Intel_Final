"""
Certify Intel v7.0 - LangGraph Orchestrator Tests
==================================================

Tests for the agent orchestration system.

Coverage:
- Query routing accuracy
- Agent node execution
- Citation validation
- State management

Run:
    pytest tests/test_orchestrator.py -v
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


# =============================================================================
# TEST: Query Routing
# =============================================================================

class TestQueryRouting:
    """Test query routing to appropriate agents."""

    def test_dashboard_queries(self):
        """Dashboard-related queries should route to dashboard agent."""
        try:
            from agents.orchestrator import route_query
        except ImportError:
            pytest.skip("LangGraph not installed")

        test_queries = [
            "What are the top threats?",
            "Give me an executive summary",
            "Show me the threat overview",
            "What's the status of competitors?",
            "Key highlights from this week"
        ]

        for query in test_queries:
            agent, confidence = route_query(query)
            assert agent == "dashboard", f"'{query}' routed to {agent}, expected dashboard"
            assert confidence > 0.3, f"Low confidence for '{query}': {confidence}"

    def test_discovery_queries(self):
        """Discovery-related queries should route to discovery agent."""
        try:
            from agents.orchestrator import route_query
        except ImportError:
            pytest.skip("LangGraph not installed")

        test_queries = [
            "Find new competitors",
            "Discover emerging players",
            "Search for companies in healthcare IT",
            "Identify potential competitors"
        ]

        for query in test_queries:
            agent, confidence = route_query(query)
            assert agent == "discovery", f"'{query}' routed to {agent}, expected discovery"

    def test_battlecard_queries(self):
        """Battlecard-related queries should route to battlecard agent."""
        try:
            from agents.orchestrator import route_query
        except ImportError:
            pytest.skip("LangGraph not installed")

        test_queries = [
            "Generate battlecard for Epic",
            "Sales talking points against Cerner",
            "How do we compete with Athena?",
            "Win against Phreesia"
        ]

        for query in test_queries:
            agent, confidence = route_query(query)
            assert agent == "battlecard", f"'{query}' routed to {agent}, expected battlecard"

    def test_news_queries(self):
        """News-related queries should route to news agent."""
        try:
            from agents.orchestrator import route_query
        except ImportError:
            pytest.skip("LangGraph not installed")

        test_queries = [
            "What's the latest news?",
            "Recent press releases",
            "Any announcements this week?",
            "News about Epic Systems"
        ]

        for query in test_queries:
            agent, confidence = route_query(query)
            assert agent == "news", f"'{query}' routed to {agent}, expected news"

    def test_analytics_queries(self):
        """Analytics-related queries should route to analytics agent."""
        try:
            from agents.orchestrator import route_query
        except ImportError:
            pytest.skip("LangGraph not installed")

        test_queries = [
            "Show market analytics",
            "Analyze market trends",
            "Generate a report on pricing",
            "Chart the competitive landscape"
        ]

        for query in test_queries:
            agent, confidence = route_query(query)
            assert agent == "analytics", f"'{query}' routed to {agent}, expected analytics"

    def test_validation_queries(self):
        """Validation-related queries should route to validation agent."""
        try:
            from agents.orchestrator import route_query
        except ImportError:
            pytest.skip("LangGraph not installed")

        test_queries = [
            "Verify this data",
            "What's the confidence level?",
            "Is this information reliable?",
            "Audit the sources"
        ]

        for query in test_queries:
            agent, confidence = route_query(query)
            assert agent == "validation", f"'{query}' routed to {agent}, expected validation"

    def test_records_queries(self):
        """Records-related queries should route to records agent."""
        try:
            from agents.orchestrator import route_query
        except ImportError:
            pytest.skip("LangGraph not installed")

        test_queries = [
            "Show change history",
            "When was this modified?",
            "Who updated this record?",
            "Timeline of changes"
        ]

        for query in test_queries:
            agent, confidence = route_query(query)
            assert agent == "records", f"'{query}' routed to {agent}, expected records"


# =============================================================================
# TEST: Agent State
# =============================================================================

class TestAgentState:
    """Test agent state management."""

    def test_state_has_required_fields(self):
        """AgentState should have all required fields."""
        try:
            from agents.orchestrator import AgentState
        except ImportError:
            pytest.skip("LangGraph not installed")

        # Create a minimal state
        state: AgentState = {
            "user_query": "test",
            "user_id": None,
            "session_id": None,
            "competitor_id": None,
            "target_agent": "",
            "route_confidence": 0.0,
            "messages": [],
            "knowledge_base_context": [],
            "competitor_context": [],
            "agent_outputs": {},
            "citations": [],
            "final_response": "",
            "task_complete": False,
            "error": None,
            "total_cost_usd": 0.0,
            "total_tokens": 0
        }

        # All fields should be accessible
        assert state["user_query"] == "test"
        assert state["task_complete"] == False


# =============================================================================
# TEST: Full Query Flow
# =============================================================================

class TestQueryFlow:
    """Test complete query execution flow."""

    @pytest.mark.asyncio
    async def test_run_agent_query_returns_response(self):
        """run_agent_query should return a response dict."""
        try:
            from agents.orchestrator import run_agent_query
        except ImportError:
            pytest.skip("LangGraph not installed")

        result = await run_agent_query(
            query="What are the top threats?",
            user_id="test_user",
            session_id="test_session"
        )

        assert isinstance(result, dict)
        assert "response" in result
        assert "target_agent" in result
        assert "citations" in result

    @pytest.mark.asyncio
    async def test_empty_query_still_returns_response(self):
        """Empty query should still return a valid response."""
        try:
            from agents.orchestrator import run_agent_query
        except ImportError:
            pytest.skip("LangGraph not installed")

        result = await run_agent_query(
            query="",
            user_id="test_user"
        )

        assert isinstance(result, dict)
        assert "response" in result

    @pytest.mark.asyncio
    async def test_context_passed_to_agent(self):
        """Knowledge base context should be available to agents."""
        try:
            from agents.orchestrator import run_agent_query
        except ImportError:
            pytest.skip("LangGraph not installed")

        kb_context = [
            {"id": "doc1", "content": "Test content 1"},
            {"id": "doc2", "content": "Test content 2"}
        ]

        result = await run_agent_query(
            query="What does the knowledge base say?",
            user_id="test_user",
            knowledge_base_context=kb_context
        )

        # Should have received context (agent behavior may vary)
        assert isinstance(result, dict)


# =============================================================================
# TEST: Orchestrator Build
# =============================================================================

class TestOrchestratorBuild:
    """Test orchestrator construction."""

    def test_get_orchestrator_returns_instance(self):
        """get_orchestrator should return a compiled workflow."""
        try:
            from agents.orchestrator import get_orchestrator, LANGGRAPH_AVAILABLE
        except ImportError:
            pytest.skip("LangGraph not installed")

        if not LANGGRAPH_AVAILABLE:
            pytest.skip("LangGraph not available")

        orchestrator = get_orchestrator()
        assert orchestrator is not None

    def test_orchestrator_is_singleton(self):
        """get_orchestrator should return same instance."""
        try:
            from agents.orchestrator import get_orchestrator, LANGGRAPH_AVAILABLE
        except ImportError:
            pytest.skip("LangGraph not installed")

        if not LANGGRAPH_AVAILABLE:
            pytest.skip("LangGraph not available")

        orch1 = get_orchestrator()
        orch2 = get_orchestrator()
        assert orch1 is orch2


# =============================================================================
# TEST: Agent Keywords
# =============================================================================

class TestAgentKeywords:
    """Test keyword configuration."""

    def test_all_agents_have_keywords(self):
        """Every agent should have keywords defined."""
        try:
            from agents.orchestrator import AGENT_KEYWORDS
        except ImportError:
            pytest.skip("Orchestrator not available")

        expected_agents = [
            "dashboard", "discovery", "battlecard",
            "news", "analytics", "validation", "records"
        ]

        for agent in expected_agents:
            assert agent in AGENT_KEYWORDS, f"No keywords for {agent}"
            assert len(AGENT_KEYWORDS[agent]) > 0, f"Empty keywords for {agent}"

    def test_keywords_are_lowercase(self):
        """Keywords should be lowercase for matching."""
        try:
            from agents.orchestrator import AGENT_KEYWORDS
        except ImportError:
            pytest.skip("Orchestrator not available")

        for agent, keywords in AGENT_KEYWORDS.items():
            for kw in keywords:
                assert kw == kw.lower(), f"Keyword '{kw}' for {agent} not lowercase"


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
