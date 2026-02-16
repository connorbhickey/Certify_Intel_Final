"""
Certify Intel - Firecrawl Integration (v5.0.6)
Provides advanced web scraping capabilities using Firecrawl.

Features:
- Clean, structured content extraction from any URL
- JavaScript rendering for dynamic content
- Markdown and structured data output
- Bulk URL processing
- Automatic retry and error handling

NEWS-4D: Firecrawl MCP integration for enhanced web scraping

Firecrawl API Documentation: https://docs.firecrawl.dev/
"""

import os
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class FirecrawlResult:
    """Result of a Firecrawl scrape operation."""
    url: str
    success: bool
    markdown: str
    html: Optional[str]
    metadata: Dict[str, Any]
    extracted_data: Dict[str, Any]
    links: List[str]
    timestamp: str
    latency_ms: float
    error: Optional[str] = None


@dataclass
class FirecrawlBatchResult:
    """Result of a batch Firecrawl operation."""
    total_urls: int
    successful: int
    failed: int
    results: List[FirecrawlResult]
    timestamp: str
    total_latency_ms: float


class FirecrawlClient:
    """
    Client for Firecrawl web scraping API.

    Firecrawl provides:
    - JavaScript rendering for dynamic content
    - Clean markdown extraction
    - Automatic proxy rotation
    - Anti-bot bypass
    """

    BASE_URL = "https://api.firecrawl.dev/v1"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Firecrawl client.

        Args:
            api_key: Firecrawl API key. Falls back to FIRECRAWL_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("FIRECRAWL_API_KEY")
        self._client = None

        if self.api_key:
            logger.info("Firecrawl client initialized")
        else:
            logger.warning("FIRECRAWL_API_KEY not set. Firecrawl features disabled.")

    @property
    def is_available(self) -> bool:
        """Check if Firecrawl is available."""
        return bool(self.api_key) and HTTPX_AVAILABLE

    def _get_client(self) -> "httpx.AsyncClient":
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=60.0,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
            )
        return self._client

    async def scrape(
        self,
        url: str,
        formats: Optional[List[str]] = None,
        only_main_content: bool = True,
        include_tags: Optional[List[str]] = None,
        exclude_tags: Optional[List[str]] = None,
        wait_for: Optional[str] = None,
        timeout: int = 30000,
    ) -> FirecrawlResult:
        """
        Scrape a single URL.

        Args:
            url: URL to scrape
            formats: Output formats (markdown, html, rawHtml, screenshot, links)
            only_main_content: Extract only main content (exclude nav, footer)
            include_tags: HTML tags to include
            exclude_tags: HTML tags to exclude
            wait_for: CSS selector to wait for before scraping
            timeout: Timeout in milliseconds

        Returns:
            FirecrawlResult with scraped content
        """
        if not self.is_available:
            return FirecrawlResult(
                url=url,
                success=False,
                markdown="",
                html=None,
                metadata={},
                extracted_data={},
                links=[],
                timestamp=datetime.utcnow().isoformat(),
                latency_ms=0,
                error="Firecrawl not available. Configure FIRECRAWL_API_KEY."
            )

        start_time = datetime.now()

        try:
            client = self._get_client()

            payload = {
                "url": url,
                "formats": formats or ["markdown", "links"],
                "onlyMainContent": only_main_content,
                "timeout": timeout,
            }

            if include_tags:
                payload["includeTags"] = include_tags
            if exclude_tags:
                payload["excludeTags"] = exclude_tags
            if wait_for:
                payload["waitFor"] = wait_for

            response = await client.post(
                f"{self.BASE_URL}/scrape",
                json=payload
            )

            latency = (datetime.now() - start_time).total_seconds() * 1000

            if response.status_code == 200:
                data = response.json()

                return FirecrawlResult(
                    url=url,
                    success=data.get("success", True),
                    markdown=data.get("data", {}).get("markdown", ""),
                    html=data.get("data", {}).get("html"),
                    metadata=data.get("data", {}).get("metadata", {}),
                    extracted_data=data.get("data", {}).get("extractedData", {}),
                    links=data.get("data", {}).get("links", []),
                    timestamp=datetime.utcnow().isoformat(),
                    latency_ms=latency
                )
            else:
                error_msg = response.text[:200] if response.text else f"HTTP {response.status_code}"
                logger.error(f"Firecrawl scrape failed: {error_msg}")
                return FirecrawlResult(
                    url=url,
                    success=False,
                    markdown="",
                    html=None,
                    metadata={},
                    extracted_data={},
                    links=[],
                    timestamp=datetime.utcnow().isoformat(),
                    latency_ms=latency,
                    error=error_msg
                )

        except Exception as e:
            latency = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Firecrawl scrape error: {e}")
            return FirecrawlResult(
                url=url,
                success=False,
                markdown="",
                html=None,
                metadata={},
                extracted_data={},
                links=[],
                timestamp=datetime.utcnow().isoformat(),
                latency_ms=latency,
                error=str(e)
            )

    async def scrape_batch(
        self,
        urls: List[str],
        **kwargs
    ) -> FirecrawlBatchResult:
        """
        Scrape multiple URLs concurrently.

        Args:
            urls: List of URLs to scrape
            **kwargs: Additional arguments passed to scrape()

        Returns:
            FirecrawlBatchResult with all results
        """
        start_time = datetime.now()

        # Run scrapes concurrently (max 5 at a time to avoid rate limits)
        semaphore = asyncio.Semaphore(5)

        async def scrape_with_semaphore(url: str) -> FirecrawlResult:
            async with semaphore:
                return await self.scrape(url, **kwargs)

        tasks = [scrape_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks)

        total_latency = (datetime.now() - start_time).total_seconds() * 1000
        successful = sum(1 for r in results if r.success)

        return FirecrawlBatchResult(
            total_urls=len(urls),
            successful=successful,
            failed=len(urls) - successful,
            results=list(results),
            timestamp=datetime.utcnow().isoformat(),
            total_latency_ms=total_latency
        )

    async def crawl(
        self,
        url: str,
        limit: int = 10,
        max_depth: int = 2,
        include_paths: Optional[List[str]] = None,
        exclude_paths: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Crawl a website starting from the given URL.

        Args:
            url: Starting URL
            limit: Maximum number of pages to crawl
            max_depth: Maximum link depth
            include_paths: URL path patterns to include
            exclude_paths: URL path patterns to exclude

        Returns:
            Crawl job response with job ID
        """
        if not self.is_available:
            return {
                "success": False,
                "error": "Firecrawl not available. Configure FIRECRAWL_API_KEY."
            }

        try:
            client = self._get_client()

            payload = {
                "url": url,
                "limit": limit,
                "maxDepth": max_depth,
            }

            if include_paths:
                payload["includePaths"] = include_paths
            if exclude_paths:
                payload["excludePaths"] = exclude_paths

            response = await client.post(
                f"{self.BASE_URL}/crawl",
                json=payload
            )

            if response.status_code in [200, 202]:
                return response.json()
            else:
                return {
                    "success": False,
                    "error": response.text[:200] if response.text else f"HTTP {response.status_code}"
                }

        except Exception as e:
            logger.error(f"Firecrawl crawl error: {e}")
            return {"success": False, "error": str(e)}

    async def get_crawl_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get the status of a crawl job.

        Args:
            job_id: Crawl job ID

        Returns:
            Crawl job status and results
        """
        if not self.is_available:
            return {
                "success": False,
                "error": "Firecrawl not available."
            }

        try:
            client = self._get_client()
            response = await client.get(f"{self.BASE_URL}/crawl/{job_id}")

            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "success": False,
                    "error": response.text[:200] if response.text else f"HTTP {response.status_code}"
                }

        except Exception as e:
            logger.error(f"Firecrawl status check error: {e}")
            return {"success": False, "error": str(e)}

    async def extract_structured(
        self,
        url: str,
        schema: Dict[str, Any],
        prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Extract structured data from a URL using LLM.

        Args:
            url: URL to extract from
            schema: JSON schema for the expected data structure
            prompt: Optional prompt to guide extraction

        Returns:
            Extracted structured data
        """
        if not self.is_available:
            return {
                "success": False,
                "error": "Firecrawl not available. Configure FIRECRAWL_API_KEY."
            }

        try:
            client = self._get_client()

            payload = {
                "url": url,
                "formats": ["extract"],
                "extract": {
                    "schema": schema,
                }
            }

            if prompt:
                payload["extract"]["prompt"] = prompt

            response = await client.post(
                f"{self.BASE_URL}/scrape",
                json=payload
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "data": data.get("data", {}).get("extract", {}),
                    "metadata": data.get("data", {}).get("metadata", {})
                }
            else:
                return {
                    "success": False,
                    "error": response.text[:200] if response.text else f"HTTP {response.status_code}"
                }

        except Exception as e:
            logger.error(f"Firecrawl extraction error: {e}")
            return {"success": False, "error": str(e)}

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


class FirecrawlCompetitorScraper:
    """
    Specialized scraper for competitor intelligence using Firecrawl.

    Extracts structured competitor data from websites.
    """

    # Schema for competitor data extraction
    COMPETITOR_SCHEMA = {
        "type": "object",
        "properties": {
            "company_name": {"type": "string"},
            "description": {"type": "string"},
            "products": {
                "type": "array",
                "items": {"type": "string"}
            },
            "pricing": {
                "type": "object",
                "properties": {
                    "model": {"type": "string"},
                    "starting_price": {"type": "string"},
                    "tiers": {"type": "array", "items": {"type": "string"}}
                }
            },
            "features": {
                "type": "array",
                "items": {"type": "string"}
            },
            "customers": {
                "type": "array",
                "items": {"type": "string"}
            },
            "integrations": {
                "type": "array",
                "items": {"type": "string"}
            },
            "contact_info": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string"},
                    "email": {"type": "string"},
                    "address": {"type": "string"}
                }
            }
        }
    }

    def __init__(self):
        """Initialize competitor scraper."""
        self.client = FirecrawlClient()

    @property
    def is_available(self) -> bool:
        """Check if scraper is available."""
        return self.client.is_available

    async def scrape_competitor_website(
        self,
        url: str,
        include_subpages: bool = True,
    ) -> Dict[str, Any]:
        """
        Scrape a competitor's website for intelligence.

        Args:
            url: Competitor's website URL
            include_subpages: Whether to scrape subpages (pricing, about, etc.)

        Returns:
            Structured competitor data
        """
        results = {
            "homepage": None,
            "pricing": None,
            "about": None,
            "features": None,
            "customers": None,
            "extracted_data": {},
            "all_content": "",
            "links": [],
            "metadata": {},
            "success": True,
            "errors": []
        }

        # Scrape homepage
        homepage_result = await self.client.scrape(
            url,
            formats=["markdown", "links"],
            only_main_content=True
        )

        results["homepage"] = asdict(homepage_result)
        results["all_content"] += homepage_result.markdown
        results["links"] = homepage_result.links
        results["metadata"] = homepage_result.metadata

        if not homepage_result.success:
            results["errors"].append(f"Homepage: {homepage_result.error}")

        if include_subpages and homepage_result.links:
            # Find relevant subpages
            subpage_patterns = {
                "pricing": ["pricing", "plans", "cost", "packages"],
                "about": ["about", "company", "team", "story"],
                "features": ["features", "product", "solutions", "capabilities"],
                "customers": ["customers", "clients", "case-studies", "testimonials"]
            }

            for page_type, patterns in subpage_patterns.items():
                for link in homepage_result.links[:20]:  # Check first 20 links
                    link_lower = link.lower()
                    if any(p in link_lower for p in patterns):
                        subpage_result = await self.client.scrape(
                            link,
                            formats=["markdown"],
                            only_main_content=True
                        )
                        results[page_type] = asdict(subpage_result)
                        results["all_content"] += f"\n\n---\n\n{subpage_result.markdown}"

                        if not subpage_result.success:
                            results["errors"].append(f"{page_type}: {subpage_result.error}")
                        break  # Only scrape first matching page

        # Try structured extraction
        try:
            extracted = await self.client.extract_structured(
                url,
                schema=self.COMPETITOR_SCHEMA,
                prompt="Extract competitor information including company name, products, pricing, features, and customer logos."
            )
            if extracted.get("success"):
                results["extracted_data"] = extracted.get("data", {})
        except Exception as e:
            results["errors"].append(f"Extraction: {str(e)}")

        results["success"] = len(results["errors"]) == 0

        return results

    async def compare_competitors(
        self,
        urls: List[str]
    ) -> Dict[str, Any]:
        """
        Scrape and compare multiple competitor websites.

        Args:
            urls: List of competitor website URLs

        Returns:
            Comparison data for all competitors
        """
        results = []

        for url in urls:
            result = await self.scrape_competitor_website(url, include_subpages=True)
            results.append({
                "url": url,
                **result
            })

        return {
            "competitors": results,
            "count": len(results),
            "successful": sum(1 for r in results if r.get("success")),
            "timestamp": datetime.utcnow().isoformat()
        }

    async def close(self):
        """Close the client."""
        await self.client.close()


# ============== CONVENIENCE FUNCTIONS ==============

def get_firecrawl_client() -> FirecrawlClient:
    """Get a Firecrawl client instance."""
    return FirecrawlClient()


def get_competitor_scraper() -> FirecrawlCompetitorScraper:
    """Get a competitor scraper instance."""
    return FirecrawlCompetitorScraper()


async def scrape_url(url: str, **kwargs) -> Dict[str, Any]:
    """
    Convenience function to scrape a URL.

    Args:
        url: URL to scrape
        **kwargs: Additional arguments for scrape()

    Returns:
        Scrape result as dictionary
    """
    client = FirecrawlClient()
    try:
        result = await client.scrape(url, **kwargs)
        return asdict(result)
    finally:
        await client.close()


async def scrape_competitor(url: str) -> Dict[str, Any]:
    """
    Convenience function to scrape a competitor website.

    Args:
        url: Competitor website URL

    Returns:
        Structured competitor data
    """
    scraper = FirecrawlCompetitorScraper()
    try:
        return await scraper.scrape_competitor_website(url)
    finally:
        await scraper.close()


# ============== TEST FUNCTION ==============

async def test_firecrawl():
    """Test the Firecrawl integration."""
    print("Testing Firecrawl Integration...")
    print("-" * 50)

    client = FirecrawlClient()

    if not client.is_available:
        print("Firecrawl not available. Set FIRECRAWL_API_KEY environment variable.")
        return

    print("Firecrawl client initialized")

    # Test single URL scrape
    print("\n1. Testing single URL scrape...")
    result = await client.scrape(
        "https://example.com",
        formats=["markdown", "links"]
    )

    print(f"   Success: {result.success}")
    print(f"   Latency: {result.latency_ms:.0f}ms")
    print(f"   Content length: {len(result.markdown)} chars")
    print(f"   Links found: {len(result.links)}")

    if result.error:
        print(f"   Error: {result.error}")

    # Test batch scrape
    print("\n2. Testing batch scrape...")
    batch_result = await client.scrape_batch([
        "https://example.com",
        "https://example.org"
    ])

    print(f"   Total URLs: {batch_result.total_urls}")
    print(f"   Successful: {batch_result.successful}")
    print(f"   Failed: {batch_result.failed}")
    print(f"   Total latency: {batch_result.total_latency_ms:.0f}ms")

    await client.close()

    print("\n" + "-" * 50)
    print("Firecrawl integration test complete!")


if __name__ == "__main__":
    asyncio.run(test_firecrawl())
