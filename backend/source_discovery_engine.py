"""
Certify Intel - AI-Powered Source Discovery Engine (v6.3.9)

Automatically discovers, validates, and attributes authoritative sources for
all competitor data field values using Gemini AI with Google Search grounding.

Features:
- Field prioritization by business importance (P0-P3)
- AI search with Google Search grounding for real-time source discovery
- URL validation to ensure sources are accessible
- Evidence extraction with confidence scoring
- Auto-population for new competitors

Author: Certify Health
Date: January 30, 2026
"""

import os
import json
import re
import logging
import asyncio
import httpx
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from database import SessionLocal, DataSource, Competitor, ChangeLog

# Import Gemini provider for AI search
try:
    from gemini_provider import GeminiProvider, GeminiConfig
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

logger = logging.getLogger(__name__)


class FieldPriority(Enum):
    """Priority levels for field source discovery."""
    P0 = 0  # Critical - Financial, Leadership, Sales dimensions
    P1 = 1  # High - Core metrics, time-sensitive data
    P2 = 2  # Medium - Tech stack, certifications
    P3 = 3  # Low - Descriptive text fields


@dataclass
class SourceResult:
    """Result of a source discovery attempt."""
    field_name: str
    source_found: bool
    source_url: Optional[str] = None
    source_type: Optional[str] = None
    source_name: Optional[str] = None
    confidence_score: int = 0
    evidence_quote: Optional[str] = None
    error: Optional[str] = None


@dataclass
class DiscoveryProgress:
    """Progress tracking for source discovery."""
    competitor_id: int
    competitor_name: str
    total_fields: int = 0
    fields_processed: int = 0
    sources_found: int = 0
    errors: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class VerificationResult:
    """Result of a field verification attempt."""
    field_name: str
    status: str  # "correct", "wrong", "unverifiable"
    verified_value: Optional[str] = None
    source_url: Optional[str] = None
    source_name: Optional[str] = None
    evidence: Optional[str] = None
    confidence_score: int = 0
    error: Optional[str] = None


# Field categorization by priority
FIELD_PRIORITIES = {
    # P0 - Critical fields
    FieldPriority.P0: [
        # Financial
        "pricing_model", "base_price", "price_unit", "estimated_revenue",
        "revenue_growth_rate", "profit_margin", "estimated_valuation",
        "burn_rate", "runway_months", "funding_total", "latest_round",
        # Leadership
        "ceo_name", "ceo_linkedin", "cto_name", "cfo_name",
        "executive_changes", "board_members", "advisors",
        # Dimension evidence (sales-critical)
        "dim_product_packaging_evidence", "dim_integration_depth_evidence",
        "dim_support_service_evidence", "dim_retention_stickiness_evidence",
        "dim_user_adoption_evidence", "dim_implementation_ttv_evidence",
        "dim_reliability_enterprise_evidence", "dim_pricing_flexibility_evidence",
        "dim_reporting_analytics_evidence",
    ],

    # P1 - High priority fields
    FieldPriority.P1: [
        # Core metrics
        "customer_count", "employee_count", "employee_growth_rate",
        "annual_revenue", "net_income", "revenue_per_employee",
        # Ratings & reviews
        "g2_rating", "glassdoor_rating", "glassdoor_reviews_count",
        "glassdoor_recommend_pct", "indeed_rating", "nps_score",
        # Social media (time-sensitive)
        "linkedin_followers", "linkedin_employees", "twitter_followers",
        "facebook_followers", "youtube_subscribers",
        # Funding
        "last_funding_date", "funding_stage", "pe_vc_backers",
        # Market
        "estimated_market_share", "competitive_win_rate",
    ],

    # P2 - Medium priority fields
    FieldPriority.P2: [
        # Tech & product
        "tech_stack", "cloud_provider", "api_available", "api_documentation_url",
        "open_source_contributions", "rd_investment_pct", "product_count",
        "latest_product_launch",
        # Certifications
        "soc2_certified", "hitrust_certified", "iso27001_certified",
        "hipaa_compliant", "certifications",
        # Patents
        "patent_count", "recent_patents", "trademark_count", "ip_litigation",
        # Partnerships
        "strategic_partners", "reseller_partners", "integration_partners",
    ],

    # P3 - Low priority fields
    FieldPriority.P3: [
        # Descriptive text
        "notes", "key_features", "product_categories", "target_segments",
        "customer_size_focus", "geographic_focus", "key_customers",
        "headquarters", "markets_served", "primary_market",
        # Historical
        "year_founded", "founder_background", "acquisition_history",
        # Misc
        "website_traffic", "news_mentions", "recent_launches",
        "marketplace_presence", "notable_customer_wins", "customer_case_studies",
    ],
}

# Fields commonly shown on battlecards — prioritized for verification
BATTLECARD_FIELDS = [
    'year_founded', 'headquarters', 'employee_count', 'customer_count',
    'funding_total', 'annual_revenue', 'estimated_revenue', 'pricing_model',
    'base_price', 'product_categories', 'key_features', 'target_segments',
    'certifications', 'integration_partners', 'ceo_name', 'tech_stack',
    'geographic_focus', 'primary_market', 'markets_served'
]

# Source type authority scores (higher = more authoritative)
SOURCE_AUTHORITY = {
    "enterprise_api": 92,
    "sec_filing": 90,
    "official_website": 85,
    "linkedin": 75,
    "crunchbase": 70,
    "g2": 65,
    "glassdoor": 65,
    "news_article": 50,
    "blog_post": 40,
    "social_media": 35,
    "unknown": 20,
}

# Domain to source type mapping
DOMAIN_SOURCE_TYPES = {
    "sec.gov": "sec_filing",
    "linkedin.com": "linkedin",
    "crunchbase.com": "crunchbase",
    "g2.com": "g2",
    "glassdoor.com": "glassdoor",
    "indeed.com": "indeed",
    "techcrunch.com": "news_article",
    "reuters.com": "news_article",
    "bloomberg.com": "news_article",
    "businesswire.com": "news_article",
    "prnewswire.com": "news_article",
    "github.com": "official_website",
}


def determine_confidence_level(score: int) -> str:
    """Map a numeric confidence score to a level string."""
    if score >= 70:
        return "high"
    elif score >= 40:
        return "moderate"
    return "low"


class SourceDiscoveryEngine:
    """
    AI-powered engine for discovering authoritative sources for competitor data.

    Uses Gemini with Google Search grounding to find real-time sources,
    validates URLs, and stores results in the DataSource table.
    """

    def __init__(self):
        """Initialize the Source Discovery Engine."""
        self.gemini: Optional[GeminiProvider] = None
        self._init_gemini()

        # HTTP client for URL validation
        self.http_client = httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=True,
            headers={"User-Agent": "CertifyIntel/6.3.9 SourceDiscovery"}
        )

    def _init_gemini(self):
        """Initialize Gemini provider for AI search."""
        if not GEMINI_AVAILABLE:
            logger.warning("Gemini provider not available for source discovery")
            return

        api_key = os.getenv("GOOGLE_AI_API_KEY")
        if not api_key:
            logger.warning("GOOGLE_AI_API_KEY not set - source discovery limited")
            return

        self.gemini = GeminiProvider(GeminiConfig(
            api_key=api_key,
            model="gemini-3-flash-preview",
            temperature=0.1,
        ))
        logger.info("Source Discovery Engine initialized with Gemini")

    def get_all_fields_by_priority(self) -> List[Tuple[str, FieldPriority]]:
        """Get all trackable fields sorted by priority."""
        result = []
        for priority, fields in FIELD_PRIORITIES.items():
            for field_name in fields:
                result.append((field_name, priority))
        return sorted(result, key=lambda x: x[1].value)

    def get_competitor_field_value(self, competitor: Competitor, field_name: str) -> Optional[str]:
        """Get the current value of a field from a competitor."""
        try:
            value = getattr(competitor, field_name, None)
            if value is None:
                return None
            if isinstance(value, bool):
                return "Yes" if value else "No"
            if isinstance(value, (int, float)):
                return str(value)
            return str(value) if value else None
        except Exception:
            return None

    def classify_source_type(self, url: str) -> str:
        """Classify source type based on URL domain."""
        if not url:
            return "unknown"

        url_lower = url.lower()

        for domain, source_type in DOMAIN_SOURCE_TYPES.items():
            if domain in url_lower:
                return source_type

        # Check if it's the company's own website
        if "about" in url_lower or "team" in url_lower or "leadership" in url_lower:
            return "official_website"

        return "unknown"

    def calculate_confidence_score(
        self,
        source_type: str,
        has_evidence: bool,
        url_validated: bool
    ) -> int:
        """Calculate confidence score based on source authority and validation."""
        base_score = SOURCE_AUTHORITY.get(source_type, 20)

        # Bonuses
        if has_evidence:
            base_score += 10
        if url_validated:
            base_score += 5

        return min(100, base_score)

    async def validate_url(self, url: str) -> bool:
        """Check if a URL is accessible."""
        if not url:
            return False

        try:
            response = await self.http_client.head(url)
            return response.status_code < 400
        except Exception as e:
            logger.debug(f"URL validation failed for {url}: {e}")
            return False

    def extract_url_from_response(self, response_text: str) -> Optional[str]:
        """Extract the first URL from AI response text."""
        # Common URL patterns
        url_pattern = r'https?://[^\s<>"\')\]]+(?<![.,;:!?\'")\]])'

        matches = re.findall(url_pattern, response_text)
        if matches:
            # Clean up the URL
            url = matches[0].rstrip(".,;:!?'\")")
            return url

        return None

    async def discover_source_for_field(
        self,
        competitor: Competitor,
        field_name: str,
        field_value: str
    ) -> SourceResult:
        """
        Discover an authoritative source for a single field value.

        Checks enterprise data providers first (PitchBook, Bloomberg, etc.),
        then falls back to Gemini with Google Search grounding.
        """
        if not field_value or field_value.strip() in ("None", "null", "N/A", ""):
            return SourceResult(
                field_name=field_name,
                source_found=False,
                error="No value to verify"
            )

        # --- Enterprise provider check (before Gemini fallback) ---
        try:
            from data_providers.provider_tools import query_enterprise_for_field
            enterprise_result = await query_enterprise_for_field(
                company_name=competitor.name,
                field_name=field_name,
                current_value=field_value,
            )
            if enterprise_result:
                source_url = enterprise_result.get("source_url", "")
                provider_name = enterprise_result.get("provider", "Enterprise API")
                confidence = self.calculate_confidence_score(
                    source_type="enterprise_api",
                    has_evidence=True,
                    url_validated=bool(source_url),
                )
                return SourceResult(
                    field_name=field_name,
                    source_found=True,
                    source_url=source_url,
                    source_type="enterprise_api",
                    source_name=f"{provider_name} - {competitor.name}",
                    confidence_score=confidence,
                    evidence_quote=f"Value from {provider_name}: {enterprise_result.get('value', '')}",
                )
        except Exception as e:
            logger.debug(f"Enterprise provider lookup skipped for {field_name}: {e}")

        # --- Gemini AI search fallback ---
        if not self.gemini:
            return SourceResult(
                field_name=field_name,
                source_found=False,
                error="Gemini not available and no enterprise providers configured"
            )

        try:
            # Build search query based on field type
            company_name = competitor.name

            # Customize query based on field category
            if "revenue" in field_name.lower() or "price" in field_name.lower():
                search_type = "financial"
                query = f"What is {company_name}'s {field_name.replace('_', ' ')}? Provide the source URL."
            elif "ceo" in field_name.lower() or "cto" in field_name.lower() or "executive" in field_name.lower():
                search_type = "general"
                query = f"Who is {company_name}'s {field_name.replace('_', ' ')}? Provide LinkedIn or official source URL."
            elif "rating" in field_name.lower() or "review" in field_name.lower():
                search_type = "product"
                query = f"What is {company_name}'s {field_name.replace('_', ' ')} on G2 or Glassdoor? Provide the source URL."
            elif "patent" in field_name.lower():
                search_type = "general"
                query = f"How many patents does {company_name} have? Provide USPTO or official source URL."
            elif "linkedin" in field_name.lower() or "twitter" in field_name.lower():
                search_type = "general"
                query = f"What is {company_name}'s official {field_name.replace('_', ' ')}? Provide the URL."
            else:
                search_type = "general"
                query = f"Find {company_name}'s {field_name.replace('_', ' ')}: {field_value}. Provide an authoritative source URL."

            # Use Gemini's grounded search
            result = self.gemini.search_and_ground(
                query=query,
                competitor_name=company_name,
                search_type=search_type
            )

            if "error" in result:
                return SourceResult(
                    field_name=field_name,
                    source_found=False,
                    error=result.get("error")
                )

            response_text = result.get("response", "")

            # Extract URL from response
            source_url = self.extract_url_from_response(response_text)

            if not source_url:
                # Try to construct a known URL for the field type
                source_url = self._get_fallback_url(company_name, field_name)

            if source_url:
                # Validate URL
                url_valid = await self.validate_url(source_url)

                # Classify source type
                source_type = self.classify_source_type(source_url)

                # Calculate confidence
                confidence = self.calculate_confidence_score(
                    source_type=source_type,
                    has_evidence=bool(response_text),
                    url_validated=url_valid
                )

                # Extract evidence quote (first 200 chars)
                evidence = response_text[:200] + "..." if len(response_text) > 200 else response_text

                # Generate source name
                source_name = self._generate_source_name(source_url, source_type, company_name)

                return SourceResult(
                    field_name=field_name,
                    source_found=True,
                    source_url=source_url,
                    source_type=source_type,
                    source_name=source_name,
                    confidence_score=confidence,
                    evidence_quote=evidence
                )

            return SourceResult(
                field_name=field_name,
                source_found=False,
                error="No source URL found in response"
            )

        except Exception as e:
            logger.error(f"Source discovery failed for {field_name}: {e}")
            return SourceResult(
                field_name=field_name,
                source_found=False,
                error=str(e)
            )

    def _get_fallback_url(self, company_name: str, field_name: str) -> Optional[str]:
        """Generate fallback URL based on field type."""
        company_slug = company_name.lower().replace(" ", "").replace(",", "").replace(".", "")

        fallbacks = {
            "linkedin_followers": f"https://www.linkedin.com/company/{company_slug}",
            "linkedin_employees": f"https://www.linkedin.com/company/{company_slug}",
            "linkedin_url": f"https://www.linkedin.com/company/{company_slug}",
            "glassdoor_rating": f"https://www.glassdoor.com/Reviews/{company_slug}-reviews.htm",
            "g2_rating": f"https://www.g2.com/products/{company_slug}/reviews",
            "crunchbase": f"https://www.crunchbase.com/organization/{company_slug}",
        }

        for key, url in fallbacks.items():
            if key in field_name.lower():
                return url

        return None

    def _generate_source_name(self, url: str, source_type: str, company_name: str) -> str:
        """Generate a human-readable source name."""
        type_names = {
            "sec_filing": f"SEC Filing - {company_name}",
            "official_website": f"{company_name} Official Website",
            "linkedin": f"LinkedIn - {company_name}",
            "crunchbase": f"Crunchbase - {company_name}",
            "g2": f"G2 Reviews - {company_name}",
            "glassdoor": f"Glassdoor - {company_name}",
            "indeed": f"Indeed - {company_name}",
            "news_article": "News Article",
            "blog_post": "Blog Post",
            "social_media": "Social Media",
        }

        return type_names.get(source_type, f"Source: {url[:50]}...")

    async def discover_sources_for_competitor(
        self,
        competitor_id: int,
        priority_filter: Optional[FieldPriority] = None,
        max_fields: int = 100
    ) -> DiscoveryProgress:
        """
        Discover sources for all fields of a competitor.

        Args:
            competitor_id: ID of the competitor to process
            priority_filter: Only process fields of this priority (or all if None)
            max_fields: Maximum number of fields to process

        Returns:
            DiscoveryProgress with results
        """
        db = SessionLocal()
        progress = DiscoveryProgress(
            competitor_id=competitor_id,
            competitor_name="Unknown",
            started_at=datetime.utcnow()
        )

        try:
            # Get competitor
            competitor = db.query(Competitor).filter(Competitor.id == competitor_id).first()
            if not competitor:
                progress.errors.append(f"Competitor {competitor_id} not found")
                progress.completed_at = datetime.utcnow()
                return progress

            progress.competitor_name = competitor.name

            # Get fields to process
            all_fields = self.get_all_fields_by_priority()

            if priority_filter:
                all_fields = [(f, p) for f, p in all_fields if p == priority_filter]

            # Limit fields
            all_fields = all_fields[:max_fields]
            progress.total_fields = len(all_fields)

            logger.info(f"Discovering sources for {competitor.name}: {len(all_fields)} fields")

            for field_name, priority in all_fields:
                field_value = self.get_competitor_field_value(competitor, field_name)

                if not field_value:
                    progress.fields_processed += 1
                    continue

                # Check if source already exists
                existing_source = db.query(DataSource).filter(
                    DataSource.competitor_id == competitor_id,
                    DataSource.field_name == field_name
                ).first()

                if existing_source and existing_source.source_url:
                    # Already has source, skip
                    progress.fields_processed += 1
                    progress.sources_found += 1
                    continue

                # Discover source
                result = await self.discover_source_for_field(
                    competitor=competitor,
                    field_name=field_name,
                    field_value=field_value
                )

                progress.fields_processed += 1

                if result.source_found and result.source_url:
                    # Create or update DataSource record
                    if existing_source:
                        existing_source.source_url = result.source_url
                        existing_source.source_type = result.source_type
                        existing_source.source_name = result.source_name
                        existing_source.confidence_score = result.confidence_score
                        existing_source.extraction_method = "ai_search_grounded"
                        existing_source.extracted_at = datetime.utcnow()
                        existing_source.updated_at = datetime.utcnow()
                    else:
                        new_source = DataSource(
                            competitor_id=competitor_id,
                            field_name=field_name,
                            current_value=field_value,
                            source_url=result.source_url,
                            source_type=result.source_type,
                            source_name=result.source_name,
                            confidence_score=result.confidence_score,
                            confidence_level="high" if result.confidence_score >= 70 else "moderate" if result.confidence_score >= 40 else "low",
                            extraction_method="ai_search_grounded",
                            extracted_at=datetime.utcnow()
                        )
                        db.add(new_source)

                    progress.sources_found += 1
                    db.commit()

                elif result.error:
                    progress.errors.append(f"{field_name}: {result.error}")

                # Small delay to avoid rate limiting
                await asyncio.sleep(0.5)

            progress.completed_at = datetime.utcnow()
            logger.info(
                f"Completed source discovery for {competitor.name}: "
                f"{progress.sources_found}/{progress.fields_processed} sources found"
            )

            return progress

        except Exception as e:
            logger.error(f"Source discovery failed for competitor {competitor_id}: {e}")
            progress.errors.append(str(e))
            progress.completed_at = datetime.utcnow()
            return progress
        finally:
            db.close()

    async def discover_sources_for_all_competitors(
        self,
        priority_filter: Optional[FieldPriority] = None,
        max_per_competitor: int = 50
    ) -> Dict[str, Any]:
        """
        Discover sources for all competitors.

        Args:
            priority_filter: Only process fields of this priority
            max_per_competitor: Max fields per competitor

        Returns:
            Summary of discovery run
        """
        db = SessionLocal()

        try:
            competitors = db.query(Competitor).filter(
                Competitor.status != "deleted"
            ).all()

            results = {
                "total_competitors": len(competitors),
                "competitors_processed": 0,
                "total_sources_found": 0,
                "total_fields_processed": 0,
                "errors": [],
                "started_at": datetime.utcnow().isoformat(),
                "completed_at": None
            }

            for competitor in competitors:
                progress = await self.discover_sources_for_competitor(
                    competitor_id=competitor.id,
                    priority_filter=priority_filter,
                    max_fields=max_per_competitor
                )

                results["competitors_processed"] += 1
                results["total_sources_found"] += progress.sources_found
                results["total_fields_processed"] += progress.fields_processed
                results["errors"].extend(progress.errors)

            results["completed_at"] = datetime.utcnow().isoformat()

            return results

        finally:
            db.close()

    def get_coverage_report(self) -> Dict[str, Any]:
        """Generate source coverage report by field category."""
        db = SessionLocal()

        try:
            # Count competitors
            total_competitors = db.query(Competitor).filter(
                Competitor.status != "deleted"
            ).count()

            # Count total fields
            all_fields = self.get_all_fields_by_priority()
            total_possible_fields = len(all_fields) * total_competitors

            # Count existing sources
            total_sources = db.query(DataSource).filter(
                DataSource.source_url.isnot(None)
            ).count()

            # Calculate coverage by category
            by_category = {}
            for priority, field_list in FIELD_PRIORITIES.items():
                category_total = len(field_list) * total_competitors
                category_sourced = db.query(DataSource).filter(
                    DataSource.field_name.in_(field_list),
                    DataSource.source_url.isnot(None)
                ).count()

                category_name = {
                    FieldPriority.P0: "critical",
                    FieldPriority.P1: "high",
                    FieldPriority.P2: "medium",
                    FieldPriority.P3: "low"
                }[priority]

                by_category[category_name] = {
                    "total": category_total,
                    "sourced": category_sourced,
                    "pct": round(category_sourced / category_total * 100, 1) if category_total > 0 else 0
                }

            return {
                "total_fields": total_possible_fields,
                "fields_with_sources": total_sources,
                "coverage_pct": round(total_sources / total_possible_fields * 100, 1) if total_possible_fields > 0 else 0,
                "total_competitors": total_competitors,
                "by_category": by_category,
                "last_checked": datetime.utcnow().isoformat()
            }

        finally:
            db.close()

    def get_source_for_field(
        self,
        competitor_id: int,
        field_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get source information for a specific field."""
        db = SessionLocal()

        try:
            source = db.query(DataSource).filter(
                DataSource.competitor_id == competitor_id,
                DataSource.field_name == field_name
            ).first()

            if not source:
                return None

            return {
                "competitor_id": source.competitor_id,
                "field_name": source.field_name,
                "current_value": source.current_value,
                "source_url": source.source_url,
                "source_type": source.source_type,
                "source_name": source.source_name,
                "confidence_score": source.confidence_score,
                "confidence_level": source.confidence_level,
                "extraction_method": source.extraction_method,
                "extracted_at": source.extracted_at.isoformat() if source.extracted_at else None,
                "is_verified": source.is_verified,
                "verified_by": source.verified_by
            }

        finally:
            db.close()

    async def verify_and_correct_field(
        self,
        company_name: str,
        website: str,
        field_name: str,
        stored_value: str
    ) -> VerificationResult:
        """
        Verify a single field value using Gemini grounded search.

        Searches for the real value and returns whether the stored value
        is correct, wrong, or unverifiable.
        """
        if not self.gemini:
            return VerificationResult(
                field_name=field_name,
                status="unverifiable",
                error="Gemini not available"
            )

        field_label = field_name.replace("_", " ").title()

        prompt = (
            f'For the company "{company_name}" ({website}), verify this data point:\n'
            f'Field: {field_label}\n'
            f'Stored Value: "{stored_value}"\n\n'
            f'Search for the current, accurate value. Respond ONLY with valid JSON (no markdown):\n'
            f'{{"status": "correct" or "wrong" or "unverifiable", '
            f'"verified_value": "the correct current value", '
            f'"source_url": "https://...", '
            f'"source_name": "Source Name", '
            f'"evidence": "brief context from source"}}'
        )

        try:
            result = self.gemini.search_and_ground(
                query=prompt,
                competitor_name=company_name,
                search_type="general"
            )

            if "error" in result:
                return VerificationResult(
                    field_name=field_name,
                    status="unverifiable",
                    error=result.get("error")
                )

            response_text = result.get("response", "")

            # Parse JSON from response
            try:
                # Strip markdown fences if present
                cleaned = response_text.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()

                parsed = json.loads(cleaned)
            except (json.JSONDecodeError, ValueError):
                logger.warning(f"Could not parse verification response for {field_name}: {response_text[:200]}")
                return VerificationResult(
                    field_name=field_name,
                    status="unverifiable",
                    error="Could not parse AI response"
                )

            status = parsed.get("status", "unverifiable")
            if status not in ("correct", "wrong", "unverifiable"):
                status = "unverifiable"

            source_url = parsed.get("source_url")
            url_valid = False
            source_type = "unknown"
            if source_url:
                url_valid = await self.validate_url(source_url)
                source_type = self.classify_source_type(source_url)

            confidence = self.calculate_confidence_score(
                source_type=source_type,
                has_evidence=bool(parsed.get("evidence")),
                url_validated=url_valid
            )

            return VerificationResult(
                field_name=field_name,
                status=status,
                verified_value=parsed.get("verified_value"),
                source_url=source_url,
                source_name=parsed.get("source_name"),
                evidence=parsed.get("evidence"),
                confidence_score=confidence
            )

        except Exception as e:
            logger.error(f"Verification failed for {field_name}: {e}")
            return VerificationResult(
                field_name=field_name,
                status="unverifiable",
                error="Verification request failed"
            )

    async def verify_sources_for_competitor(
        self,
        competitor_id: int,
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        Verify and correct all battlecard fields for a competitor.

        For each field:
        - "correct": Create/update DataSource with is_verified=True
        - "wrong": Update competitor field with corrected value, log to ChangeLog
        - "unverifiable": Set field to N/A, store old value in DataSource.previous_value

        Returns summary dict with counts and per-field results.
        """
        db = SessionLocal()
        summary = {
            "competitor_id": competitor_id,
            "competitor_name": "Unknown",
            "fields_checked": 0,
            "fields_correct": 0,
            "fields_corrected": 0,
            "fields_unverifiable": 0,
            "errors": [],
            "details": []
        }

        try:
            competitor = db.query(Competitor).filter(Competitor.id == competitor_id).first()
            if not competitor:
                summary["errors"].append(f"Competitor {competitor_id} not found")
                return summary

            summary["competitor_name"] = competitor.name
            company_name = competitor.name
            website = getattr(competitor, "website", "") or ""

            for field_name in BATTLECARD_FIELDS:
                current_value = self.get_competitor_field_value(competitor, field_name)

                # Skip empty / N/A fields
                if not current_value or current_value.strip() in ("None", "null", "N/A", ""):
                    continue

                vr = await self.verify_and_correct_field(
                    company_name=company_name,
                    website=website,
                    field_name=field_name,
                    stored_value=current_value
                )

                summary["fields_checked"] += 1
                detail = {
                    "field": field_name,
                    "status": vr.status,
                    "old_value": current_value,
                    "new_value": vr.verified_value,
                    "source_url": vr.source_url,
                    "confidence": vr.confidence_score
                }

                # Find or create DataSource record
                existing_source = db.query(DataSource).filter(
                    DataSource.competitor_id == competitor_id,
                    DataSource.field_name == field_name
                ).first()

                if vr.status == "correct":
                    summary["fields_correct"] += 1
                    if existing_source:
                        existing_source.is_verified = True
                        existing_source.verified_by = "ai_verification"
                        existing_source.verification_date = datetime.utcnow()
                        existing_source.confidence_score = vr.confidence_score
                        if vr.source_url:
                            existing_source.source_url = vr.source_url
                        if vr.source_name:
                            existing_source.source_name = vr.source_name
                        existing_source.updated_at = datetime.utcnow()
                    else:
                        new_source = DataSource(
                            competitor_id=competitor_id,
                            field_name=field_name,
                            current_value=current_value,
                            source_url=vr.source_url,
                            source_type=self.classify_source_type(vr.source_url) if vr.source_url else "unknown",
                            source_name=vr.source_name,
                            confidence_score=vr.confidence_score,
                            confidence_level=determine_confidence_level(vr.confidence_score),
                            extraction_method="ai_verification",
                            is_verified=True,
                            verified_by="ai_verification",
                            verification_date=datetime.utcnow()
                        )
                        db.add(new_source)

                elif vr.status == "wrong":
                    summary["fields_corrected"] += 1
                    new_value = vr.verified_value or "N/A"

                    # Update competitor field
                    setattr(competitor, field_name, new_value)

                    # Log the change
                    change = ChangeLog(
                        competitor_id=competitor_id,
                        competitor_name=company_name,
                        change_type=field_name,
                        previous_value=current_value,
                        new_value=new_value,
                        source="ai_verification",
                        severity="Medium"
                    )
                    db.add(change)

                    # Create/update DataSource
                    if existing_source:
                        existing_source.previous_value = current_value
                        existing_source.current_value = new_value
                        existing_source.is_verified = True
                        existing_source.verified_by = "ai_verification"
                        existing_source.verification_date = datetime.utcnow()
                        existing_source.confidence_score = vr.confidence_score
                        if vr.source_url:
                            existing_source.source_url = vr.source_url
                        if vr.source_name:
                            existing_source.source_name = vr.source_name
                        existing_source.updated_at = datetime.utcnow()
                    else:
                        new_source = DataSource(
                            competitor_id=competitor_id,
                            field_name=field_name,
                            current_value=new_value,
                            previous_value=current_value,
                            source_url=vr.source_url,
                            source_type=self.classify_source_type(vr.source_url) if vr.source_url else "unknown",
                            source_name=vr.source_name,
                            confidence_score=vr.confidence_score,
                            confidence_level=determine_confidence_level(vr.confidence_score),
                            extraction_method="ai_verification",
                            is_verified=True,
                            verified_by="ai_verification",
                            verification_date=datetime.utcnow()
                        )
                        db.add(new_source)

                else:  # unverifiable
                    summary["fields_unverifiable"] += 1

                    # Set field to N/A
                    setattr(competitor, field_name, "N/A")

                    # Store old value in DataSource.previous_value
                    if existing_source:
                        existing_source.previous_value = current_value
                        existing_source.current_value = "N/A"
                        existing_source.is_verified = False
                        existing_source.verified_by = "ai_verification_unverifiable"
                        existing_source.verification_date = datetime.utcnow()
                        existing_source.updated_at = datetime.utcnow()
                    else:
                        new_source = DataSource(
                            competitor_id=competitor_id,
                            field_name=field_name,
                            current_value="N/A",
                            previous_value=current_value,
                            source_type="unknown",
                            confidence_score=0,
                            confidence_level="low",
                            extraction_method="ai_verification",
                            is_verified=False,
                            verified_by="ai_verification_unverifiable",
                            verification_date=datetime.utcnow()
                        )
                        db.add(new_source)

                db.commit()
                summary["details"].append(detail)

                if progress_callback:
                    progress_callback(field_name, vr.status, summary["fields_checked"])

                # Rate limit between AI calls
                await asyncio.sleep(1.0)

            competitor.last_updated = datetime.utcnow()
            db.commit()

            logger.info(
                f"Verification complete for {company_name}: "
                f"{summary['fields_checked']} checked, "
                f"{summary['fields_correct']} correct, "
                f"{summary['fields_corrected']} corrected, "
                f"{summary['fields_unverifiable']} unverifiable"
            )

            return summary

        except Exception as e:
            logger.error(f"Verification failed for competitor {competitor_id}: {e}")
            summary["errors"].append("Verification process failed")
            return summary
        finally:
            db.close()

    async def close(self):
        """Clean up resources."""
        await self.http_client.aclose()


# Singleton instance for reuse
_engine: Optional[SourceDiscoveryEngine] = None


def get_source_discovery_engine() -> SourceDiscoveryEngine:
    """Get or create the source discovery engine singleton."""
    global _engine
    if _engine is None:
        _engine = SourceDiscoveryEngine()
    return _engine
