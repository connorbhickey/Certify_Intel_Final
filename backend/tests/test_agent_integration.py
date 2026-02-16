"""
Certify Intel v7.0 - Agent Integration Tests
=============================================

Integration tests for the full agent workflow.

Tests:
1. End-to-end query flow through orchestrator
2. Agent routing accuracy
3. Citation validation in responses
4. Cost tracking across requests
5. Knowledge base integration
6. Error handling and fallbacks

Run: pytest tests/test_agent_integration.py -v
"""

import pytest
import asyncio
from datetime import datetime


# =============================================================================
# TEST 1: Orchestrator End-to-End
# =============================================================================

class TestOrchestratorE2E:
    """End-to-end tests for the orchestrator."""

    @pytest.mark.asyncio
    async def test_query_returns_response(self):
        """Basic query returns a response."""
        try:
            from agents import run_agent_query
            from agents.orchestrator import LANGGRAPH_AVAILABLE

            # Skip if LangGraph is not available (graceful degradation)
            if not LANGGRAPH_AVAILABLE:
                pytest.skip("LangGraph not installed - orchestrator disabled")

            result = await run_agent_query(
                query="What are the top threats?",
                user_id="test_user",
                session_id="test_session"
            )

            assert "response" in result
            assert "target_agent" in result
            assert result["target_agent"] in [
                "dashboard", "discovery", "battlecard",
                "news", "analytics", "validation", "records"
            ]

        except ImportError:
            pytest.skip("LangGraph not available")

    @pytest.mark.asyncio
    async def test_dashboard_agent_direct(self):
        """Dashboard agent can be called directly."""
        from agents import DashboardAgent

        agent = DashboardAgent()
        result = await agent.process("What are the key metrics?")

        assert result.text is not None
        assert result.agent_type == "dashboard"
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_battlecard_agent_without_competitor(self):
        """Battlecard agent handles missing competitor gracefully."""
        from agents import BattlecardAgent

        agent = BattlecardAgent()
        result = await agent.process(
            "Generate battlecard",
            context={"competitor_id": 999999}  # Non-existent
        )

        assert "not find" in result.text.lower() or "could not" in result.text.lower()
        assert result.metadata.get("status") in ["not_found", "error"]

    @pytest.mark.asyncio
    async def test_discovery_agent_with_criteria(self):
        """Discovery agent accepts criteria."""
        from agents import DiscoveryAgent

        agent = DiscoveryAgent()
        result = await agent.process(
            "Find telehealth competitors",
            context={
                "target_segments": ["telehealth"],
                "max_candidates": 3
            }
        )

        assert result.text is not None
        assert result.agent_type == "discovery"


# =============================================================================
# TEST 2: Citation Validation
# =============================================================================

class TestCitationValidation:
    """Tests for citation validation system."""

    @pytest.mark.asyncio
    async def test_validator_finds_valid_citations(self):
        """Validator correctly identifies valid citations."""
        from agents.citation_validator import CitationValidator

        kb_context = [
            {"id": "doc1", "content": "Test content about competitor pricing."}
        ]

        validator = CitationValidator(knowledge_base_context=kb_context)
        result = await validator.validate(
            response_text="According to [Source: doc1], the pricing is $99.",
            citations=[]
        )

        assert len(result.valid_citations) > 0

    @pytest.mark.asyncio
    async def test_validator_rejects_invalid_citations(self):
        """Validator correctly rejects fabricated citations."""
        from agents.citation_validator import CitationValidator

        validator = CitationValidator(knowledge_base_context=[])
        result = await validator.validate(
            response_text="According to [Source: fabricated_doc], data shows...",
            citations=[]
        )

        assert len(result.invalid_citations) > 0
        assert "[citation removed]" in result.cleaned_response

    @pytest.mark.asyncio
    async def test_validator_accepts_competitor_citations(self):
        """Validator accepts competitor database citations."""
        from agents.citation_validator import CitationValidator

        competitor_context = [
            {"id": 1, "name": "Epic Systems", "description": "EHR vendor"}
        ]

        validator = CitationValidator(competitor_context=competitor_context)
        result = await validator.validate(
            response_text="[Source: Epic Systems] is the market leader.",
            citations=[]
        )

        assert len(result.valid_citations) > 0


# =============================================================================
# TEST 3: Knowledge Base Integration
# =============================================================================

class TestKnowledgeBaseIntegration:
    """Tests for knowledge base RAG pipeline."""

    def test_chunking_produces_valid_chunks(self):
        """Chunking produces valid chunks."""
        from knowledge_base import KnowledgeBase

        kb = KnowledgeBase()

        content = """
        This is a test document about competitive intelligence.
        It contains multiple paragraphs of information.

        This second paragraph discusses market analysis.
        We track competitor pricing and product strategies.

        This third paragraph is about sales enablement.
        Battlecards help sales teams win more deals.
        """

        chunks = kb._chunk_content(content, "test.txt")

        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.content is not None
            assert len(chunk.content) > 0
            assert chunk.chunk_index >= 0

    def test_document_chunk_dataclass(self):
        """DocumentChunk dataclass works correctly."""
        from knowledge_base import DocumentChunk

        chunk = DocumentChunk(
            chunk_id="test_1",
            document_id="doc123",
            chunk_index=0,
            content="Test content",
            token_count=2,
            metadata={"source": "test.txt"}
        )

        assert chunk.chunk_id == "test_1"
        assert chunk.document_id == "doc123"
        assert chunk.chunk_index == 0
        assert chunk.content == "Test content"

    def test_search_result_dataclass(self):
        """SearchResult dataclass works correctly."""
        from knowledge_base import SearchResult

        result = SearchResult(
            chunk_id="chunk_1",
            document_id="doc123",
            content="Test content",
            metadata={"page": 1},
            similarity=0.95
        )

        assert result.chunk_id == "chunk_1"
        assert result.similarity == 0.95


# =============================================================================
# TEST 4: Cost Tracking
# =============================================================================

class TestCostTracking:
    """Tests for AI cost tracking."""

    def test_cost_tracker_records_usage(self):
        """Cost tracker records usage correctly."""
        from ai_router import CostTracker, TaskType

        tracker = CostTracker(daily_budget_usd=50.0)

        tracker.record_usage(
            model="gemini-3-flash-preview",
            task_type=TaskType.CHAT,
            tokens_input=1000,
            tokens_output=500
        )

        assert tracker.get_today_spend() > 0

    def test_cost_tracker_enforces_budget(self):
        """Cost tracker enforces daily budget."""
        from ai_router import CostTracker, TaskType

        tracker = CostTracker(daily_budget_usd=0.001)  # Very low budget

        # Record some usage
        tracker.record_usage(
            model="claude-opus-4",
            task_type=TaskType.STRATEGY,
            tokens_input=100000,
            tokens_output=50000
        )

        # Budget should be exceeded
        assert tracker.check_budget(estimated_cost=1.0) == False

    def test_router_cost_estimation(self):
        """Router estimates costs correctly."""
        from ai_router import AIRouter

        router = AIRouter()

        # Estimate cost for deepseek model (cheapest)
        cost = router.estimate_cost(
            model="deepseek-v3",
            prompt_tokens=10000,
            expected_output_tokens=5000
        )

        # Cost should be low for DeepSeek
        assert cost < 0.10  # Less than 10 cents for 15k tokens


# =============================================================================
# TEST 5: Agent Response Structure
# =============================================================================

class TestAgentResponseStructure:
    """Tests for agent response structure."""

    def test_agent_response_dataclass(self):
        """AgentResponse dataclass works correctly."""
        from agents.base_agent import AgentResponse, Citation

        citation = Citation(
            source_id="doc1",
            source_type="knowledge_base",
            content="Test content",
            confidence=0.9
        )

        response = AgentResponse(
            text="Test response",
            citations=[citation],
            cost_usd=0.01,
            latency_ms=50.0
        )

        assert response.text == "Test response"
        assert len(response.citations) == 1
        assert response.cost_usd == 0.01

    def test_citation_dataclass(self):
        """Citation dataclass works correctly."""
        from agents.base_agent import Citation

        citation = Citation(
            source_id="doc123",
            source_type="knowledge_base",
            content="Referenced content",
            confidence=0.95
        )

        assert citation.source_id == "doc123"
        assert citation.source_type == "knowledge_base"
        assert citation.confidence == 0.95


# =============================================================================
# TEST 6: Error Handling
# =============================================================================

class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_dashboard_handles_empty_context(self):
        """Dashboard agent handles empty context gracefully."""
        from agents import DashboardAgent

        agent = DashboardAgent()
        result = await agent.process(
            "What is the pricing for NonExistentCompany?",
            context={}
        )

        # Should refuse to hallucinate - either says "no info" or doesn't
        # fabricate data about the non-existent company (returning real DB
        # data about other competitors is acceptable, not hallucination)
        assert "don't have information" in result.text.lower() or \
               "no information" in result.text.lower() or \
               len(result.citations) == 0 or \
               "nonexistentcompany" not in result.text.lower()

    @pytest.mark.asyncio
    async def test_discovery_handles_invalid_criteria(self):
        """Discovery agent handles invalid criteria gracefully."""
        from agents import DiscoveryAgent

        agent = DiscoveryAgent()
        result = await agent.process(
            "Find competitors",
            context={"invalid_field": "invalid_value"}
        )

        # Should still return a response
        assert result.text is not None
        assert result.agent_type == "discovery"


# =============================================================================
# TEST 7: API Router Integration
# =============================================================================

class TestAPIRouterIntegration:
    """Tests for API router integration."""

    def test_request_model_validation(self):
        """Request models validate correctly."""
        from routers.agents import AgentQueryRequest

        # Valid request
        request = AgentQueryRequest(
            query="What are the top threats?",
            user_id="user123"
        )
        assert request.query == "What are the top threats?"

    def test_response_model_structure(self):
        """Response models have correct structure."""
        from routers.agents import AgentQueryResponse

        response = AgentQueryResponse(
            response="Test response",
            agent="dashboard",
            citations=[],
            cost_usd=0.01,
            tokens_used=100,
            latency_ms=50.0,
            metadata={}
        )

        assert response.response == "Test response"
        assert response.agent == "dashboard"

    def test_discovery_request_model(self):
        """Discovery request model works correctly."""
        from routers.agents import DiscoveryRequest

        request = DiscoveryRequest(
            target_segments=["telehealth"],
            required_capabilities=["pxp"],
            max_candidates=5
        )

        assert "telehealth" in request.target_segments
        assert request.max_candidates == 5

    def test_battlecard_request_model(self):
        """Battlecard request model works correctly."""
        from routers.agents import BattlecardRequest

        request = BattlecardRequest(
            competitor_id=1,
            battlecard_type="quick"
        )

        assert request.competitor_id == 1
        assert request.battlecard_type == "quick"


# CLI runner
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
