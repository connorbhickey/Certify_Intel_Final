"""
Certify Intel - AI Deep Research Integration (v5.0.6)
Provides deep research capabilities using ChatGPT and Gemini.

Features:
- ChatGPT Deep Research: Comprehensive multi-source research using GPT-4
- Gemini Deep Research: Real-time grounded research using Google Search
- Battlecard Report Generation: One-click competitive reports

NEWS-4B: ChatGPT Deep Research integration
NEWS-4C: Gemini Deep Research integration
"""

import os
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from gemini_provider import GeminiProvider
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("Gemini provider not available")


@dataclass
class ResearchResult:
    """Result of a deep research request."""
    competitor_name: str
    research_type: str
    content: str
    sections: Dict[str, str]
    sources_used: List[str]
    provider: str
    model: str
    timestamp: str
    cost_estimate: float
    latency_ms: float
    success: bool
    error: Optional[str] = None


class ChatGPTResearcher:
    """
    ChatGPT Deep Research for competitive intelligence.

    Uses GPT-4 with structured prompts to generate comprehensive
    competitor research reports.
    """

    # Research templates
    RESEARCH_TEMPLATES = {
        "battlecard": """You are generating a concise competitive win strategy \
for a sales team competing against {competitor_name} in the healthcare technology market.

RULES:
- Be extremely concise. Maximum 400 words total.
- Use only factual, verifiable information.
- Every claim must reference a source. Include the source URL in parentheses after the claim.
- No generic advice. Every point must be specific to this competitor.
- No filler, no fluff, no introductions, no conclusions.
- Use markdown formatting with ## headers and bullet points.

FORMAT (follow exactly):

## QUICK PROFILE
- One-line description with founding year, HQ, and employee count
- Core products and target market

## KEY VULNERABILITIES (3 max)
- Specific, actionable weaknesses we can exploit in deals
- Each must cite a source (review site, news article, or public data)

## WIN STRATEGY (3-4 bullets max)
- Concrete actions for the sales team in competitive deals
- Reference specific product gaps, pricing disadvantages, or customer complaints

## OBJECTION RESPONSES (top 2 only)
- "They have [specific advantage]" → Our counter with evidence
- "They're [specific claim]" → Our counter with evidence

## RECENT INTELLIGENCE
- 2-3 most recent relevant developments (news, funding, product changes)
- Each with date and source URL

{additional_context_marker}
""",
        "market_analysis": """Analyze {competitor_name}'s market position:

## MARKET POSITION
- Current market standing
- Market share estimate
- Growth trajectory

## TARGET CUSTOMERS
- Primary customer segments
- Ideal customer profile
- Key verticals

## GO-TO-MARKET STRATEGY
- Sales approach
- Marketing channels
- Partnership strategy

## COMPETITIVE LANDSCAPE
- Key competitors
- Positioning vs. alternatives

## SWOT ANALYSIS
- Strengths
- Weaknesses
- Opportunities
- Threats

## MARKET TRENDS
- Industry trends affecting them
- How they're responding
""",
        "product_deep_dive": """Deep dive into {competitor_name}'s product:

## PRODUCT OVERVIEW
- Product name(s) and description
- Core functionality
- User interface/experience

## FEATURE ANALYSIS
- Key features (list with descriptions)
- Unique capabilities
- Feature gaps

## TECHNICAL ARCHITECTURE
- Technology stack (if known)
- Integration capabilities
- Security/compliance

## PRICING
- Pricing model
- Price points
- Value proposition

## CUSTOMER FEEDBACK
- Common praise
- Common complaints
- Feature requests

## PRODUCT ROADMAP
- Recent releases
- Announced future features
- Strategic direction
""",
        "quick_summary": """Provide a quick competitive summary for {competitor_name}:

## AT A GLANCE
- One sentence description
- Key metric: customers/revenue/employees
- Threat level: High/Medium/Low

## TOP 3 STRENGTHS
1.
2.
3.

## TOP 3 WEAKNESSES
1.
2.
3.

## KEY TAKEAWAY
One paragraph on how to compete with them.
"""
    }

    def __init__(self):
        """Initialize researcher (uses Claude Opus 4.5 via AIRouter)."""
        self.api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.model = "claude-opus-4.5"
        self.client = None  # No longer used directly — AIRouter handles clients

        if self.api_key:
            logger.info(f"AI researcher initialized — routing via AIRouter to {self.model}")

    @property
    def is_available(self) -> bool:
        """Check if researcher is available."""
        return self.api_key is not None

    async def research(
        self,
        competitor_name: str,
        research_type: str = "battlecard",
        additional_context: Optional[str] = None,
    ) -> ResearchResult:
        """
        Generate deep research report using Claude Opus 4.5 via AIRouter.

        Args:
            competitor_name: Name of the competitor
            research_type: Type of research (battlecard, market_analysis, product_deep_dive, quick_summary)
            additional_context: Additional context to include

        Returns:
            ResearchResult with the generated report
        """
        if not self.is_available:
            return ResearchResult(
                competitor_name=competitor_name,
                research_type=research_type,
                content="",
                sections={},
                sources_used=[],
                provider="none",
                model=self.model,
                timestamp=datetime.utcnow().isoformat(),
                cost_estimate=0.0,
                latency_ms=0.0,
                success=False,
                error="No AI provider available. Configure ANTHROPIC_API_KEY or OPENAI_API_KEY."
            )

        start_time = datetime.now()

        try:
            from ai_router import get_ai_router, TaskType

            router = get_ai_router()

            # Get template
            template = self.RESEARCH_TEMPLATES.get(research_type, self.RESEARCH_TEMPLATES["battlecard"])

            # For battlecard, inject additional context into the template marker
            if research_type == "battlecard" and additional_context:
                context_block = f"USE THIS DATA TO INFORM YOUR ANALYSIS:\n{additional_context}"
                prompt = template.replace("{additional_context_marker}", context_block)
                prompt = prompt.format(competitor_name=competitor_name)
            else:
                prompt = template.format(competitor_name=competitor_name)
                if "{additional_context_marker}" in prompt:
                    prompt = prompt.replace("{additional_context_marker}", "")
                if additional_context:
                    prompt += f"\n\nADDITIONAL CONTEXT:\n{additional_context}"

            # Map research_type to TaskType
            task_map = {
                "battlecard": TaskType.BATTLECARD,
                "market_analysis": TaskType.ANALYSIS,
                "product_deep_dive": TaskType.ANALYSIS,
                "quick_summary": TaskType.SUMMARIZATION,
            }
            task_type = task_map.get(research_type, TaskType.BATTLECARD)

            # Route through AIRouter → Claude Opus 4.5 (with fallback to GPT-4o → Gemini)
            result = await router.generate(
                prompt=prompt,
                task_type=task_type,
                system_prompt=(
                    "You are a senior competitive intelligence analyst. "
                    "Be extremely concise and direct. Every claim must be sourced. "
                    "No filler. No generic advice. Maximum 400 words. "
                    "CRITICAL DATA INTEGRITY RULE: You must ONLY reference data provided "
                    "in this context. Do NOT fabricate, estimate, or assume any data points. "
                    "If data is not available, state 'No verified data available for this metric.'"
                ),
                max_tokens=1500,
                temperature=0.2,
            )

            latency = (datetime.now() - start_time).total_seconds() * 1000
            content = result["response"]

            # Parse sections from markdown
            sections = self._parse_sections(content)

            return ResearchResult(
                competitor_name=competitor_name,
                research_type=research_type,
                content=content,
                sections=sections,
                sources_used=[f"Claude Opus 4.5 via AIRouter ({result.get('provider', 'anthropic')})"],
                provider=result.get("provider", "anthropic"),
                model=result.get("model", "claude-opus-4.5"),
                timestamp=datetime.utcnow().isoformat(),
                cost_estimate=result.get("cost_usd", 0.0),
                latency_ms=latency,
                success=True
            )

        except Exception as e:
            latency = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"AI research failed: {e}")
            return ResearchResult(
                competitor_name=competitor_name,
                research_type=research_type,
                content="",
                sections={},
                sources_used=[],
                provider="error",
                model=self.model,
                timestamp=datetime.utcnow().isoformat(),
                cost_estimate=0.0,
                latency_ms=latency,
                success=False,
                error=str(e)
            )

    def _parse_sections(self, content: str) -> Dict[str, str]:
        """Parse markdown sections from content."""
        sections = {}
        current_section = None
        current_content = []

        for line in content.split('\n'):
            if line.startswith('## '):
                if current_section:
                    sections[current_section] = '\n'.join(current_content).strip()
                current_section = line[3:].strip()
                current_content = []
            elif current_section:
                current_content.append(line)

        if current_section:
            sections[current_section] = '\n'.join(current_content).strip()

        return sections

    def _estimate_cost(self, tokens: int) -> float:
        """Estimate cost based on model and tokens."""
        # GPT-4o pricing (approximate)
        pricing = {
            "gpt-4o": {"input": 2.50, "output": 10.00},
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
            "gpt-4-turbo": {"input": 10.00, "output": 30.00},
        }
        model_pricing = pricing.get(self.model, pricing["gpt-4o-mini"])
        # Rough 50/50 split between input and output
        return (tokens / 2 / 1_000_000) * (model_pricing["input"] + model_pricing["output"])


class GeminiResearcher:
    """
    Gemini Deep Research for competitive intelligence.

    Uses Gemini with real-time Google Search grounding for
    current, factual information about competitors.
    """

    def __init__(self):
        """Initialize Gemini researcher."""
        self.provider = None
        if GEMINI_AVAILABLE:
            self.provider = GeminiProvider()
            if self.provider.is_available:
                logger.info("Gemini researcher initialized")

    @property
    def is_available(self) -> bool:
        """Check if researcher is available."""
        return self.provider is not None and self.provider.is_available

    def research(
        self,
        competitor_name: str,
        research_type: str = "battlecard",
        additional_context: Optional[str] = None,
    ) -> ResearchResult:
        """
        Generate deep research report using Gemini with grounding.

        Args:
            competitor_name: Name of the competitor
            research_type: Type of research
            additional_context: Additional context to include

        Returns:
            ResearchResult with the generated report
        """
        if not self.is_available:
            return ResearchResult(
                competitor_name=competitor_name,
                research_type=research_type,
                content="",
                sections={},
                sources_used=[],
                provider="gemini",
                model="",
                timestamp=datetime.utcnow().isoformat(),
                cost_estimate=0.0,
                latency_ms=0.0,
                success=False,
                error="Gemini not available. Configure GOOGLE_AI_API_KEY."
            )

        start_time = datetime.now()

        try:
            # Use research_competitor for comprehensive research
            result = self.provider.research_competitor(
                competitor_name=competitor_name,
                research_areas=self._get_research_areas(research_type)
            )

            latency = (datetime.now() - start_time).total_seconds() * 1000

            # Format content from sections
            content = self._format_research_content(competitor_name, result, research_type)
            sections = result.get("sections", {})

            return ResearchResult(
                competitor_name=competitor_name,
                research_type=research_type,
                content=content,
                sections=sections,
                sources_used=["Google Search", "Gemini Grounding"],
                provider="gemini",
                model="gemini-3-pro-preview",
                timestamp=datetime.utcnow().isoformat(),
                cost_estimate=0.01,  # Rough estimate
                latency_ms=latency,
                success=True
            )

        except Exception as e:
            latency = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Gemini research failed: {e}")
            return ResearchResult(
                competitor_name=competitor_name,
                research_type=research_type,
                content="",
                sections={},
                sources_used=[],
                provider="gemini",
                model="gemini-3-pro-preview",
                timestamp=datetime.utcnow().isoformat(),
                cost_estimate=0.0,
                latency_ms=latency,
                success=False,
                error=str(e)
            )

    def _get_research_areas(self, research_type: str) -> List[str]:
        """Get research areas for a given research type."""
        areas = {
            "battlecard": ["overview", "products", "pricing", "news", "customers", "competitors"],
            "market_analysis": ["overview", "customers", "competitors", "financials"],
            "product_deep_dive": ["products", "technology", "pricing", "partnerships"],
            "quick_summary": ["overview", "products", "news"],
        }
        return areas.get(research_type, areas["battlecard"])

    def _format_research_content(
        self,
        competitor_name: str,
        result: Dict[str, Any],
        research_type: str
    ) -> str:
        """Format research results into markdown content."""
        sections = result.get("sections", {})

        content = f"# {competitor_name} - {research_type.replace('_', ' ').title()}\n\n"
        content += f"*Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}*\n"
        content += "*Source: Real-time Google Search via Gemini*\n\n"

        for section_name, section_content in sections.items():
            content += f"## {section_name.upper()}\n\n"
            content += f"{section_content}\n\n"

        return content


class DeepResearchManager:
    """
    Unified manager for deep research across providers.

    Automatically selects the best provider based on availability
    and research type.
    """

    def __init__(self):
        """Initialize research manager."""
        self.chatgpt = ChatGPTResearcher()
        self.gemini = GeminiResearcher()

    async def research(
        self,
        competitor_name: str,
        research_type: str = "battlecard",
        provider: Optional[str] = None,
        additional_context: Optional[str] = None,
    ) -> ResearchResult:
        """
        Generate deep research report.

        Args:
            competitor_name: Name of the competitor
            research_type: Type of research
            provider: Preferred provider ("chatgpt", "gemini", or None for auto)
            additional_context: Additional context

        Returns:
            ResearchResult from the selected provider
        """
        # Select provider
        if provider == "chatgpt" and self.chatgpt.is_available:
            return await self.chatgpt.research(competitor_name, research_type, additional_context)
        elif provider == "gemini" and self.gemini.is_available:
            return self.gemini.research(competitor_name, research_type, additional_context)
        elif provider is None:
            # Auto-select: Gemini for quick/news (real-time data), Claude for comprehensive analysis
            if research_type in ["quick_summary", "news"]:
                if self.gemini.is_available:
                    return self.gemini.research(competitor_name, research_type, additional_context)
            if self.chatgpt.is_available:
                return await self.chatgpt.research(competitor_name, research_type, additional_context)
            if self.gemini.is_available:
                return self.gemini.research(competitor_name, research_type, additional_context)

        return ResearchResult(
            competitor_name=competitor_name,
            research_type=research_type,
            content="",
            sections={},
            sources_used=[],
            provider="none",
            model="none",
            timestamp=datetime.utcnow().isoformat(),
            cost_estimate=0.0,
            latency_ms=0.0,
            success=False,
            error="No AI provider available. Configure ANTHROPIC_API_KEY or GOOGLE_AI_API_KEY."
        )

    def get_available_providers(self) -> Dict[str, bool]:
        """Get availability status of all providers."""
        return {
            "chatgpt": self.chatgpt.is_available,
            "gemini": self.gemini.is_available,
        }

    def get_research_types(self) -> List[Dict[str, str]]:
        """Get available research types with descriptions."""
        return [
            {
                "type": "battlecard",
                "name": "Sales Battlecard",
                "description": "Comprehensive competitive analysis for sales",
            },
            {
                "type": "market_analysis",
                "name": "Market Analysis",
                "description": "Market position and competitive landscape",
            },
            {
                "type": "product_deep_dive",
                "name": "Product Deep Dive",
                "description": "Detailed product analysis",
            },
            {
                "type": "quick_summary",
                "name": "Quick Summary",
                "description": "Brief competitive overview",
            },
        ]


# ============== CONVENIENCE FUNCTIONS ==============

def get_research_manager() -> DeepResearchManager:
    """Get the deep research manager instance."""
    return DeepResearchManager()


async def generate_battlecard(
    competitor_name: str,
    provider: Optional[str] = None,
    additional_context: Optional[str] = None,
    news_articles: Optional[List[Dict[str, Any]]] = None,
    competitor_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate a sales battlecard for a competitor.

    Enriches the AI prompt with real news articles and competitor data
    so the output contains real, sourced intelligence.

    Args:
        competitor_name: Name of the competitor
        provider: Preferred provider (chatgpt/gemini)
        additional_context: Additional context to include
        news_articles: Real news articles fetched from web sources
        competitor_data: Competitor record fields from the database

    Returns:
        Dictionary with battlecard content
    """
    # Build enriched context from real data
    context_parts = []

    # Add competitor database fields
    if competitor_data:
        if competitor_data.get("website"):
            context_parts.append(f"Website: {competitor_data['website']}")
        if competitor_data.get("description") or competitor_data.get("notes"):
            context_parts.append(f"Description: {competitor_data.get('description') or competitor_data.get('notes')}")
        if competitor_data.get("employee_count"):
            context_parts.append(f"Employees: {competitor_data['employee_count']}")
        if competitor_data.get("annual_revenue") or competitor_data.get("estimated_revenue"):
            rev = competitor_data.get('annual_revenue') or competitor_data.get('estimated_revenue')
            context_parts.append(f"Revenue: {rev}")
        if competitor_data.get("founding_year"):
            context_parts.append(f"Founded: {competitor_data['founding_year']}")
        if competitor_data.get("headquarters"):
            context_parts.append(f"HQ: {competitor_data['headquarters']}")
        if competitor_data.get("pricing_model"):
            context_parts.append(f"Pricing: {competitor_data['pricing_model']}")
        if competitor_data.get("product_categories"):
            context_parts.append(f"Products: {competitor_data['product_categories']}")
        if competitor_data.get("key_features"):
            context_parts.append(f"Key Features: {competitor_data['key_features']}")
        if competitor_data.get("threat_level"):
            context_parts.append(f"Threat Level: {competitor_data['threat_level']}")
        if competitor_data.get("target_segments"):
            context_parts.append(f"Target Segments: {competitor_data['target_segments']}")
        if competitor_data.get("g2_rating"):
            context_parts.append(f"G2 Rating: {competitor_data['g2_rating']}")
        if competitor_data.get("customer_count"):
            context_parts.append(f"Customers: {competitor_data['customer_count']}")
        if competitor_data.get("certifications"):
            context_parts.append(f"Certifications: {competitor_data['certifications']}")
        if competitor_data.get("integration_partners"):
            context_parts.append(f"Integration Partners: {competitor_data['integration_partners']}")
        if competitor_data.get("dim_overall_score"):
            context_parts.append(f"Overall Dimension Score: {competitor_data['dim_overall_score']}/5")

    # Add real news articles with URLs
    if news_articles and len(news_articles) > 0:
        context_parts.append("\nRECENT NEWS ARTICLES (real sources — use these URLs in your response):")
        for i, article in enumerate(news_articles[:8], 1):
            title = article.get("title", "Untitled")
            url = article.get("url") or article.get("link", "")
            source = article.get("source", "Unknown")
            pub_date = article.get("published_date") or article.get("published_at", "")
            sent = article.get("sentiment", "")
            sent_tag = f" [{sent}]" if sent else ""
            context_parts.append(f"  {i}. \"{title}\" — {source} ({pub_date}){sent_tag} URL: {url}")

    # Add any user-provided additional context
    if additional_context:
        context_parts.append(f"\nADDITIONAL CONTEXT FROM DATABASE:\n{additional_context}")

    enriched_context = "\n".join(context_parts) if context_parts else additional_context

    manager = get_research_manager()
    result = await manager.research(
        competitor_name=competitor_name,
        research_type="battlecard",
        provider=provider,
        additional_context=enriched_context
    )
    return asdict(result)


async def generate_quick_summary(competitor_name: str) -> Dict[str, Any]:
    """Generate a quick competitive summary."""
    manager = get_research_manager()
    result = await manager.research(
        competitor_name=competitor_name,
        research_type="quick_summary"
    )
    return asdict(result)


# ============== TEST FUNCTION ==============

async def test_ai_research():
    """Test the AI research module."""
    print("Testing AI Deep Research...")
    print("-" * 50)

    manager = get_research_manager()
    providers = manager.get_available_providers()

    print(f"ChatGPT available: {providers['chatgpt']}")
    print(f"Gemini available: {providers['gemini']}")

    if not any(providers.values()):
        print("\nNo AI providers configured. Set OPENAI_API_KEY or GOOGLE_AI_API_KEY.")
        return

    print("\nAvailable research types:")
    for rt in manager.get_research_types():
        print(f"  - {rt['type']}: {rt['description']}")

    # Test with available provider
    print("\nGenerating quick summary for 'Phreesia'...")
    result = await manager.research("Phreesia", "quick_summary")

    if result.success:
        print(f"Provider: {result.provider}")
        print(f"Latency: {result.latency_ms:.0f}ms")
        print(f"Cost: ${result.cost_estimate:.4f}")
        print(f"\nContent preview:\n{result.content[:500]}...")
    else:
        print(f"Error: {result.error}")

    print("\n" + "-" * 50)
    print("AI Deep Research test complete!")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_ai_research())
