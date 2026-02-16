"""
Certify Intel v7.0 - Records Agent Tests (ERR-009)
===================================================

Tests for the RecordsAgent covering:
1. Constructor with no KB (defaults to None)
2. Constructor with KB and VectorStore
3. _get_knowledge_base_context() with KB available
4. _get_knowledge_base_context() with no KB (returns empty)
5. _get_knowledge_base_context() with exception (graceful fallback)
6. process() with basic records query
7. process() returns correct response format
8. process() handles missing/invalid input gracefully
9. Agent type is 'records'
10. Agent has expected attributes

Run: pytest tests/test_records_agent.py -v
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
        "context": "Change tracking data from internal audit docs.",
        "citations": [
            {"source_id": "doc_1", "content": "Audit policy document"},
            {"source_id": "doc_2", "content": "Change management guide"}
        ],
        "chunks_found": 2,
        "total_tokens": 200
    })
    kb.search = AsyncMock(return_value=[
        {
            "chunk_id": "chunk_1",
            "document_id": "doc_1",
            "content": "Change tracking data from internal audit docs.",
            "metadata": {"source": "audit_policy.pdf"},
            "similarity": 0.88
        }
    ])
    return kb


@pytest.fixture
def mock_vector_store():
    """Create a mock VectorStore for testing."""
    vs = Mock()
    vs.search = AsyncMock(return_value=[
        {"id": "vec_1", "content": "Historical change record content", "score": 0.9},
        {"id": "vec_2", "content": "Audit trail documentation", "score": 0.85}
    ])
    return vs


@pytest.fixture
def mock_ai_router():
    """Create a mock AIRouter for testing."""
    router = Mock()
    router.route = Mock(return_value="gemini-3-flash-preview")
    router.generate = AsyncMock(return_value={
        "text": "Audit analysis response",
        "tokens_used": 80,
        "cost_usd": 0.0005
    })
    return router


@pytest.fixture
def sample_competitor_context():
    """Sample context with competitor_id for records queries."""
    return {
        "competitor_id": 1,
        "days": 7
    }


# =============================================================================
# TEST CLASS: RecordsAgent
# =============================================================================

class TestRecordsAgent:
    """Tests for the RecordsAgent."""

    # -------------------------------------------------------------------------
    # Test 1: Constructor with no KB (defaults to None)
    # -------------------------------------------------------------------------
    def test_constructor_no_kb(self):
        """RecordsAgent can be initialized with no arguments; KB defaults to None."""
        from agents import RecordsAgent

        agent = RecordsAgent()
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
        """RecordsAgent accepts KB, VectorStore, and AIRouter in constructor."""
        from agents import RecordsAgent

        agent = RecordsAgent(
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
        from agents import RecordsAgent

        agent = RecordsAgent(knowledge_base=mock_knowledge_base)
        result = await agent._get_knowledge_base_context(
            query="Show change history",
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
        from agents import RecordsAgent

        agent = RecordsAgent()
        result = await agent._get_knowledge_base_context(
            query="Show change history",
            context={}
        )

        assert result == {"context": "", "citations": [], "chunks_found": 0}

    # -------------------------------------------------------------------------
    # Test 5: _get_knowledge_base_context() with exception (graceful fallback)
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_get_kb_context_exception_falls_back(self, mock_vector_store):
        """When KB raises an exception, falls back to vector store."""
        from agents import RecordsAgent

        failing_kb = Mock()
        failing_kb.get_context_for_query = AsyncMock(
            side_effect=RuntimeError("KB connection failed")
        )

        agent = RecordsAgent(
            knowledge_base=failing_kb,
            vector_store=mock_vector_store
        )
        result = await agent._get_knowledge_base_context(
            query="Show audit trail",
            context={}
        )

        # Should fall back to vector store results
        assert result is not None
        assert result.get("chunks_found", 0) > 0
        mock_vector_store.search.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_kb_context_both_fail_returns_empty(self):
        """When both KB and VS raise exceptions, returns empty result."""
        from agents import RecordsAgent

        failing_kb = Mock()
        failing_kb.get_context_for_query = AsyncMock(
            side_effect=RuntimeError("KB down")
        )

        failing_vs = Mock()
        failing_vs.search = AsyncMock(
            side_effect=RuntimeError("VS down")
        )

        agent = RecordsAgent(knowledge_base=failing_kb, vector_store=failing_vs)
        result = await agent._get_knowledge_base_context(
            query="audit report",
            context={}
        )

        assert result == {"context": "", "citations": [], "chunks_found": 0}

    # -------------------------------------------------------------------------
    # Test 6: process() with basic records query
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_process_recent_changes_query(self):
        """process() routes a generic query to _get_recent_changes."""
        from agents import RecordsAgent
        from agents.base_agent import AgentResponse

        agent = RecordsAgent()

        # Mock the internal method to avoid database calls
        mock_response = AgentResponse(
            text="## Recent Changes\n*Last 7 days*\nNo changes recorded.",
            citations=[],
            agent_type="records",
            data={"total_changes": 0, "days": 7},
            latency_ms=5.0
        )
        agent._get_recent_changes = AsyncMock(return_value=mock_response)

        result = await agent.process("What changed recently?")

        assert result is not None
        assert result.agent_type == "records"
        assert result.text is not None
        agent._get_recent_changes.assert_awaited_once()

    # -------------------------------------------------------------------------
    # Test 7: process() returns correct response format
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_process_returns_agent_response_format(self):
        """process() returns a properly structured AgentResponse."""
        from agents import RecordsAgent
        from agents.base_agent import AgentResponse

        agent = RecordsAgent()

        mock_response = AgentResponse(
            text="## Activity Log\n5 activities found.",
            citations=[],
            agent_type="records",
            data={"total_activities": 5, "days": 1},
            latency_ms=12.0
        )
        agent._get_activity_log = AsyncMock(return_value=mock_response)

        result = await agent.process("Show activity log")

        assert isinstance(result, AgentResponse)
        assert hasattr(result, "text")
        assert hasattr(result, "citations")
        assert hasattr(result, "agent_type")
        assert hasattr(result, "data")
        assert hasattr(result, "latency_ms")
        assert result.agent_type == "records"

    # -------------------------------------------------------------------------
    # Test 8: process() handles missing/invalid input gracefully
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_process_handles_exception_gracefully(self):
        """process() catches internal errors and returns error AgentResponse."""
        from agents import RecordsAgent
        from agents.base_agent import AgentResponse

        agent = RecordsAgent()

        # Force an error in the internal method
        agent._get_recent_changes = AsyncMock(
            side_effect=RuntimeError("Database unavailable")
        )

        result = await agent.process("What changed?")

        assert isinstance(result, AgentResponse)
        assert "error" in result.text.lower() or "error" in (result.data or {})
        assert result.agent_type == "records"

    @pytest.mark.asyncio
    async def test_process_empty_query(self):
        """process() handles an empty query without crashing."""
        from agents import RecordsAgent
        from agents.base_agent import AgentResponse

        agent = RecordsAgent()

        # Empty query should route to _get_recent_changes (no keyword match)
        mock_response = AgentResponse(
            text="## Recent Changes\nNo changes.",
            citations=[],
            agent_type="records",
            data={"total_changes": 0, "days": 7},
            latency_ms=3.0
        )
        agent._get_recent_changes = AsyncMock(return_value=mock_response)

        result = await agent.process("")

        assert result is not None
        assert result.agent_type == "records"

    # -------------------------------------------------------------------------
    # Test 9: Agent type is 'records'
    # -------------------------------------------------------------------------
    def test_agent_type_is_records(self):
        """RecordsAgent has agent_type set to 'records'."""
        from agents import RecordsAgent

        agent = RecordsAgent()
        assert agent.agent_type == "records"

    # -------------------------------------------------------------------------
    # Test 10: Agent has expected attributes
    # -------------------------------------------------------------------------
    def test_agent_has_expected_attributes(self):
        """RecordsAgent has all expected attributes and methods."""
        from agents import RecordsAgent

        agent = RecordsAgent()

        # Attributes
        assert hasattr(agent, "agent_type")
        assert hasattr(agent, "knowledge_base")
        assert hasattr(agent, "vector_store")
        assert hasattr(agent, "ai_router")

        # Methods
        assert callable(getattr(agent, "process", None))
        assert callable(getattr(agent, "_get_knowledge_base_context", None))
        assert callable(getattr(agent, "_get_competitor_history", None))
        assert callable(getattr(agent, "_get_recent_changes", None))
        assert callable(getattr(agent, "_get_activity_log", None))
        assert callable(getattr(agent, "_generate_audit_report", None))

    # -------------------------------------------------------------------------
    # Bonus: Query routing based on keywords
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_process_routes_activity_query(self):
        """process() routes 'activity log' queries to _get_activity_log."""
        from agents import RecordsAgent
        from agents.base_agent import AgentResponse

        agent = RecordsAgent()

        mock_response = AgentResponse(
            text="## Activity Log",
            citations=[],
            agent_type="records",
            data={"total_activities": 0, "days": 1},
            latency_ms=2.0
        )
        agent._get_activity_log = AsyncMock(return_value=mock_response)

        result = await agent.process("Show me the activity log for today")

        agent._get_activity_log.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_routes_audit_query(self):
        """process() routes 'audit report' queries to _generate_audit_report."""
        from agents import RecordsAgent
        from agents.base_agent import AgentResponse

        agent = RecordsAgent()

        mock_response = AgentResponse(
            text="## Audit Report",
            citations=[],
            agent_type="records",
            data={"total_changes": 0},
            latency_ms=2.0
        )
        agent._generate_audit_report = AsyncMock(return_value=mock_response)

        result = await agent.process("Generate an audit trail report")

        agent._generate_audit_report.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_routes_competitor_query(self):
        """process() routes competitor queries to _get_competitor_history."""
        from agents import RecordsAgent
        from agents.base_agent import AgentResponse

        agent = RecordsAgent()

        mock_response = AgentResponse(
            text="## Change History: Epic",
            citations=[],
            agent_type="records",
            data={"competitor_id": 1, "changes_count": 0},
            latency_ms=2.0
        )
        agent._get_competitor_history = AsyncMock(return_value=mock_response)

        result = await agent.process(
            "Show competitor changes",
            context={"competitor_id": 1}
        )

        agent._get_competitor_history.assert_awaited_once()
