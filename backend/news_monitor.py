"""
Certify Intel - Real-Time News Monitor (v5.0.7)
Fetches and analyzes competitor news from multiple sources.

v5.0.3: Added SEC EDGAR and USPTO patent integration for government data sources.
v5.0.4: Added GNews, MediaStack, and NewsData.io API integrations (Phase 3).
v5.0.5: Added Hugging Face ML sentiment analysis (Phase 4).
v5.0.7: Added dimension tagging integration for Sales & Marketing module.
"""
import os
import re
import json
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
import logging
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import httpx

logger = logging.getLogger(__name__)

# Module-level state for async progress tracking and circuit breaker
_news_fetch_progress: Dict[str, Dict[str, Any]] = {}
_circuit_breaker: Dict[str, Dict[str, Any]] = {}
_CB_THRESHOLD = 3  # consecutive failures before opening circuit
_CB_RESET_SECONDS = 3600  # 1 hour cooldown

# Import government data scrapers (v5.0.3)
try:
    from sec_edgar_scraper import SECEdgarScraper, get_sec_news
    SEC_AVAILABLE = True
except ImportError:
    SEC_AVAILABLE = False
    logger.info("SEC EDGAR scraper not available")

try:
    from uspto_scraper import USPTOScraper
    USPTO_AVAILABLE = True
except ImportError:
    USPTO_AVAILABLE = False
    logger.info("USPTO patent scraper not available")

# Enhanced Google News library (v5.0.3)
try:
    from pygooglenews import GoogleNews
    PYGOOGLENEWS_AVAILABLE = True
except ImportError:
    PYGOOGLENEWS_AVAILABLE = False
    logger.info("pygooglenews not available, using raw RSS")

# ML-powered sentiment analysis (v5.0.5)
try:
    from ml_sentiment import get_headline_analyzer, NewsHeadlineSentimentAnalyzer
    ML_SENTIMENT_AVAILABLE = True
except ImportError:
    ML_SENTIMENT_AVAILABLE = False
    logger.info("ML sentiment not available, using keyword-based")

# Dimension tagging for Sales & Marketing module (v5.0.7)
try:
    from dimension_analyzer import DimensionAnalyzer
    DIMENSION_ANALYZER_AVAILABLE = True
except ImportError:
    DIMENSION_ANALYZER_AVAILABLE = False
    logger.info("Dimension analyzer not available")


@dataclass
class NewsArticle:
    """Represents a news article."""
    title: str
    url: str
    source: str
    published_date: str
    snippet: str
    sentiment: str  # positive, negative, neutral
    is_major_event: bool
    event_type: Optional[str]  # funding, acquisition, product_launch, partnership
    dimension_tags: Optional[List[Dict[str, Any]]] = None  # v5.0.7: dimension classifications


@dataclass
class NewsDigest:
    """Collection of news articles with analysis."""
    company_name: str
    articles: List[NewsArticle]
    total_count: int
    sentiment_breakdown: Dict[str, int]
    major_events: List[NewsArticle]
    fetched_at: str


class NewsMonitor:
    """Multi-source news monitoring for competitors."""
    
    # Keywords indicating major events
    EVENT_KEYWORDS = {
        "funding": ["raises", "funding", "series a", "series b", "series c", "investment", "venture capital", "capital raise"],
        "acquisition": ["acquires", "acquisition", "acquired", "merger", "buys", "purchased", "takeover"],
        "product_launch": ["launches", "introduces", "unveils", "new product", "release", "rolls out", "debuts"],
        "partnership": ["partners", "partnership", "collaboration", "integrates", "alliance", "joint venture"],
        "leadership": ["ceo", "cto", "cfo", "appoints", "names new", "executive", "board of directors", "steps down"],
        "financial": ["earnings", "revenue", "quarterly", "ipo", "stock", "valuation", "profit", "fiscal"],
        "legal": ["lawsuit", "sued", "regulatory", "compliance", "fda", "patent infringement", "antitrust", "settlement"],
        "expansion": ["expands", "opens", "enters", "new market", "expansion", "new office", "headcount"],
    }
    
    # Sentiment keywords
    POSITIVE_KEYWORDS = ["growth", "success", "award", "wins", "leading", "innovative", "raises", "expands"]
    NEGATIVE_KEYWORDS = ["layoffs", "lawsuit", "breach", "decline", "struggles", "loses", "cuts", "failed"]
    
    def __init__(
        self,
        include_sec: bool = True,
        include_patents: bool = True,
        use_pygooglenews: bool = True,
        use_ml_sentiment: bool = True,
        tag_dimensions: bool = True
    ):
        """
        Initialize NewsMonitor.

        Args:
            include_sec: Include SEC EDGAR filings as news (v5.0.3)
            include_patents: Include USPTO patents as news (v5.0.3)
            use_pygooglenews: Use enhanced pygooglenews library (v5.0.3)
            use_ml_sentiment: Use ML-based sentiment analysis (v5.0.5)
            tag_dimensions: Tag articles with competitive dimensions (v5.0.7)
        """
        self.newsapi_key = os.getenv("NEWSAPI_KEY")
        self.bing_news_key = os.getenv("BING_NEWS_KEY")

        # v5.0.4: Free news API keys (Phase 3)
        self.gnews_api_key = os.getenv("GNEWS_API_KEY")
        self.mediastack_api_key = os.getenv("MEDIASTACK_API_KEY")
        self.newsdata_api_key = os.getenv("NEWSDATA_API_KEY")

        # v5.0.3: Government data sources
        self.include_sec = include_sec and SEC_AVAILABLE
        self.include_patents = include_patents and USPTO_AVAILABLE

        # v5.0.3: Enhanced Google News with pygooglenews
        self.use_pygooglenews = use_pygooglenews and PYGOOGLENEWS_AVAILABLE
        self.google_news_client = GoogleNews(lang='en', country='US') if self.use_pygooglenews else None

        # v5.0.5: ML-powered sentiment analysis
        self.use_ml_sentiment = use_ml_sentiment and ML_SENTIMENT_AVAILABLE
        self.ml_sentiment_analyzer = get_headline_analyzer() if self.use_ml_sentiment else None

        # v5.0.7: Dimension tagging for Sales & Marketing module
        self.tag_dimensions = tag_dimensions and DIMENSION_ANALYZER_AVAILABLE
        self.dimension_analyzer = DimensionAnalyzer() if self.tag_dimensions else None

        # Initialize scrapers if available
        self.sec_scraper = SECEdgarScraper() if self.include_sec else None
        self.patent_scraper = USPTOScraper() if self.include_patents else None

    # ============== Circuit Breaker (v5.1.0) ==============

    def _is_circuit_open(self, source_name: str) -> bool:
        """Check if a source's circuit breaker is open (too many failures)."""
        cb = _circuit_breaker.get(source_name)
        if not cb:
            return False
        if cb["failures"] >= _CB_THRESHOLD:
            elapsed = time.time() - cb["last_failure"]
            if elapsed < _CB_RESET_SECONDS:
                return True
            # Reset after cooldown period
            _circuit_breaker[source_name] = {"failures": 0, "last_failure": 0}
            return False
        return False

    def _record_source_failure(self, source_name: str) -> None:
        """Record a fetch failure for circuit breaker tracking."""
        cb = _circuit_breaker.get(source_name, {"failures": 0, "last_failure": 0})
        cb["failures"] += 1
        cb["last_failure"] = time.time()
        _circuit_breaker[source_name] = cb
        logger.warning(
            f"Circuit breaker: {source_name} failure "
            f"({cb['failures']}/{_CB_THRESHOLD})"
        )

    def _record_source_success(self, source_name: str) -> None:
        """Reset failure count on successful fetch."""
        _circuit_breaker[source_name] = {"failures": 0, "last_failure": 0}

    # ============== Async Parallel Fetching (v5.1.0) ==============

    async def fetch_news_async(
        self,
        company_name: str,
        days: int = 90,
        progress_key: Optional[str] = None,
        real_name: Optional[str] = None,
        website: Optional[str] = None,
    ) -> NewsDigest:
        """
        Fetch news from all sources in parallel using async HTTP.

        Args:
            company_name: Name of the company
            days: Number of days to look back
            progress_key: Optional key for tracking progress via get_news_fetch_progress()

        Returns:
            NewsDigest with deduplicated, analyzed articles
        """
        if progress_key:
            _news_fetch_progress[progress_key] = {
                "status": "fetching",
                "sources_checked": 0,
                "articles_found": 0,
                "total_sources": 0,
                "company": company_name,
            }

        # Build list of (source_name, coroutine) pairs
        source_tasks: List[tuple] = []

        async with httpx.AsyncClient(timeout=8.0) as client:
            # Google News RSS (always available)
            if not self._is_circuit_open("google_news"):
                source_tasks.append(
                    ("google_news", self._fetch_google_news_async(client, company_name))
                )

            # NewsAPI
            if self.newsapi_key and not self._is_circuit_open("newsapi"):
                source_tasks.append(
                    ("newsapi", self._fetch_newsapi_async(client, company_name, days))
                )

            # Bing News
            if self.bing_news_key and not self._is_circuit_open("bing_news"):
                source_tasks.append(
                    ("bing_news", self._fetch_bing_news_async(client, company_name))
                )

            # GNews
            if self.gnews_api_key and not self._is_circuit_open("gnews"):
                source_tasks.append(
                    ("gnews", self._fetch_gnews_async(client, company_name))
                )

            # MediaStack
            if self.mediastack_api_key and not self._is_circuit_open("mediastack"):
                source_tasks.append(
                    ("mediastack", self._fetch_mediastack_async(client, company_name))
                )

            # NewsData.io
            if self.newsdata_api_key and not self._is_circuit_open("newsdata"):
                source_tasks.append(
                    ("newsdata", self._fetch_newsdata_async(client, company_name))
                )

            # SEC EDGAR (sync, wrapped in to_thread)
            if self.include_sec and not self._is_circuit_open("sec_edgar"):
                source_tasks.append(
                    ("sec_edgar", asyncio.to_thread(self._fetch_sec_filings, company_name, days))
                )

            # USPTO (sync, wrapped in to_thread)
            if self.include_patents and not self._is_circuit_open("uspto"):
                source_tasks.append(
                    ("uspto", asyncio.to_thread(self._fetch_patent_news, company_name))
                )

            if progress_key:
                _news_fetch_progress[progress_key]["total_sources"] = len(source_tasks)

            # Run all source fetches in parallel
            source_names = [name for name, _ in source_tasks]
            coroutines = [coro for _, coro in source_tasks]
            results = await asyncio.gather(*coroutines, return_exceptions=True)

        # Process results
        articles: List[NewsArticle] = []
        sources_checked = 0

        for source_name, result in zip(source_names, results):
            sources_checked += 1
            if isinstance(result, Exception):
                self._record_source_failure(source_name)
                logger.warning(f"Async fetch failed for {source_name}: {result}")
            else:
                self._record_source_success(source_name)
                articles.extend(result)

            if progress_key:
                _news_fetch_progress[progress_key].update({
                    "sources_checked": sources_checked,
                    "articles_found": len(articles),
                })

        # Deduplicate by URL
        seen_urls: set = set()
        unique_articles: List[NewsArticle] = []
        for article in articles:
            if article.url not in seen_urls:
                seen_urls.add(article.url)
                unique_articles.append(article)

        # v8.0.8: Filter out irrelevant articles (non-healthcare noise)
        unique_articles = self._filter_irrelevant_articles(
            unique_articles, company_name, real_name=real_name, website=website
        )

        # v8.0.5: AI-powered sentiment + event_type classification (both in one call)
        await asyncio.to_thread(self._analyze_sentiment_batch, unique_articles)

        # Dimension tagging
        if self.tag_dimensions:
            await asyncio.to_thread(
                self._tag_dimensions_batch, unique_articles, company_name
            )

        # Build digest
        sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}
        for article in unique_articles:
            sentiment_counts[article.sentiment] += 1

        major_events = [a for a in unique_articles if a.is_major_event]

        if progress_key:
            _news_fetch_progress[progress_key].update({
                "status": "complete",
                "articles_found": len(unique_articles),
            })

        return NewsDigest(
            company_name=company_name,
            articles=unique_articles,
            total_count=len(unique_articles),
            sentiment_breakdown=sentiment_counts,
            major_events=major_events,
            fetched_at=datetime.utcnow().isoformat()
        )

    # ============== Async HTTP Fetch Methods (v5.1.0) ==============

    async def _fetch_google_news_async(
        self, client: httpx.AsyncClient, company_name: str
    ) -> List[NewsArticle]:
        """Async Google News RSS fetch."""
        articles: List[NewsArticle] = []
        try:
            query = urllib.parse.quote(f'"{company_name}"')
            url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
            response = await client.get(url)
            response.raise_for_status()
            root = ET.fromstring(response.content)

            for item in root.findall(".//item"):
                title_el = item.find("title")
                link_el = item.find("link")
                pub_date_el = item.find("pubDate")
                source_el = item.find("source")

                if title_el is not None and link_el is not None:
                    title_text = title_el.text or ""
                    source_name = source_el.text if source_el is not None else "Google News"

                    if " - " in title_text:
                        parts = title_text.rsplit(" - ", 1)
                        title_text = parts[0]
                        if len(parts) > 1:
                            source_name = parts[1]

                    articles.append(NewsArticle(
                        title=title_text,
                        url=link_el.text or "",
                        source=source_name,
                        published_date=pub_date_el.text if pub_date_el is not None else "",
                        snippet="",
                        sentiment="neutral",
                        is_major_event=False,
                        event_type=None
                    ))
        except Exception as e:
            logger.warning(f"Async Google News RSS fetch failed: {e}")
            raise
        return articles

    async def _fetch_newsapi_async(
        self, client: httpx.AsyncClient, company_name: str, days: int
    ) -> List[NewsArticle]:
        """Async NewsAPI fetch."""
        articles: List[NewsArticle] = []
        try:
            from_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
            query = urllib.parse.quote(f'"{company_name}"')
            url = (
                f"https://newsapi.org/v2/everything?q={query}"
                f"&from={from_date}&sortBy=publishedAt&pageSize=100"
                f"&apiKey={self.newsapi_key}"
            )
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            for item in data.get("articles", []):
                articles.append(NewsArticle(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    source=item.get("source", {}).get("name", "NewsAPI"),
                    published_date=item.get("publishedAt", ""),
                    snippet=item.get("description", ""),
                    sentiment="neutral",
                    is_major_event=False,
                    event_type=None
                ))
        except Exception as e:
            logger.warning(f"Async NewsAPI fetch failed: {e}")
            raise
        return articles

    async def _fetch_bing_news_async(
        self, client: httpx.AsyncClient, company_name: str
    ) -> List[NewsArticle]:
        """Async Bing News API fetch."""
        articles: List[NewsArticle] = []
        try:
            query = urllib.parse.quote(f'"{company_name}"')
            url = f"https://api.bing.microsoft.com/v7.0/news/search?q={query}&count=100"
            response = await client.get(
                url, headers={"Ocp-Apim-Subscription-Key": self.bing_news_key}
            )
            response.raise_for_status()
            data = response.json()

            for item in data.get("value", []):
                articles.append(NewsArticle(
                    title=item.get("name", ""),
                    url=item.get("url", ""),
                    source=item.get("provider", [{}])[0].get("name", "Bing News"),
                    published_date=item.get("datePublished", ""),
                    snippet=item.get("description", ""),
                    sentiment="neutral",
                    is_major_event=False,
                    event_type=None
                ))
        except Exception as e:
            logger.warning(f"Async Bing News fetch failed: {e}")
            raise
        return articles

    async def _fetch_gnews_async(
        self, client: httpx.AsyncClient, company_name: str
    ) -> List[NewsArticle]:
        """Async GNews API fetch."""
        articles: List[NewsArticle] = []
        try:
            query = urllib.parse.quote(f'"{company_name}"')
            url = (
                f"https://gnews.io/api/v4/search?q={query}"
                f"&lang=en&country=us&max=50&apikey={self.gnews_api_key}"
            )
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            for item in data.get("articles", []):
                articles.append(NewsArticle(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    source=item.get("source", {}).get("name", "GNews"),
                    published_date=item.get("publishedAt", ""),
                    snippet=item.get("description", ""),
                    sentiment="neutral",
                    is_major_event=False,
                    event_type=None
                ))
        except Exception as e:
            logger.warning(f"Async GNews fetch failed: {e}")
            raise
        return articles

    async def _fetch_mediastack_async(
        self, client: httpx.AsyncClient, company_name: str
    ) -> List[NewsArticle]:
        """Async MediaStack API fetch."""
        articles: List[NewsArticle] = []
        try:
            query = urllib.parse.quote(company_name)
            url = (
                f"http://api.mediastack.com/v1/news"
                f"?access_key={self.mediastack_api_key}"
                f"&keywords={query}&languages=en&limit=50"
            )
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            for item in data.get("data", []):
                articles.append(NewsArticle(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    source=item.get("source", "MediaStack"),
                    published_date=item.get("published_at", ""),
                    snippet=item.get("description", ""),
                    sentiment="neutral",
                    is_major_event=False,
                    event_type=None
                ))
        except Exception as e:
            logger.warning(f"Async MediaStack fetch failed: {e}")
            raise
        return articles

    async def _fetch_newsdata_async(
        self, client: httpx.AsyncClient, company_name: str
    ) -> List[NewsArticle]:
        """Async NewsData.io API fetch."""
        articles: List[NewsArticle] = []
        try:
            query = urllib.parse.quote(company_name)
            url = (
                f"https://newsdata.io/api/1/news"
                f"?apikey={self.newsdata_api_key}&q={query}&language=en"
            )
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            for item in data.get("results", []):
                categories = item.get("category", [])
                event_type = None
                if "technology" in categories:
                    event_type = "product_launch"
                elif "business" in categories:
                    event_type = "financial"
                elif "health" in categories:
                    event_type = "expansion"

                snippet_text = item.get("description", "")
                if not snippet_text and item.get("content"):
                    snippet_text = item["content"][:200]

                articles.append(NewsArticle(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    source=item.get("source_id", "NewsData.io"),
                    published_date=item.get("pubDate", ""),
                    snippet=snippet_text,
                    sentiment="neutral",
                    is_major_event=event_type is not None,
                    event_type=event_type
                ))
        except Exception as e:
            logger.warning(f"Async NewsData.io fetch failed: {e}")
            raise
        return articles

    # ============== Bulk Async Fetch (v5.1.0) ==============

    async def fetch_all_competitors_async(
        self,
        competitors: List[Dict[str, Any]],
        days: int = 7,
        progress_key: str = "default"
    ) -> Dict[str, Any]:
        """
        Fetch news for multiple competitors in parallel with concurrency limit.

        Args:
            competitors: List of dicts with at least 'name' key (and optionally 'id')
            days: Number of days to look back
            progress_key: Key for tracking progress via get_news_fetch_progress()

        Returns:
            Summary dict with totals and per-competitor/per-source breakdowns
        """
        total = len(competitors)
        _news_fetch_progress[progress_key] = {
            "status": "running",
            "current_competitor": "",
            "total_competitors": total,
            "completed": 0,
            "articles_found": 0,
            "sources_checked": 0,
            "percentage": 0,
        }

        sem = asyncio.Semaphore(10)
        per_competitor: Dict[str, int] = {}
        per_source: Dict[str, int] = {}
        sentiment_totals = {"positive": 0, "negative": 0, "neutral": 0}
        total_articles = 0

        async def _fetch_one(comp: Dict[str, Any]) -> None:
            nonlocal total_articles
            name = comp["name"]
            _news_fetch_progress[progress_key]["current_competitor"] = name

            async with sem:
                try:
                    digest = await self.fetch_news_async(name, days=days)
                    count = digest.total_count
                    per_competitor[name] = count
                    total_articles += count

                    # Aggregate sources
                    for article in digest.articles:
                        per_source[article.source] = per_source.get(article.source, 0) + 1

                    # Aggregate sentiment
                    for key in sentiment_totals:
                        sentiment_totals[key] += digest.sentiment_breakdown.get(key, 0)

                except Exception as e:
                    logger.error(f"Bulk fetch failed for {name}: {e}")
                    per_competitor[name] = 0

            completed = _news_fetch_progress[progress_key]["completed"] + 1
            _news_fetch_progress[progress_key].update({
                "completed": completed,
                "articles_found": total_articles,
                "percentage": int((completed / total) * 100) if total else 100,
            })

        tasks = [_fetch_one(comp) for comp in competitors]
        await asyncio.gather(*tasks)

        _news_fetch_progress[progress_key]["status"] = "complete"

        return {
            "total_articles": total_articles,
            "competitors_fetched": total,
            "per_competitor": per_competitor,
            "per_source": per_source,
            "sentiment_breakdown": sentiment_totals,
        }

    def fetch_news(self, company_name: str, days: int = 90, real_name: Optional[str] = None, website: Optional[str] = None) -> NewsDigest:
        """
        Fetch news for a company from all available sources.

        Args:
            company_name: Name of the company
            days: Number of days to look back (default: 90 days / 3 months)

        Returns:
            NewsDigest with articles and analysis
        """
        articles = []

        # Try Google News RSS (free, no API key needed)
        google_articles = self._fetch_google_news(company_name)
        articles.extend(google_articles)

        # Try NewsAPI if key available
        if self.newsapi_key:
            newsapi_articles = self._fetch_newsapi(company_name, days)
            articles.extend(newsapi_articles)

        # Try Bing News if key available
        if self.bing_news_key:
            bing_articles = self._fetch_bing_news(company_name)
            articles.extend(bing_articles)

        # v5.0.3: SEC EDGAR filings (free, no API key needed)
        if self.include_sec:
            sec_articles = self._fetch_sec_filings(company_name, days)
            articles.extend(sec_articles)

        # v5.0.3: USPTO patent news (free, no API key needed)
        if self.include_patents:
            patent_articles = self._fetch_patent_news(company_name)
            articles.extend(patent_articles)

        # v5.0.4: GNews API (100 req/day free)
        if self.gnews_api_key:
            gnews_articles = self._fetch_gnews(company_name)
            articles.extend(gnews_articles)

        # v5.0.4: MediaStack API (500 req/month free)
        if self.mediastack_api_key:
            mediastack_articles = self._fetch_mediastack(company_name)
            articles.extend(mediastack_articles)

        # v5.0.4: NewsData.io API (200 req/day free, tech/healthcare specialty)
        if self.newsdata_api_key:
            newsdata_articles = self._fetch_newsdata(company_name)
            articles.extend(newsdata_articles)

        # Deduplicate by URL
        seen_urls = set()
        unique_articles = []
        for article in articles:
            if article.url not in seen_urls:
                seen_urls.add(article.url)
                unique_articles.append(article)

        # v8.0.8: Filter out irrelevant articles (non-healthcare noise)
        unique_articles = self._filter_irrelevant_articles(
            unique_articles, company_name, real_name=real_name, website=website
        )

        # v8.0.5: AI-powered sentiment + event_type classification (both in one call)
        self._analyze_sentiment_batch(unique_articles)

        # v5.0.7: Tag articles with competitive dimensions
        if self.tag_dimensions:
            self._tag_dimensions_batch(unique_articles, company_name)

        # Build digest
        sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}
        for article in unique_articles:
            sentiment_counts[article.sentiment] += 1

        major_events = [a for a in unique_articles if a.is_major_event]

        return NewsDigest(
            company_name=company_name,
            articles=unique_articles,  # Include ALL articles
            total_count=len(unique_articles),
            sentiment_breakdown=sentiment_counts,
            major_events=major_events,  # Include ALL major events
            fetched_at=datetime.utcnow().isoformat()
        )
    
    def _fetch_google_news(self, company_name: str) -> List[NewsArticle]:
        """
        Fetch news from Google News.

        v5.0.3: Uses pygooglenews library when available for enhanced features.
        Falls back to raw RSS parsing if pygooglenews not installed.
        """
        # Try enhanced pygooglenews first (v5.0.3)
        if self.use_pygooglenews and self.google_news_client:
            return self._fetch_google_news_enhanced(company_name)

        # Fallback to raw RSS parsing
        return self._fetch_google_news_rss(company_name)

    def _fetch_google_news_enhanced(self, company_name: str) -> List[NewsArticle]:
        """
        Fetch news using pygooglenews library.

        v5.0.3: Enhanced Google News with better date filtering, geo targeting, and parsing.
        """
        articles = []

        try:
            # Search for company news
            search_result = self.google_news_client.search(f'"{company_name}"')

            if search_result and 'entries' in search_result:
                for entry in search_result['entries']:
                    title_text = entry.get('title', '')
                    source_name = entry.get('source', {}).get('title', 'Google News')

                    # pygooglenews provides cleaner title without source suffix
                    articles.append(NewsArticle(
                        title=title_text,
                        url=entry.get('link', ''),
                        source=source_name,
                        published_date=entry.get('published', ''),
                        snippet=entry.get('summary', ''),
                        sentiment="neutral",
                        is_major_event=False,
                        event_type=None
                    ))

        except Exception as e:
            logger.warning(f"pygooglenews fetch failed: {e}, falling back to RSS")
            # Fallback to RSS if pygooglenews fails
            return self._fetch_google_news_rss(company_name)

        return articles

    def _fetch_google_news_rss(self, company_name: str) -> List[NewsArticle]:
        """Fetch news from Google News RSS (fallback method)."""
        articles = []

        try:
            # Search by company name only (most general)
            query = urllib.parse.quote(f'"{company_name}"')
            url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

            with urllib.request.urlopen(url, timeout=8) as response:
                content = response.read()

            root = ET.fromstring(content)

            # Get ALL matching articles (no limit)
            for item in root.findall(".//item"):
                title = item.find("title")
                link = item.find("link")
                pub_date = item.find("pubDate")
                source = item.find("source")

                if title is not None and link is not None:
                    # Extract source from title (Google News format: "Title - Source")
                    title_text = title.text or ""
                    source_name = source.text if source is not None else "Google News"

                    if " - " in title_text:
                        parts = title_text.rsplit(" - ", 1)
                        title_text = parts[0]
                        if len(parts) > 1:
                            source_name = parts[1]

                    articles.append(NewsArticle(
                        title=title_text,
                        url=link.text or "",
                        source=source_name,
                        published_date=pub_date.text if pub_date is not None else "",
                        snippet="",
                        sentiment="neutral",
                        is_major_event=False,
                        event_type=None
                    ))

        except Exception as e:
            logger.warning(f"Google News RSS fetch failed: {e}")

        return articles
    
    def _fetch_newsapi(self, company_name: str, days: int) -> List[NewsArticle]:
        """Fetch news from NewsAPI.org."""
        articles = []
        
        if not self.newsapi_key:
            return articles
        
        try:
            from_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
            # Search by company name only (most general)
            query = urllib.parse.quote(f'"{company_name}"')
            url = f"https://newsapi.org/v2/everything?q={query}&from={from_date}&sortBy=publishedAt&pageSize=100&apiKey={self.newsapi_key}"
            
            with urllib.request.urlopen(url, timeout=8) as response:
                data = json.loads(response.read())
            
            # Get ALL matching articles (up to 100 per source)
            for item in data.get("articles", []):
                articles.append(NewsArticle(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    source=item.get("source", {}).get("name", "NewsAPI"),
                    published_date=item.get("publishedAt", ""),
                    snippet=item.get("description", ""),
                    sentiment="neutral",
                    is_major_event=False,
                    event_type=None
                ))
                
        except Exception as e:
            logger.warning(f"NewsAPI fetch failed: {e}")
        
        return articles
    
    def _fetch_bing_news(self, company_name: str) -> List[NewsArticle]:
        """Fetch news from Bing News API."""
        articles = []
        
        if not self.bing_news_key:
            return articles
        
        try:
            # Search by company name only (most general)
            query = urllib.parse.quote(f'"{company_name}"')
            url = f"https://api.bing.microsoft.com/v7.0/news/search?q={query}&count=100"
            
            req = urllib.request.Request(url)
            req.add_header("Ocp-Apim-Subscription-Key", self.bing_news_key)
            
            with urllib.request.urlopen(req, timeout=8) as response:
                data = json.loads(response.read())
            
            # Get ALL matching articles
            for item in data.get("value", []):
                articles.append(NewsArticle(
                    title=item.get("name", ""),
                    url=item.get("url", ""),
                    source=item.get("provider", [{}])[0].get("name", "Bing News"),
                    published_date=item.get("datePublished", ""),
                    snippet=item.get("description", ""),
                    sentiment="neutral",
                    is_major_event=False,
                    event_type=None
                ))
                
        except Exception as e:
            logger.warning(f"Bing News fetch failed: {e}")

        return articles

    # ============== Government Data Sources (v5.0.3) ==============

    def _fetch_sec_filings(self, company_name: str, days: int = 90) -> List[NewsArticle]:
        """
        Fetch SEC EDGAR filings as news articles.

        v5.0.3: Government data source - free, no API key needed.
        """
        articles = []

        if not self.sec_scraper:
            return articles

        try:
            # Get SEC filings formatted as news articles
            sec_articles = self.sec_scraper.get_news_articles(company_name, days_back=days)

            for item in sec_articles:
                articles.append(NewsArticle(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    source="SEC EDGAR",
                    published_date=item.get("published_at", ""),
                    snippet=item.get("snippet", ""),
                    sentiment=item.get("sentiment", "neutral"),
                    is_major_event=item.get("is_major_event", False),
                    event_type=item.get("event_type")
                ))

        except Exception as e:
            logger.warning(f"SEC EDGAR fetch failed: {e}")

        return articles

    def _fetch_patent_news(self, company_name: str) -> List[NewsArticle]:
        """
        Fetch USPTO patent filings as news articles.

        v5.0.3: Government data source - free, no API key needed.
        """
        articles = []

        if not self.patent_scraper:
            return articles

        try:
            # Get patent data
            patent_data = self.patent_scraper.get_patent_data(company_name)

            # Convert recent patent filings to news articles
            for patent in patent_data.recent_filings[:5]:  # Limit to recent 5
                title = f"{company_name} Files Patent: {patent.title}"
                snippet = f"Patent #{patent.patent_number} - {patent.technology_area}"

                articles.append(NewsArticle(
                    title=title,
                    url=patent.url,
                    source="USPTO Patents",
                    published_date=patent.filing_date,
                    snippet=snippet,
                    sentiment="positive",  # Patents are generally positive news
                    is_major_event=True,
                    event_type="product_launch"  # Patents often indicate new products/features
                ))

            # Also include recently granted patents
            granted = [p for p in patent_data.patents if p.status == "Granted"][:3]
            for patent in granted:
                title = f"{company_name} Granted Patent: {patent.title}"
                snippet = f"Patent #{patent.patent_number} granted - {patent.technology_area}"

                articles.append(NewsArticle(
                    title=title,
                    url=patent.url,
                    source="USPTO Patents",
                    published_date=patent.grant_date,
                    snippet=snippet,
                    sentiment="positive",
                    is_major_event=True,
                    event_type="product_launch"
                ))

        except Exception as e:
            logger.warning(f"USPTO patent fetch failed: {e}")

        return articles

    # ============== Free News APIs (v5.0.4 - Phase 3) ==============

    def _fetch_gnews(self, company_name: str) -> List[NewsArticle]:
        """
        Fetch news from GNews API.

        v5.0.4: 100 requests/day free tier.
        API docs: https://gnews.io/docs/v4

        Features:
        - 60,000+ sources
        - Historical to 6 years
        - Fast response times
        - Good for breaking news
        """
        articles = []

        if not self.gnews_api_key:
            return articles

        try:
            # GNews API endpoint
            query = urllib.parse.quote(f'"{company_name}"')
            url = f"https://gnews.io/api/v4/search?q={query}&lang=en&country=us&max=50&apikey={self.gnews_api_key}"

            with urllib.request.urlopen(url, timeout=8) as response:
                data = json.loads(response.read())

            for item in data.get("articles", []):
                articles.append(NewsArticle(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    source=item.get("source", {}).get("name", "GNews"),
                    published_date=item.get("publishedAt", ""),
                    snippet=item.get("description", ""),
                    sentiment="neutral",
                    is_major_event=False,
                    event_type=None
                ))

        except Exception as e:
            logger.warning(f"GNews API fetch failed: {e}")

        return articles

    def _fetch_mediastack(self, company_name: str) -> List[NewsArticle]:
        """
        Fetch news from MediaStack API.

        v5.0.4: 500 requests/month free tier.
        API docs: https://mediastack.com/documentation

        Features:
        - 7,500+ sources in 50 countries
        - 13 languages supported
        - Broad international coverage
        - Good for global competitor monitoring
        """
        articles = []

        if not self.mediastack_api_key:
            return articles

        try:
            # MediaStack API endpoint (note: free tier uses HTTP, not HTTPS)
            query = urllib.parse.quote(company_name)
            url = f"http://api.mediastack.com/v1/news?access_key={self.mediastack_api_key}&keywords={query}&languages=en&limit=50"

            with urllib.request.urlopen(url, timeout=8) as response:
                data = json.loads(response.read())

            for item in data.get("data", []):
                articles.append(NewsArticle(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    source=item.get("source", "MediaStack"),
                    published_date=item.get("published_at", ""),
                    snippet=item.get("description", ""),
                    sentiment="neutral",
                    is_major_event=False,
                    event_type=None
                ))

        except Exception as e:
            logger.warning(f"MediaStack API fetch failed: {e}")

        return articles

    def _fetch_newsdata(self, company_name: str) -> List[NewsArticle]:
        """
        Fetch news from NewsData.io API.

        v5.0.4: 200 requests/day free tier.
        API docs: https://newsdata.io/docs

        Features:
        - 89 languages supported
        - Crypto/tech/healthcare news specialty
        - 1M+ articles indexed weekly
        - Best for tech/healthcare news categorization
        """
        articles = []

        if not self.newsdata_api_key:
            return articles

        try:
            # NewsData.io API endpoint
            query = urllib.parse.quote(company_name)
            # Use health and technology category filters for better relevance
            url = f"https://newsdata.io/api/1/news?apikey={self.newsdata_api_key}&q={query}&language=en"

            with urllib.request.urlopen(url, timeout=8) as response:
                data = json.loads(response.read())

            for item in data.get("results", []):
                # NewsData.io provides category which we can use for event detection
                categories = item.get("category", [])
                event_type = None
                if "technology" in categories:
                    event_type = "product_launch"
                elif "business" in categories:
                    event_type = "financial"
                elif "health" in categories:
                    event_type = "expansion"

                articles.append(NewsArticle(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    source=item.get("source_id", "NewsData.io"),
                    published_date=item.get("pubDate", ""),
                    snippet=item.get("description", "") or item.get("content", "")[:200] if item.get("content") else "",
                    sentiment="neutral",
                    is_major_event=event_type is not None,
                    event_type=event_type
                ))

        except Exception as e:
            logger.warning(f"NewsData.io API fetch failed: {e}")

        return articles

    def _analyze_sentiment(self, text: str, snippet: str = "") -> str:
        """
        Analyze sentiment of text.

        v5.0.5: Uses ML-based sentiment when available, falls back to keywords.

        Args:
            text: Main text (usually headline)
            snippet: Optional snippet for additional context

        Returns:
            Sentiment label (positive, negative, neutral)
        """
        # Use ML sentiment if available (v5.0.5)
        if self.use_ml_sentiment and self.ml_sentiment_analyzer:
            try:
                result = self.ml_sentiment_analyzer.analyze_headline(text, snippet)
                return result.label
            except Exception as e:
                logger.warning(f"ML sentiment failed, using keywords: {e}")

        # Fallback to keyword-based
        return self._keyword_sentiment(text)

    def _keyword_sentiment(self, text: str) -> str:
        """Keyword-based sentiment analysis fallback."""
        text_lower = text.lower()

        positive_count = sum(1 for word in self.POSITIVE_KEYWORDS if word in text_lower)
        negative_count = sum(1 for word in self.NEGATIVE_KEYWORDS if word in text_lower)

        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"

    def _ai_classify_batch(self, articles: List[NewsArticle]) -> None:
        """
        Classify sentiment AND event_type for articles using AI (Gemini).

        Sends batches of up to 25 headlines to the AI router for accurate
        classification. Falls back to keyword-based if AI is unavailable.

        Args:
            articles: List of NewsArticle objects to classify (modified in place)
        """
        if not articles:
            return

        try:
            import asyncio as _asyncio
            from ai_router import get_ai_router, TaskType

            router = get_ai_router()

            # Process in batches of 25
            batch_size = 25
            for i in range(0, len(articles), batch_size):
                batch = articles[i:i + batch_size]
                headlines = []
                for idx, a in enumerate(batch):
                    headlines.append(f"{idx}. {a.title}")

                prompt = (
                    "Classify each news headline below. For EACH headline, provide:\n"
                    "- sentiment: exactly one of \"positive\", \"negative\", or \"neutral\"\n"
                    "- event_type: exactly one of \"funding\", \"acquisition\", \"product_launch\", "
                    "\"partnership\", \"leadership\", \"financial\", \"legal\", \"expansion\", or \"general\"\n\n"
                    "Rules:\n"
                    "- funding: fundraising rounds, investment, venture capital, Series A/B/C\n"
                    "- acquisition: M&A, buyouts, mergers, company purchases\n"
                    "- product_launch: new products, features, releases, platform launches\n"
                    "- partnership: alliances, collaborations, integrations, joint ventures\n"
                    "- leadership: executive hires, appointments, departures, board changes\n"
                    "- financial: earnings, revenue, IPO, stock, quarterly results, valuation\n"
                    "- legal: lawsuits, regulatory, compliance, FDA, patents, legal disputes\n"
                    "- expansion: new markets, office openings, geographic growth, headcount growth\n"
                    "- general: anything that doesn't fit the above categories\n\n"
                    "- positive: good news for the company (growth, wins, awards, strong results)\n"
                    "- negative: bad news (layoffs, lawsuits, losses, breaches, failures, declines)\n"
                    "- neutral: factual reporting without clear positive/negative framing\n\n"
                    "Respond with a JSON array of objects, one per headline, in the same order.\n"
                    "Example: [{\"sentiment\":\"positive\",\"event_type\":\"funding\"}, ...]\n\n"
                    "Headlines:\n" + "\n".join(headlines)
                )

                try:
                    loop = _asyncio.new_event_loop()
                    try:
                        result = loop.run_until_complete(
                            router.generate_json(
                                prompt=prompt,
                                task_type=TaskType.CLASSIFICATION,
                                system_prompt="You are a news classification expert. Respond ONLY with valid JSON.",
                                max_tokens=2048,
                                temperature=0.1
                            )
                        )
                    finally:
                        loop.close()

                    classifications = result.get("response_json", {})
                    if isinstance(classifications, dict) and "raw" not in classifications:
                        # Handle case where response is wrapped in a key
                        for key in classifications:
                            if isinstance(classifications[key], list):
                                classifications = classifications[key]
                                break
                    if isinstance(classifications, list) and len(classifications) == len(batch):
                        valid_sentiments = {"positive", "negative", "neutral"}
                        valid_events = {
                            "funding", "acquisition", "product_launch", "partnership",
                            "leadership", "financial", "legal", "expansion", "general"
                        }
                        for article, cls in zip(batch, classifications):
                            if isinstance(cls, dict):
                                s = cls.get("sentiment", "").lower()
                                e = cls.get("event_type", "").lower()
                                if s in valid_sentiments:
                                    article.sentiment = s
                                if e in valid_events:
                                    article.event_type = e
                                    article.is_major_event = e != "general"
                    else:
                        logger.warning(
                            f"AI classify: expected {len(batch)} results, got "
                            f"{len(classifications) if isinstance(classifications, list) else 'non-list'}"
                        )
                        self._keyword_classify_batch(batch)

                except Exception as e:
                    logger.warning(f"AI batch classification failed for batch {i // batch_size}: {e}")
                    self._keyword_classify_batch(batch)

        except ImportError:
            logger.warning("AI router not available, using keyword classification")
            self._keyword_classify_batch(articles)
        except Exception as e:
            logger.warning(f"AI classification setup failed: {e}")
            self._keyword_classify_batch(articles)

    def _keyword_classify_batch(self, articles: List[NewsArticle]) -> None:
        """Keyword-based fallback for sentiment + event_type classification."""
        for article in articles:
            if article.source not in ["SEC EDGAR", "USPTO Patents"]:
                article.sentiment = self._keyword_sentiment(article.title + " " + article.snippet)
            if article.event_type is None:
                article.event_type = self._detect_event_type(article.title + " " + article.snippet)
                article.is_major_event = article.event_type is not None

    def _analyze_sentiment_batch(self, articles: List[NewsArticle]) -> None:
        """
        Analyze sentiment and event_type for multiple articles using AI.

        v8.0.5: Uses AI router (Gemini) for accurate classification.
        Falls back to keyword-based if AI is unavailable.

        Args:
            articles: List of NewsArticle objects to analyze (modified in place)
        """
        if not articles:
            return

        # Use AI classification for both sentiment AND event_type
        self._ai_classify_batch(articles)

        # Ensure all articles have event_type set (fallback for any missed)
        for article in articles:
            if article.event_type is None:
                article.event_type = self._detect_event_type(article.title + " " + article.snippet)
            article.is_major_event = article.event_type is not None and article.event_type != "general"
    
    # ============== Relevance Filter (v8.0.8) ==============

    HEALTHCARE_KEYWORDS = {
        "healthcare", "health", "medical", "patient", "clinical", "hospital",
        "ehr", "telehealth", "doctor", "nurse", "pharmacy", "hipaa", "wellness",
        "healthtech", "medtech", "biotech", "pharma", "therapeutic", "diagnosis",
        "treatment", "care", "provider", "payer", "insurance", "cms", "fda",
        "hipaa", "interoperability", "emr", "revenue cycle", "population health",
        "credentialing", "certification", "compliance", "regulatory",
    }

    def _filter_irrelevant_articles(
        self, articles: List[NewsArticle], company_name: str,
        real_name: Optional[str] = None, website: Optional[str] = None,
    ) -> List[NewsArticle]:
        """
        Filter out articles that are not relevant to the healthcare competitor.

        Logic varies by name specificity:
        - Multi-word names (e.g., "Change Healthcare"): keep if name OR healthcare kw
        - Single-word generic names (e.g., "Access", "Mend"): REQUIRE healthcare kw
          AND the company domain/brand to appear (because healthcare keywords alone
          catch articles about "healthcare access" the concept, not Access the company)

        Args:
            articles: List of NewsArticle objects
            company_name: Search term used (may include disambiguation)
            real_name: Actual competitor name (e.g., "Access") if different from search term
            website: Competitor's website URL for domain matching

        Returns:
            Filtered list with irrelevant articles removed
        """
        if not articles:
            return articles

        # Use real_name if provided, otherwise try to extract from search term
        if real_name:
            raw_name = real_name.strip()
        else:
            raw_name = company_name.strip('"').strip()

        name_words = [
            w.lower() for w in raw_name.split()
            if len(w) > 2 and w.lower() not in {
                "the", "and", "inc", "llc", "ltd", "corp", "co", "or",
            }
        ]
        name_lower = raw_name.lower()

        # Words that are too common to match individually
        COMMON_WORDS = {
            "get", "well", "set", "change", "care", "one", "first", "best",
            "next", "open", "clear", "smart", "true", "pure", "prime",
            "lead", "core", "base", "way", "rise", "bold", "vital",
            "health", "healthcare", "medical", "med",
        }
        # Significant words (not common English) for individual matching
        significant_words = [
            w for w in name_words if w not in COMMON_WORDS
        ]

        # Single-word names are ambiguous — "Access", "Mend", "Tonic", "Creo"
        # are common English words. Require stronger matching for these.
        # Also treat names made entirely of common words as generic
        # (e.g., "Get Well" = both words common, "Change Healthcare" = both common)
        has_only_common_words = len(significant_words) == 0 and len(name_words) > 0
        is_generic_name = (len(name_words) <= 1 and len(raw_name) < 15) or has_only_common_words

        # Extract domain name for generic-name matching (e.g., "accessefm" from accessefm.com)
        domain_name = ""
        if website:
            try:
                from urllib.parse import urlparse
                netloc = urlparse(website).netloc.replace('www.', '')
                domain_name = netloc.split('.')[0].lower() if netloc else ''
            except Exception:
                pass

        filtered = []
        removed = 0
        for article in articles:
            title_lower = (article.title or "").lower()
            snippet_lower = (article.snippet or "").lower()
            combined = title_lower + " " + snippet_lower

            # Check 1: Does the article mention the company domain?
            domain_match = domain_name and (
                domain_name in title_lower or domain_name in snippet_lower
            )

            # Check 2: Does the article mention healthcare keywords?
            healthcare_match = any(
                kw in combined for kw in self.HEALTHCARE_KEYWORDS
            )

            # Check 3: Does the title contain the company name?
            # Prefer full phrase match; fall back to significant-word matching
            full_phrase_match = name_lower in title_lower or name_lower in snippet_lower
            significant_word_match = len(significant_words) > 0 and any(
                w in title_lower for w in significant_words
            )
            name_match = full_phrase_match or significant_word_match

            if is_generic_name:
                # Generic names: require domain match, OR healthcare + name as
                # a standalone brand (not just a common word in healthcare context)
                if domain_match:
                    filtered.append(article)
                elif healthcare_match and name_match and domain_name and domain_name != name_lower:
                    # Healthcare article mentions the name - but for very common
                    # words like "access", "care", this still catches false positives.
                    # Only keep if domain also appears somewhere in the article.
                    removed += 1
                elif healthcare_match and not domain_name:
                    # No domain to check - fall back to healthcare match
                    filtered.append(article)
                else:
                    removed += 1
            else:
                # Multi-word / specific names: name OR healthcare is enough
                if name_match or healthcare_match:
                    filtered.append(article)
                else:
                    removed += 1

        if removed > 0:
            logger.info(
                f"[Relevance Filter] Removed {removed}/{len(articles)} "
                f"irrelevant articles for '{raw_name}'"
                f"{' (domain: ' + domain_name + ')' if domain_name else ''}"
            )

        return filtered

    def _detect_event_type(self, text: str) -> Optional[str]:
        """Detect if text indicates a major event."""
        text_lower = text.lower()

        for event_type, keywords in self.EVENT_KEYWORDS.items():
            if any(keyword in text_lower for keyword in keywords):
                return event_type

        return None

    def _tag_dimensions_batch(self, articles: List[NewsArticle], company_name: str) -> None:
        """
        Tag articles with competitive dimensions.

        v5.0.7: Uses DimensionAnalyzer to classify articles by dimension.

        Args:
            articles: List of NewsArticle objects to tag (modified in place)
            company_name: Name of the competitor
        """
        if not self.dimension_analyzer:
            return

        for article in articles:
            try:
                # Classify which dimensions this article relates to
                dimension_matches = self.dimension_analyzer.classify_article_dimension(
                    title=article.title,
                    snippet=article.snippet,
                    competitor_name=company_name
                )

                # Convert to list of dicts with dimension info
                if dimension_matches:
                    article.dimension_tags = [
                        {
                            "dimension_id": dim_id,
                            "confidence": confidence,
                            "sentiment": article.sentiment
                        }
                        for dim_id, confidence in dimension_matches
                    ]
                else:
                    article.dimension_tags = []

            except Exception as e:
                logger.warning(f"Dimension tagging failed for article: {e}")
                article.dimension_tags = []

    def store_dimension_tags(
        self,
        articles: List[NewsArticle],
        competitor_id: int,
        db_session
    ) -> int:
        """
        Store dimension tags for articles in the database.

        v5.0.7: Persists dimension tags to DimensionNewsTag table.

        Args:
            articles: List of NewsArticle objects with dimension_tags
            competitor_id: Database ID of the competitor
            db_session: SQLAlchemy database session

        Returns:
            Number of tags stored
        """
        from database import DimensionNewsTag
        from datetime import datetime

        tags_stored = 0

        for article in articles:
            if not article.dimension_tags:
                continue

            for tag in article.dimension_tags:
                try:
                    # Check if this article-dimension combo already exists
                    existing = db_session.query(DimensionNewsTag).filter(
                        DimensionNewsTag.news_url == article.url,
                        DimensionNewsTag.dimension_id == tag["dimension_id"]
                    ).first()

                    if existing:
                        # Update existing tag
                        existing.relevance_score = tag["confidence"]
                        existing.sentiment = tag.get("sentiment")
                        existing.tagged_at = datetime.utcnow()
                    else:
                        # Create new tag
                        new_tag = DimensionNewsTag(
                            news_url=article.url,
                            news_title=article.title[:500] if article.title else "",
                            news_snippet=article.snippet[:1000] if article.snippet else None,
                            competitor_id=competitor_id,
                            dimension_id=tag["dimension_id"],
                            relevance_score=tag["confidence"],
                            sentiment=tag.get("sentiment"),
                            tagged_at=datetime.utcnow(),
                            tagged_by="ai"
                        )
                        db_session.add(new_tag)
                        tags_stored += 1

                except Exception as e:
                    logger.warning(f"Error storing dimension tag: {e}")
                    continue

        try:
            db_session.commit()
        except Exception as e:
            logger.error(f"Error committing dimension tags: {e}")
            db_session.rollback()

        return tags_stored

    def get_news_summary(self, company_name: str) -> Dict[str, Any]:
        """Get a summary of news for a company."""
        digest = self.fetch_news(company_name)
        
        return {
            "company": company_name,
            "total_articles": digest.total_count,
            "sentiment": digest.sentiment_breakdown,
            "major_events": [
                {
                    "type": a.event_type,
                    "title": a.title,
                    "url": a.url,
                    "date": a.published_date
                }
                for a in digest.major_events
            ],
            "recent_headlines": [a.title for a in digest.articles[:5]],
            "fetched_at": digest.fetched_at
        }


# API convenience functions
def fetch_competitor_news(
    company_name: str,
    days: int = 90,
    tag_dimensions: bool = True
) -> Dict[str, Any]:
    """
    Fetch news for a competitor.

    Args:
        company_name: Name of the company
        days: Number of days to look back
        tag_dimensions: Whether to tag articles with competitive dimensions (v5.0.7)

    Returns:
        Dict with articles, sentiment, and dimension tags
    """
    monitor = NewsMonitor(tag_dimensions=tag_dimensions)
    digest = monitor.fetch_news(company_name, days)

    # v5.0.7: Count dimension tags across articles
    dimension_counts = {}
    for article in digest.articles:
        if article.dimension_tags:
            for tag in article.dimension_tags:
                dim_id = tag["dimension_id"]
                dimension_counts[dim_id] = dimension_counts.get(dim_id, 0) + 1

    return {
        "company": digest.company_name,
        "articles": [asdict(a) for a in digest.articles],
        "total_count": digest.total_count,
        "sentiment_breakdown": digest.sentiment_breakdown,
        "major_events": [asdict(a) for a in digest.major_events],
        "dimension_breakdown": dimension_counts,  # v5.0.7
        "fetched_at": digest.fetched_at
    }


def check_for_alerts(company_name: str) -> List[Dict[str, Any]]:
    """Check for news that should trigger alerts."""
    monitor = NewsMonitor()
    digest = monitor.fetch_news(company_name, days=1)
    
    alerts = []
    for event in digest.major_events:
        alert_level = "High" if event.event_type in ["funding", "acquisition"] else "Medium"
        alerts.append({
            "company": company_name,
            "event_type": event.event_type,
            "title": event.title,
            "url": event.url,
            "alert_level": alert_level,
            "detected_at": datetime.utcnow().isoformat()
        })
    
    return alerts


# ============== Progress & Circuit Breaker Accessors (v5.1.0) ==============

def get_news_fetch_progress(progress_key: str) -> Optional[Dict[str, Any]]:
    """Get the current progress of an async news fetch operation."""
    return _news_fetch_progress.get(progress_key)


def clear_news_fetch_progress(progress_key: str) -> None:
    """Clear stored progress for a completed fetch operation."""
    _news_fetch_progress.pop(progress_key, None)


def get_circuit_breaker_status() -> Dict[str, Dict[str, Any]]:
    """Get current circuit breaker state for all tracked sources."""
    return dict(_circuit_breaker)


if __name__ == "__main__":
    # Test with sample company
    logger.info("Testing News Monitor...")
    result = fetch_competitor_news("Phreesia")
    logger.info(json.dumps(result, indent=2, default=str))
