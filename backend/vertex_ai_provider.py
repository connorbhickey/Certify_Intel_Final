"""
Certify Intel - Vertex AI Provider (v5.3.0)
Enterprise-grade AI provider using Google Cloud Vertex AI.

Migration from google-generativeai SDK to google-cloud-aiplatform for:
- Enterprise Security: VPC Service Controls, CMEK encryption, HIPAA compliance
- RAG Engine: Grounded responses from competitor knowledge bases
- Agent Builder: Autonomous competitive intelligence agents
- Vector Search: Semantic search across competitor data
- Model Fine-Tuning: Custom models trained on healthcare competitive intelligence

Prerequisites:
1. GCP Project with Vertex AI API enabled
2. Service Account with roles/aiplatform.user
3. Either:
   - GOOGLE_APPLICATION_CREDENTIALS pointing to service account JSON
   - Application Default Credentials (gcloud auth application-default login)

Documentation: https://cloud.google.com/vertex-ai/docs
"""

import os
import json
import time
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Check for Vertex AI SDK availability
try:
    import vertexai
    from vertexai.generative_models import (
        GenerativeModel,
        Part,
        Content,
        GenerationConfig,
        SafetySetting,
        HarmCategory,
        HarmBlockThreshold
    )
    VERTEX_AI_AVAILABLE = True
except ImportError:
    VERTEX_AI_AVAILABLE = False
    logger.warning("Vertex AI SDK not installed. Run: pip install google-cloud-aiplatform")

# Check for RAG components (Phase 2)
try:
    from vertexai.preview.rag import RagCorpus, RagFile
    from vertexai.preview.rag_data import RagData
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    logger.info("Vertex AI RAG not available (requires preview features)")

# Check for Vector Search (Phase 3)
try:
    from google.cloud import aiplatform_v1
    VECTOR_SEARCH_AVAILABLE = True
except ImportError:
    VECTOR_SEARCH_AVAILABLE = False
    logger.info("Vector Search client not available")


@dataclass
class VertexAIConfig:
    """Configuration for Vertex AI provider."""
    project_id: str
    location: str = "us-central1"
    model: str = "gemini-3-flash-preview"
    temperature: float = 0.1
    max_output_tokens: int = 8192
    top_p: float = 0.95
    top_k: int = 40
    # Safety settings
    safety_settings: Optional[Dict[str, str]] = None
    # RAG settings (Phase 2)
    rag_corpus_name: Optional[str] = None
    # Agent settings (Phase 4)
    agent_id: Optional[str] = None


@dataclass
class VertexAIResponse:
    """Response from Vertex AI."""
    content: str
    model: str
    provider: str = "vertex_ai"
    tokens_used: int = 0
    cost_estimate: float = 0.0
    latency_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None
    # RAG-specific fields
    grounding_sources: Optional[List[Dict]] = None
    citations: Optional[List[Dict]] = None
    # Agent-specific fields
    agent_response: Optional[Dict] = None


@dataclass
class RAGCorpusConfig:
    """Configuration for a RAG corpus (competitor knowledge base)."""
    name: str
    display_name: str
    description: str
    competitor_id: Optional[int] = None
    # Document sources
    gcs_bucket: Optional[str] = None
    web_urls: Optional[List[str]] = None


class VertexAIProvider:
    """
    Google Cloud Vertex AI provider for Certify Intel.

    Provides enterprise-grade AI capabilities including:
    - Generative AI with Gemini models
    - RAG Engine for grounded responses
    - Vector Search for semantic search
    - Agent Builder for autonomous agents
    - HIPAA compliance and enterprise security

    Usage:
        provider = VertexAIProvider(
            project_id="your-project-id",
            location="us-central1"
        )
        response = await provider.generate("Analyze this competitor...")
    """

    # Model pricing per 1M tokens (Vertex AI pricing as of 2026)
    MODEL_PRICING = {
        "gemini-3-flash": {"input": 0.10, "output": 0.40},
        "gemini-3-pro": {"input": 1.50, "output": 12.00},
        "gemini-2.5-flash": {"input": 0.075, "output": 0.30},
        "gemini-2.5-flash-lite": {"input": 0.01875, "output": 0.075},
        "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    }

    # Task-to-model routing for cost optimization
    TASK_ROUTING = {
        "bulk_extraction": "gemini-3-flash-preview",
        "data_classification": "gemini-3-flash-preview",
        "executive_summary": "gemini-3-pro-preview",
        "complex_analysis": "gemini-3-pro-preview",
        "multimodal": "gemini-3-flash-preview",
        "rag_query": "gemini-3-flash-preview",
        "agent_reasoning": "gemini-3-flash-preview",
    }

    def __init__(
        self,
        project_id: Optional[str] = None,
        location: str = "us-central1",
        model: str = "gemini-3-flash-preview",
        **kwargs
    ):
        """
        Initialize Vertex AI provider.

        Args:
            project_id: GCP project ID (or from GOOGLE_CLOUD_PROJECT env var)
            location: GCP region (default: us-central1)
            model: Default model to use
            **kwargs: Additional configuration options
        """
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT_ID")
        self.location = location or os.getenv("VERTEX_AI_LOCATION", "us-central1")
        self.model = model or os.getenv("VERTEX_AI_MODEL", "gemini-3-flash-preview")

        self.config = VertexAIConfig(
            project_id=self.project_id,
            location=self.location,
            model=self.model,
            **kwargs
        )

        self._initialized = False
        self._model_cache: Dict[str, GenerativeModel] = {}

        if VERTEX_AI_AVAILABLE and self.project_id:
            self._initialize()

    def _initialize(self):
        """Initialize Vertex AI SDK."""
        if not VERTEX_AI_AVAILABLE:
            logger.error("Vertex AI SDK not available")
            return

        if not self.project_id:
            logger.error("GCP project ID not configured")
            return

        try:
            vertexai.init(
                project=self.project_id,
                location=self.location
            )
            self._initialized = True
            logger.info(f"Vertex AI initialized: project={self.project_id}, location={self.location}")
        except Exception as e:
            logger.error(f"Failed to initialize Vertex AI: {e}")
            self._initialized = False

    @property
    def is_available(self) -> bool:
        """Check if Vertex AI is available and initialized."""
        return VERTEX_AI_AVAILABLE and self._initialized

    def _get_model(self, model_name: Optional[str] = None) -> Optional[GenerativeModel]:
        """Get or create a Generative Model instance."""
        if not self.is_available:
            return None

        model_name = model_name or self.model

        if model_name not in self._model_cache:
            try:
                self._model_cache[model_name] = GenerativeModel(model_name)
            except Exception as e:
                logger.error(f"Failed to create model {model_name}: {e}")
                return None

        return self._model_cache[model_name]

    def _get_safety_settings(self) -> List[SafetySetting]:
        """Get safety settings for content generation."""
        return [
            SafetySetting(
                category=HarmCategory.HARM_CATEGORY_HARASSMENT,
                threshold=HarmBlockThreshold.BLOCK_ONLY_HIGH
            ),
            SafetySetting(
                category=HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                threshold=HarmBlockThreshold.BLOCK_ONLY_HIGH
            ),
            SafetySetting(
                category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                threshold=HarmBlockThreshold.BLOCK_ONLY_HIGH
            ),
            SafetySetting(
                category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=HarmBlockThreshold.BLOCK_ONLY_HIGH
            ),
        ]

    def _estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """Estimate cost for a request."""
        pricing = self.MODEL_PRICING.get(model, {"input": 0.10, "output": 0.40})
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        system_instruction: Optional[str] = None,
        response_format: Optional[str] = None,  # "json" for structured output
    ) -> VertexAIResponse:
        """
        Generate content using Vertex AI.

        Args:
            prompt: The prompt to send to the model
            model: Model to use (overrides default)
            temperature: Temperature for generation
            max_tokens: Maximum output tokens
            system_instruction: System prompt
            response_format: "json" for JSON output

        Returns:
            VertexAIResponse with generated content
        """
        if not self.is_available:
            return VertexAIResponse(
                content="",
                model=model or self.model,
                success=False,
                error="Vertex AI not available or not initialized"
            )

        model_name = model or self.model
        gen_model = self._get_model(model_name)

        if not gen_model:
            return VertexAIResponse(
                content="",
                model=model_name,
                success=False,
                error=f"Failed to load model: {model_name}"
            )

        start_time = time.time()

        try:
            # Build generation config
            gen_config = GenerationConfig(
                temperature=temperature or self.config.temperature,
                max_output_tokens=max_tokens or self.config.max_output_tokens,
                top_p=self.config.top_p,
                top_k=self.config.top_k,
            )

            # Add response MIME type for JSON
            if response_format == "json":
                gen_config.response_mime_type = "application/json"

            # Build content
            contents = []
            if system_instruction:
                contents.append(Content(role="user", parts=[Part.from_text(system_instruction)]))
                contents.append(Content(role="model", parts=[Part.from_text("I understand. I will follow these instructions.")]))
            contents.append(Content(role="user", parts=[Part.from_text(prompt)]))

            # Generate
            response = gen_model.generate_content(
                contents,
                generation_config=gen_config,
                safety_settings=self._get_safety_settings(),
            )

            latency_ms = (time.time() - start_time) * 1000

            # Extract content
            content = response.text if response.text else ""

            # Estimate tokens (approximate)
            input_tokens = len(prompt.split()) * 1.3
            output_tokens = len(content.split()) * 1.3

            return VertexAIResponse(
                content=content,
                model=model_name,
                tokens_used=int(input_tokens + output_tokens),
                cost_estimate=self._estimate_cost(int(input_tokens), int(output_tokens), model_name),
                latency_ms=latency_ms,
                success=True
            )

        except Exception as e:
            logger.error(f"Vertex AI generation error: {e}")
            return VertexAIResponse(
                content="",
                model=model_name,
                success=False,
                error=str(e),
                latency_ms=(time.time() - start_time) * 1000
            )

    async def generate_json(
        self,
        prompt: str,
        schema: Optional[Dict] = None,
        model: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate structured JSON output.

        Args:
            prompt: The prompt
            schema: Expected JSON schema (for validation)
            model: Model to use
            **kwargs: Additional generation parameters

        Returns:
            Parsed JSON dictionary
        """
        response = await self.generate(
            prompt=prompt,
            model=model,
            response_format="json",
            **kwargs
        )

        if not response.success:
            return {"error": response.error}

        try:
            return json.loads(response.content)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response: {e}")
            # Try to extract JSON from response
            content = response.content
            if "{" in content and "}" in content:
                start = content.index("{")
                end = content.rindex("}") + 1
                try:
                    return json.loads(content[start:end])
                except:
                    pass
            return {"raw_content": content, "parse_error": str(e)}

    async def analyze_competitor(
        self,
        competitor_name: str,
        data: Dict[str, Any],
        analysis_type: str = "comprehensive"
    ) -> VertexAIResponse:
        """
        Analyze competitor data using Vertex AI.

        Args:
            competitor_name: Name of the competitor
            data: Competitor data dictionary
            analysis_type: Type of analysis (comprehensive, swot, positioning, etc.)

        Returns:
            VertexAIResponse with analysis
        """
        analysis_prompts = {
            "comprehensive": f"""
Analyze {competitor_name} as a healthcare technology competitor.

Data:
{json.dumps(data, indent=2)}

Provide a comprehensive analysis including:
1. Company Overview
2. Product Portfolio
3. Market Position
4. Strengths and Weaknesses
5. Competitive Threats
6. Key Differentiators
7. Recent Developments
8. Recommended Counter-Strategies

Format as structured sections.
""",
            "swot": f"""
Perform a SWOT analysis for {competitor_name}.

Data:
{json.dumps(data, indent=2)}

Provide:
- Strengths (internal positive factors)
- Weaknesses (internal negative factors)
- Opportunities (external positive factors)
- Threats (external negative factors)

For each category, provide 3-5 specific, actionable points.
""",
            "positioning": f"""
Analyze {competitor_name}'s market positioning.

Data:
{json.dumps(data, indent=2)}

Analyze:
1. Target Market Segments
2. Value Proposition
3. Pricing Strategy
4. Go-to-Market Approach
5. Brand Positioning
6. Competitive Differentiation
"""
        }

        prompt = analysis_prompts.get(analysis_type, analysis_prompts["comprehensive"])

        return await self.generate(
            prompt=prompt,
            model="gemini-3-pro-preview",  # Use Pro for complex analysis
            temperature=0.3
        )

    async def extract_competitor_data(
        self,
        content: str,
        content_type: str = "webpage",
        fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Extract structured competitor data from content.

        Args:
            content: Raw content to extract from
            content_type: Type of content (webpage, pdf, news, etc.)
            fields: Specific fields to extract

        Returns:
            Dictionary of extracted data
        """
        default_fields = [
            "company_name", "founded_year", "headquarters", "employee_count",
            "funding_total", "products", "pricing", "key_customers",
            "integrations", "certifications", "recent_news"
        ]

        extract_fields = fields or default_fields

        prompt = f"""
Extract the following information from this {content_type} content.
Return as JSON with these fields: {', '.join(extract_fields)}

Content:
{content[:15000]}  # Limit content length

Return ONLY valid JSON. Use null for missing fields.
"""

        return await self.generate_json(
            prompt=prompt,
            model="gemini-3-flash-preview"  # Use Flash for extraction
        )

    def get_recommended_model(self, task_type: str) -> str:
        """Get recommended model for a task type."""
        return self.TASK_ROUTING.get(task_type, self.model)

    def get_status(self) -> Dict[str, Any]:
        """Get provider status information."""
        return {
            "provider": "vertex_ai",
            "available": self.is_available,
            "project_id": self.project_id,
            "location": self.location,
            "default_model": self.model,
            "sdk_available": VERTEX_AI_AVAILABLE,
            "rag_available": RAG_AVAILABLE,
            "vector_search_available": VECTOR_SEARCH_AVAILABLE,
            "initialized": self._initialized,
            "cached_models": list(self._model_cache.keys()),
        }


# =============================================================================
# RAG Engine Integration (Phase 2)
# =============================================================================

class VertexRAGEngine:
    """
    RAG (Retrieval-Augmented Generation) Engine using Vertex AI.

    Creates and manages knowledge bases (corpora) for each competitor,
    enabling grounded responses with citations.

    Phase 2 Implementation - requires Vertex AI RAG preview features.
    """

    def __init__(self, provider: VertexAIProvider):
        """Initialize RAG Engine with Vertex AI provider."""
        self.provider = provider
        self.corpora: Dict[str, Any] = {}  # competitor_id -> corpus

        if not RAG_AVAILABLE:
            logger.warning("RAG features not available. Install preview SDK.")

    async def create_corpus(
        self,
        competitor_id: int,
        competitor_name: str,
        description: str = ""
    ) -> Optional[str]:
        """
        Create a RAG corpus for a competitor.

        Args:
            competitor_id: Database ID of competitor
            competitor_name: Name of competitor
            description: Corpus description

        Returns:
            Corpus resource name or None if failed
        """
        if not RAG_AVAILABLE:
            return None

        # Placeholder for Phase 2 implementation
        logger.info(f"RAG corpus creation for {competitor_name} - Phase 2")
        return None

    async def add_documents(
        self,
        corpus_name: str,
        documents: List[Dict[str, str]]
    ) -> bool:
        """
        Add documents to a RAG corpus.

        Args:
            corpus_name: Name of the corpus
            documents: List of documents with 'content' and 'metadata'

        Returns:
            True if successful
        """
        if not RAG_AVAILABLE:
            return False

        # Placeholder for Phase 2 implementation
        logger.info(f"Adding {len(documents)} documents to corpus - Phase 2")
        return False

    async def query_with_grounding(
        self,
        query: str,
        competitor_id: Optional[int] = None,
        top_k: int = 5
    ) -> VertexAIResponse:
        """
        Query with RAG grounding.

        Args:
            query: The query
            competitor_id: Optional competitor to scope query
            top_k: Number of sources to retrieve

        Returns:
            VertexAIResponse with grounded content and citations
        """
        if not RAG_AVAILABLE:
            # Fall back to standard generation
            return await self.provider.generate(query)

        # Placeholder for Phase 2 implementation
        logger.info("RAG grounded query - Phase 2")
        return await self.provider.generate(query)


# =============================================================================
# Vector Search Integration (Phase 3)
# =============================================================================

class VertexVectorSearch:
    """
    Vector Search for semantic competitor search.

    Phase 3 Implementation - enables natural language search
    across all competitor data.
    """

    def __init__(self, provider: VertexAIProvider):
        """Initialize Vector Search with Vertex AI provider."""
        self.provider = provider
        self.index_endpoint = None

        if not VECTOR_SEARCH_AVAILABLE:
            logger.warning("Vector Search not available. Install google-cloud-aiplatform.")

    async def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search.

        Args:
            query: Natural language query
            top_k: Number of results
            filters: Optional metadata filters

        Returns:
            List of matching documents with scores
        """
        if not VECTOR_SEARCH_AVAILABLE:
            return []

        # Placeholder for Phase 3 implementation
        logger.info(f"Vector search for: {query} - Phase 3")
        return []


# =============================================================================
# Agent Builder Integration (Phase 4)
# =============================================================================

class VertexAgentBuilder:
    """
    Agent Builder for autonomous competitive intelligence agents.

    Phase 4 Implementation - creates autonomous agents that can:
    - Research competitors
    - Monitor news and updates
    - Generate reports
    - Answer questions with grounding
    """

    def __init__(self, provider: VertexAIProvider):
        """Initialize Agent Builder with Vertex AI provider."""
        self.provider = provider
        self.agents: Dict[str, Any] = {}

    async def create_ci_agent(
        self,
        name: str = "certify_ci_agent",
        description: str = "Competitive Intelligence Agent for Certify Intel"
    ) -> Optional[str]:
        """
        Create a Competitive Intelligence agent.

        Args:
            name: Agent name
            description: Agent description

        Returns:
            Agent ID or None if failed
        """
        # Placeholder for Phase 4 implementation
        logger.info(f"Creating CI agent: {name} - Phase 4")
        return None

    async def chat(
        self,
        agent_id: str,
        message: str,
        session_id: Optional[str] = None
    ) -> VertexAIResponse:
        """
        Chat with an agent.

        Args:
            agent_id: The agent ID
            message: User message
            session_id: Optional session for context

        Returns:
            VertexAIResponse from agent
        """
        # Placeholder for Phase 4 implementation
        # Fall back to standard generation for now
        return await self.provider.generate(message)


# =============================================================================
# Convenience Functions
# =============================================================================

def get_vertex_provider() -> Optional[VertexAIProvider]:
    """
    Get a configured Vertex AI provider instance.

    Returns:
        VertexAIProvider if configured, None otherwise
    """
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT_ID")

    if not project_id:
        logger.warning("GCP project ID not configured. Set GOOGLE_CLOUD_PROJECT env var.")
        return None

    if not VERTEX_AI_AVAILABLE:
        logger.warning("Vertex AI SDK not installed.")
        return None

    return VertexAIProvider(
        project_id=project_id,
        location=os.getenv("VERTEX_AI_LOCATION", "us-central1"),
        model=os.getenv("VERTEX_AI_MODEL", "gemini-3-flash-preview")
    )


def check_vertex_ai_prerequisites() -> Dict[str, Any]:
    """
    Check if Vertex AI prerequisites are met.

    Returns:
        Dictionary with status of each prerequisite
    """
    return {
        "sdk_installed": VERTEX_AI_AVAILABLE,
        "rag_available": RAG_AVAILABLE,
        "vector_search_available": VECTOR_SEARCH_AVAILABLE,
        "project_id_configured": bool(os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT_ID")),
        "credentials_available": bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS")) or _check_adc(),
        "location_configured": bool(os.getenv("VERTEX_AI_LOCATION")),
    }


def _check_adc() -> bool:
    """Check if Application Default Credentials are available."""
    try:
        from google.auth import default
        credentials, project = default()
        return credentials is not None
    except:
        return False


# =============================================================================
# Module Initialization
# =============================================================================

# Create default provider instance if configured
_default_provider: Optional[VertexAIProvider] = None


def get_default_provider() -> Optional[VertexAIProvider]:
    """Get the default Vertex AI provider instance."""
    global _default_provider

    if _default_provider is None:
        _default_provider = get_vertex_provider()

    return _default_provider


# Log availability on import
if VERTEX_AI_AVAILABLE:
    logger.info("Vertex AI SDK available")
else:
    logger.info("Vertex AI SDK not installed - run: pip install google-cloud-aiplatform")
