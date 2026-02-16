"""
Certify Intel v7.0 - Base Agent Class
======================================

Abstract base class for all LangGraph agents.

Enforces:
- Citation validation on all responses
- Cost tracking via AI router
- Langfuse tracing (when enabled)
- Error handling with retry logic

All agents inherit from this class to ensure consistent behavior.
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Citation:
    """A citation reference in an agent response."""
    source_id: str
    source_type: str  # document, competitor, news, manual
    content: str = ""  # Full content or snippet
    confidence: float = 1.0
    url: Optional[str] = None

    @property
    def content_snippet(self) -> str:
        """Alias for backward compatibility."""
        return self.content[:200] if self.content else ""


@dataclass
class AgentResponse:
    """Structured response from an agent."""
    text: str
    citations: List[Citation] = field(default_factory=list)
    agent_type: str = ""
    data: Optional[Dict[str, Any]] = None
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    tokens_used: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    model_used: str = ""
    tokens_input: int = 0
    tokens_output: int = 0


class CitationError(Exception):
    """Raised when citation validation fails."""
    pass


class BudgetExceededError(Exception):
    """Raised when daily AI budget is exceeded."""
    pass


class BaseAgent(ABC):
    """
    Abstract base class for all Certify Intel agents.

    All agents must implement:
    - process(): Core agent logic
    - agent_type: String identifier for the agent

    The base class provides:
    - Citation validation
    - Cost tracking
    - Langfuse tracing (optional)
    - Error handling
    """

    def __init__(
        self,
        agent_type: str,
        ai_router: Optional[Any] = None,
        vector_store: Optional[Any] = None,
        enable_tracing: bool = True,
        knowledge_base: Optional[Any] = None,
        reconciliation_engine: Optional[Any] = None,
        db_session: Optional[Any] = None
    ):
        """
        Initialize base agent.

        Args:
            agent_type: Agent identifier (dashboard, discovery, battlecard, etc.)
            ai_router: AIRouter instance for model selection
            vector_store: VectorStore instance for knowledge base access
            enable_tracing: Whether to enable Langfuse tracing
            knowledge_base: KnowledgeBase instance for RAG context
            reconciliation_engine: SourceReconciliationEngine for data merging
            db_session: SQLAlchemy database session
        """
        self.agent_type = agent_type
        self.ai_router = ai_router
        self.vector_store = vector_store
        self.enable_tracing = enable_tracing and os.getenv("ENABLE_LANGFUSE", "false").lower() == "true"
        self.knowledge_base = knowledge_base
        self.reconciliation_engine = reconciliation_engine
        self.db = db_session

        # Langfuse observer (lazy initialized)
        self._langfuse = None

    def _get_langfuse(self):
        """Get or create Langfuse client."""
        if self._langfuse is None and self.enable_tracing:
            try:
                from langfuse import Langfuse
                self._langfuse = Langfuse(
                    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
                    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
                    host=os.getenv("LANGFUSE_HOST", "http://localhost:3000")
                )
            except ImportError:
                logger.warning("Langfuse not installed, tracing disabled")
                self.enable_tracing = False
            except Exception as e:
                logger.warning(f"Failed to initialize Langfuse: {e}")
                self.enable_tracing = False

        return self._langfuse

    @abstractmethod
    async def process(
        self,
        user_input: str,
        context: Dict[str, Any]
    ) -> AgentResponse:
        """
        Process user input and generate response.

        Must be implemented by each agent.

        Args:
            user_input: User's query or request
            context: Context dict with:
                - relevant_documents: List of knowledge base chunks
                - relevant_competitors: List of competitor data
                - user_id: Current user ID
                - session_id: Current session ID

        Returns:
            AgentResponse with text, citations, and metadata
        """
        pass

    async def process_request(
        self,
        user_input: str,
        context_override: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> AgentResponse:
        """
        Public entry point for agent requests.

        Wraps process() with:
        - Context retrieval from vector store
        - Citation validation
        - Cost tracking
        - Langfuse tracing

        Args:
            user_input: User's query
            context_override: Optional context override (for testing)
            user_id: User ID for tracking
            session_id: Session ID for tracking

        Returns:
            Validated AgentResponse
        """
        import time
        start_time = time.time()

        # Start Langfuse trace
        trace = None
        if self.enable_tracing:
            langfuse = self._get_langfuse()
            if langfuse:
                trace = langfuse.trace(
                    name=f"{self.agent_type}_request",
                    user_id=user_id,
                    session_id=session_id,
                    input={"query": user_input}
                )

        try:
            # Build context
            if context_override is not None:
                context = context_override
            else:
                context = await self._build_context(user_input, user_id)

            context["user_id"] = user_id
            context["session_id"] = session_id

            # Log context retrieval
            if trace:
                trace.span(
                    name="context_retrieval",
                    input={"query": user_input},
                    output={"document_count": len(context.get("relevant_documents", []))}
                )

            # Process request
            response = await self.process(user_input, context)

            # Validate citations
            if response.citations:
                await self._validate_citations(response, context)

            # Calculate latency
            response.latency_ms = int((time.time() - start_time) * 1000)

            # Log to Langfuse
            if trace:
                trace.span(
                    name="agent_response",
                    output={
                        "text": response.text[:500],  # Truncate for logging
                        "citations": len(response.citations),
                        "cost_usd": response.cost_usd,
                        "latency_ms": response.latency_ms
                    }
                )
                trace.update(
                    output={"response": response.text[:500]},
                    level="DEFAULT"
                )

            # Log AI usage
            await self._log_usage(response, user_id)

            return response

        except Exception as e:
            logger.error(f"Agent {self.agent_type} error: {e}")
            if trace:
                trace.update(level="ERROR", output={"error": str(e)})
            raise

    async def _build_context(
        self,
        user_input: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build context for agent processing.

        Retrieves relevant documents from vector store
        and relevant competitor data.
        """
        context = {
            "relevant_documents": [],
            "relevant_competitors": [],
            "source_ids": set()
        }

        # Get relevant documents from vector store
        if self.vector_store:
            try:
                results = await self.vector_store.search(
                    user_input,
                    limit=10,
                    min_similarity=0.7
                )
                context["relevant_documents"] = [
                    {
                        "id": r.document_id,
                        "content": r.content,
                        "metadata": r.metadata,
                        "similarity": r.similarity
                    }
                    for r in results
                ]
                context["source_ids"] = {r.document_id for r in results}
            except Exception as e:
                logger.warning(f"Failed to retrieve from vector store: {e}")

        return context

    async def _get_reconciled_context(
        self,
        competitor_id: int,
        competitor_name: str,
        query: Optional[str] = None,
        fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get unified context combining KB and live data sources.

        This is the recommended method for agents to use instead of
        separate KB/database queries. It provides:
        - Reconciled field values (best from all sources)
        - KB semantic context for RAG
        - Source citations from both KB and live data
        - Conflict warnings for human review
        - Data freshness indicators

        Args:
            competitor_id: ID of the competitor
            competitor_name: Name of the competitor (for KB search)
            query: Optional query for KB semantic search
            fields: Optional list of specific fields to include

        Returns:
            Dict containing:
            - context: Formatted context string for prompts
            - citations: Combined citations from KB + live
            - reconciled_data: Dict of field -> best value
            - conflicts: List of unresolved conflicts
            - freshness: Data freshness summary
            - kb_sources: Number of KB sources
            - live_sources: Number of live sources
        """
        # If reconciliation engine available, use unified approach
        if self.reconciliation_engine:
            try:
                unified = await self.reconciliation_engine.get_unified_context(
                    competitor_id=competitor_id,
                    competitor_name=competitor_name,
                    query=query,
                    fields=fields
                )

                # Build formatted context string
                context_parts = []

                # Add KB context
                if unified.kb_context:
                    context_parts.append("## Knowledge Base Context\n" + unified.kb_context)

                # Add reconciled data
                if unified.reconciled_fields:
                    data_lines = ["## Reconciled Competitor Data"]
                    for fld, fld_result in unified.reconciled_fields.items():
                        if fld_result.best_value:
                            confidence_badge = f"[{fld_result.confidence_level}]" if fld_result.confidence_level else ""
                            data_lines.append(f"- {fld}: {fld_result.best_value} {confidence_badge}")
                    context_parts.append("\n".join(data_lines))

                # Add conflict warnings
                if unified.conflicts_summary:
                    conflict_lines = ["## Data Conflicts (Needs Review)"]
                    for conflict in unified.conflicts_summary:
                        conflict_lines.append(
                            f"- {conflict['field']}: "
                            f"KB={conflict.get('kb_value')} vs Live={conflict.get('live_value')}"
                        )
                    context_parts.append("\n".join(conflict_lines))

                # Build combined citations
                all_citations = list(unified.kb_citations)

                # Add citations from reconciled sources
                for fld, fld_result in unified.reconciled_fields.items():
                    for source in fld_result.sources_used[:2]:  # Top 2 sources per field
                        all_citations.append({
                            "source_type": source.source_origin,
                            "source_id": source.source_id,
                            "field": fld,
                            "value": source.value,
                            "confidence": source.confidence,
                            "is_verified": source.is_verified
                        })

                return {
                    "context": "\n\n".join(context_parts),
                    "citations": all_citations,
                    "reconciled_data": {
                        f: {
                            "value": r.best_value,
                            "confidence": r.confidence_score,
                            "method": r.reconciliation_method
                        }
                        for f, r in unified.reconciled_fields.items()
                    },
                    "conflicts": unified.conflicts_summary,
                    "freshness": unified.freshness_summary,
                    "kb_sources": unified.kb_sources,
                    "live_sources": unified.live_sources,
                    "total_sources": unified.total_sources
                }

            except Exception as e:
                logger.warning(f"Reconciliation failed, falling back to basic context: {e}")

        # Fallback: Use basic KB context retrieval
        if self.knowledge_base:
            try:
                kb_result = await self.knowledge_base.get_context_for_query(
                    query=query or f"Information about {competitor_name}",
                    max_chunks=5,
                    max_tokens=3000,
                    filter_metadata={"competitor": competitor_name}
                )

                return {
                    "context": kb_result.get("context", ""),
                    "citations": kb_result.get("citations", []),
                    "reconciled_data": {},
                    "conflicts": [],
                    "freshness": {},
                    "kb_sources": kb_result.get("chunks_used", 0),
                    "live_sources": 0,
                    "total_sources": kb_result.get("chunks_used", 0)
                }
            except Exception as e:
                logger.warning(f"KB context retrieval failed: {e}")

        # Final fallback: Vector store only
        if self.vector_store:
            try:
                results = await self.vector_store.search(
                    query or competitor_name,
                    limit=5,
                    min_similarity=0.5
                )

                context_parts = [f"[Source {i+1}] {r.content}" for i, r in enumerate(results)]

                return {
                    "context": "\n\n".join(context_parts),
                    "citations": [
                        {
                            "source_number": i + 1,
                            "document_id": r.document_id,
                            "similarity": r.similarity
                        }
                        for i, r in enumerate(results)
                    ],
                    "reconciled_data": {},
                    "conflicts": [],
                    "freshness": {},
                    "kb_sources": len(results),
                    "live_sources": 0,
                    "total_sources": len(results)
                }
            except Exception as e:
                logger.warning(f"Vector store search failed: {e}")

        # No data available
        return {
            "context": "",
            "citations": [],
            "reconciled_data": {},
            "conflicts": [],
            "freshness": {},
            "kb_sources": 0,
            "live_sources": 0,
            "total_sources": 0
        }

    async def _validate_citations(
        self,
        response: AgentResponse,
        context: Dict[str, Any]
    ) -> None:
        """
        Validate that all citations reference real sources.

        Raises CitationError if invalid citations found.
        """
        source_ids = context.get("source_ids", set())

        for citation in response.citations:
            if citation.source_id not in source_ids:
                # Check if it's a competitor reference
                if citation.source_type == "competitor":
                    continue  # Competitors are validated differently

                raise CitationError(
                    f"Invalid citation: {citation.source_id} not found in context. "
                    f"Agent {self.agent_type} may be hallucinating."
                )

    async def _log_usage(
        self,
        response: AgentResponse,
        user_id: Optional[str] = None
    ) -> None:
        """Log AI usage for cost tracking."""
        if response.cost_usd > 0:
            try:
                from database_async import log_ai_usage
                await log_ai_usage(
                    agent_type=self.agent_type,
                    model=response.model_used,
                    task_type="agent_request",
                    tokens_input=response.tokens_input,
                    tokens_output=response.tokens_output,
                    cost_usd=response.cost_usd,
                    latency_ms=response.latency_ms,
                    user_id=user_id
                )
            except Exception as e:
                logger.warning(f"Failed to log AI usage: {e}")

    def refuse_without_sources(self) -> AgentResponse:
        """
        Return a refusal response when no sources are available.

        Use this when the agent cannot answer due to lack of data.
        """
        return AgentResponse(
            text="I don't have enough information to answer that question. "
                 "Please ensure relevant documents are uploaded to the knowledge base, "
                 "or try rephrasing your query.",
            citations=[],
            data=None,
            cost_usd=0.0
        )

    async def enterprise_lookup(
        self,
        company_name: str,
        fields: Optional[list] = None,
        providers: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Query enterprise data providers for competitor intelligence.

        This is the agent-accessible tool for looking up company data
        from institutional sources (PitchBook, Bloomberg, Capital IQ, etc.).

        Args:
            company_name: Name of the company to look up.
            fields: Optional list of specific Competitor field names.
            providers: Optional list of provider names to query.

        Returns:
            Dict with merged_fields, provider_results, and errors.
        """
        try:
            from data_providers.provider_tools import query_enterprise_sources
            result = await query_enterprise_sources(
                company_name=company_name,
                fields=fields,
                providers=providers,
            )
            return result
        except Exception as e:
            logger.warning(f"Enterprise lookup failed for '{company_name}': {e}")
            return {
                "merged_fields": {},
                "provider_results": [],
                "providers_queried": 0,
                "providers_with_data": 0,
                "errors": [f"Enterprise lookup unavailable: {e}"],
            }

    async def _get_internal_company_context(self) -> Dict[str, Any]:
        """
        Retrieve internal Certify Health company context from the knowledge base.

        This method provides agents with information about:
        - Certify Health as a company (mission, values, positioning)
        - Our products and services
        - Our target customers and markets
        - Our competitive advantages and differentiators
        - Internal documentation and guidelines

        The context is retrieved from KB documents with category='internal' or
        'company' or by searching for 'Certify Health' in the knowledge base.

        Returns:
            Dict containing:
            - context: Formatted internal company context string
            - citations: Sources for the context
            - company_profile: Key company information
            - products: List of our products/services
            - has_internal_data: Whether internal docs were found
        """
        result = {
            "context": "",
            "citations": [],
            "company_profile": {},
            "products": [],
            "has_internal_data": False
        }

        # Try KB search for internal company documents
        if self.knowledge_base:
            try:
                # Search for internal/company documents
                internal_context = await self.knowledge_base.get_context_for_query(
                    query="Certify Health company products services customers market positioning",
                    max_chunks=5,
                    max_tokens=2000,
                    filter_metadata={"category": ["internal", "company", "strategy", "product"]}
                )

                if internal_context.get("context"):
                    result["context"] = (
                        "## Internal Company Context (Certify Health)\n\n"
                        + internal_context.get("context", "")
                    )
                    result["citations"] = internal_context.get("citations", [])
                    result["has_internal_data"] = True

                    # Mark these as internal sources
                    for cit in result["citations"]:
                        cit["source_type"] = "internal_company"

            except Exception as e:
                logger.warning(f"Failed to retrieve internal company context from KB: {e}")

        # Fallback: Try vector store directly
        if not result["has_internal_data"] and self.vector_store:
            try:
                search_results = await self.vector_store.search(
                    query="Certify Health our company products services",
                    limit=5,
                    min_similarity=0.4
                )

                if search_results:
                    context_parts = []
                    for i, r in enumerate(search_results):
                        context_parts.append(f"[Internal Source {i+1}]\n{r.content}")
                        result["citations"].append({
                            "source_number": i + 1,
                            "document_id": r.document_id,
                            "chunk_id": str(r.chunk_id),
                            "content_preview": r.content[:150],
                            "similarity_score": round(r.similarity, 3),
                            "source_type": "internal_company"
                        })

                    result["context"] = (
                        "## Internal Company Context (Certify Health)\n\n"
                        + "\n\n".join(context_parts)
                    )
                    result["has_internal_data"] = True

            except Exception as e:
                logger.warning(f"Failed to retrieve internal context from vector store: {e}")

        # Fallback: Try to load from database KnowledgeBaseItem directly
        if not result["has_internal_data"]:
            try:
                from database import SessionLocal, KnowledgeBaseItem

                db = SessionLocal()
                try:
                    # Query for internal/company category documents
                    internal_docs = db.query(KnowledgeBaseItem).filter(
                        KnowledgeBaseItem.is_active.is_(True),
                        KnowledgeBaseItem.category.in_(["internal", "company", "strategy", "product"])
                    ).limit(5).all()

                    if internal_docs:
                        context_parts = []
                        for i, doc in enumerate(internal_docs):
                            context_parts.append(
                                f"[Internal Doc {i+1}: {doc.title}]\n{doc.content_text[:500]}"
                            )
                            result["citations"].append({
                                "source_number": i + 1,
                                "document_id": str(doc.id),
                                "title": doc.title,
                                "category": doc.category,
                                "source_type": "internal_company"
                            })

                        result["context"] = (
                            "## Internal Company Context (Certify Health)\n\n"
                            + "\n\n".join(context_parts)
                        )
                        result["has_internal_data"] = True

                finally:
                    db.close()

            except Exception as e:
                logger.warning(f"Failed to load internal docs from database: {e}")

        # If still no internal context, provide a minimal default
        if not result["has_internal_data"]:
            result["context"] = (
                "## Internal Company Context (Certify Health)\n\n"
                "Certify Health is a healthcare technology company providing competitive intelligence "
                "solutions. For detailed company information, products, and services, please upload "
                "internal documentation to the knowledge base with category='internal' or 'company'."
            )

        return result


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def extract_citations(text: str) -> List[Dict[str, str]]:
    """
    Extract citation markers from response text.

    Looks for patterns like [Source 1], [Source 2], etc.

    Args:
        text: Response text with citations

    Returns:
        List of citation references
    """
    import re

    pattern = r'\[Source (\d+)\]'
    matches = re.findall(pattern, text)

    return [{"marker": f"[Source {m}]", "index": int(m)} for m in matches]


def format_citations(citations: List[Citation]) -> str:
    """
    Format citations as a reference list.

    Args:
        citations: List of Citation objects

    Returns:
        Formatted citation list string
    """
    if not citations:
        return ""

    lines = ["\n\n---\n**Sources:**"]
    for i, c in enumerate(citations, 1):
        line = f"\n[Source {i}] {c.source_type}: {c.content_snippet[:100]}"
        if c.url:
            line += f" - {c.url}"
        lines.append(line)

    return "".join(lines)
