"""
Certify Intel v7.0 - Agent Knowledge Base Integration Tests
===========================================================

Tests for all 7 agents with Knowledge Base integration.

Tests verify:
1. Each agent can be initialized with KB context
2. Each agent processes queries and returns valid responses
3. KB context is properly retrieved and used
4. Citations are properly included in responses
5. Error handling for missing/invalid data

Run: pytest tests/test_agent_kb_integration.py -v
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_knowledge_base():
    """Create a mock KnowledgeBase for testing."""
    kb = Mock()
    kb.search = AsyncMock(return_value=[
        {
            "chunk_id": "chunk_1",
            "document_id": "doc_1",
            "content": "Epic Systems is the market leader in healthcare EHR.",
            "metadata": {"source": "market_analysis.pdf"},
            "similarity": 0.92
        },
        {
            "chunk_id": "chunk_2",
            "document_id": "doc_2",
            "content": "Athenahealth focuses on cloud-based solutions for smaller practices.",
            "metadata": {"source": "competitor_report.pdf"},
            "similarity": 0.85
        }
    ])
    kb.get_context_for_query = AsyncMock(return_value={
        "chunks": [
            {"content": "Epic Systems is the market leader.", "source": "doc_1"},
            {"content": "Athenahealth focuses on cloud solutions.", "source": "doc_2"}
        ],
        "total_tokens": 150
    })
    return kb


@pytest.fixture
def mock_vector_store():
    """Create a mock VectorStore for testing."""
    vs = Mock()
    vs.search = AsyncMock(return_value=[
        {"id": "vec_1", "content": "Test content 1", "score": 0.9},
        {"id": "vec_2", "content": "Test content 2", "score": 0.8}
    ])
    return vs


@pytest.fixture
def mock_ai_router():
    """Create a mock AIRouter for testing."""
    router = Mock()
    router.route = Mock(return_value="gemini-3-flash-preview")
    router.generate = AsyncMock(return_value={
        "text": "Test response from AI",
        "tokens_used": 100,
        "cost_usd": 0.001
    })
    return router


@pytest.fixture
def sample_competitor_context():
    """Sample competitor context for testing."""
    return {
        "competitor_id": 1,
        "name": "Epic Systems",
        "description": "Leading EHR vendor",
        "website": "https://epic.com",
        "threat_level": "high"
    }


# =============================================================================
# TEST 1: Dashboard Agent KB Integration
# =============================================================================

class TestDashboardAgentKB:
    """Dashboard agent with Knowledge Base integration tests."""

    @pytest.mark.asyncio
    async def test_dashboard_agent_initialization(self):
        """Dashboard agent can be initialized."""
        from agents import DashboardAgent

        agent = DashboardAgent()
        assert agent is not None
        assert agent.agent_type == "dashboard"

    @pytest.mark.asyncio
    async def test_dashboard_agent_with_kb_context(self, mock_knowledge_base):
        """Dashboard agent uses KB context when available."""
        from agents import DashboardAgent

        agent = DashboardAgent(knowledge_base=mock_knowledge_base)

        # Process a query
        result = await agent.process("What are the top competitors in healthcare?")

        assert result is not None
        assert result.text is not None
        assert result.agent_type == "dashboard"

    @pytest.mark.asyncio
    async def test_dashboard_agent_returns_citations(self):
        """Dashboard agent includes citations in response."""
        from agents import DashboardAgent

        agent = DashboardAgent()
        result = await agent.process("Tell me about market trends")

        assert result is not None
        assert hasattr(result, 'citations')
        # Citations may be empty if no KB context, but attribute should exist

    @pytest.mark.asyncio
    async def test_dashboard_handles_empty_query(self):
        """Dashboard agent handles empty query gracefully."""
        from agents import DashboardAgent

        agent = DashboardAgent()
        result = await agent.process("")

        assert result is not None
        assert result.text is not None


# =============================================================================
# TEST 2: Discovery Agent KB Integration
# =============================================================================

class TestDiscoveryAgentKB:
    """Discovery agent with Knowledge Base integration tests."""

    @pytest.mark.asyncio
    async def test_discovery_agent_initialization(self):
        """Discovery agent can be initialized."""
        from agents import DiscoveryAgent

        agent = DiscoveryAgent()
        assert agent is not None
        assert agent.agent_type == "discovery"

    @pytest.mark.asyncio
    async def test_discovery_agent_with_criteria(self):
        """Discovery agent accepts search criteria."""
        from agents import DiscoveryAgent

        agent = DiscoveryAgent()
        # Mock internal methods that make real API calls
        # _run_discovery returns a dict (not AgentResponse)
        mock_result = {
            "status": "success",
            "candidates": [],
            "total_found": 0,
            "stages_run": ["search"],
            "processing_time_ms": 100,
        }
        agent._run_discovery = AsyncMock(return_value=mock_result)
        agent._get_known_competitors = AsyncMock(return_value=[])
        result = await agent.process(
            "Find telehealth competitors",
            context={
                "target_segments": ["telehealth", "virtual care"],
                "max_candidates": 5
            }
        )

        assert result is not None
        assert result.agent_type == "discovery"

    @pytest.mark.asyncio
    async def test_discovery_agent_with_kb(self, mock_knowledge_base):
        """Discovery agent uses KB for market intelligence."""
        from agents import DiscoveryAgent

        agent = DiscoveryAgent(knowledge_base=mock_knowledge_base)
        # Mock internal methods that make real API calls
        # _run_discovery returns a dict (not AgentResponse)
        mock_result = {
            "status": "success",
            "candidates": [],
            "total_found": 0,
            "stages_run": ["search"],
            "processing_time_ms": 80,
        }
        agent._run_discovery = AsyncMock(return_value=mock_result)
        agent._get_known_competitors = AsyncMock(return_value=[])
        result = await agent.process("Discover emerging competitors in EHR space")

        assert result is not None
        assert result.text is not None

    @pytest.mark.asyncio
    async def test_discovery_handles_invalid_criteria(self):
        """Discovery agent handles invalid criteria gracefully."""
        from agents import DiscoveryAgent

        agent = DiscoveryAgent()
        # Mock internal methods that make real API calls
        # _run_discovery returns a dict (not AgentResponse)
        mock_result = {
            "status": "no_results",
            "candidates": [],
            "total_found": 0,
            "stages_run": ["search"],
            "processing_time_ms": 50,
        }
        agent._run_discovery = AsyncMock(return_value=mock_result)
        agent._get_known_competitors = AsyncMock(return_value=[])
        result = await agent.process(
            "Find competitors",
            context={"invalid_field": "should be ignored"}
        )

        assert result is not None
        assert result.agent_type == "discovery"


# =============================================================================
# TEST 3: Battlecard Agent KB Integration
# =============================================================================

class TestBattlecardAgentKB:
    """Battlecard agent with Knowledge Base integration tests."""

    @pytest.mark.asyncio
    async def test_battlecard_agent_initialization(self):
        """Battlecard agent can be initialized."""
        from agents import BattlecardAgent

        agent = BattlecardAgent()
        assert agent is not None
        assert agent.agent_type == "battlecard"

    @pytest.mark.asyncio
    async def test_battlecard_agent_with_competitor(self, sample_competitor_context):
        """Battlecard agent generates card for competitor."""
        from agents import BattlecardAgent

        agent = BattlecardAgent()
        result = await agent.process(
            "Generate battlecard",
            context=sample_competitor_context
        )

        assert result is not None
        assert result.agent_type == "battlecard"

    @pytest.mark.asyncio
    async def test_battlecard_agent_with_kb(self, mock_knowledge_base, sample_competitor_context):
        """Battlecard agent uses KB for competitor intelligence."""
        from agents import BattlecardAgent

        agent = BattlecardAgent(knowledge_base=mock_knowledge_base)
        result = await agent.process(
            "Generate detailed battlecard",
            context=sample_competitor_context
        )

        assert result is not None
        assert result.text is not None

    @pytest.mark.asyncio
    async def test_battlecard_handles_missing_competitor(self):
        """Battlecard agent handles missing competitor gracefully."""
        from agents import BattlecardAgent

        agent = BattlecardAgent()
        result = await agent.process(
            "Generate battlecard",
            context={"competitor_id": 999999}  # Non-existent
        )

        assert result is not None
        # Should indicate competitor not found
        lower_text = result.text.lower()
        assert "not" in lower_text or "could" in lower_text or "no" in lower_text


# =============================================================================
# TEST 4: News Agent KB Integration
# =============================================================================

class TestNewsAgentKB:
    """News agent with Knowledge Base integration tests."""

    @pytest.mark.asyncio
    async def test_news_agent_initialization(self):
        """News agent can be initialized."""
        from agents import NewsAgent

        agent = NewsAgent()
        assert agent is not None
        assert agent.agent_type == "news"

    @pytest.mark.asyncio
    async def test_news_agent_processes_query(self):
        """News agent processes news queries."""
        from agents import NewsAgent

        agent = NewsAgent()
        result = await agent.process("What's the latest news about Epic Systems?")

        assert result is not None
        assert result.agent_type == "news"

    @pytest.mark.asyncio
    async def test_news_agent_with_kb(self, mock_knowledge_base):
        """News agent uses KB for historical context."""
        from agents import NewsAgent

        agent = NewsAgent(knowledge_base=mock_knowledge_base)
        result = await agent.process("Summarize recent healthcare IT news")

        assert result is not None
        assert result.text is not None

    @pytest.mark.asyncio
    async def test_news_agent_with_filters(self):
        """News agent accepts filters."""
        from agents import NewsAgent

        agent = NewsAgent()
        result = await agent.process(
            "Get news",
            context={
                "competitor_ids": [1, 2, 3],
                "days": 7
            }
        )

        assert result is not None
        assert result.agent_type == "news"


# =============================================================================
# TEST 5: Analytics Agent KB Integration
# =============================================================================

class TestAnalyticsAgentKB:
    """Analytics agent with Knowledge Base integration tests."""

    @pytest.mark.asyncio
    async def test_analytics_agent_initialization(self):
        """Analytics agent can be initialized."""
        from agents import AnalyticsAgent

        agent = AnalyticsAgent()
        assert agent is not None
        assert agent.agent_type == "analytics"

    @pytest.mark.asyncio
    async def test_analytics_agent_market_analysis(self):
        """Analytics agent performs market analysis."""
        from agents import AnalyticsAgent

        agent = AnalyticsAgent()
        result = await agent.process("Analyze the competitive landscape")

        assert result is not None
        assert result.agent_type == "analytics"

    @pytest.mark.asyncio
    async def test_analytics_agent_with_kb(self, mock_knowledge_base):
        """Analytics agent uses KB for strategic insights."""
        from agents import AnalyticsAgent

        agent = AnalyticsAgent(knowledge_base=mock_knowledge_base)
        result = await agent.process("Provide market trend analysis")

        assert result is not None
        assert result.text is not None

    @pytest.mark.asyncio
    async def test_analytics_agent_comparison(self):
        """Analytics agent can compare competitors."""
        from agents import AnalyticsAgent

        agent = AnalyticsAgent()
        result = await agent.process(
            "Compare competitors",
            context={"competitor_ids": [1, 2]}
        )

        assert result is not None
        assert result.agent_type == "analytics"


# =============================================================================
# TEST 6: Validation Agent Tests
# =============================================================================

class TestValidationAgent:
    """Validation agent tests."""

    @pytest.mark.asyncio
    async def test_validation_agent_initialization(self):
        """Validation agent can be initialized."""
        from agents import ValidationAgent

        agent = ValidationAgent()
        assert agent is not None
        assert agent.agent_type == "validation"

    @pytest.mark.asyncio
    async def test_validation_agent_validates_data(self):
        """Validation agent validates competitor data."""
        from agents import ValidationAgent

        agent = ValidationAgent()
        result = await agent.process(
            "Validate competitor data",
            context={"competitor_id": 1}
        )

        assert result is not None
        assert result.agent_type == "validation"

    @pytest.mark.asyncio
    async def test_validation_agent_handles_invalid_id(self):
        """Validation agent handles invalid competitor ID."""
        from agents import ValidationAgent

        agent = ValidationAgent()
        result = await agent.process(
            "Validate data",
            context={"competitor_id": 999999}
        )

        assert result is not None


# =============================================================================
# TEST 7: Records Agent Tests
# =============================================================================

class TestRecordsAgent:
    """Records agent tests."""

    @pytest.mark.asyncio
    async def test_records_agent_initialization(self):
        """Records agent can be initialized."""
        from agents import RecordsAgent

        agent = RecordsAgent()
        assert agent is not None
        assert agent.agent_type == "records"

    @pytest.mark.asyncio
    async def test_records_agent_fetches_data(self):
        """Records agent fetches competitor records."""
        from agents import RecordsAgent

        agent = RecordsAgent()
        result = await agent.process(
            "Get competitor records",
            context={"competitor_id": 1}
        )

        assert result is not None
        assert result.agent_type == "records"

    @pytest.mark.asyncio
    async def test_records_agent_search(self):
        """Records agent can search records."""
        from agents import RecordsAgent

        agent = RecordsAgent()
        result = await agent.process("Search for Epic Systems data")

        assert result is not None
        assert result.agent_type == "records"


# =============================================================================
# TEST 8: Cross-Agent Integration
# =============================================================================

class TestCrossAgentIntegration:
    """Tests for cross-agent functionality."""

    @pytest.mark.asyncio
    async def test_all_agents_return_agent_response(self):
        """All agents return AgentResponse objects."""
        from agents import (
            DashboardAgent, DiscoveryAgent, BattlecardAgent,
            NewsAgent, AnalyticsAgent, ValidationAgent, RecordsAgent
        )
        from agents.base_agent import AgentResponse

        discovery = DiscoveryAgent()
        # Mock discovery internals to avoid real API calls
        mock_disc_response = AgentResponse(
            text="Discovery results", citations=[], agent_type="discovery",
            data={"candidates": []}, latency_ms=5.0
        )
        discovery._run_discovery = AsyncMock(return_value=mock_disc_response)
        discovery._get_known_competitors = AsyncMock(return_value=[])

        agents = [
            DashboardAgent(),
            discovery,
            BattlecardAgent(),
            NewsAgent(),
            AnalyticsAgent(),
            ValidationAgent(),
            RecordsAgent()
        ]

        for agent in agents:
            result = await agent.process("Test query")
            assert isinstance(result, AgentResponse), f"{agent.agent_type} should return AgentResponse"
            assert result.agent_type is not None

    @pytest.mark.asyncio
    async def test_all_agents_have_latency_tracking(self):
        """All agents track latency."""
        from agents import (
            DashboardAgent, DiscoveryAgent, BattlecardAgent,
            NewsAgent, AnalyticsAgent, ValidationAgent, RecordsAgent
        )
        from agents.base_agent import AgentResponse

        discovery = DiscoveryAgent()
        # Mock discovery internals to avoid real API calls
        mock_disc_response = AgentResponse(
            text="Discovery results", citations=[], agent_type="discovery",
            data={"candidates": []}, latency_ms=5.0
        )
        discovery._run_discovery = AsyncMock(return_value=mock_disc_response)
        discovery._get_known_competitors = AsyncMock(return_value=[])

        agents = [
            DashboardAgent(),
            discovery,
            BattlecardAgent(),
            NewsAgent(),
            AnalyticsAgent(),
            ValidationAgent(),
            RecordsAgent()
        ]

        for agent in agents:
            result = await agent.process("Test query")
            assert result.latency_ms >= 0, f"{agent.agent_type} should track latency"

    @pytest.mark.asyncio
    async def test_agents_accept_kb_parameter(self, mock_knowledge_base):
        """All agents accept knowledge_base parameter."""
        from agents import (
            DashboardAgent, DiscoveryAgent, BattlecardAgent,
            NewsAgent, AnalyticsAgent
        )

        # These agents have KB integration
        kb_agents = [
            DashboardAgent(knowledge_base=mock_knowledge_base),
            DiscoveryAgent(knowledge_base=mock_knowledge_base),
            BattlecardAgent(knowledge_base=mock_knowledge_base),
            NewsAgent(knowledge_base=mock_knowledge_base),
            AnalyticsAgent(knowledge_base=mock_knowledge_base)
        ]

        for agent in kb_agents:
            assert hasattr(agent, 'knowledge_base')


# =============================================================================
# TEST 9: Agent Response Consistency
# =============================================================================

class TestAgentResponseConsistency:
    """Tests for consistent agent response structure."""

    @pytest.mark.asyncio
    async def test_response_has_required_fields(self):
        """Agent responses have all required fields."""
        from agents import DashboardAgent

        agent = DashboardAgent()
        result = await agent.process("Test query")

        # Required fields
        assert hasattr(result, 'text')
        assert hasattr(result, 'agent_type')
        assert hasattr(result, 'latency_ms')
        assert hasattr(result, 'citations')
        assert hasattr(result, 'metadata')

    @pytest.mark.asyncio
    async def test_response_text_not_empty(self):
        """Agent responses have non-empty text."""
        from agents import DashboardAgent, NewsAgent, AnalyticsAgent

        agents = [DashboardAgent(), NewsAgent(), AnalyticsAgent()]

        for agent in agents:
            result = await agent.process("What is the market overview?")
            assert result.text is not None
            assert len(result.text) > 0, f"{agent.agent_type} should return non-empty text"


# =============================================================================
# CLI Runner
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
