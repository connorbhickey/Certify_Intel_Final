"""
Certify Intel - AI-Powered Discovery Engine (v7.2)
Multi-stage competitor discovery using Gemini grounding, web scraping, and AI qualification.

Stages:
1. Search: Gemini with Google Search grounding for real-time discovery
2. Scrape: Deep website analysis using Firecrawl/httpx (parallel, max 5 concurrent)
3. Qualify: AIRouter (Claude Opus -> GPT-4o -> Gemini fallback) for qualification
4. Analyze: AIRouter (Claude Opus -> GPT-4o -> Gemini fallback) for threat assessment

Model Routing:
- Stage 1 (Search): Gemini 2.0 Flash with grounding (needs Google Search)
- Stage 2 (Scrape): Firecrawl (500 free credits/month) or httpx (free)
- Stage 3 (Qualify): AIRouter DISCOVERY task -> Claude Opus 4.5 primary
- Stage 4 (Analyze): AIRouter DISCOVERY task -> Claude Opus 4.5 primary
- Fallback chain: Claude Opus -> GPT-4o -> Gemini (automatic)
"""

import asyncio

# Per-stage timeout constants (in seconds)
STAGE_SEARCH_TIMEOUT = 30    # Was 60 -> 30s
STAGE_SCRAPE_TIMEOUT = 10    # Was 15 -> 10s
STAGE_QUALIFY_TIMEOUT = 30   # Was 45 -> 30s
STAGE_ANALYZE_TIMEOUT = 30   # Was 45 -> 30s
DEFAULT_PIPELINE_TIMEOUT = 300  # 5 minutes for full 4-stage AI pipeline
import json  # noqa: E402, F401
import logging  # noqa: E402
import re  # noqa: E402
from typing import Dict, List, Any, Optional  # noqa: E402
from dataclasses import dataclass, field, asdict  # noqa: E402
from datetime import datetime  # noqa: E402
from enum import Enum  # noqa: E402
from urllib.parse import urlparse  # noqa: E402

logger = logging.getLogger(__name__)


class DiscoveryStage(Enum):
    SEARCH = "search"
    SCRAPE = "scrape"
    QUALIFY = "qualify"
    ANALYZE = "analyze"


@dataclass
class QualificationCriteria:
    """Structured qualification criteria for discovery."""
    target_segments: List[str] = field(default_factory=list)
    required_capabilities: List[str] = field(default_factory=list)
    company_size: Dict[str, Any] = field(default_factory=dict)
    geography: List[str] = field(default_factory=list)
    funding_stages: List[str] = field(default_factory=list)
    tech_requirements: List[str] = field(default_factory=list)
    exclusions: List[str] = field(default_factory=list)
    custom_keywords: Dict[str, List[str]] = field(default_factory=dict)

    def to_prompt(self) -> str:
        """Convert criteria to AI prompt text."""
        parts = []

        segment_names = {
            'hospital': 'Hospitals & Health Systems',
            'ambulatory': 'Ambulatory Care',
            'urgent_care': 'Urgent Care',
            'behavioral': 'Behavioral Health',
            'telehealth': 'Telehealth',
            'dental_dso': 'Dental / DSO',
            'lab': 'Laboratory',
            'ltc': 'Long-Term Care'
        }

        if self.target_segments:
            segs = [segment_names.get(s, s) for s in self.target_segments]
            parts.append(f"Target Markets: {', '.join(segs)}")

        capability_names = {
            'pxp': 'Patient Experience Platform',
            'pms': 'Practice Management System',
            'rcm': 'Revenue Cycle Management',
            'ehr': 'EHR/EMR',
            'telehealth': 'Telehealth',
            'payments': 'Patient Payments',
            'biometric': 'Biometric Identification',
            'ai_scribe': 'AI Clinical Scribe'
        }

        if self.required_capabilities:
            caps = [capability_names.get(c, c) for c in self.required_capabilities]
            parts.append(f"Required Capabilities: {', '.join(caps)}")

        if self.company_size:
            size_parts = []
            if self.company_size.get('min_employees'):
                size_parts.append(
                    f"min {self.company_size['min_employees']} employees"
                )
            if self.company_size.get('max_employees'):
                size_parts.append(
                    f"max {self.company_size['max_employees']} employees"
                )
            if size_parts:
                parts.append(f"Company Size: {', '.join(size_parts)}")

        if self.geography:
            geo_names = {
                'us': 'United States',
                'canada': 'Canada',
                'international': 'International'
            }
            geos = [geo_names.get(g, g) for g in self.geography]
            parts.append(f"Geography: {', '.join(geos)}")

        if self.funding_stages:
            parts.append(f"Funding Stage: {', '.join(self.funding_stages)}")

        tech_names = {
            'cloud': 'Cloud-Based',
            'mobile_app': 'Mobile App',
            'fhir': 'FHIR API',
            'hl7': 'HL7 Integration',
            'api': 'Open API',
            'hipaa': 'HIPAA Certified'
        }

        if self.tech_requirements:
            techs = [tech_names.get(t, t) for t in self.tech_requirements]
            parts.append(f"Technology: {', '.join(techs)}")

        exclusion_names = {
            'consulting': 'Consulting Firms',
            'pharma': 'Pharmaceutical',
            'devices': 'Medical Devices',
            'insurance': 'Insurance Providers',
            'staffing': 'Staffing Agencies'
        }

        if self.exclusions:
            excls = [exclusion_names.get(e, e) for e in self.exclusions]
            parts.append(f"EXCLUDE: {', '.join(excls)}")

        if self.custom_keywords.get('include'):
            parts.append(
                f"Must mention: {', '.join(self.custom_keywords['include'])}"
            )

        if self.custom_keywords.get('exclude'):
            parts.append(
                f"Must NOT mention: {', '.join(self.custom_keywords['exclude'])}"
            )

        return '\n'.join(parts) if parts else "Healthcare IT competitors"


@dataclass
class DiscoveryCandidate:
    """A discovered competitor candidate with full analysis."""
    # Basic info
    name: str
    url: str
    domain: str

    # Stage 1: Search results
    search_snippet: str = ""
    search_source: str = ""  # google_grounded, duckduckgo

    # Stage 2: Scraped data
    scraped_content: str = ""
    page_title: str = ""
    meta_description: str = ""
    products_found: List[str] = field(default_factory=list)
    features_found: List[str] = field(default_factory=list)

    # Stage 3: Qualification
    is_qualified: bool = False
    qualification_score: int = 0  # 0-100
    qualification_reasoning: str = ""
    criteria_matches: Dict[str, bool] = field(default_factory=dict)

    # Stage 4: Analysis
    threat_level: str = "Unknown"  # Low, Medium, High, Critical
    threat_score: int = 0  # 0-100
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    competitive_positioning: str = ""
    ai_summary: str = ""

    # Source tracking
    scraped_urls: List[str] = field(default_factory=list)
    data_sources: List[Dict[str, Any]] = field(default_factory=list)

    # Metadata
    discovered_at: str = ""
    stages_completed: List[str] = field(default_factory=list)
    total_processing_time_ms: float = 0


class AIDiscoveryEngine:
    """
    Multi-stage AI-powered competitor discovery engine.

    Uses a pipeline approach:
    1. Search Stage: Gemini with Google Search grounding
    2. Scrape Stage: Firecrawl or httpx (parallel, max 5 concurrent)
    3. Qualify Stage: AIRouter (Claude Opus primary) evaluation
    4. Analyze Stage: AIRouter (Claude Opus primary) threat assessment
    """

    # Domains to ignore (not companies)
    IGNORED_DOMAINS = {
        'g2.com', 'capterra.com', 'softwareadvice.com', 'getapp.com',
        'linkedin.com', 'twitter.com', 'facebook.com', 'instagram.com',
        'youtube.com', 'wikipedia.org', 'crunchbase.com', 'glassdoor.com',
        'indeed.com', 'bloomberg.com', 'reuters.com', 'forbes.com',
        'techcrunch.com', 'healthcareitnews.com',
        'beckershospitalreview.com',
        'github.com', 'medium.com', 'reddit.com', 'quora.com'
    }

    def __init__(self):
        # Import providers
        self.gemini = None
        self.firecrawl = None
        self.scraper = None

        # Initialize Gemini provider with comprehensive logging
        try:
            logger.info("AIDiscoveryEngine: Initializing Gemini provider...")
            from gemini_provider import GeminiProvider
            self.gemini = GeminiProvider()
            if self.gemini and self.gemini.is_available:
                logger.info(
                    "AIDiscoveryEngine: Gemini provider initialized "
                    f"(model: {self.gemini.config.model})"
                )
            else:
                logger.warning(
                    "AIDiscoveryEngine: Gemini provider created but "
                    "NOT available (API key missing or invalid)"
                )
                self.gemini = None
        except ImportError as e:
            logger.error(
                f"AIDiscoveryEngine: Gemini provider import failed: {e}"
            )
            import traceback
            logger.error(
                "AIDiscoveryEngine: Import traceback: "
                f"{traceback.format_exc()}"
            )
            self.gemini = None
        except Exception as e:
            logger.error(
                "AIDiscoveryEngine: Gemini provider init failed: "
                f"{type(e).__name__}: {e}"
            )
            import traceback
            logger.error(
                "AIDiscoveryEngine: Init traceback: "
                f"{traceback.format_exc()}"
            )
            self.gemini = None

        try:
            from firecrawl_integration import FirecrawlClient
            self.firecrawl = FirecrawlClient()
            logger.info("Firecrawl client initialized")
        except ImportError as e:
            logger.warning(f"Firecrawl not available: {e}")

        # Known competitors to exclude
        self._known_competitors = set()
        self._known_domains = set()

        # Track errors per stage for better user feedback
        self._stage_errors: Dict[str, List[Dict[str, str]]] = {}

        # Progress tracking for real-time reporting
        self._progress: Dict[str, Any] = {
            "current_stage": None,
            "current_stage_name": "Initializing...",
            "stages_completed": [],
            "candidates_found": 0,
            "candidates_scraped": 0,
            "candidates_qualified": 0,
            "candidates_analyzed": 0,
            "percent_complete": 0,
            "estimated_time_remaining": 0,
        }

        # Market context for qualification (set in run_discovery)
        self._market_context: Optional[str] = None

        # AIRouter for Stages 3 & 4 (lazy-loaded)
        self._ai_router = None

    def _get_ai_router(self):
        """Get or create the AIRouter singleton for Stages 3-4."""
        if self._ai_router is None:
            try:
                from ai_router import get_ai_router
                self._ai_router = get_ai_router()
                logger.info(
                    "AIDiscoveryEngine: AIRouter loaded for Stages 3-4"
                )
            except ImportError:
                logger.warning(
                    "AIDiscoveryEngine: AIRouter not available, "
                    "will use Gemini fallback"
                )
        return self._ai_router

    def get_progress(self) -> Dict[str, Any]:
        """Get current pipeline progress for polling."""
        return dict(self._progress)

    async def generate_summary(
        self, candidates: list
    ) -> str:
        """Generate executive summary of discovery results."""
        router = self._get_ai_router()
        if not router:
            return "AI router not available for summary generation."

        candidate_text = ""
        for i, c in enumerate(candidates[:15], 1):
            name = c.name if hasattr(c, 'name') else c.get('name', 'Unknown')
            threat = c.threat_level if hasattr(c, 'threat_level') else c.get('threat_level', 'Unknown')
            score = c.qualification_score if hasattr(c, 'qualification_score') else c.get('qualification_score', 0)
            summary = c.ai_summary if hasattr(c, 'ai_summary') else c.get('ai_summary', '')
            candidate_text += f"{i}. {name} (Threat: {threat}, Score: {score}%): {summary}\n"

        prompt = (
            "Generate a concise executive summary (3-4 paragraphs) "
            "of these competitor discovery results:\n\n"
            f"{candidate_text}\n"
            "Include top threats, common patterns, and recommended actions."
        )

        try:
            from ai_router import TaskType
            result = await asyncio.wait_for(
                router.generate(
                    prompt=prompt,
                    task_type=TaskType.DISCOVERY,
                    temperature=0.3,
                    max_tokens=1024,
                    agent_type="discovery_summary"
                ),
                timeout=30.0
            )
            return result.get("response", "Summary generation failed.")
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return "Failed to generate summary."

    def set_known_competitors(self, competitors: List[Dict[str, Any]]):
        """Set list of known competitors to exclude from results."""
        self._known_competitors = set()
        self._known_domains = set()
        for comp in competitors:
            if isinstance(comp, dict):
                name = comp.get('name', '')
                website = comp.get('website', '')
            else:
                name = str(comp)
                website = ''

            if name:
                self._known_competitors.add(name.lower())
            if website:
                domain = self._extract_domain(website)
                if domain:
                    self._known_domains.add(domain.lower())

    async def run_discovery(
        self,
        criteria: QualificationCriteria,
        max_candidates: int = 10,
        stages: Optional[List[DiscoveryStage]] = None,
        timeout_seconds: int = DEFAULT_PIPELINE_TIMEOUT,
        market_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run the full discovery pipeline.

        Args:
            criteria: Qualification criteria
            max_candidates: Maximum candidates to return
            stages: Which stages to run (default: all)
            timeout_seconds: Maximum execution time (default 5 min)
            market_context: Optional KB context for qualification

        Returns:
            Dictionary with candidates and metadata
        """
        # Store market context for use in qualification stage
        self._market_context = market_context

        try:
            # Wrap the actual discovery in a timeout (B9 fix)
            return await asyncio.wait_for(
                self._run_discovery_pipeline(
                    criteria, max_candidates, stages
                ),
                timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            logger.error(
                f"Discovery timed out after {timeout_seconds} seconds"
            )
            return {
                "status": "error",
                "error": (
                    f"Discovery timed out after {timeout_seconds // 60} "
                    "minutes. Try reducing the number of candidates."
                ),
                "candidates": [],
                "total_found": 0,
                "stages_run": [],
                "processing_time_ms": timeout_seconds * 1000,
                "timestamp": datetime.utcnow().isoformat()
            }

    async def _run_discovery_pipeline(
        self,
        criteria: QualificationCriteria,
        max_candidates: int,
        stages: Optional[List[DiscoveryStage]]
    ) -> Dict[str, Any]:
        """Internal discovery pipeline (extracted for timeout wrapper)."""
        if stages is None:
            stages = [
                DiscoveryStage.SEARCH, DiscoveryStage.SCRAPE,
                DiscoveryStage.QUALIFY, DiscoveryStage.ANALYZE
            ]

        # Reset stage errors and progress for this run
        self._stage_errors = {}
        self._progress = {
            "current_stage": None,
            "current_stage_name": "Initializing...",
            "stages_completed": [],
            "candidates_found": 0,
            "candidates_scraped": 0,
            "candidates_qualified": 0,
            "candidates_analyzed": 0,
            "percent_complete": 0,
            "estimated_time_remaining": 0,
        }

        start_time = datetime.now()
        candidates = []
        provider_status = "unknown"

        # Check provider availability
        if self.gemini and self.gemini.is_available:
            provider_status = "gemini"
        else:
            try:
                from duckduckgo_search import DDGS  # noqa: F401
                provider_status = "duckduckgo"
            except ImportError:
                provider_status = "none"
                logger.error("No search providers available")
                return {
                    "status": "error",
                    "error": (
                        "No search providers configured. Please set "
                        "GOOGLE_AI_API_KEY in your .env file, or "
                        "install duckduckgo-search package."
                    ),
                    "candidates": [],
                    "total_found": 0,
                    "stages_run": [],
                    "provider": provider_status,
                    "processing_time_ms": 0,
                    "timestamp": datetime.utcnow().isoformat()
                }

        logger.info(f"Using search provider: {provider_status}")
        total_stages = len(stages)

        try:
            # Stage 1: Search
            if DiscoveryStage.SEARCH in stages:
                self._progress["current_stage"] = "search"
                self._progress["current_stage_name"] = "Searching with AI grounding..."
                self._progress["estimated_time_remaining"] = 90
                logger.info("Starting Stage 1: Search")
                candidates = await self._stage_search(
                    criteria, max_candidates * 3
                )
                self._progress["candidates_found"] = len(candidates)
                self._progress["stages_completed"].append("search")
                self._progress["percent_complete"] = int(
                    len(self._progress["stages_completed"])
                    / total_stages * 100
                )
                logger.info(
                    f"Stage 1 complete: Found {len(candidates)} candidates"
                )

            # Stage 2: Scrape (parallel)
            if DiscoveryStage.SCRAPE in stages and candidates:
                self._progress["current_stage"] = "scrape"
                self._progress["current_stage_name"] = "Analyzing competitor websites..."
                self._progress["estimated_time_remaining"] = 60
                logger.info("Starting Stage 2: Scrape (parallel)")
                candidates = await self._stage_scrape(
                    candidates[:max_candidates * 2]
                )
                scraped_count = sum(
                    1 for c in candidates
                    if "scrape" in c.stages_completed
                )
                self._progress["candidates_scraped"] = scraped_count
                self._progress["stages_completed"].append("scrape")
                self._progress["percent_complete"] = int(
                    len(self._progress["stages_completed"])
                    / total_stages * 100
                )
                logger.info(
                    f"Stage 2 complete: Scraped {scraped_count} candidates"
                )

            # Stage 3: Qualify (parallel, via AIRouter)
            if DiscoveryStage.QUALIFY in stages and candidates:
                self._progress["current_stage"] = "qualify"
                self._progress["current_stage_name"] = "Qualifying competitors with AI..."
                self._progress["estimated_time_remaining"] = 40
                logger.info(
                    "Starting Stage 3: Qualify (parallel, AIRouter)"
                )
                candidates = await self._stage_qualify(
                    candidates, criteria
                )
                candidates = [c for c in candidates if c.is_qualified]
                self._progress["candidates_qualified"] = len(candidates)
                self._progress["stages_completed"].append("qualify")
                self._progress["percent_complete"] = int(
                    len(self._progress["stages_completed"])
                    / total_stages * 100
                )
                logger.info(
                    f"Stage 3 complete: {len(candidates)} qualified"
                )

            # Stage 4: Analyze (parallel, via AIRouter)
            if DiscoveryStage.ANALYZE in stages and candidates:
                self._progress["current_stage"] = "analyze"
                self._progress["current_stage_name"] = "Performing threat analysis..."
                self._progress["estimated_time_remaining"] = 20
                logger.info(
                    "Starting Stage 4: Analyze (parallel, AIRouter)"
                )
                candidates = await self._stage_analyze(
                    candidates[:max_candidates]
                )
                analyzed_count = sum(
                    1 for c in candidates
                    if "analyze" in c.stages_completed
                )
                self._progress["candidates_analyzed"] = analyzed_count
                self._progress["stages_completed"].append("analyze")
                self._progress["percent_complete"] = 100
                logger.info(
                    f"Stage 4 complete: Analyzed {analyzed_count} candidates"
                )

            # Sort by qualification score
            candidates.sort(
                key=lambda c: c.qualification_score, reverse=True
            )

        except Exception as e:
            logger.error(f"Discovery pipeline error: {e}")

        self._progress["current_stage"] = "complete"
        self._progress["current_stage_name"] = "Complete"
        self._progress["estimated_time_remaining"] = 0

        total_time = (
            (datetime.now() - start_time).total_seconds() * 1000
        )

        # Determine status based on results and errors
        has_errors = bool(self._stage_errors)
        status = "success" if candidates else (
            "partial" if has_errors else "no_results"
        )

        return {
            "status": status,
            "candidates": [
                asdict(c) for c in candidates[:max_candidates]
            ],
            "total_found": len(candidates),
            "stages_run": [s.value for s in stages],
            "stage_errors": (
                self._stage_errors if has_errors else None
            ),
            "processing_time_ms": total_time,
            "criteria_used": asdict(criteria),
            "timestamp": datetime.utcnow().isoformat()
        }

    async def _stage_search(
        self,
        criteria: QualificationCriteria,
        max_results: int
    ) -> List[DiscoveryCandidate]:
        """Stage 1: Search using Gemini grounding."""
        candidates = []

        if not self.gemini or not self.gemini.is_available:
            logger.warning(
                "Gemini not available, falling back to DuckDuckGo"
            )
            return await self._fallback_duckduckgo_search(
                criteria, max_results
            )

        # Generate search queries based on criteria
        queries = self._generate_search_queries(criteria)
        found_domains = set()

        for query in queries:
            if len(candidates) >= max_results:
                break

            try:
                search_prompt = (
                    "Find healthcare IT software companies that "
                    "match this criteria:\n\n"
                    f"{criteria.to_prompt()}\n\n"
                    f"Search query: {query}\n\n"
                    "List 5-10 specific companies with their website "
                    "URLs. For each company provide:\n"
                    "- Company name\n"
                    "- Website URL\n"
                    "- Brief description of what they do\n\n"
                    "Only include actual software companies, not "
                    "review sites, news articles, or directories."
                )
                # Append market context if provided
                if hasattr(self, '_market_context') and self._market_context:
                    search_prompt += f"\n\nADDITIONAL CONTEXT:\n{self._market_context}"

                # Wrap Gemini call with timeout
                try:
                    result = await asyncio.wait_for(
                        asyncio.to_thread(
                            self.gemini.search_and_ground,
                            query=search_prompt,
                            search_type="general"
                        ),
                        timeout=STAGE_SEARCH_TIMEOUT
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        f"Search timeout ({STAGE_SEARCH_TIMEOUT}s) "
                        f"for query: {query[:50]}..."
                    )
                    self._stage_errors.setdefault(
                        "search", []
                    ).append({
                        "query": query[:100],
                        "error": (
                            f"timeout after {STAGE_SEARCH_TIMEOUT}s"
                        )
                    })
                    continue

                if result.get("error"):
                    logger.warning(
                        f"Search error for '{query}': "
                        f"{result.get('error')}"
                    )
                    self._stage_errors.setdefault(
                        "search", []
                    ).append({
                        "query": query[:100],
                        "error": result.get('error')
                    })
                    continue

                response_text = result.get("response", "")

                # Extract companies and URLs from grounded response
                extracted = self._extract_companies_from_response(
                    response_text
                )

                for company in extracted:
                    url = company.get("url", "")
                    domain = self._extract_domain(url)

                    if not domain:
                        continue

                    # Skip ignored domains
                    if domain.lower() in self.IGNORED_DOMAINS:
                        continue

                    # Skip known competitors
                    if domain.lower() in self._known_domains:
                        continue

                    # Skip duplicates
                    if domain in found_domains:
                        continue

                    found_domains.add(domain)
                    cand_url = (
                        url if url.startswith('http')
                        else f"https://{domain}"
                    )
                    candidates.append(DiscoveryCandidate(
                        name=company.get(
                            "name",
                            domain.replace('.com', '').title()
                        ),
                        url=cand_url,
                        domain=domain,
                        search_snippet=company.get("description", ""),
                        search_source="google_grounded",
                        discovered_at=datetime.utcnow().isoformat(),
                        stages_completed=["search"]
                    ))

                # Rate limiting
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(
                    f"Search error for query '{query}': {e}"
                )
                continue

        return candidates

    async def _stage_scrape(
        self,
        candidates: List[DiscoveryCandidate]
    ) -> List[DiscoveryCandidate]:
        """Stage 2: Scrape websites (parallel, max 5 concurrent)."""
        semaphore = asyncio.Semaphore(5)

        async def _scrape_one(
            candidate: DiscoveryCandidate
        ) -> None:
            async with semaphore:
                try:
                    try:
                        scraped = await asyncio.wait_for(
                            self._scrape_website(candidate.url),
                            timeout=STAGE_SCRAPE_TIMEOUT
                        )
                    except asyncio.TimeoutError:
                        logger.warning(
                            f"Scrape timeout ({STAGE_SCRAPE_TIMEOUT}s)"
                            f" for: {candidate.url}"
                        )
                        self._stage_errors.setdefault(
                            "scrape", []
                        ).append({
                            "url": candidate.url,
                            "error": (
                                "timeout after "
                                f"{STAGE_SCRAPE_TIMEOUT}s"
                            )
                        })
                        return

                    if scraped:
                        candidate.scraped_content = (
                            scraped.get("content", "")[:5000]
                        )
                        candidate.page_title = (
                            scraped.get("title", "")
                        )
                        candidate.meta_description = (
                            scraped.get("description", "")
                        )
                        candidate.products_found = (
                            scraped.get("products", [])
                        )
                        candidate.features_found = (
                            scraped.get("features", [])
                        )
                        candidate.stages_completed.append("scrape")
                        # Track the exact URL that was scraped
                        scraped_url = scraped.get(
                            "final_url", candidate.url
                        )
                        candidate.scraped_urls.append(scraped_url)

                except Exception as e:
                    logger.error(
                        f"Scrape error for {candidate.url}: {e}"
                    )
                    self._stage_errors.setdefault(
                        "scrape", []
                    ).append({
                        "url": candidate.url,
                        "error": str(e)
                    })

        await asyncio.gather(*[_scrape_one(c) for c in candidates])
        return candidates

    async def _stage_qualify(
        self,
        candidates: List[DiscoveryCandidate],
        criteria: QualificationCriteria
    ) -> List[DiscoveryCandidate]:
        """Stage 3: AI qualification (parallel via AIRouter)."""
        router = self._get_ai_router()

        # If no router and no Gemini, fall back to heuristics
        if router is None and (
            not self.gemini or not self.gemini.is_available
        ):
            return self._heuristic_qualification(candidates, criteria)

        criteria_prompt = criteria.to_prompt()
        semaphore = asyncio.Semaphore(5)

        async def _qualify_one(
            candidate: DiscoveryCandidate
        ) -> None:
            async with semaphore:
                try:
                    content_preview = (
                        candidate.scraped_content[:2000]
                        if candidate.scraped_content
                        else candidate.search_snippet
                    )

                    prompt = (
                        "Evaluate this company as a potential "
                        "healthcare IT competitor based on the "
                        "criteria below.\n\n"
                        f"COMPANY: {candidate.name}\n"
                        f"URL: {candidate.url}\n"
                        f"TITLE: {candidate.page_title}\n"
                        "DESCRIPTION: "
                        f"{candidate.meta_description or candidate.search_snippet}\n\n"
                        "CONTENT PREVIEW:\n"
                        f"{content_preview}\n\n"
                        "QUALIFICATION CRITERIA:\n"
                        f"{criteria_prompt}\n\n"
                        "Respond ONLY with valid JSON "
                        "(no markdown, no explanation):\n"
                        '{"is_qualified": true, "score": 75, '
                        '"reasoning": "Brief explanation", '
                        '"criteria_matches": '
                        '{"healthcare_it": true, '
                        '"target_market": true, '
                        '"product_overlap": true, '
                        '"not_excluded": true}, '
                        '"source_urls": '
                        '["https://example.com/about"]}\n\n'
                        "IMPORTANT: In source_urls, list the "
                        "specific URLs from the content that "
                        "support your qualification claims."
                    )
                    # Append market context to qualification
                    if hasattr(self, '_market_context') and self._market_context:
                        prompt += f"\n\nADDITIONAL MARKET CONTEXT:\n{self._market_context}"

                    # Try AIRouter first (Claude Opus w/ fallback)
                    if router is not None:
                        try:
                            from ai_router import TaskType
                            ai_result = await asyncio.wait_for(
                                router.generate_json(
                                    prompt=prompt,
                                    task_type=TaskType.DISCOVERY,
                                    temperature=0.1,
                                    max_tokens=1024,
                                    agent_type="discovery_qualify"
                                ),
                                timeout=STAGE_QUALIFY_TIMEOUT
                            )
                            result = ai_result.get(
                                "response_json", {}
                            )
                        except asyncio.TimeoutError:
                            logger.warning(
                                "Qualify timeout "
                                f"({STAGE_QUALIFY_TIMEOUT}s) "
                                f"for: {candidate.name}"
                            )
                            self._stage_errors.setdefault(
                                "qualify", []
                            ).append({
                                "candidate": candidate.name,
                                "error": (
                                    "timeout after "
                                    f"{STAGE_QUALIFY_TIMEOUT}s"
                                )
                            })
                            candidate.is_qualified = False
                            candidate.qualification_score = 0
                            return
                        except Exception as e:
                            logger.warning(
                                "AIRouter qualify failed for "
                                f"{candidate.name}, falling back "
                                f"to Gemini: {e}"
                            )
                            result = await self._qualify_via_gemini(
                                prompt, candidate.name
                            )
                    else:
                        result = await self._qualify_via_gemini(
                            prompt, candidate.name
                        )

                    if isinstance(result, dict):
                        candidate.is_qualified = result.get(
                            "is_qualified", False
                        )
                        candidate.qualification_score = result.get(
                            "score", 0
                        )
                        candidate.qualification_reasoning = result.get(
                            "reasoning", ""
                        )
                        candidate.criteria_matches = result.get(
                            "criteria_matches", {}
                        )
                        # Capture source URLs from AI response
                        source_urls = result.get("source_urls", [])
                        if source_urls:
                            for src_url in source_urls:
                                candidate.data_sources.append({
                                    "field_name": "qualification",
                                    "value": (
                                        candidate
                                        .qualification_reasoning[:100]
                                    ),
                                    "source_url": src_url
                                })
                    else:
                        candidate.is_qualified = False
                        candidate.qualification_score = 0

                    candidate.stages_completed.append("qualify")

                except Exception as e:
                    logger.error(
                        f"Qualification error for "
                        f"{candidate.name}: {e}"
                    )
                    self._stage_errors.setdefault(
                        "qualify", []
                    ).append({
                        "candidate": candidate.name,
                        "error": str(e)
                    })
                    candidate.qualification_score = 0
                    candidate.is_qualified = False

        await asyncio.gather(*[_qualify_one(c) for c in candidates])
        return candidates

    async def _qualify_via_gemini(
        self,
        prompt: str,
        candidate_name: str
    ) -> Optional[Dict]:
        """Fallback: qualify via direct Gemini call."""
        if not self.gemini or not self.gemini.is_available:
            return None
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    self.gemini.generate_json,
                    prompt=prompt,
                    temperature=0.1
                ),
                timeout=STAGE_QUALIFY_TIMEOUT
            )
            return result if isinstance(result, dict) else None
        except asyncio.TimeoutError:
            logger.warning(
                f"Gemini qualify timeout for: {candidate_name}"
            )
            return None
        except Exception as e:
            logger.warning(
                f"Gemini qualify failed for {candidate_name}: {e}"
            )
            return None

    async def _stage_analyze(
        self,
        candidates: List[DiscoveryCandidate]
    ) -> List[DiscoveryCandidate]:
        """Stage 4: Threat analysis (parallel via AIRouter)."""
        router = self._get_ai_router()

        if router is None and (
            not self.gemini or not self.gemini.is_available
        ):
            return candidates

        semaphore = asyncio.Semaphore(5)

        async def _analyze_one(
            candidate: DiscoveryCandidate
        ) -> None:
            async with semaphore:
                try:
                    content = (
                        candidate.scraped_content[:3000]
                        if candidate.scraped_content
                        else candidate.search_snippet
                    )

                    analysis_prompt = (
                        "Analyze this healthcare IT competitor "
                        "and provide a threat assessment.\n\n"
                        f"COMPANY: {candidate.name}\n"
                        f"URL: {candidate.url}\n"
                        "DESCRIPTION: "
                        f"{candidate.meta_description or candidate.search_snippet}\n\n"
                        f"CONTENT:\n{content}\n\n"
                        "Respond ONLY with valid JSON "
                        "(no markdown):\n"
                        '{"threat_level": "Medium", '
                        '"threat_score": 65, '
                        '"strengths": ["s1", "s2", "s3"], '
                        '"weaknesses": ["w1", "w2"], '
                        '"competitive_positioning": '
                        '"How they position", '
                        '"summary": "2-3 sentence summary", '
                        '"data_sources": [{"field_name": '
                        '"threat_level", "value": "Medium", '
                        '"source_url": '
                        '"https://example.com/about"}]}\n\n'
                        "Threat levels: Low (0-30), Medium (31-60),"
                        " High (61-80), Critical (81-100)\n"
                        "IMPORTANT: In data_sources, cite the "
                        "specific URLs that support each data point."
                    )

                    # Try AIRouter first (Claude Opus w/ fallback)
                    if router is not None:
                        try:
                            from ai_router import TaskType
                            ai_result = await asyncio.wait_for(
                                router.generate_json(
                                    prompt=analysis_prompt,
                                    task_type=TaskType.DISCOVERY,
                                    temperature=0.2,
                                    max_tokens=2048,
                                    agent_type="discovery_analyze"
                                ),
                                timeout=STAGE_ANALYZE_TIMEOUT
                            )
                            result = ai_result.get(
                                "response_json", {}
                            )
                        except asyncio.TimeoutError:
                            logger.warning(
                                "Analyze timeout "
                                f"({STAGE_ANALYZE_TIMEOUT}s) "
                                f"for: {candidate.name}"
                            )
                            self._stage_errors.setdefault(
                                "analyze", []
                            ).append({
                                "candidate": candidate.name,
                                "error": (
                                    "timeout after "
                                    f"{STAGE_ANALYZE_TIMEOUT}s"
                                )
                            })
                            return
                        except Exception as e:
                            logger.warning(
                                "AIRouter analyze failed for "
                                f"{candidate.name}, falling back "
                                f"to Gemini: {e}"
                            )
                            result = await self._analyze_via_gemini(
                                analysis_prompt, candidate.name
                            )
                    else:
                        result = await self._analyze_via_gemini(
                            analysis_prompt, candidate.name
                        )

                    if isinstance(result, dict):
                        candidate.threat_level = result.get(
                            "threat_level", "Unknown"
                        )
                        candidate.threat_score = result.get(
                            "threat_score", 0
                        )
                        candidate.strengths = result.get(
                            "strengths", []
                        )
                        candidate.weaknesses = result.get(
                            "weaknesses", []
                        )
                        candidate.competitive_positioning = (
                            result.get("competitive_positioning", "")
                        )
                        candidate.ai_summary = result.get(
                            "summary", ""
                        )
                        # Capture data_sources from AI response
                        ai_sources = result.get("data_sources", [])
                        if isinstance(ai_sources, list):
                            for ds in ai_sources:
                                if (isinstance(ds, dict)
                                        and ds.get("source_url")):
                                    candidate.data_sources.append({
                                        "field_name": ds.get(
                                            "field_name", "unknown"
                                        ),
                                        "value": str(
                                            ds.get("value", "")
                                        )[:200],
                                        "source_url": ds.get(
                                            "source_url", ""
                                        )
                                    })

                    candidate.stages_completed.append("analyze")

                except Exception as e:
                    logger.error(
                        f"Analysis error for {candidate.name}: {e}"
                    )
                    self._stage_errors.setdefault(
                        "analyze", []
                    ).append({
                        "candidate": candidate.name,
                        "error": str(e)
                    })

        await asyncio.gather(*[_analyze_one(c) for c in candidates])
        return candidates

    async def _analyze_via_gemini(
        self,
        prompt: str,
        candidate_name: str
    ) -> Optional[Dict]:
        """Fallback: analyze via direct Gemini call."""
        if not self.gemini or not self.gemini.is_available:
            return None
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    self.gemini.generate_json,
                    prompt=prompt,
                    temperature=0.2
                ),
                timeout=STAGE_ANALYZE_TIMEOUT
            )
            return result if isinstance(result, dict) else None
        except asyncio.TimeoutError:
            logger.warning(
                f"Gemini analyze timeout for: {candidate_name}"
            )
            return None
        except Exception as e:
            logger.warning(
                f"Gemini analyze failed for {candidate_name}: {e}"
            )
            return None

    def _generate_search_queries(
        self,
        criteria: QualificationCriteria
    ) -> List[str]:
        """Generate search queries based on criteria."""
        queries = []

        # Capability-specific queries
        capability_queries = {
            'pxp': [
                "patient experience platform software",
                "patient engagement platform healthcare"
            ],
            'pms': [
                "practice management software healthcare",
                "medical practice management system"
            ],
            'rcm': [
                "revenue cycle management healthcare software",
                "medical billing RCM software"
            ],
            'ehr': [
                "EHR software companies",
                "electronic health records software"
            ],
            'telehealth': [
                "telehealth platform software",
                "telemedicine software company"
            ],
            'payments': [
                "patient payment platform healthcare",
                "medical payment processing software"
            ],
            'biometric': [
                "biometric patient identification healthcare"
            ],
            'ai_scribe': [
                "AI medical scribe software",
                "clinical documentation AI"
            ]
        }

        for cap in criteria.required_capabilities:
            if cap in capability_queries:
                queries.extend(capability_queries[cap])

        # Segment-specific queries
        segment_queries = {
            'hospital': [
                "hospital patient intake software",
                "health system software solutions"
            ],
            'ambulatory': [
                "ambulatory care software",
                "outpatient clinic software"
            ],
            'urgent_care': ["urgent care software solutions"],
            'behavioral': [
                "behavioral health software",
                "mental health EHR software"
            ],
            'dental_dso': [
                "dental practice management software",
                "DSO software solutions"
            ],
            'lab': ["laboratory information system software"],
            'ltc': [
                "long-term care software",
                "nursing home software"
            ]
        }

        for seg in criteria.target_segments:
            if seg in segment_queries:
                queries.extend(segment_queries[seg])

        # Custom keyword queries
        for keyword in criteria.custom_keywords.get('include', []):
            if keyword.strip():
                queries.append(
                    f"{keyword} healthcare software company"
                )

        # Default queries if none specified
        if not queries:
            queries = [
                "healthcare IT software companies",
                "patient experience platform competitors",
                "medical practice management software companies",
                "healthcare technology startups 2026",
                "digital health software companies"
            ]

        # Remove duplicates while preserving order
        seen = set()
        unique_queries = []
        for q in queries:
            if q.lower() not in seen:
                seen.add(q.lower())
                unique_queries.append(q)

        return unique_queries[:8]  # Limit to 8 queries for speed

    def _extract_companies_from_response(
        self,
        text: str
    ) -> List[Dict]:
        """Extract company names and URLs from AI response."""
        companies = []

        # Pattern for URLs
        url_pattern = (
            r'https?://[^\s\)\]<"\']+[^\s\)\]<"\'\.,]'
        )
        urls = re.findall(url_pattern, text)

        # Also look for domain patterns
        domain_pattern = (
            r'\b([a-zA-Z0-9-]+\.'
            r'(com|io|health|ai|co|net|org))\b'
        )
        domains = re.findall(domain_pattern, text)

        found_domains = set()

        for url in urls:
            domain = self._extract_domain(url)
            if domain and domain not in found_domains:
                found_domains.add(domain)

                # Try to find company name near URL in text
                name = self._find_company_name_near_url(
                    text, url, domain
                )

                companies.append({
                    "name": name,
                    "url": url,
                    "description": ""
                })

        # Add domains not found as URLs
        for domain_tuple in domains:
            domain = domain_tuple[0].lower()
            if (domain not in found_domains
                    and domain not in self.IGNORED_DOMAINS):
                found_domains.add(domain)
                clean_name = (
                    domain
                    .replace('.com', '')
                    .replace('.io', '')
                    .replace('.health', '')
                    .title()
                )
                companies.append({
                    "name": clean_name,
                    "url": f"https://{domain}",
                    "description": ""
                })

        return companies

    def _find_company_name_near_url(
        self, text: str, url: str, domain: str
    ) -> str:
        """Try to find company name near a URL in the text."""
        patterns = [
            (
                rf'([A-Z][a-zA-Z0-9\s]+)\s*[\(\-\:]\s*'
                rf'{re.escape(url[:30])}'
            ),
            (
                rf'([A-Z][a-zA-Z0-9\s]+)\s+'
                rf'{re.escape(domain)}'
            ),
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                name = match.group(1).strip()
                if 2 < len(name) < 50:
                    return name

        # Default to cleaned domain
        return (
            domain
            .replace('.com', '')
            .replace('.io', '')
            .replace('.health', '')
            .replace('-', ' ')
            .title()
        )

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            if not url:
                return ""
            if not url.startswith('http'):
                url = 'https://' + url
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            domain = domain.replace("www.", "")
            return domain
        except Exception:
            return ""

    async def _scrape_website(self, url: str) -> Optional[Dict]:
        """Scrape a website using Firecrawl or simple fetch."""

        # Try Firecrawl first (better quality)
        if self.firecrawl:
            try:
                result = await self.firecrawl.scrape(url)
                if result and result.success:
                    metadata = result.metadata or {}
                    return {
                        "content": (result.markdown or '')[:5000],
                        "title": metadata.get('title', ''),
                        "description": metadata.get(
                            'description', ''
                        ),
                        "products": [],
                        "features": [],
                        "final_url": metadata.get(
                            'sourceURL', url
                        )
                    }
            except Exception as e:
                logger.warning(
                    f"Firecrawl failed for {url}: {e}"
                )

        # Fallback to simple HTTP fetch
        try:
            import httpx
            async with httpx.AsyncClient(
                timeout=10.0, follow_redirects=True
            ) as client:
                response = await client.get(url, headers={
                    'User-Agent': (
                        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                        'AppleWebKit/537.36'
                    )
                })
                if response.status_code == 200:
                    html = response.text
                    final_url = str(response.url)

                    # Extract title
                    title_match = re.search(
                        r'<title[^>]*>([^<]+)</title>',
                        html, re.IGNORECASE
                    )
                    title = (
                        title_match.group(1).strip()
                        if title_match else ""
                    )

                    # Extract meta description
                    desc_match = re.search(
                        r'<meta[^>]+name=["\']description["\']'
                        r'[^>]+content=["\']([^"\']+)["\']',
                        html, re.IGNORECASE
                    )
                    if not desc_match:
                        desc_match = re.search(
                            r'<meta[^>]+content=["\']([^"\']+)["\']'
                            r'[^>]+name=["\']description["\']',
                            html, re.IGNORECASE
                        )
                    description = (
                        desc_match.group(1).strip()
                        if desc_match else ""
                    )

                    # Strip HTML tags for content
                    content = re.sub(
                        r'<script[^>]*>.*?</script>', '',
                        html, flags=re.DOTALL | re.IGNORECASE
                    )
                    content = re.sub(
                        r'<style[^>]*>.*?</style>', '',
                        content, flags=re.DOTALL | re.IGNORECASE
                    )
                    content = re.sub(r'<[^>]+>', ' ', content)
                    content = re.sub(
                        r'\s+', ' ', content
                    ).strip()

                    return {
                        "content": content[:5000],
                        "title": title,
                        "description": description,
                        "products": [],
                        "features": [],
                        "final_url": final_url
                    }
        except Exception as e:
            logger.warning(f"HTTP fetch failed for {url}: {e}")

        return None

    async def _fallback_duckduckgo_search(
        self,
        criteria: QualificationCriteria,
        max_results: int
    ) -> List[DiscoveryCandidate]:
        """Fallback to DuckDuckGo if Gemini not available."""
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            logger.error(
                "DuckDuckGo search not available. "
                "Install: pip install duckduckgo-search"
            )
            logger.warning(
                "No search providers available - returning empty"
            )
            return []

        candidates = []
        queries = self._generate_search_queries(criteria)
        found_domains = set()

        for query in queries[:3]:  # Limit DDG queries for speed
            try:
                with DDGS() as ddgs:
                    results = list(ddgs.text(query, max_results=5))

                    for r in results:
                        url = r.get('href', '')
                        domain = self._extract_domain(url)

                        if not domain or domain in found_domains:
                            continue

                        if domain.lower() in self.IGNORED_DOMAINS:
                            continue

                        if domain.lower() in self._known_domains:
                            continue

                        found_domains.add(domain)
                        raw_title = r.get('title', domain)
                        name = (
                            raw_title.split(' - ')[0]
                            .split(' | ')[0][:50]
                        )
                        candidates.append(DiscoveryCandidate(
                            name=name,
                            url=url,
                            domain=domain,
                            search_snippet=r.get('body', ''),
                            search_source="duckduckgo",
                            discovered_at=(
                                datetime.utcnow().isoformat()
                            ),
                            stages_completed=["search"]
                        ))

                        if len(candidates) >= max_results:
                            return candidates

                # Rate limiting
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"DDG search error: {e}")

        return candidates

    def _heuristic_qualification(
        self,
        candidates: List[DiscoveryCandidate],
        criteria: QualificationCriteria
    ) -> List[DiscoveryCandidate]:
        """Heuristic-based qualification when AI not available."""

        healthcare_keywords = [
            'health', 'medical', 'patient', 'clinical',
            'hospital', 'provider', 'care', 'ehr', 'emr',
            'practice'
        ]

        for candidate in candidates:
            text = (
                candidate.search_snippet + " "
                + candidate.meta_description + " "
                + candidate.page_title + " "
                + candidate.scraped_content[:1000]
            ).lower()

            # Check healthcare context
            healthcare_matches = sum(
                1 for kw in healthcare_keywords if kw in text
            )
            has_healthcare = healthcare_matches >= 2

            # Check exclusions
            not_excluded = not any(
                exc.lower() in text for exc in criteria.exclusions
            )

            if has_healthcare and not_excluded:
                candidate.is_qualified = True
                candidate.qualification_score = min(
                    50 + healthcare_matches * 10, 80
                )
                candidate.qualification_reasoning = (
                    f"Heuristic: Found {healthcare_matches} "
                    "healthcare keywords"
                )
            else:
                candidate.is_qualified = False
                candidate.qualification_score = 0
                candidate.qualification_reasoning = (
                    "Heuristic: Insufficient healthcare context"
                )

            candidate.stages_completed.append("qualify")

        return candidates
