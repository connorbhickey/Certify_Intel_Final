"""
Certify Intel - Web Scraper (v5.2.0)
Uses Playwright to scrape competitor websites and extract content.

Enhanced Features:
- Comprehensive multi-page scraping
- Automatic page discovery
- Retry logic with exponential backoff
- Screenshot capture
- Better JavaScript handling
"""
import asyncio
import re
import os
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from urllib.parse import urljoin, urlparse
import hashlib

try:
    from playwright.async_api import async_playwright, Page, Browser, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Page = object
    Browser = object
    async_playwright = None
    PlaywrightTimeout = Exception
    print("Warning: Playwright not installed. Run: pip install playwright && playwright install chromium")


@dataclass
class ScrapedPage:
    """Represents a single scraped page."""
    url: str
    title: str
    content: str
    html: str
    scraped_at: datetime
    page_type: str  # homepage, pricing, about, features, etc.
    screenshot_path: Optional[str] = None
    meta_description: Optional[str] = None
    links_found: List[str] = field(default_factory=list)
    status_code: int = 200


@dataclass
class ScrapeResult:
    """Result of scraping a competitor's website."""
    competitor_name: str
    website: str
    pages: List[ScrapedPage]
    success: bool
    error: Optional[str] = None
    total_content_length: int = 0
    discovered_pages: List[str] = field(default_factory=list)
    scrape_duration_seconds: float = 0.0
    screenshots: List[str] = field(default_factory=list)


@dataclass
class ExtractedData:
    """Extracted structured data from a website."""
    company_name: Optional[str] = None
    tagline: Optional[str] = None
    description: Optional[str] = None
    products: List[str] = field(default_factory=list)
    features: List[str] = field(default_factory=list)
    pricing_info: Optional[str] = None
    pricing_tiers: List[Dict] = field(default_factory=list)
    integrations: List[str] = field(default_factory=list)
    customers: List[str] = field(default_factory=list)
    certifications: List[str] = field(default_factory=list)
    contact_info: Dict[str, str] = field(default_factory=dict)
    social_links: Dict[str, str] = field(default_factory=dict)
    founded_year: Optional[str] = None
    headquarters: Optional[str] = None
    employee_count: Optional[str] = None


class CompetitorScraper:
    """
    Scrapes competitor websites to extract content for AI analysis.

    v5.2.0 Enhancements:
    - Comprehensive multi-page scraping
    - Automatic page discovery from navigation
    - Retry logic with exponential backoff
    - Screenshot capture for visual verification
    - Better JavaScript handling with wait strategies
    """

    # Common page patterns for healthcare/SaaS companies
    PAGE_PATTERNS = {
        "homepage": [""],
        "pricing": ["pricing", "plans", "price", "packages", "cost", "subscription"],
        "about": ["about", "about-us", "company", "who-we-are", "our-story", "team"],
        "products": ["products", "product", "solutions", "platform", "features", "capabilities"],
        "features": ["features", "functionality", "capabilities", "what-we-offer"],
        "customers": ["customers", "case-studies", "clients", "success-stories", "testimonials"],
        "integrations": ["integrations", "partners", "marketplace", "apps", "ecosystem", "connect"],
        "resources": ["resources", "blog", "insights", "news", "knowledge-base", "help"],
        "contact": ["contact", "contact-us", "get-in-touch", "demo", "request-demo", "get-started"],
        "careers": ["careers", "jobs", "join-us", "work-with-us"],
        "security": ["security", "compliance", "trust", "privacy", "hipaa", "soc2"],
    }

    # Maximum retries for failed requests
    MAX_RETRIES = 3

    # Default pages to scrape for comprehensive analysis
    DEFAULT_PAGES = ["homepage", "pricing", "about", "products", "features", "customers", "integrations"]

    def __init__(
        self,
        headless: bool = True,
        timeout_ms: int = 30000,
        capture_screenshots: bool = False,
        screenshot_dir: str = "./screenshots"
    ):
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.capture_screenshots = capture_screenshots
        self.screenshot_dir = screenshot_dir
        self.browser: Optional[Browser] = None

        # Create screenshot directory if needed
        if capture_screenshots and not os.path.exists(screenshot_dir):
            os.makedirs(screenshot_dir, exist_ok=True)

    async def __aenter__(self):
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright is not installed")
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox'
            ]
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
    
    async def scrape_competitor(
        self,
        name: str,
        website: str,
        pages_to_scrape: List[str] = None,
        discover_pages: bool = True
    ) -> ScrapeResult:
        """
        Scrape a competitor's website comprehensively.

        Args:
            name: Competitor name
            website: Base website URL
            pages_to_scrape: List of page types to scrape (uses DEFAULT_PAGES if None)
            discover_pages: If True, discover additional pages from navigation

        Returns:
            ScrapeResult with all scraped pages
        """
        start_time = datetime.utcnow()

        if pages_to_scrape is None:
            pages_to_scrape = self.DEFAULT_PAGES.copy()

        if not self.browser:
            return ScrapeResult(
                competitor_name=name,
                website=website,
                pages=[],
                success=False,
                error="Browser not initialized"
            )

        scraped_pages = []
        discovered_pages = []
        screenshots = []
        total_content = 0

        try:
            context = await self.browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                }
            )
            page = await context.new_page()

            # Block unnecessary resources for faster scraping
            await page.route("**/*.{png,jpg,jpeg,gif,svg,mp4,webm,mp3,wav,woff,woff2,ttf}", lambda route: route.abort())

            # First, scrape homepage and discover navigation links
            if discover_pages:
                homepage_url = self._normalize_url(website)
                nav_links = await self._discover_navigation_links(page, homepage_url)
                discovered_pages = nav_links

            # Scrape each requested page type
            scraped_urls = set()  # Avoid duplicates

            for page_type in pages_to_scrape:
                urls_to_try = self._get_page_urls(website, page_type)

                for url in urls_to_try:
                    if url in scraped_urls:
                        continue

                    scraped = await self._scrape_page_with_retry(page, url, page_type, name)
                    if scraped:
                        scraped_pages.append(scraped)
                        scraped_urls.add(url)
                        total_content += len(scraped.content)

                        # Capture screenshot if enabled
                        if self.capture_screenshots and scraped.screenshot_path:
                            screenshots.append(scraped.screenshot_path)

                        break  # Found a working URL for this page type

            await context.close()

            duration = (datetime.utcnow() - start_time).total_seconds()

            return ScrapeResult(
                competitor_name=name,
                website=website,
                pages=scraped_pages,
                success=len(scraped_pages) > 0,
                total_content_length=total_content,
                discovered_pages=discovered_pages,
                scrape_duration_seconds=duration,
                screenshots=screenshots
            )

        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            return ScrapeResult(
                competitor_name=name,
                website=website,
                pages=scraped_pages,
                success=False,
                error=str(e),
                total_content_length=total_content,
                scrape_duration_seconds=duration
            )
    
    async def scrape(self, url: str) -> dict:
        """
        Simple scrape method for compatibility with main.py calls.
        Returns dict with extracted content from the website.
        """
        try:
            if not self.browser:
                return {"error": "Browser not initialized"}

            context = await self.browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            # Block heavy resources
            await page.route("**/*.{png,jpg,jpeg,gif,svg,mp4,webm}", lambda route: route.abort())

            url = self._normalize_url(url)

            # Retry logic
            last_error = None
            for attempt in range(self.MAX_RETRIES):
                try:
                    response = await page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=self.timeout_ms
                    )

                    if response and response.status < 400:
                        break
                except PlaywrightTimeout:
                    last_error = f"Timeout on attempt {attempt + 1}"
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                except Exception as e:
                    last_error = str(e)
                    await asyncio.sleep(2 ** attempt)
            else:
                await context.close()
                return {"error": last_error or "Failed after retries"}

            # Wait for JavaScript to execute
            await page.wait_for_timeout(2000)

            # Extract text content
            content = await self._extract_text_content(page)
            title = await page.title()
            meta_desc = await self._get_meta_description(page)

            await context.close()

            return {
                "content": content,
                "title": title,
                "url": url,
                "meta_description": meta_desc,
                "success": True
            }
        except Exception as e:
            return {"error": str(e)}

    def _normalize_url(self, url: str) -> str:
        """Normalize URL to have proper scheme."""
        if not url:
            return ""
        url = url.strip()
        if not url.startswith("http"):
            url = f"https://{url}"
        # Remove trailing slash for consistency
        return url.rstrip("/")

    def _get_page_urls(self, website: str, page_type: str) -> List[str]:
        """Get list of possible URLs for a page type."""
        base_url = self._normalize_url(website)
        urls = []

        if page_type == "homepage":
            return [base_url]

        patterns = self.PAGE_PATTERNS.get(page_type, [page_type])
        for pattern in patterns:
            urls.append(f"{base_url}/{pattern}")

        return urls

    async def _discover_navigation_links(self, page: Page, homepage_url: str) -> List[str]:
        """Discover navigation links from the homepage."""
        try:
            await page.goto(homepage_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
            await page.wait_for_timeout(1500)

            links = await page.evaluate("""
                () => {
                    const navLinks = [];
                    const baseUrl = window.location.origin;

                    // Look for links in nav, header, and common navigation areas
                    const selectors = [
                        'nav a', 'header a', '[role="navigation"] a',
                        '.nav a', '.navbar a', '.menu a', '.navigation a'
                    ];

                    for (const selector of selectors) {
                        const elements = document.querySelectorAll(selector);
                        elements.forEach(el => {
                            const href = el.getAttribute('href');
                            if (href && !href.startsWith('#') && !href.startsWith('javascript:')) {
                                // Convert relative to absolute
                                try {
                                    const absoluteUrl = new URL(href, baseUrl).href;
                                    // Only include internal links
                                    if (absoluteUrl.startsWith(baseUrl)) {
                                        navLinks.push(absoluteUrl);
                                    }
                                } catch(e) {}
                            }
                        });
                    }

                    // Deduplicate
                    return [...new Set(navLinks)];
                }
            """)

            return links[:20]  # Limit to prevent excessive scraping

        except Exception as e:
            print(f"Error discovering navigation: {e}")
            return []

    async def _scrape_page_with_retry(
        self,
        page: Page,
        url: str,
        page_type: str,
        competitor_name: str
    ) -> Optional[ScrapedPage]:
        """Scrape a page with retry logic and exponential backoff."""
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            try:
                result = await self._scrape_page(page, url, page_type, competitor_name)
                if result:
                    return result
            except PlaywrightTimeout:
                last_error = f"Timeout on attempt {attempt + 1}"
            except Exception as e:
                last_error = str(e)

            # Exponential backoff
            if attempt < self.MAX_RETRIES - 1:
                await asyncio.sleep(2 ** attempt)

        print(f"Failed to scrape {url} after {self.MAX_RETRIES} attempts: {last_error}")
        return None

    async def _extract_text_content(self, page: Page) -> str:
        """Extract clean text content from page."""
        return await page.evaluate("""
            () => {
                // Clone body to avoid modifying the actual page
                const clone = document.body.cloneNode(true);

                // Remove unwanted elements
                const unwanted = clone.querySelectorAll(
                    'script, style, noscript, iframe, svg, img, video, audio, ' +
                    'nav, footer, header, aside, .cookie-banner, .popup, .modal, ' +
                    '[role="banner"], [role="navigation"], [role="contentinfo"]'
                );
                unwanted.forEach(el => el.remove());

                // Get text and clean up whitespace
                let text = clone.innerText || '';
                text = text.replace(/\\s+/g, ' ').trim();

                return text;
            }
        """)

    async def _get_meta_description(self, page: Page) -> Optional[str]:
        """Get meta description from page."""
        try:
            return await page.evaluate("""
                () => {
                    const meta = document.querySelector('meta[name="description"]');
                    return meta ? meta.getAttribute('content') : null;
                }
            """)
        except:
            return None

    
    def _get_page_url(self, website: str, page_type: str) -> Optional[str]:
        """Get the URL for a specific page type (legacy compatibility)."""
        urls = self._get_page_urls(website, page_type)
        return urls[0] if urls else None

    async def _scrape_page(
        self,
        page: Page,
        url: str,
        page_type: str,
        competitor_name: str = ""
    ) -> Optional[ScrapedPage]:
        """
        Scrape a single page with enhanced extraction.

        Args:
            page: Playwright page object
            url: URL to scrape
            page_type: Type of page (pricing, about, etc.)
            competitor_name: Name of competitor for screenshot naming

        Returns:
            ScrapedPage object or None if failed
        """
        try:
            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self.timeout_ms
            )

            if not response:
                return None

            status_code = response.status
            if status_code >= 400:
                return None

            # Wait for JavaScript to execute
            await page.wait_for_timeout(2000)

            # Try to wait for common content containers
            try:
                await page.wait_for_selector('main, article, .content, #content', timeout=3000)
            except:
                pass  # Continue even if selector not found

            # Get page title
            title = await page.title()

            # Get clean text content
            content = await self._extract_text_content(page)

            # Get meta description
            meta_desc = await self._get_meta_description(page)

            # Get internal links for discovery
            links = await page.evaluate("""
                () => {
                    const baseUrl = window.location.origin;
                    return Array.from(document.querySelectorAll('a[href]'))
                        .map(a => {
                            try {
                                return new URL(a.href, baseUrl).href;
                            } catch(e) {
                                return null;
                            }
                        })
                        .filter(url => url && url.startsWith(baseUrl))
                        .slice(0, 50);
                }
            """)

            # Get HTML for more detailed extraction
            html = await page.content()

            # Capture screenshot if enabled
            screenshot_path = None
            if self.capture_screenshots:
                safe_name = re.sub(r'[^a-zA-Z0-9]', '_', competitor_name)
                screenshot_path = os.path.join(
                    self.screenshot_dir,
                    f"{safe_name}_{page_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
                )
                try:
                    await page.screenshot(path=screenshot_path, full_page=False)
                except Exception as e:
                    print(f"Screenshot failed: {e}")
                    screenshot_path = None

            return ScrapedPage(
                url=url,
                title=title,
                content=content,
                html=html,
                scraped_at=datetime.utcnow(),
                page_type=page_type,
                screenshot_path=screenshot_path,
                meta_description=meta_desc,
                links_found=links,
                status_code=status_code
            )

        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return None
    
    async def discover_pricing_page(self, page: Page, website: str) -> Optional[str]:
        """Try to discover the pricing page URL."""
        website = self._normalize_url(website)

        try:
            await page.goto(website, wait_until="domcontentloaded", timeout=self.timeout_ms)

            # Look for pricing links
            pricing_link = await page.evaluate("""
                () => {
                    const links = Array.from(document.querySelectorAll('a'));
                    const pricingPatterns = ['pricing', 'price', 'plans', 'cost', 'packages'];

                    for (const link of links) {
                        const href = link.getAttribute('href') || '';
                        const text = link.textContent?.toLowerCase() || '';

                        for (const pattern of pricingPatterns) {
                            if (href.includes(pattern) || text.includes(pattern)) {
                                return link.href;
                            }
                        }
                    }
                    return null;
                }
            """)

            return pricing_link

        except Exception as e:
            print(f"Error discovering pricing page: {e}")
            return None

    async def scrape_comprehensive(
        self,
        name: str,
        website: str
    ) -> Tuple[ScrapeResult, ExtractedData]:
        """
        Perform comprehensive scraping and extraction.

        Scrapes all default pages and extracts structured data.

        Args:
            name: Competitor name
            website: Base website URL

        Returns:
            Tuple of (ScrapeResult, ExtractedData)
        """
        # Scrape all pages
        result = await self.scrape_competitor(
            name=name,
            website=website,
            pages_to_scrape=self.DEFAULT_PAGES,
            discover_pages=True
        )

        # Extract structured data from scraped content
        extracted = await self._extract_structured_data(result)

        return result, extracted

    async def _extract_structured_data(self, result: ScrapeResult) -> ExtractedData:
        """Extract structured data from scrape result."""
        data = ExtractedData()
        data.company_name = result.competitor_name

        all_content = " ".join([p.content for p in result.pages])

        # Extract from homepage
        homepage = next((p for p in result.pages if p.page_type == "homepage"), None)
        if homepage:
            data.tagline = homepage.meta_description

        # Extract from about page
        about_page = next((p for p in result.pages if p.page_type == "about"), None)
        if about_page:
            # Try to extract year founded
            year_match = re.search(r'founded\s+(?:in\s+)?(\d{4})', about_page.content, re.I)
            if year_match:
                data.founded_year = year_match.group(1)

            # Try to extract headquarters
            hq_match = re.search(
                r'headquartered?\s+(?:in|at)\s+([^.]+)',
                about_page.content, re.I
            )
            if hq_match:
                data.headquarters = hq_match.group(1).strip()[:100]

        # Extract from pricing page
        pricing_page = next((p for p in result.pages if p.page_type == "pricing"), None)
        if pricing_page:
            data.pricing_info = pricing_page.content[:2000]  # First 2000 chars

            # Try to find pricing tiers
            tier_patterns = [
                r'(free|starter|basic|pro|professional|enterprise|business)\s*[-:]\s*\$?(\d+)',
                r'\$(\d+)\s*(?:per|/)\s*(month|user|seat)',
            ]
            for pattern in tier_patterns:
                matches = re.findall(pattern, pricing_page.content, re.I)
                for match in matches[:5]:
                    data.pricing_tiers.append({
                        "tier": match[0] if len(match) > 1 else "Standard",
                        "price": match[-1]
                    })

        # Extract certifications (common healthcare ones)
        cert_patterns = [
            'HIPAA', 'SOC 2', 'SOC2', 'HITRUST', 'ISO 27001',
            'GDPR', 'PCI DSS', 'EHNAC', 'ONC-ACB', 'CEHRT'
        ]
        for cert in cert_patterns:
            if cert.lower() in all_content.lower():
                data.certifications.append(cert)

        # Extract integrations
        integration_keywords = [
            'Epic', 'Cerner', 'Allscripts', 'athenahealth', 'eClinicalWorks',
            'NextGen', 'Meditech', 'DrChrono', 'Salesforce', 'HubSpot',
            'Slack', 'Microsoft Teams', 'Zapier', 'AWS', 'Azure', 'Google Cloud'
        ]
        for integration in integration_keywords:
            if integration.lower() in all_content.lower():
                data.integrations.append(integration)

        return data


# Standalone scrape function for simple usage
async def scrape_competitor(name: str, website: str, pages: List[str] = None) -> ScrapeResult:
    """Convenience function to scrape a single competitor."""
    async with CompetitorScraper() as scraper:
        return await scraper.scrape_competitor(name, website, pages)


async def scrape_comprehensive(name: str, website: str) -> Tuple[ScrapeResult, ExtractedData]:
    """Convenience function for comprehensive scraping."""
    async with CompetitorScraper() as scraper:
        return await scraper.scrape_comprehensive(name, website)


# Test function
async def test_scraper():
    """Test the scraper with a sample website."""
    print("Testing enhanced scraper (v5.2.0)...")
    print("-" * 50)

    async with CompetitorScraper(headless=True) as scraper:
        # Test comprehensive scrape
        result, extracted = await scraper.scrape_comprehensive(
            name="Phreesia",
            website="https://www.phreesia.com"
        )

        print(f"\nScraped: {result.competitor_name}")
        print(f"Success: {result.success}")
        print(f"Duration: {result.scrape_duration_seconds:.2f}s")
        print(f"Total content: {result.total_content_length:,} chars")
        print(f"Pages scraped: {len(result.pages)}")

        for page in result.pages:
            print(f"  - {page.page_type}: {page.title[:50]}... ({len(page.content):,} chars)")

        print(f"\nDiscovered pages: {len(result.discovered_pages)}")

        if extracted.certifications:
            print(f"Certifications: {', '.join(extracted.certifications)}")
        if extracted.integrations:
            print(f"Integrations: {', '.join(extracted.integrations[:5])}...")
        if extracted.founded_year:
            print(f"Founded: {extracted.founded_year}")

        if result.error:
            print(f"\nError: {result.error}")


if __name__ == "__main__":
    asyncio.run(test_scraper())
