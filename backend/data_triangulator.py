"""
Certify Intel - Data Triangulation Module
Cross-references data from multiple independent sources to verify accuracy.

Based on data triangulation best practices from:
- https://www.evalacademy.com/articles/part-1-what-is-data-triangulation-in-evaluation
- https://www.kingsresearch.com/blog/data-triangulation-in-market-research
"""

import asyncio
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict

# Internal imports
from confidence_scoring import (
    calculate_confidence_score,
    get_source_defaults,
    SOURCE_TYPE_DEFAULTS
)


@dataclass
class SourceData:
    """Data from a single source."""
    value: str
    source_type: str
    source_name: str
    source_url: Optional[str] = None
    reliability: str = "F"  # A-F
    credibility: int = 6    # 1-6
    extracted_at: Optional[datetime] = None
    raw_context: Optional[str] = None  # The text where value was found


@dataclass
class TriangulationResult:
    """Result of multi-source triangulation."""
    field_name: str
    best_value: str
    confidence_score: int
    confidence_level: str  # "high", "moderate", "low"
    source_used: str
    sources_checked: int
    sources_agreeing: int
    all_sources: List[Dict]
    discrepancy_flag: bool
    review_reason: Optional[str] = None
    triangulated_at: datetime = field(default_factory=datetime.utcnow)


class DataTriangulator:
    """
    Cross-reference data from multiple sources to verify accuracy.

    Methodology:
    1. Collect same data point from multiple sources
    2. Compare values for consistency
    3. Flag discrepancies for human review
    4. Calculate confidence based on agreement
    """

    # Authority order for source selection (highest authority first)
    # Enterprise data providers are at the top for institutional-grade data
    AUTHORITY_ORDER = [
        "pitchbook",
        "sp_capital_iq",
        "bloomberg",
        "factset",
        "lseg",
        "orbis",
        "crunchbase",
        "cb_insights",
        "dealroom",
        "preqin",
        "enterprise_api",
        "sec_filing",
        "api_verified",
        "klas_report",
        "definitive_hc",
        "manual_verified",
        "website_scrape",
        "news_article",
        "linkedin_estimate",
        "unknown",
    ]

    def __init__(self, db_session=None):
        self.db = db_session

    async def triangulate_customer_count(
        self,
        competitor_id: int,
        competitor_name: str,
        website: str,
        is_public: bool = False,
        ticker_symbol: str = None
    ) -> TriangulationResult:
        """
        Verify customer count using multiple sources.

        Sources checked:
        1. Company website (marketing claims)
        2. SEC filings (if public)
        3. News/press releases
        4. G2 Crowd reviews (as proxy)
        """
        sources = []

        # Source 1: Get existing website scrape data from database
        website_data = await self._get_website_customer_count(competitor_id, competitor_name)
        if website_data:
            sources.append(website_data)

        # Source 2: SEC filings (for public companies)
        if is_public and ticker_symbol:
            sec_data = await self._get_sec_customer_data(competitor_name, ticker_symbol)
            if sec_data:
                sources.append(sec_data)

        # Source 3: News mentions (search for customer count mentions)
        news_data = await self._search_news_for_customer_count(competitor_name)
        if news_data:
            sources.append(news_data)

        return self._calculate_triangulated_result("customer_count", sources)

    async def triangulate_employee_count(
        self,
        competitor_id: int,
        competitor_name: str,
        is_public: bool = False,
        ticker_symbol: str = None
    ) -> TriangulationResult:
        """
        Verify employee count using multiple sources.

        Sources:
        1. Company website
        2. SEC filings (if public)
        3. LinkedIn (via API or estimate)
        """
        sources = []

        # Source 1: Website scrape
        website_data = await self._get_website_employee_count(competitor_id, competitor_name)
        if website_data:
            sources.append(website_data)

        # Source 2: SEC filings
        if is_public and ticker_symbol:
            sec_data = await self._get_sec_employee_count(competitor_name, ticker_symbol)
            if sec_data:
                sources.append(sec_data)

        return self._calculate_triangulated_result("employee_count", sources)

    async def triangulate_pricing(
        self,
        competitor_id: int,
        competitor_name: str,
        website: str
    ) -> TriangulationResult:
        """
        Verify pricing data using multiple sources.

        Sources:
        1. Pricing page scrape
        2. G2/Capterra pricing info
        3. Sales intel (manual entries)
        """
        sources = []

        # Source 1: Website pricing page
        website_data = await self._get_website_pricing(competitor_id, competitor_name)
        if website_data:
            sources.append(website_data)

        # Source 2: Manual verified pricing (if exists)
        manual_data = await self._get_manual_pricing(competitor_id)
        if manual_data:
            sources.append(manual_data)

        return self._calculate_triangulated_result("base_price", sources)

    async def triangulate_all_key_fields(
        self,
        competitor_id: int,
        competitor_name: str,
        website: str,
        is_public: bool = False,
        ticker_symbol: str = None
    ) -> Dict[str, TriangulationResult]:
        """Triangulate all key data fields for a competitor."""
        results = {}

        # Run triangulations in parallel
        tasks = [
            self.triangulate_customer_count(
                competitor_id, competitor_name, website, is_public, ticker_symbol
            ),
            self.triangulate_employee_count(
                competitor_id, competitor_name, is_public, ticker_symbol
            ),
            self.triangulate_pricing(
                competitor_id, competitor_name, website
            )
        ]

        triangulated = await asyncio.gather(*tasks, return_exceptions=True)

        field_names = ["customer_count", "employee_count", "base_price"]
        for i, result in enumerate(triangulated):
            if isinstance(result, TriangulationResult):
                results[field_names[i]] = result
            else:
                # Handle exceptions
                results[field_names[i]] = TriangulationResult(
                    field_name=field_names[i],
                    best_value="Unknown",
                    confidence_score=0,
                    confidence_level="low",
                    source_used="none",
                    sources_checked=0,
                    sources_agreeing=0,
                    all_sources=[],
                    discrepancy_flag=True,
                    review_reason=f"Triangulation failed: {str(result)}"
                )

        return results

    # ==================== INTERNAL SOURCE FETCHERS ====================

    async def _get_website_customer_count(self, competitor_id: int, competitor_name: str) -> Optional[SourceData]:
        """Get customer count from database (website scrape)."""
        if not self.db:
            return None

        from database import DataSource

        source = self.db.query(DataSource).filter(
            DataSource.competitor_id == competitor_id,
            DataSource.field_name == "customer_count"
        ).first()

        if source and source.current_value:
            return SourceData(
                value=source.current_value,
                source_type="website_scrape",
                source_name=f"{competitor_name} Website",
                source_url=source.source_url,
                reliability="D",
                credibility=4,
                extracted_at=source.extracted_at
            )
        return None

    async def _get_sec_customer_data(self, competitor_name: str, ticker_symbol: str) -> Optional[SourceData]:
        """Get customer count from SEC filings."""
        try:
            from sec_edgar_scraper import SECEdgarScraper
            scraper = SECEdgarScraper()
            data = scraper.get_company_data(competitor_name)

            if data.customers_mentioned:
                # SEC filings often mention customer names rather than counts
                customer_info = f"{len(data.customers_mentioned)} key customers mentioned: {', '.join(data.customers_mentioned[:3])}"
                return SourceData(
                    value=customer_info,
                    source_type="sec_filing",
                    source_name=f"{ticker_symbol} SEC 10-K",
                    source_url=f"https://sec.gov/cgi-bin/browse-edgar?CIK={data.cik}",
                    reliability="A",
                    credibility=1,
                    extracted_at=datetime.utcnow()
                )
        except Exception as e:
            print(f"SEC data fetch error: {e}")
        return None

    async def _get_sec_employee_count(self, competitor_name: str, ticker_symbol: str) -> Optional[SourceData]:
        """Get employee count from SEC filings."""
        try:
            from sec_edgar_scraper import SECEdgarScraper
            scraper = SECEdgarScraper()
            data = scraper.get_company_data(competitor_name)

            if data.employee_count:
                return SourceData(
                    value=str(data.employee_count),
                    source_type="sec_filing",
                    source_name=f"{ticker_symbol} SEC 10-K",
                    source_url=f"https://sec.gov/cgi-bin/browse-edgar?CIK={data.cik}",
                    reliability="A",
                    credibility=1,
                    extracted_at=datetime.utcnow(),
                    raw_context=f"Full-time employees as reported in 10-K filing"
                )
        except Exception as e:
            print(f"SEC employee count error: {e}")
        return None

    async def _get_website_employee_count(self, competitor_id: int, competitor_name: str) -> Optional[SourceData]:
        """Get employee count from database (website scrape)."""
        if not self.db:
            return None

        from database import DataSource

        source = self.db.query(DataSource).filter(
            DataSource.competitor_id == competitor_id,
            DataSource.field_name == "employee_count"
        ).first()

        if source and source.current_value:
            return SourceData(
                value=source.current_value,
                source_type="website_scrape",
                source_name=f"{competitor_name} Website",
                source_url=source.source_url,
                reliability="D",
                credibility=4,
                extracted_at=source.extracted_at
            )
        return None

    async def _get_website_pricing(self, competitor_id: int, competitor_name: str) -> Optional[SourceData]:
        """Get pricing from database (website scrape)."""
        if not self.db:
            return None

        from database import DataSource

        source = self.db.query(DataSource).filter(
            DataSource.competitor_id == competitor_id,
            DataSource.field_name == "base_price"
        ).first()

        if source and source.current_value:
            return SourceData(
                value=source.current_value,
                source_type="website_scrape",
                source_name=f"{competitor_name} Pricing Page",
                source_url=source.source_url,
                reliability="C",  # Pricing pages are more reliable than general marketing
                credibility=3,
                extracted_at=source.extracted_at
            )
        return None

    async def _get_manual_pricing(self, competitor_id: int) -> Optional[SourceData]:
        """Get manually verified pricing from database."""
        if not self.db:
            return None

        from database import DataSource

        source = self.db.query(DataSource).filter(
            DataSource.competitor_id == competitor_id,
            DataSource.field_name == "base_price",
            DataSource.source_type == "manual"
        ).first()

        if source and source.current_value:
            return SourceData(
                value=source.current_value,
                source_type="manual_verified",
                source_name="Sales Team Intel",
                reliability="B",
                credibility=2,
                extracted_at=source.extracted_at
            )
        return None

    async def _search_news_for_customer_count(self, competitor_name: str) -> Optional[SourceData]:
        """Search news articles for customer count mentions."""
        try:
            # Use existing news scraper to find customer count mentions
            from external_scrapers import NewsScraper
            scraper = NewsScraper()
            articles = await scraper.scrape_google_news(f"{competitor_name} customers", limit=5)

            # Look for customer count patterns in articles
            for article in articles:
                text = f"{article.title} {article.snippet}"
                # Pattern: "X customers", "X+ customers", "over X customers"
                patterns = [
                    r'(\d{1,3}(?:,\d{3})*)\+?\s*(?:healthcare\s+)?(?:customers|clients|organizations)',
                    r'over\s+(\d{1,3}(?:,\d{3})*)\s*(?:healthcare\s+)?(?:customers|clients)',
                    r'more\s+than\s+(\d{1,3}(?:,\d{3})*)\s*(?:customers|clients)'
                ]

                for pattern in patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        count = match.group(1).replace(',', '')
                        return SourceData(
                            value=f"{count}+",
                            source_type="news_article",
                            source_name=article.source,
                            source_url=article.url,
                            reliability="C",
                            credibility=3,
                            extracted_at=datetime.utcnow(),
                            raw_context=text[:200]
                        )
        except Exception as e:
            print(f"News search error: {e}")
        return None

    # ==================== TRIANGULATION LOGIC ====================

    def _calculate_triangulated_result(
        self,
        field_name: str,
        sources: List[SourceData]
    ) -> TriangulationResult:
        """
        Determine most reliable value and overall confidence.

        Rules:
        1. If authoritative source exists (SEC, API), use that
        2. If multiple sources agree, high confidence
        3. If sources disagree, flag for review
        """
        if not sources:
            return TriangulationResult(
                field_name=field_name,
                best_value="Unknown",
                confidence_score=0,
                confidence_level="low",
                source_used="none",
                sources_checked=0,
                sources_agreeing=0,
                all_sources=[],
                discrepancy_flag=True,
                review_reason="No data sources available"
            )

        # Convert sources to dicts for storage
        sources_as_dicts = [
            {
                "value": s.value,
                "source_type": s.source_type,
                "source_name": s.source_name,
                "source_url": s.source_url,
                "reliability": s.reliability,
                "credibility": s.credibility
            }
            for s in sources
        ]

        # Check for authoritative source first
        for auth_type in self.AUTHORITY_ORDER:
            for source in sources:
                if source.source_type == auth_type and source.value:
                    # Calculate confidence for this source
                    confidence = calculate_confidence_score(
                        source_type=auth_type,
                        source_reliability=source.reliability,
                        information_credibility=source.credibility,
                        corroborating_sources=len(sources) - 1
                    )

                    # Check if other sources agree (within tolerance)
                    agreeing = self._count_agreeing_sources(source.value, sources)

                    return TriangulationResult(
                        field_name=field_name,
                        best_value=source.value,
                        confidence_score=confidence.score,
                        confidence_level=confidence.level,
                        source_used=source.source_type,
                        sources_checked=len(sources),
                        sources_agreeing=agreeing,
                        all_sources=sources_as_dicts,
                        discrepancy_flag=agreeing < len(sources)
                    )

        # No authoritative source - use best available
        best_source = sources[0]
        confidence = calculate_confidence_score(
            source_type=best_source.source_type,
            source_reliability=best_source.reliability,
            information_credibility=best_source.credibility,
            corroborating_sources=0
        )

        return TriangulationResult(
            field_name=field_name,
            best_value=best_source.value,
            confidence_score=confidence.score,
            confidence_level=confidence.level,
            source_used=best_source.source_type,
            sources_checked=len(sources),
            sources_agreeing=1,
            all_sources=sources_as_dicts,
            discrepancy_flag=True,
            review_reason="No authoritative source; recommend manual verification"
        )

    def _count_agreeing_sources(self, reference_value: str, sources: List[SourceData]) -> int:
        """Count how many sources have similar values."""
        agreeing = 0

        # Extract numeric value from reference
        ref_num = self._extract_number(reference_value)

        for source in sources:
            source_num = self._extract_number(source.value)

            if ref_num is not None and source_num is not None:
                # Check if within 20% tolerance
                if ref_num > 0:
                    tolerance = abs(source_num - ref_num) / ref_num
                    if tolerance <= 0.20:
                        agreeing += 1
            elif reference_value.lower() == source.value.lower():
                agreeing += 1

        return agreeing

    def _extract_number(self, value: str) -> Optional[int]:
        """Extract numeric value from string like '3000+' or '3,500'."""
        if not value:
            return None

        # Remove common suffixes and clean
        cleaned = re.sub(r'[+,\s]', '', value)

        # Extract first number
        match = re.search(r'(\d+)', cleaned)
        if match:
            return int(match.group(1))

        return None


# Convenience functions

async def triangulate_competitor(
    competitor_id: int,
    competitor_name: str,
    website: str,
    is_public: bool = False,
    ticker_symbol: str = None,
    db_session = None
) -> Dict[str, TriangulationResult]:
    """Triangulate all key fields for a competitor."""
    triangulator = DataTriangulator(db_session)
    return await triangulator.triangulate_all_key_fields(
        competitor_id, competitor_name, website, is_public, ticker_symbol
    )


def triangulation_result_to_dict(result: TriangulationResult) -> Dict[str, Any]:
    """Convert TriangulationResult to JSON-serializable dict."""
    return {
        "field_name": result.field_name,
        "best_value": result.best_value,
        "confidence": {
            "score": result.confidence_score,
            "level": result.confidence_level
        },
        "source_used": result.source_used,
        "verification": {
            "sources_checked": result.sources_checked,
            "sources_agreeing": result.sources_agreeing,
            "discrepancy_flag": result.discrepancy_flag,
            "review_reason": result.review_reason
        },
        "all_sources": result.all_sources,
        "triangulated_at": result.triangulated_at.isoformat()
    }
