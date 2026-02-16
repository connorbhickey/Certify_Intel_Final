"""
Certify Intel v7.0 - Validation Agent Tests (ERR-009)
=====================================================

Tests for the ValidationAgent covering:
1. Constructor with no KB (defaults to None)
2. Constructor with KB and VectorStore
3. _get_knowledge_base_context() with KB available
4. _get_knowledge_base_context() with no KB (returns empty)
5. _get_knowledge_base_context() with exception (graceful fallback)
6. process() with basic validation query
7. process() returns correct response format
8. process() handles missing/invalid input gracefully
9. Agent type is 'validation'
10. Agent has expected attributes
11. Query routing (low confidence, quality report, competitor)

Run: pytest tests/test_validation_agent.py -v
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock, MagicMock


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_knowledge_base():
    """Create a mock KnowledgeBase for testing."""
    kb = Mock()
    kb.get_context_for_query = AsyncMock(return_value={
        "context": "Data validation policies and Admiralty Code framework.",
        "citations": [
            {"source_id": "doc_1", "content": "Admiralty Code scoring guide"},
            {"source_id": "doc_2", "content": "Data quality standards"}
        ],
        "chunks_found": 2,
        "total_tokens": 180
    })
    kb.search = AsyncMock(return_value=[
        {
            "chunk_id": "chunk_1",
            "document_id": "doc_1",
            "content": "Admiralty Code scoring guide for data validation.",
            "metadata": {"source": "validation_policy.pdf"},
            "similarity": 0.90
        }
    ])
    return kb


@pytest.fixture
def mock_vector_store():
    """Create a mock VectorStore for testing."""
    vs = Mock()
    vs.search = AsyncMock(return_value=[
        {"id": "vec_1", "content": "Confidence scoring methodology", "score": 0.92},
        {"id": "vec_2", "content": "Source reliability assessment", "score": 0.87}
    ])
    return vs


@pytest.fixture
def mock_ai_router():
    """Create a mock AIRouter for testing."""
    router = Mock()
    router.route = Mock(return_value="gemini-3-flash-preview")
    router.generate = AsyncMock(return_value={
        "text": "Validation analysis response",
        "tokens_used": 60,
        "cost_usd": 0.0004
    })
    return router


@pytest.fixture
def sample_competitor_context():
    """Sample context with competitor_id for validation queries."""
    return {
        "competitor_id": 1,
        "field_name": "revenue"
    }


# =============================================================================
# TEST CLASS: ValidationAgent
# =============================================================================

class TestValidationAgent:
    """Tests for the ValidationAgent."""

    # -------------------------------------------------------------------------
    # Test 1: Constructor with no KB (defaults to None)
    # -------------------------------------------------------------------------
    def test_constructor_no_kb(self):
        """ValidationAgent can be initialized with no arguments; KB defaults to None."""
        from agents import ValidationAgent

        agent = ValidationAgent()
        assert agent is not None
        assert agent.knowledge_base is None
        assert agent.vector_store is None
        assert agent.ai_router is None

    # -------------------------------------------------------------------------
    # Test 2: Constructor with KB and VectorStore
    # -------------------------------------------------------------------------
    def test_constructor_with_kb_and_vector_store(
        self, mock_knowledge_base, mock_vector_store, mock_ai_router
    ):
        """ValidationAgent accepts KB, VectorStore, and AIRouter in constructor."""
        from agents import ValidationAgent

        agent = ValidationAgent(
            knowledge_base=mock_knowledge_base,
            vector_store=mock_vector_store,
            ai_router=mock_ai_router
        )
        assert agent.knowledge_base is mock_knowledge_base
        assert agent.vector_store is mock_vector_store
        assert agent.ai_router is mock_ai_router

    # -------------------------------------------------------------------------
    # Test 3: _get_knowledge_base_context() with KB available
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_get_kb_context_with_kb(self, mock_knowledge_base):
        """_get_knowledge_base_context returns KB context when available."""
        from agents import ValidationAgent

        agent = ValidationAgent(knowledge_base=mock_knowledge_base)
        result = await agent._get_knowledge_base_context(
            query="Validate competitor data",
            context={}
        )

        assert result is not None
        assert "citations" in result
        mock_knowledge_base.get_context_for_query.assert_awaited_once()

        # Verify source_type is set on citations
        for cit in result.get("citations", []):
            assert cit.get("source_type") == "knowledge_base"

    # -------------------------------------------------------------------------
    # Test 4: _get_knowledge_base_context() with no KB (returns empty)
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_get_kb_context_no_kb(self):
        """_get_knowledge_base_context returns empty dict when no KB or VS is set."""
        from agents import ValidationAgent

        agent = ValidationAgent()
        result = await agent._get_knowledge_base_context(
            query="Validate data quality",
            context={}
        )

        assert result == {"context": "", "citations": [], "chunks_found": 0}

    # -------------------------------------------------------------------------
    # Test 5: _get_knowledge_base_context() with exception (graceful fallback)
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_get_kb_context_exception_falls_back(self, mock_vector_store):
        """When KB raises an exception, falls back to vector store."""
        from agents import ValidationAgent

        failing_kb = Mock()
        failing_kb.get_context_for_query = AsyncMock(
            side_effect=RuntimeError("KB connection failed")
        )

        agent = ValidationAgent(
            knowledge_base=failing_kb,
            vector_store=mock_vector_store
        )
        result = await agent._get_knowledge_base_context(
            query="Show confidence scores",
            context={}
        )

        # Should fall back to vector store results
        assert result is not None
        assert result.get("chunks_found", 0) > 0
        mock_vector_store.search.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_kb_context_both_fail_returns_empty(self):
        """When both KB and VS raise exceptions, returns empty result."""
        from agents import ValidationAgent

        failing_kb = Mock()
        failing_kb.get_context_for_query = AsyncMock(
            side_effect=RuntimeError("KB down")
        )

        failing_vs = Mock()
        failing_vs.search = AsyncMock(
            side_effect=RuntimeError("VS down")
        )

        agent = ValidationAgent(knowledge_base=failing_kb, vector_store=failing_vs)
        result = await agent._get_knowledge_base_context(
            query="data quality",
            context={}
        )

        assert result == {"context": "", "citations": [], "chunks_found": 0}

    # -------------------------------------------------------------------------
    # Test 6: process() with basic validation query
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_process_quality_report_query(self):
        """process() routes a quality report query to _generate_quality_report."""
        from agents import ValidationAgent
        from agents.base_agent import AgentResponse

        agent = ValidationAgent()

        mock_response = AgentResponse(
            text="## Data Quality Report\n**Average Confidence**: 72/100",
            citations=[],
            agent_type="validation",
            data={"avg_confidence": 72, "grade": "B"},
            latency_ms=8.0
        )
        agent._generate_quality_report = AsyncMock(return_value=mock_response)

        result = await agent.process("Data quality report")

        assert result is not None
        assert result.agent_type == "validation"
        agent._generate_quality_report.assert_awaited_once()

    # -------------------------------------------------------------------------
    # Test 7: process() returns correct response format
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_process_returns_agent_response_format(self):
        """process() returns a properly structured AgentResponse."""
        from agents import ValidationAgent
        from agents.base_agent import AgentResponse

        agent = ValidationAgent()

        mock_response = AgentResponse(
            text="## Low Confidence Data\n3 items found.",
            citations=[],
            agent_type="validation",
            data={"low_confidence_count": 3, "threshold": 50},
            latency_ms=10.0
        )
        agent._get_low_confidence_data = AsyncMock(return_value=mock_response)

        result = await agent.process("Show low confidence data")

        assert isinstance(result, AgentResponse)
        assert hasattr(result, "text")
        assert hasattr(result, "citations")
        assert hasattr(result, "agent_type")
        assert hasattr(result, "data")
        assert hasattr(result, "latency_ms")
        assert result.agent_type == "validation"

    # -------------------------------------------------------------------------
    # Test 8: process() handles missing/invalid input gracefully
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_process_handles_exception_gracefully(self):
        """process() catches internal errors and returns error AgentResponse."""
        from agents import ValidationAgent
        from agents.base_agent import AgentResponse

        agent = ValidationAgent()

        # Force an error in the internal method
        agent._generate_quality_report = AsyncMock(
            side_effect=RuntimeError("Database unavailable")
        )

        result = await agent.process("Data quality report")

        assert isinstance(result, AgentResponse)
        assert "error" in result.text.lower() or "error" in (result.data or {})
        assert result.agent_type == "validation"

    @pytest.mark.asyncio
    async def test_process_empty_query(self):
        """process() handles an empty query without crashing."""
        from agents import ValidationAgent
        from agents.base_agent import AgentResponse

        agent = ValidationAgent()

        # Empty query defaults to quality report
        mock_response = AgentResponse(
            text="## Data Quality Report",
            citations=[],
            agent_type="validation",
            data={"avg_confidence": 65},
            latency_ms=5.0
        )
        agent._generate_quality_report = AsyncMock(return_value=mock_response)

        result = await agent.process("")

        assert result is not None
        assert result.agent_type == "validation"

    # -------------------------------------------------------------------------
    # Test 9: Agent type is 'validation'
    # -------------------------------------------------------------------------
    def test_agent_type_is_validation(self):
        """ValidationAgent has agent_type set to 'validation'."""
        from agents import ValidationAgent

        agent = ValidationAgent()
        assert agent.agent_type == "validation"

    # -------------------------------------------------------------------------
    # Test 10: Agent has expected attributes
    # -------------------------------------------------------------------------
    def test_agent_has_expected_attributes(self):
        """ValidationAgent has all expected attributes and methods."""
        from agents import ValidationAgent

        agent = ValidationAgent()

        # Attributes
        assert hasattr(agent, "agent_type")
        assert hasattr(agent, "knowledge_base")
        assert hasattr(agent, "vector_store")
        assert hasattr(agent, "ai_router")

        # Methods
        assert callable(getattr(agent, "process", None))
        assert callable(getattr(agent, "_get_knowledge_base_context", None))
        assert callable(getattr(agent, "_validate_competitor", None))
        assert callable(getattr(agent, "_get_low_confidence_data", None))
        assert callable(getattr(agent, "_generate_quality_report", None))

    # -------------------------------------------------------------------------
    # Query routing tests
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_process_routes_low_confidence_query(self):
        """process() routes 'low confidence' queries to _get_low_confidence_data."""
        from agents import ValidationAgent
        from agents.base_agent import AgentResponse

        agent = ValidationAgent()

        mock_response = AgentResponse(
            text="## Low Confidence Data",
            citations=[],
            agent_type="validation",
            data={"low_confidence_count": 5, "threshold": 50},
            latency_ms=4.0
        )
        agent._get_low_confidence_data = AsyncMock(return_value=mock_response)

        result = await agent.process("Show me low confidence data points")

        agent._get_low_confidence_data.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_routes_competitor_query(self):
        """process() routes competitor queries to _validate_competitor."""
        from agents import ValidationAgent
        from agents.base_agent import AgentResponse

        agent = ValidationAgent()

        mock_response = AgentResponse(
            text="## Validation: Epic Systems",
            citations=[],
            agent_type="validation",
            data={"competitor_id": 1, "avg_confidence": 78},
            latency_ms=6.0
        )
        agent._validate_competitor = AsyncMock(return_value=mock_response)

        result = await agent.process(
            "Validate competitor data",
            context={"competitor_id": 1}
        )

        agent._validate_competitor.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_routes_unverified_query(self):
        """process() routes 'needs verification' queries to _get_low_confidence_data."""
        from agents import ValidationAgent
        from agents.base_agent import AgentResponse

        agent = ValidationAgent()

        mock_response = AgentResponse(
            text="## Unverified Data",
            citations=[],
            agent_type="validation",
            data={"low_confidence_count": 2},
            latency_ms=3.0
        )
        agent._get_low_confidence_data = AsyncMock(return_value=mock_response)

        result = await agent.process("Show data that needs verification")

        agent._get_low_confidence_data.assert_awaited_once()

    # -------------------------------------------------------------------------
    # Convenience method tests
    # -------------------------------------------------------------------------
    def test_validate_field_convenience_method(self):
        """ValidationAgent has validate_field() convenience method."""
        from agents import ValidationAgent

        agent = ValidationAgent()
        assert callable(getattr(agent, "validate_field", None))

    def test_get_quality_overview_convenience_method(self):
        """ValidationAgent has get_quality_overview() convenience method."""
        from agents import ValidationAgent

        agent = ValidationAgent()
        assert callable(getattr(agent, "get_quality_overview", None))
