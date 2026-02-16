"""
Certify Intel - Gemini AI Provider (v7.0.1)
Uses Google GenAI SDK (unified) as a secondary AI provider alongside OpenAI.

MIGRATION NOTE (v7.0.1): Migrated from deprecated `google-generativeai` to `google-genai`.
The old SDK was deprecated August 31, 2025. The new unified SDK uses a Client-based pattern.
See: https://ai.google.dev/gemini-api/docs/migrate

Cost Savings: ~90% reduction on bulk tasks compared to OpenAI
Model Options:
- gemini-3-flash-preview: Fast, cost-effective for bulk operations ($0.50/1M input tokens)
- gemini-3-pro-preview: Higher quality for complex analysis, grounded search ($2.00/1M input tokens)

v5.0.5: Added multimodal capabilities:
- Screenshot analysis for competitor websites
- PDF/Document analysis for competitor whitepapers
- Image analysis for visual competitive intelligence

v5.0.6: Added advanced features:
- Video intelligence for competitor demos/webinars
- Real-time grounding using Google Search
- Bulk news processing with Flash-Lite

v7.0.1: Migrated to google-genai SDK (unified Client pattern)

Documentation: https://ai.google.dev/gemini-api/docs
"""

import os
import json
import base64
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import logging

# Image processing
try:
    from PIL import Image
    import io
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# PDF processing
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

logger = logging.getLogger(__name__)

try:
    from google import genai
    from google.genai import types as genai_types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None
    genai_types = None
    logger.warning("Google GenAI SDK not installed. Run: pip install google-genai")


@dataclass
class GeminiConfig:
    """Configuration for Gemini AI provider."""
    api_key: str
    model: str = "gemini-3-flash-preview"
    temperature: float = 0.1
    max_output_tokens: int = 8192
    top_p: float = 0.95
    top_k: int = 40


@dataclass
class AIResponse:
    """Unified response format for AI providers."""
    content: str
    model: str
    provider: str  # "openai" or "gemini"
    tokens_used: int
    cost_estimate: float
    latency_ms: float
    success: bool
    error: Optional[str] = None


class GeminiProvider:
    """
    Google Gemini AI provider for Certify Intel.

    Provides a unified interface compatible with existing OpenAI integration.
    Supports both text generation and structured JSON output.
    """

    # Model pricing per 1M tokens (as of 2026)
    MODEL_PRICING = {
        "gemini-3-flash-preview": {"input": 0.50, "output": 3.00},
        "gemini-3-pro-preview": {"input": 2.00, "output": 12.00},
        "gemini-2.5-flash": {"input": 0.075, "output": 0.30},
        "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    }

    # Task-to-model routing recommendations
    TASK_ROUTING = {
        "bulk_extraction": "gemini-3-flash-preview",  # Fast, high throughput
        "data_extraction": "gemini-3-flash-preview",   # Good balance
        "executive_summary": "gemini-3-pro-preview",   # Quality text generation
        "complex_analysis": "gemini-3-pro-preview",    # Highest quality
        "quick_classification": "gemini-3-flash-preview",  # Fast and cheap
    }

    def __init__(self, config: Optional[GeminiConfig] = None):
        """
        Initialize Gemini provider.

        Args:
            config: Optional GeminiConfig. If not provided, uses environment variables.
        """
        logger.info("GeminiProvider.__init__ starting...")

        if config:
            self.config = config
            logger.info("GeminiProvider: Using provided config")
        else:
            api_key = os.getenv("GOOGLE_AI_API_KEY", "")
            logger.info(f"GeminiProvider: API key present: {bool(api_key)}, length: {len(api_key)}")
            self.config = GeminiConfig(
                api_key=api_key,
                model=os.getenv("GOOGLE_AI_MODEL", "gemini-3-flash-preview"),
                temperature=float(os.getenv("GEMINI_TEMPERATURE", "0.1")),
            )
            logger.info(f"GeminiProvider: Config loaded - model: {self.config.model}")

        self.client = None

        if not self.config.api_key:
            logger.warning("GeminiProvider: GOOGLE_AI_API_KEY not set - Gemini features disabled")
        elif not GEMINI_AVAILABLE:
            logger.warning("GeminiProvider: google-genai package not installed (GEMINI_AVAILABLE=False)")
        else:
            try:
                logger.info("GeminiProvider: Creating genai.Client...")
                self.client = genai.Client(api_key=self.config.api_key)
                logger.info(f"GeminiProvider: Client created successfully, model: {self.config.model}")
            except Exception as e:
                logger.error(f"GeminiProvider: Failed to create Client: {type(e).__name__}: {e}")
                import traceback
                logger.error(f"GeminiProvider: Traceback: {traceback.format_exc()}")

    @property
    def is_available(self) -> bool:
        """Check if Gemini provider is available and configured."""
        return self.client is not None

    def get_recommended_model(self, task_type: str) -> str:
        """Get the recommended model for a specific task type."""
        return self.TASK_ROUTING.get(task_type, self.config.model)

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: Optional[str] = None) -> float:
        """
        Estimate the cost for a given number of tokens.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: Model name (uses config.model if not specified)

        Returns:
            Estimated cost in USD
        """
        model = model or self.config.model
        pricing = self.MODEL_PRICING.get(model, {"input": 0.10, "output": 0.40})

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AIResponse:
        """
        Generate text using Gemini.

        Args:
            prompt: The user prompt
            system_prompt: Optional system instruction
            model: Override model for this request
            temperature: Override temperature for this request
            max_tokens: Override max output tokens

        Returns:
            AIResponse with generated content
        """
        if not self.is_available:
            return AIResponse(
                content="",
                model=self.config.model,
                provider="gemini",
                tokens_used=0,
                cost_estimate=0.0,
                latency_ms=0.0,
                success=False,
                error="Gemini provider not available. Check GOOGLE_AI_API_KEY."
            )

        start_time = datetime.now()

        try:
            # Use specified model or default
            model_name = model or self.config.model

            # Build full prompt with system instruction
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"

            # Generate response using new Client-based API
            response = self.client.models.generate_content(
                model=model_name,
                contents=full_prompt,
                config=genai_types.GenerateContentConfig(
                    temperature=temperature or self.config.temperature,
                    max_output_tokens=max_tokens or self.config.max_output_tokens,
                    top_p=self.config.top_p,
                    top_k=self.config.top_k,
                ),
            )

            # Calculate metrics
            latency = (datetime.now() - start_time).total_seconds() * 1000

            # Estimate tokens (Gemini doesn't always return token counts)
            input_tokens = len(full_prompt.split()) * 1.3  # Rough estimate
            output_tokens = len(response.text.split()) * 1.3

            return AIResponse(
                content=response.text,
                model=model_name,
                provider="gemini",
                tokens_used=int(input_tokens + output_tokens),
                cost_estimate=self.estimate_cost(int(input_tokens), int(output_tokens), model_name),
                latency_ms=latency,
                success=True,
            )

        except Exception as e:
            latency = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Gemini generation failed: {e}")

            return AIResponse(
                content="",
                model=self.config.model,
                provider="gemini",
                tokens_used=0,
                cost_estimate=0.0,
                latency_ms=latency,
                success=False,
                error=str(e),
            )

    # ============== MULTIMODAL METHODS (v5.0.5) ==============

    def analyze_image(
        self,
        image_source: Union[str, bytes, Path],
        prompt: str,
        model: Optional[str] = None,
    ) -> AIResponse:
        """
        Analyze an image using Gemini's multimodal capabilities.

        v5.0.5: Added for visual competitive intelligence.

        Args:
            image_source: File path, URL, or raw bytes of the image
            prompt: Analysis prompt (e.g., "Describe the pricing table in this screenshot")
            model: Override model (defaults to gemini-2.5-flash which supports vision)

        Returns:
            AIResponse with analysis content
        """
        if not self.is_available:
            return AIResponse(
                content="",
                model=self.config.model,
                provider="gemini",
                tokens_used=0,
                cost_estimate=0.0,
                latency_ms=0.0,
                success=False,
                error="Gemini provider not available. Check GOOGLE_AI_API_KEY."
            )

        start_time = datetime.now()

        try:
            model_name = model or "gemini-3-flash-preview"  # Vision-capable model

            # Process image source
            image_part = self._prepare_image(image_source)
            if image_part is None:
                return AIResponse(
                    content="",
                    model=model_name,
                    provider="gemini",
                    tokens_used=0,
                    cost_estimate=0.0,
                    latency_ms=0.0,
                    success=False,
                    error="Failed to load image. Check file path or URL."
                )

            # Generate with image using new Client API
            response = self.client.models.generate_content(
                model=model_name,
                contents=[prompt, image_part],
            )

            latency = (datetime.now() - start_time).total_seconds() * 1000

            # Estimate tokens (images counted as ~258 tokens)
            input_tokens = 258 + len(prompt.split()) * 1.3
            output_tokens = len(response.text.split()) * 1.3

            return AIResponse(
                content=response.text,
                model=model_name,
                provider="gemini",
                tokens_used=int(input_tokens + output_tokens),
                cost_estimate=self.estimate_cost(int(input_tokens), int(output_tokens), model_name),
                latency_ms=latency,
                success=True,
            )

        except Exception as e:
            latency = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Gemini image analysis failed: {e}")

            return AIResponse(
                content="",
                model=self.config.model,
                provider="gemini",
                tokens_used=0,
                cost_estimate=0.0,
                latency_ms=latency,
                success=False,
                error=str(e),
            )

    def _prepare_image(self, image_source: Union[str, bytes, Path]) -> Optional[Any]:
        """Prepare image for Google GenAI SDK using types.Part."""
        try:
            if isinstance(image_source, bytes):
                # Raw bytes - use Part.from_bytes in new SDK
                return genai_types.Part.from_bytes(data=image_source, mime_type="image/png")

            if isinstance(image_source, Path):
                image_source = str(image_source)

            if isinstance(image_source, str):
                if image_source.startswith(("http://", "https://")):
                    # URL - download first then create Part
                    import urllib.request
                    with urllib.request.urlopen(image_source, timeout=30) as response:
                        data = response.read()
                    mime_type = "image/jpeg" if ".jpg" in image_source or ".jpeg" in image_source else "image/png"
                    return genai_types.Part.from_bytes(data=data, mime_type=mime_type)
                else:
                    # File path
                    with open(image_source, "rb") as f:
                        data = f.read()
                    ext = image_source.lower()
                    if ext.endswith(".png"):
                        mime_type = "image/png"
                    elif ext.endswith((".jpg", ".jpeg")):
                        mime_type = "image/jpeg"
                    elif ext.endswith(".webp"):
                        mime_type = "image/webp"
                    elif ext.endswith(".gif"):
                        mime_type = "image/gif"
                    else:
                        mime_type = "image/png"
                    return genai_types.Part.from_bytes(data=data, mime_type=mime_type)

            return None
        except Exception as e:
            logger.error(f"Failed to prepare image: {e}")
            return None

    def analyze_screenshot(
        self,
        image_source: Union[str, bytes, Path],
        competitor_name: str,
        page_type: str = "homepage",
    ) -> Dict[str, Any]:
        """
        Analyze a competitor website screenshot for competitive intelligence.

        v5.0.5: Specialized method for competitor analysis.

        Args:
            image_source: Screenshot file path, URL, or raw bytes
            competitor_name: Name of the competitor
            page_type: Type of page (homepage, pricing, features, about)

        Returns:
            Dictionary with extracted competitive intelligence
        """
        prompts = {
            "homepage": f"""Analyze this screenshot of the homepage for {competitor_name} for competitive intelligence.
Extract and return as JSON:
{{
    "value_proposition": "Main value proposition or tagline",
    "key_messages": ["List of key marketing messages"],
    "target_audience": "Who they seem to target",
    "call_to_action": "Primary CTA text",
    "visual_style": "Description of design style (modern, corporate, playful, etc.)",
    "trust_signals": ["Logos, certifications, testimonials visible"],
    "feature_highlights": ["Features prominently displayed"],
    "competitive_positioning": "How they position vs competitors",
    "notable_elements": ["Any other notable UI/UX elements"]
}}""",
            "pricing": f"""Analyze this screenshot of the pricing page for {competitor_name} for competitive intelligence.
Extract and return as JSON:
{{
    "pricing_tiers": [
        {{"name": "tier name", "price": "price with unit", "features": ["key features"]}}
    ],
    "pricing_model": "Per user/month, per transaction, flat fee, etc.",
    "free_trial": "true/false if mentioned",
    "enterprise_option": "true/false if custom/enterprise pricing available",
    "discounts": "Annual discount or other promotions",
    "comparison_table": "true/false if feature comparison shown",
    "lowest_price": "Lowest price point visible",
    "highest_price": "Highest price point visible",
    "notable_elements": ["Any other notable pricing elements"]
}}""",
            "features": f"""Analyze this screenshot of the features/product page for {competitor_name} for competitive intelligence.
Extract and return as JSON:
{{
    "product_categories": ["Main product/feature categories"],
    "key_features": ["List of specific features mentioned"],
    "integrations": ["Integration partners or platforms mentioned"],
    "unique_capabilities": ["Features that seem unique or differentiated"],
    "technology_keywords": ["Tech-related terms (AI, cloud, etc.)"],
    "use_cases": ["Use cases or scenarios shown"],
    "certifications": ["Security or compliance certifications"],
    "notable_elements": ["Any other notable elements"]
}}""",
            "about": f"""Analyze this screenshot of the about/company page for {competitor_name} for competitive intelligence.
Extract and return as JSON:
{{
    "company_description": "Brief company description",
    "founding_info": "Year founded, founders if mentioned",
    "headquarters": "Location if mentioned",
    "team_size": "Number of employees if mentioned",
    "customers_count": "Number of customers if mentioned",
    "key_customers": ["Notable customer names/logos visible"],
    "investors": ["Investor names if mentioned"],
    "awards": ["Awards or recognition mentioned"],
    "mission_vision": "Mission or vision statement",
    "notable_elements": ["Any other notable elements"]
}}"""
        }

        prompt = prompts.get(page_type, prompts["homepage"])

        response = self.analyze_image(image_source, prompt)

        if not response.success:
            return {
                "error": response.error,
                "competitor": competitor_name,
                "page_type": page_type,
                "_provider": "gemini"
            }

        # Parse JSON from response
        try:
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]

            result = json.loads(content.strip())
            result["_provider"] = "gemini"
            result["_model"] = response.model
            result["_cost"] = response.cost_estimate
            result["competitor"] = competitor_name
            result["page_type"] = page_type

            return result

        except json.JSONDecodeError as e:
            return {
                "raw_analysis": response.content,
                "competitor": competitor_name,
                "page_type": page_type,
                "_provider": "gemini",
                "_parse_error": str(e)
            }

    def analyze_pdf(
        self,
        pdf_source: Union[str, bytes, Path],
        prompt: Optional[str] = None,
        competitor_name: Optional[str] = None,
        document_type: str = "general",
    ) -> Dict[str, Any]:
        """
        Analyze a PDF document using Gemini.

        v5.0.5: Added for analyzing competitor whitepapers, case studies, etc.

        Args:
            pdf_source: PDF file path or raw bytes
            prompt: Custom analysis prompt (optional)
            competitor_name: Name of competitor (optional, for context)
            document_type: Type of document (whitepaper, case_study, datasheet, annual_report)

        Returns:
            Dictionary with extracted insights
        """
        if not PYMUPDF_AVAILABLE:
            return {
                "error": "PyMuPDF not installed. Run: pip install pymupdf",
                "_provider": "gemini"
            }

        if not self.is_available:
            return {
                "error": "Gemini provider not available. Check GOOGLE_AI_API_KEY.",
                "_provider": "gemini"
            }

        try:
            # Extract text from PDF
            text_content = self._extract_pdf_text(pdf_source)

            if not text_content:
                return {
                    "error": "Failed to extract text from PDF",
                    "_provider": "gemini"
                }

            # Build analysis prompt based on document type
            if prompt:
                analysis_prompt = prompt
            else:
                analysis_prompt = self._get_pdf_analysis_prompt(document_type, competitor_name)

            # Truncate if too long
            max_length = 30000  # Gemini has large context
            if len(text_content) > max_length:
                text_content = text_content[:max_length] + "\n...[truncated]..."

            full_prompt = f"{analysis_prompt}\n\nDOCUMENT CONTENT:\n{text_content}"

            response = self.generate_text(full_prompt, temperature=0.2)

            if not response.success:
                return {
                    "error": response.error,
                    "_provider": "gemini"
                }

            # Try to parse as JSON if the prompt requested it
            try:
                content = response.content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]

                result = json.loads(content.strip())
                result["_provider"] = "gemini"
                result["_model"] = response.model
                result["_cost"] = response.cost_estimate
                if competitor_name:
                    result["competitor"] = competitor_name
                result["document_type"] = document_type

                return result

            except json.JSONDecodeError:
                # Return raw analysis if not JSON
                return {
                    "analysis": response.content,
                    "competitor": competitor_name,
                    "document_type": document_type,
                    "_provider": "gemini",
                    "_model": response.model,
                    "_cost": response.cost_estimate
                }

        except Exception as e:
            logger.error(f"PDF analysis failed: {e}")
            return {
                "error": str(e),
                "_provider": "gemini"
            }

    def _extract_pdf_text(self, pdf_source: Union[str, bytes, Path]) -> Optional[str]:
        """Extract text content from PDF."""
        try:
            if isinstance(pdf_source, bytes):
                doc = fitz.open(stream=pdf_source, filetype="pdf")
            else:
                doc = fitz.open(str(pdf_source))

            text_parts = []
            for page_num, page in enumerate(doc):
                text = page.get_text()
                if text.strip():
                    text_parts.append(f"--- Page {page_num + 1} ---\n{text}")

            doc.close()
            return "\n\n".join(text_parts)

        except Exception as e:
            logger.error(f"Failed to extract PDF text: {e}")
            return None

    def _get_pdf_analysis_prompt(self, document_type: str, competitor_name: Optional[str]) -> str:
        """Get analysis prompt based on document type."""
        company_ref = f"from {competitor_name}" if competitor_name else ""

        prompts = {
            "whitepaper": f"""Analyze this whitepaper {company_ref} for competitive intelligence.
Extract and return as JSON:
{{
    "title": "Document title",
    "main_topic": "Primary topic/theme",
    "key_claims": ["Main claims or assertions"],
    "technology_mentioned": ["Technologies or approaches discussed"],
    "statistics": ["Key statistics or data points"],
    "competitive_advantages": ["Advantages or differentiators claimed"],
    "target_audience": "Who this document is for",
    "call_to_action": "What action they want readers to take",
    "key_takeaways": ["3-5 main takeaways for competitive analysis"]
}}""",
            "case_study": f"""Analyze this case study {company_ref} for competitive intelligence.
Extract and return as JSON:
{{
    "customer_name": "Customer featured",
    "customer_industry": "Customer's industry",
    "customer_size": "Size of customer (employees, revenue, etc.)",
    "challenge": "Problem the customer faced",
    "solution": "How the product/service solved it",
    "results": ["Quantified results and outcomes"],
    "implementation_time": "How long implementation took",
    "products_used": ["Specific products or features mentioned"],
    "quotes": ["Notable customer quotes"],
    "key_takeaways": ["3-5 takeaways for competitive positioning"]
}}""",
            "datasheet": f"""Analyze this product datasheet {company_ref} for competitive intelligence.
Extract and return as JSON:
{{
    "product_name": "Product name",
    "product_category": "Category/type of product",
    "key_features": ["Main features and capabilities"],
    "technical_specs": {{"spec_name": "value"}},
    "integrations": ["Integrations mentioned"],
    "deployment_options": ["Cloud, on-prem, hybrid, etc."],
    "compliance_certifications": ["Security/compliance certs"],
    "pricing_info": "Any pricing information",
    "unique_capabilities": ["What makes this product unique"]
}}""",
            "annual_report": f"""Analyze this annual report {company_ref} for competitive intelligence.
Extract and return as JSON:
{{
    "fiscal_year": "Year covered",
    "revenue": "Total revenue if mentioned",
    "growth_rate": "Revenue growth rate",
    "customer_count": "Number of customers",
    "employee_count": "Number of employees",
    "key_products": ["Main products/services"],
    "market_segments": ["Target markets"],
    "strategic_priorities": ["Strategic focus areas"],
    "risks_mentioned": ["Key risks discussed"],
    "acquisitions": ["Any acquisitions mentioned"],
    "geographic_expansion": ["New markets entered"],
    "key_metrics": {{"metric_name": "value"}}
}}""",
            "general": f"""Analyze this document {company_ref} for competitive intelligence.
Extract key information and return as JSON:
{{
    "document_type": "Type of document",
    "main_topic": "Primary topic",
    "key_points": ["Main points or claims"],
    "data_points": ["Statistics or metrics"],
    "products_mentioned": ["Products or services"],
    "competitive_insights": ["Insights relevant for competitive analysis"],
    "target_audience": "Who this document is for",
    "summary": "2-3 sentence summary"
}}"""
        }

        return prompts.get(document_type, prompts["general"])

    # ============== VIDEO INTELLIGENCE (v5.0.6) ==============

    def analyze_video(
        self,
        video_source: Union[str, bytes, Path],
        prompt: Optional[str] = None,
        competitor_name: Optional[str] = None,
        video_type: str = "demo",
    ) -> Dict[str, Any]:
        """
        Analyze a video using Gemini's multimodal capabilities.

        v5.0.6: Added for analyzing competitor demos, webinars, and product tours.

        Args:
            video_source: Video file path, URL, or raw bytes
            prompt: Custom analysis prompt (optional)
            competitor_name: Name of competitor (optional)
            video_type: Type of video (demo, webinar, tutorial, advertisement)

        Returns:
            Dictionary with extracted competitive intelligence
        """
        if not self.is_available:
            return {
                "error": "Gemini provider not available. Check GOOGLE_AI_API_KEY.",
                "_provider": "gemini"
            }

        start_time = datetime.now()

        try:
            model_name = "gemini-3-flash-preview"  # Video-capable model

            # Prepare video for API
            video_part = self._prepare_video(video_source)
            if video_part is None:
                return {
                    "error": "Failed to load video. Check file path or format.",
                    "_provider": "gemini"
                }

            # Build analysis prompt
            if prompt:
                analysis_prompt = prompt
            else:
                analysis_prompt = self._get_video_analysis_prompt(video_type, competitor_name)

            # Generate with video using new Client API
            response = self.client.models.generate_content(
                model=model_name,
                contents=[analysis_prompt, video_part],
            )

            latency = (datetime.now() - start_time).total_seconds() * 1000

            # Try to parse as JSON
            try:
                content = response.text.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]

                result = json.loads(content.strip())
                result["_provider"] = "gemini"
                result["_model"] = model_name
                result["_latency_ms"] = latency
                if competitor_name:
                    result["competitor"] = competitor_name
                result["video_type"] = video_type

                return result

            except json.JSONDecodeError:
                return {
                    "analysis": response.text,
                    "competitor": competitor_name,
                    "video_type": video_type,
                    "_provider": "gemini",
                    "_model": model_name,
                    "_latency_ms": latency
                }

        except Exception as e:
            logger.error(f"Video analysis failed: {e}")
            return {
                "error": str(e),
                "_provider": "gemini"
            }

    def _prepare_video(self, video_source: Union[str, bytes, Path]) -> Optional[Any]:
        """Prepare video for Google GenAI SDK using types.Part."""
        try:
            if isinstance(video_source, bytes):
                return genai_types.Part.from_bytes(data=video_source, mime_type="video/mp4")

            if isinstance(video_source, Path):
                video_source = str(video_source)

            if isinstance(video_source, str):
                if video_source.startswith(("http://", "https://")):
                    # URL - download first
                    import urllib.request
                    with urllib.request.urlopen(video_source, timeout=120) as response:
                        data = response.read()
                    mime_type = self._get_video_mime_type(video_source)
                    return genai_types.Part.from_bytes(data=data, mime_type=mime_type)
                else:
                    # File path
                    with open(video_source, "rb") as f:
                        data = f.read()
                    mime_type = self._get_video_mime_type(video_source)
                    return genai_types.Part.from_bytes(data=data, mime_type=mime_type)

            return None
        except Exception as e:
            logger.error(f"Failed to prepare video: {e}")
            return None

    def _get_video_mime_type(self, path: str) -> str:
        """Get MIME type for video file."""
        path_lower = path.lower()
        if path_lower.endswith(".mp4"):
            return "video/mp4"
        elif path_lower.endswith(".webm"):
            return "video/webm"
        elif path_lower.endswith(".mov"):
            return "video/quicktime"
        elif path_lower.endswith(".avi"):
            return "video/x-msvideo"
        elif path_lower.endswith(".mkv"):
            return "video/x-matroska"
        return "video/mp4"  # Default

    def _get_video_analysis_prompt(self, video_type: str, competitor_name: Optional[str]) -> str:
        """Get analysis prompt based on video type."""
        company_ref = f"from {competitor_name}" if competitor_name else ""

        prompts = {
            "demo": f"""Analyze this product demo video {company_ref} for competitive intelligence.
Watch the entire video carefully and extract:
{{
    "product_name": "Name of the product being demonstrated",
    "key_features_shown": ["List of features demonstrated"],
    "user_interface_notes": "Description of the UI/UX design",
    "workflow_steps": ["Key workflow steps shown"],
    "integration_mentions": ["Integrations or third-party tools mentioned"],
    "unique_capabilities": ["Features that seem unique or innovative"],
    "target_user": "Who this product seems designed for",
    "pain_points_addressed": ["Problems the product solves"],
    "competitive_advantages": ["What they emphasize as differentiators"],
    "areas_of_weakness": ["Potential limitations or missing features"],
    "call_to_action": "What action they want viewers to take",
    "production_quality": "Assessment of video production quality",
    "key_timestamps": [{{"time": "0:00", "event": "description"}}],
    "summary": "2-3 sentence summary for competitive analysis"
}}""",
            "webinar": f"""Analyze this webinar recording {company_ref} for competitive intelligence.
Watch carefully and extract:
{{
    "webinar_title": "Title or topic of the webinar",
    "speakers": ["Names and titles of speakers"],
    "key_topics": ["Main topics covered"],
    "product_mentions": ["Products or features mentioned"],
    "customer_stories": ["Customer examples or case studies mentioned"],
    "statistics_cited": ["Key statistics or data points shared"],
    "industry_trends": ["Industry trends discussed"],
    "roadmap_hints": ["Future features or direction mentioned"],
    "competitive_positioning": "How they position against competitors",
    "target_audience": "Who this webinar is for",
    "q_and_a_highlights": ["Notable questions and answers"],
    "marketing_messages": ["Key marketing messages"],
    "summary": "2-3 sentence summary for competitive analysis"
}}""",
            "tutorial": f"""Analyze this tutorial video {company_ref} for competitive intelligence.
Watch and extract:
{{
    "tutorial_topic": "What the tutorial teaches",
    "feature_depth": "How advanced/basic the features shown are",
    "user_experience": "Assessment of ease of use shown",
    "configuration_options": ["Settings and customization shown"],
    "technical_requirements": ["Technical requirements mentioned"],
    "integration_setup": ["Integration steps demonstrated"],
    "common_issues": ["Troubleshooting or issues addressed"],
    "best_practices": ["Recommended practices shared"],
    "learning_curve": "Assessment of product complexity",
    "support_resources": ["Help resources mentioned"],
    "summary": "2-3 sentence summary for competitive analysis"
}}""",
            "advertisement": f"""Analyze this advertisement video {company_ref} for competitive intelligence.
Watch and extract:
{{
    "main_message": "Primary marketing message",
    "value_proposition": "Core value proposition presented",
    "target_audience": "Who the ad targets",
    "emotional_appeal": "Emotional triggers used",
    "key_benefits": ["Benefits highlighted"],
    "proof_points": ["Evidence or social proof shown"],
    "brand_positioning": "How they position their brand",
    "call_to_action": "Desired viewer action",
    "production_style": "Description of ad style and quality",
    "competitive_claims": ["Claims about being better than alternatives"],
    "estimated_budget": "Assessment of production budget (low/medium/high)",
    "summary": "2-3 sentence summary for competitive analysis"
}}""",
            "general": f"""Analyze this video {company_ref} for competitive intelligence.
Watch and extract all relevant information:
{{
    "video_type": "Type of video content",
    "main_topic": "Primary topic or purpose",
    "key_information": ["Most important points"],
    "products_mentioned": ["Products or services shown"],
    "people_featured": ["Key people and their roles"],
    "notable_quotes": ["Important statements made"],
    "visual_elements": ["Notable visual content"],
    "competitive_insights": ["Insights relevant for competitive analysis"],
    "summary": "2-3 sentence summary"
}}"""
        }

        return prompts.get(video_type, prompts["general"])

    # ============== REAL-TIME GROUNDING (v5.0.6) ==============

    def search_and_ground(
        self,
        query: str,
        competitor_name: Optional[str] = None,
        search_type: str = "general",
    ) -> Dict[str, Any]:
        """
        Use Gemini with Google Search grounding for real-time information.

        v5.0.6: Added for getting current, factual information about competitors.

        Args:
            query: Search query or question
            competitor_name: Name of competitor (optional, adds context)
            search_type: Type of search (general, news, financial, product)

        Returns:
            Dictionary with grounded response and sources
        """
        if not self.is_available:
            return {
                "error": "Gemini provider not available. Check GOOGLE_AI_API_KEY.",
                "_provider": "gemini"
            }

        start_time = datetime.now()

        try:
            # Use gemini-3-pro-preview for grounding support
            model_name = "gemini-3-pro-preview"

            # Build prompt based on search type
            if competitor_name:
                context = f"About {competitor_name}: "
            else:
                context = ""

            prompts = {
                "general": f"{context}{query}\n\nProvide accurate, current information with specific facts and sources.",
                "news": f"Find the latest news about {competitor_name or 'this topic'}: {query}\n\nFocus on recent announcements, press releases, and industry news.",
                "financial": f"Find financial information about {competitor_name or 'this company'}: {query}\n\nInclude revenue, funding, stock performance, and financial metrics if available.",
                "product": f"Find product information about {competitor_name or 'this company'}: {query}\n\nFocus on features, pricing, updates, and customer feedback.",
            }

            full_prompt = prompts.get(search_type, prompts["general"])

            # Use new Client API with Google Search tool for grounding
            response = self.client.models.generate_content(
                model=model_name,
                contents=full_prompt,
                config=genai_types.GenerateContentConfig(
                    tools=[genai_types.Tool(google_search=genai_types.GoogleSearch())],
                ),
            )

            latency = (datetime.now() - start_time).total_seconds() * 1000

            # Extract grounding metadata if available
            grounding_metadata = None
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'grounding_metadata'):
                    grounding_metadata = candidate.grounding_metadata

            return {
                "response": response.text,
                "grounded": True,
                "search_type": search_type,
                "competitor": competitor_name,
                "query": query,
                "grounding_metadata": str(grounding_metadata) if grounding_metadata else None,
                "_provider": "gemini",
                "_model": model_name,
                "_latency_ms": latency
            }

        except Exception as e:
            logger.error(f"Grounded search failed: {e}")
            # Fallback to non-grounded response
            try:
                response = self.generate_text(
                    prompt=query,
                    system_prompt=f"Provide information about {competitor_name}" if competitor_name else None,
                )
                return {
                    "response": response.content,
                    "grounded": False,
                    "fallback_reason": str(e),
                    "search_type": search_type,
                    "competitor": competitor_name,
                    "_provider": "gemini",
                    "_model": self.config.model
                }
            except:
                return {
                    "error": str(e),
                    "_provider": "gemini"
                }

    def research_competitor(
        self,
        competitor_name: str,
        research_areas: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Comprehensive competitor research using real-time grounding.

        v5.0.6: Deep research feature for competitor profiles.

        Args:
            competitor_name: Name of the competitor
            research_areas: Optional list of areas to research

        Returns:
            Dictionary with comprehensive research results
        """
        if not research_areas:
            research_areas = ["overview", "products", "pricing", "news", "financials"]

        results = {
            "competitor": competitor_name,
            "research_timestamp": datetime.utcnow().isoformat(),
            "sections": {},
            "_provider": "gemini"
        }

        queries = {
            "overview": f"What is {competitor_name}? Provide company overview including founding, headquarters, and market position.",
            "products": f"What products and services does {competitor_name} offer? List main products with descriptions.",
            "pricing": f"What is the pricing model for {competitor_name}? Include specific prices if available.",
            "news": f"What is the latest news about {competitor_name}? Focus on recent announcements.",
            "financials": f"What is the financial status of {competitor_name}? Include funding, revenue, and growth metrics.",
            "customers": f"Who are the customers of {competitor_name}? Include notable clients and target market.",
            "technology": f"What technology does {competitor_name} use? Include tech stack and innovations.",
            "leadership": f"Who leads {competitor_name}? Include key executives and their backgrounds.",
            "partnerships": f"What partnerships does {competitor_name} have? Include integrations and alliances.",
            "competitors": f"Who are the main competitors of {competitor_name}? Include market comparison.",
        }

        for area in research_areas:
            if area in queries:
                result = self.search_and_ground(
                    query=queries[area],
                    competitor_name=competitor_name,
                    search_type="general"
                )
                results["sections"][area] = result.get("response", result.get("error", "No data"))

        return results

    # ============== BULK NEWS PROCESSING (v5.0.6) ==============

    def process_news_batch(
        self,
        articles: List[Dict[str, str]],
        analysis_type: str = "summary",
    ) -> List[Dict[str, Any]]:
        """
        Process multiple news articles efficiently using Flash-Lite.

        v5.0.6: Bulk processing for cost-effective news analysis.

        Args:
            articles: List of article dicts with 'title', 'snippet', 'url' keys
            analysis_type: Type of analysis (summary, sentiment, categorize, extract)

        Returns:
            List of analysis results
        """
        if not self.is_available:
            return [{"error": "Gemini not available"} for _ in articles]

        # Use Flash for bulk processing (fast, high throughput)
        model_name = "gemini-3-flash-preview"

        try:
            results = []
            batch_size = 10  # Process in batches for efficiency

            for i in range(0, len(articles), batch_size):
                batch = articles[i:i + batch_size]

                # Build batch prompt
                prompt = self._build_batch_news_prompt(batch, analysis_type)

                # Use new Client API
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=4096,
                    ),
                )

                # Parse batch results
                batch_results = self._parse_batch_news_response(response.text, batch)
                results.extend(batch_results)

            return results

        except Exception as e:
            logger.error(f"Batch news processing failed: {e}")
            return [{"error": str(e)} for _ in articles]

    def _build_batch_news_prompt(
        self,
        articles: List[Dict[str, str]],
        analysis_type: str
    ) -> str:
        """Build prompt for batch news processing."""
        articles_text = ""
        for i, article in enumerate(articles):
            articles_text += f"\n[Article {i+1}]\nTitle: {article.get('title', 'N/A')}\nSnippet: {article.get('snippet', 'N/A')}\n"

        prompts = {
            "summary": f"""Analyze these news articles and provide a brief summary for each.
Return JSON array:
[{{"article_id": 1, "summary": "1-2 sentence summary", "relevance": "high/medium/low"}}]

ARTICLES:
{articles_text}""",
            "sentiment": f"""Analyze the sentiment of these news articles.
Return JSON array:
[{{"article_id": 1, "sentiment": "positive/negative/neutral", "confidence": 0.0-1.0, "key_phrases": ["phrases"]}}]

ARTICLES:
{articles_text}""",
            "categorize": f"""Categorize these news articles by event type.
Categories: funding, acquisition, partnership, product_launch, leadership, legal, earnings, expansion, layoffs, other

Return JSON array:
[{{"article_id": 1, "category": "category", "subcategory": "optional", "importance": "high/medium/low"}}]

ARTICLES:
{articles_text}""",
            "extract": f"""Extract key competitive intelligence from these articles.
Return JSON array:
[{{"article_id": 1, "company_mentioned": "name", "key_facts": ["facts"], "numbers": ["metrics"], "implications": "competitive implication"}}]

ARTICLES:
{articles_text}"""
        }

        return prompts.get(analysis_type, prompts["summary"])

    def _parse_batch_news_response(
        self,
        response_text: str,
        articles: List[Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        """Parse batch news processing response."""
        try:
            # Clean response
            content = response_text.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]

            results = json.loads(content.strip())

            # Merge with original article data
            for result in results:
                idx = result.get("article_id", 1) - 1
                if 0 <= idx < len(articles):
                    result["title"] = articles[idx].get("title")
                    result["url"] = articles[idx].get("url")
                result["_provider"] = "gemini"
                result["_model"] = "gemini-3-flash-preview"

            return results

        except json.JSONDecodeError:
            # Return raw analysis if not JSON
            return [{"raw_analysis": response_text, "_provider": "gemini"}]

    def analyze_news_trends(
        self,
        articles: List[Dict[str, str]],
        competitor_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyze trends across multiple news articles.

        v5.0.6: Trend analysis for competitive intelligence.

        Args:
            articles: List of article dicts
            competitor_name: Optional competitor focus

        Returns:
            Trend analysis dictionary
        """
        if not articles:
            return {"error": "No articles provided"}

        # Build context from articles
        articles_text = ""
        for i, article in enumerate(articles[:50]):  # Limit to 50 articles
            articles_text += f"- {article.get('title', 'N/A')}: {article.get('snippet', '')[:200]}\n"

        company_ref = f"about {competitor_name}" if competitor_name else ""

        prompt = f"""Analyze these news articles {company_ref} and identify trends.

ARTICLES:
{articles_text}

Provide analysis as JSON:
{{
    "overall_sentiment": "positive/negative/neutral/mixed",
    "sentiment_trend": "improving/declining/stable",
    "key_themes": ["top 5 recurring themes"],
    "notable_events": ["most significant events"],
    "market_signals": ["competitive intelligence signals"],
    "risk_indicators": ["potential risks or concerns"],
    "opportunity_indicators": ["potential opportunities"],
    "competitor_mentions": ["other companies mentioned"],
    "time_pattern": "Are events clustered in time?",
    "recommendation": "Strategic recommendation based on news",
    "summary": "3-4 sentence executive summary"
}}"""

        response = self.generate_text(prompt, temperature=0.2)

        if not response.success:
            return {"error": response.error, "_provider": "gemini"}

        try:
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]

            result = json.loads(content.strip())
            result["_provider"] = "gemini"
            result["_model"] = response.model
            result["articles_analyzed"] = len(articles)
            if competitor_name:
                result["competitor"] = competitor_name

            return result

        except json.JSONDecodeError:
            return {
                "analysis": response.content,
                "articles_analyzed": len(articles),
                "_provider": "gemini"
            }

    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Generate structured JSON output using Gemini.

        Args:
            prompt: The user prompt requesting JSON output
            system_prompt: Optional system instruction
            model: Override model for this request
            temperature: Override temperature (defaults to 0.1 for JSON)

        Returns:
            Parsed JSON as dictionary, or {"error": "..."} on failure
        """
        # Add JSON instruction to system prompt
        json_system = (system_prompt or "") + "\n\nIMPORTANT: Respond ONLY with valid JSON. No markdown, no explanation, just the JSON object."

        response = self.generate_text(
            prompt=prompt,
            system_prompt=json_system.strip(),
            model=model,
            temperature=temperature or 0.1,
        )

        if not response.success:
            return {"error": response.error, "_provider": "gemini"}

        try:
            # Clean response (remove markdown code blocks if present)
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]

            result = json.loads(content.strip())
            result["_provider"] = "gemini"
            result["_model"] = response.model
            result["_cost"] = response.cost_estimate

            return result

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Gemini JSON response: {e}")
            return {
                "error": f"JSON parse error: {str(e)}",
                "raw_response": response.content[:500],
                "_provider": "gemini",
            }


class GeminiExtractor:
    """
    Data extractor using Gemini, compatible with existing GPTExtractor interface.

    This class provides the same methods as GPTExtractor but uses Gemini models.
    Can be used as a drop-in replacement or in hybrid mode.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-3-flash-preview"):
        """
        Initialize Gemini extractor.

        Args:
            api_key: Google AI API key (uses env var if not provided)
            model: Gemini model to use
        """
        self.provider = GeminiProvider(GeminiConfig(
            api_key=api_key or os.getenv("GOOGLE_AI_API_KEY", ""),
            model=model,
        ))

    @property
    def is_available(self) -> bool:
        """Check if extractor is available."""
        return self.provider.is_available

    def extract_from_content(
        self,
        competitor_name: str,
        content: str,
        page_type: str = "homepage"
    ) -> Dict[str, Any]:
        """
        Extract structured data from page content using Gemini.

        Compatible with GPTExtractor.extract_from_content() interface.

        Args:
            competitor_name: Name of the competitor
            content: Page content to analyze
            page_type: Type of page (homepage, pricing, about, features, customers)

        Returns:
            Dictionary with extracted data
        """
        if not self.is_available:
            return {
                "extraction_notes": "Gemini not available. Set GOOGLE_AI_API_KEY.",
                "_provider": "gemini",
            }

        # Truncate content if too long
        max_content_length = 12000  # Gemini has larger context windows
        if len(content) > max_content_length:
            content = content[:max_content_length] + "..."

        prompt = self._build_extraction_prompt(competitor_name, content, page_type)
        system_prompt = self._get_system_prompt()

        return self.provider.generate_json(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1,
        )

    def _get_system_prompt(self) -> str:
        """System prompt for the extraction agent."""
        return """You are a competitive intelligence analyst specializing in healthcare IT companies.
Your task is to extract structured data from competitor websites.
Be precise and only extract information that is clearly stated.
If information is not available, use null.
For pricing, look for specific numbers, not vague ranges.
For features, focus on product capabilities relevant to patient intake, eligibility verification, payments, and patient engagement."""

    def _build_extraction_prompt(self, competitor_name: str, content: str, page_type: str) -> str:
        """Build the extraction prompt based on page type."""

        if page_type == "pricing":
            return f"""Analyze this PRICING page for {competitor_name}.
Extract the following pricing details. Be extremely specific with numbers.
Return JSON:
{{
    "pricing_model": "Describe the model (e.g., 'Per Provider/Month', 'Per Visit', 'Platform Fee'). Look for tiers.",
    "base_price": "Lowest numeric price found (e.g., '$299'). Include currency symbol.",
    "price_unit": "The unit for the base price (e.g., 'per month', 'per provider', 'one-time').",
    "free_trial": "True/False if mentioned",
    "setup_fee": "Implementation or setup fee if mentioned",
    "confidence_score": "Confidence 1-100",
    "extraction_notes": "Quote the text where price was found"
}}

CONTENT:
{content}"""

        elif page_type == "features" or page_type == "product":
            return f"""Analyze this FEATURES page for {competitor_name}.
Identify key capabilities relevant to healthcare patient engagement.
Return JSON:
{{
    "product_categories": "High-level categories (e.g., 'Intake', 'Payments', 'Telehealth'). Semicolon-separated.",
    "key_features": "List specific features (e.g., 'Mobile Check-in', 'Real-time Eligibility', 'Biometric Auth'). Comma-separated.",
    "integration_partners": "List EHRs/PMs mentioned (e.g., Epic, Cerner, Athena). Semicolon-separated.",
    "certifications": "Security certs (HIPAA, SOC2, etc.) if mentioned.",
    "confidence_score": "Confidence 1-100",
    "extraction_notes": "Notes on feature availability"
}}

CONTENT:
{content}"""

        elif page_type == "about" or page_type == "customers":
            return f"""Analyze this ABOUT/CUSTOMERS page for {competitor_name}.
Extract company and market data.
Return JSON:
{{
    "year_founded": "Year founded",
    "headquarters": "City, State, Country",
    "employee_count": "Number of employees",
    "customer_count": "Number of customers/providers/users",
    "key_customers": "List specific health system or client names",
    "target_segments": "Who they serve (e.g. 'Large Health Systems', 'Small Practices')",
    "geographic_focus": "Regions served",
    "funding_total": "Total funding or investment details",
    "confidence_score": "Confidence 1-100",
    "extraction_notes": "Notes on company data"
}}

CONTENT:
{content}"""

        else:
            return f"""Analyze this GENERAL content from the {page_type} page of {competitor_name}.
Extract as much structured data as possible. Use null if not found.
Return JSON:
{{
    "pricing_model": "How they charge (e.g., 'Per Visit', 'Per Provider', 'Subscription', 'Custom')",
    "base_price": "Starting price with currency symbol (e.g., '$3.00', '$199/month')",
    "price_unit": "Unit of pricing (e.g., 'per visit', 'per provider/month')",
    "product_categories": "Product types separated by semicolons",
    "key_features": "Main features, comma-separated",
    "integration_partners": "EHR/PM systems they integrate with, semicolon-separated",
    "certifications": "Security certifications (e.g., 'HIPAA; SOC2; HITRUST')",
    "target_segments": "Customer segments (e.g., 'Health Systems; Specialty Practices')",
    "customer_size_focus": "Practice size focus (e.g., 'Small (1-15)', 'Medium (15-50)', 'Large (50+)')",
    "geographic_focus": "Geographic markets",
    "customer_count": "Number of customers if mentioned",
    "key_customers": "Notable customer names if mentioned",
    "employee_count": "Employee count if mentioned",
    "year_founded": "Year company was founded",
    "headquarters": "Company headquarters location",
    "funding_total": "Total funding raised if mentioned",
    "recent_launches": "Recent product announcements",
    "confidence_score": "Your confidence in the extraction (1-100)",
    "extraction_notes": "Any notes about the extraction or data quality"
}}

CONTENT TO ANALYZE:
{content}"""

    def generate_executive_summary(
        self,
        competitor_data: List[Dict[str, Any]],
        custom_prompt: Optional[str] = None,
    ) -> str:
        """
        Generate an executive summary using Gemini.

        Args:
            competitor_data: List of competitor data dictionaries
            custom_prompt: Optional custom prompt to use

        Returns:
            Generated summary text
        """
        if not self.is_available:
            return "Gemini not available. Unable to generate summary."

        # Build context from competitor data
        context = "COMPETITOR DATA:\n"
        for comp in competitor_data[:10]:  # Limit to 10 competitors
            context += f"\n## {comp.get('name', 'Unknown')}\n"
            for key, value in comp.items():
                if value and key not in ['id', 'created_at', 'updated_at']:
                    context += f"- {key}: {value}\n"

        prompt = custom_prompt or """Analyze the competitive landscape and provide an executive summary covering:

1. **Market Overview**: Key trends and competitive dynamics
2. **Top Threats**: Which competitors pose the biggest threat and why
3. **Pricing Analysis**: How competitors are pricing relative to each other
4. **Feature Gaps**: Key differentiators and gaps in the market
5. **Recommendations**: Strategic recommendations based on the data

Be specific and reference actual competitor data. Focus on actionable insights."""

        response = self.provider.generate_text(
            prompt=f"{prompt}\n\n{context}",
            system_prompt="You are a senior competitive intelligence analyst providing strategic insights to healthcare IT executives.",
            temperature=0.3,
            max_tokens=2000,
        )

        if response.success:
            return response.content
        else:
            return f"Failed to generate summary: {response.error}"


# ============== AI ROUTER/DISPATCHER ==============

class AIRouter:
    """
    Routes AI tasks to the most appropriate provider (OpenAI or Gemini).

    Implements cost optimization, fallback logic, and task-specific routing.
    """

    def __init__(self):
        """Initialize AI router with both providers."""
        self.gemini = GeminiProvider()
        self.openai_available = self._check_openai()

        # Default routing preferences
        self.routing_config = {
            # Task type -> preferred provider
            "bulk_extraction": "gemini",      # Gemini is 90% cheaper
            "data_extraction": "gemini",      # Good quality, lower cost
            "executive_summary": "auto",      # Use best available
            "chat_response": "openai",        # OpenAI often better for chat
            "news_analysis": "gemini",        # Bulk processing
            "classification": "gemini",       # Simple tasks
            "complex_reasoning": "openai",    # Complex logic
        }

        # Load config from environment
        self._load_env_config()

    def _check_openai(self) -> bool:
        """Check if OpenAI is available."""
        try:
            from openai import OpenAI
            return bool(os.getenv("OPENAI_API_KEY"))
        except ImportError:
            return False

    def _load_env_config(self):
        """Load routing configuration from environment variables."""
        # AI_PROVIDER can be "openai", "gemini", or "hybrid"
        provider_pref = os.getenv("AI_PROVIDER", "hybrid")

        if provider_pref == "openai":
            # Force all tasks to OpenAI
            for task in self.routing_config:
                self.routing_config[task] = "openai"
        elif provider_pref == "gemini":
            # Force all tasks to Gemini
            for task in self.routing_config:
                self.routing_config[task] = "gemini"
        # "hybrid" keeps the default balanced routing

        # Override specific task routing
        if os.getenv("AI_BULK_TASKS"):
            provider = os.getenv("AI_BULK_TASKS")
            self.routing_config["bulk_extraction"] = provider
            self.routing_config["news_analysis"] = provider

        if os.getenv("AI_QUALITY_TASKS"):
            provider = os.getenv("AI_QUALITY_TASKS")
            self.routing_config["executive_summary"] = provider
            self.routing_config["complex_reasoning"] = provider

    def get_provider(self, task_type: str) -> str:
        """
        Get the recommended provider for a task type.

        Args:
            task_type: Type of AI task

        Returns:
            "openai" or "gemini"
        """
        preference = self.routing_config.get(task_type, "auto")

        if preference == "auto":
            # Choose based on availability and cost
            if self.gemini.is_available:
                return "gemini"  # Default to cheaper option
            elif self.openai_available:
                return "openai"
            else:
                return "none"

        # Check if preferred provider is available
        if preference == "gemini" and not self.gemini.is_available:
            if os.getenv("AI_FALLBACK_ENABLED", "true").lower() == "true":
                return "openai" if self.openai_available else "none"
            return "none"

        if preference == "openai" and not self.openai_available:
            if os.getenv("AI_FALLBACK_ENABLED", "true").lower() == "true":
                return "gemini" if self.gemini.is_available else "none"
            return "none"

        return preference

    def route_request(
        self,
        task_type: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        require_json: bool = False,
    ) -> AIResponse:
        """
        Route a request to the appropriate provider.

        Args:
            task_type: Type of task (affects routing)
            prompt: The prompt to send
            system_prompt: Optional system instruction
            require_json: Whether to request JSON output

        Returns:
            AIResponse from the chosen provider
        """
        provider = self.get_provider(task_type)

        if provider == "none":
            return AIResponse(
                content="",
                model="none",
                provider="none",
                tokens_used=0,
                cost_estimate=0.0,
                latency_ms=0.0,
                success=False,
                error="No AI provider available. Configure OPENAI_API_KEY or GOOGLE_AI_API_KEY.",
            )

        if provider == "gemini":
            if require_json:
                result = self.gemini.generate_json(prompt, system_prompt)
                return AIResponse(
                    content=json.dumps(result),
                    model=self.gemini.config.model,
                    provider="gemini",
                    tokens_used=0,
                    cost_estimate=result.get("_cost", 0.0),
                    latency_ms=0.0,
                    success="error" not in result,
                    error=result.get("error"),
                )
            else:
                return self.gemini.generate_text(prompt, system_prompt)

        else:  # OpenAI
            return self._call_openai(prompt, system_prompt, require_json)

    def _call_openai(
        self,
        prompt: str,
        system_prompt: Optional[str],
        require_json: bool,
    ) -> AIResponse:
        """Call OpenAI API."""
        try:
            from openai import OpenAI

            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            start_time = datetime.now()

            kwargs = {
                "model": model,
                "messages": messages,
                "temperature": 0.1,
            }

            if require_json:
                kwargs["response_format"] = {"type": "json_object"}

            response = client.chat.completions.create(**kwargs)

            latency = (datetime.now() - start_time).total_seconds() * 1000

            return AIResponse(
                content=response.choices[0].message.content,
                model=model,
                provider="openai",
                tokens_used=response.usage.total_tokens if response.usage else 0,
                cost_estimate=0.0,  # Could calculate based on model
                latency_ms=latency,
                success=True,
            )

        except Exception as e:
            return AIResponse(
                content="",
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                provider="openai",
                tokens_used=0,
                cost_estimate=0.0,
                latency_ms=0.0,
                success=False,
                error=str(e),
            )


# ============== CONVENIENCE FUNCTIONS ==============

def get_gemini_provider() -> Optional[GeminiProvider]:
    """Get a configured Gemini provider, or None if not available."""
    provider = GeminiProvider()
    return provider if provider.is_available else None


def get_ai_router() -> AIRouter:
    """Get the AI router instance."""
    return AIRouter()


def extract_with_gemini(competitor_name: str, content: str, page_type: str = "homepage") -> Dict[str, Any]:
    """
    Extract competitor data using Gemini.

    Convenience function for quick extraction.
    """
    extractor = GeminiExtractor()
    return extractor.extract_from_content(competitor_name, content, page_type)


# ============== TEST FUNCTION ==============

def test_gemini_provider():
    """Test the Gemini provider."""
    print("Testing Gemini Provider...")
    print("-" * 50)

    provider = GeminiProvider()

    if not provider.is_available:
        print("Gemini not available. Set GOOGLE_AI_API_KEY environment variable.")
        return

    print(f"Model: {provider.config.model}")

    # Test text generation
    print("\n1. Testing text generation...")
    response = provider.generate_text(
        prompt="Explain in one sentence what Gemini AI is.",
        temperature=0.3,
    )

    if response.success:
        print(f"   Response: {response.content[:100]}...")
        print(f"   Cost: ${response.cost_estimate:.6f}")
        print(f"   Latency: {response.latency_ms:.0f}ms")
    else:
        print(f"   Error: {response.error}")

    # Test JSON generation
    print("\n2. Testing JSON generation...")
    result = provider.generate_json(
        prompt='Extract the company name and year founded from this text: "Phreesia was founded in 2005 in Raleigh, NC."',
    )

    if "error" not in result:
        print(f"   Result: {json.dumps(result, indent=2)}")
    else:
        print(f"   Error: {result['error']}")

    # Test AI Router
    print("\n3. Testing AI Router...")
    router = AIRouter()
    print(f"   OpenAI available: {router.openai_available}")
    print(f"   Gemini available: {router.gemini.is_available}")
    print(f"   Bulk extraction -> {router.get_provider('bulk_extraction')}")
    print(f"   Executive summary -> {router.get_provider('executive_summary')}")

    print("\n" + "-" * 50)
    print("Gemini provider test complete!")


if __name__ == "__main__":
    test_gemini_provider()
