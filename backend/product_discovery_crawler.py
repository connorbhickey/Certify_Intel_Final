"""
Certify Intel - Product Discovery Crawler (v5.1.0)

Systematically discovers all products/services/solutions offered by competitors.
Crawls competitor websites, cross-references with G2/Capterra, and populates
the CompetitorProduct table for complete product coverage.

Features:
- Crawls competitor Products/Solutions pages
- Extracts individual product names and details
- Cross-references with review sites (G2, Capterra)
- Creates CompetitorProduct records with source tracking
- Monitors for new product launches
"""

import asyncio
import os
import re
import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict, field
from urllib.parse import urljoin, urlparse

# Playwright for web scraping
try:
    from playwright.async_api import async_playwright, Page, Browser
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Page = object
    Browser = object

# AI for product extraction
try:
    from gemini_provider import GeminiProvider
    GEMINI_AVAILABLE = bool(os.getenv("GOOGLE_AI_API_KEY"))
except ImportError:
    GEMINI_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = bool(os.getenv("OPENAI_API_KEY"))
except ImportError:
    OPENAI_AVAILABLE = False


@dataclass
class DiscoveredProduct:
    """A product/service discovered from a competitor."""
    product_name: str
    product_category: str  # Patient Intake, RCM, EHR, etc.
    product_subcategory: Optional[str] = None
    description: Optional[str] = None
    key_features: Optional[List[str]] = None
    target_segment: Optional[str] = None  # SMB, Mid-Market, Enterprise
    product_page_url: Optional[str] = None
    pricing_page_url: Optional[str] = None
    discovery_source: str = "website_crawl"  # website_crawl, g2, capterra, press_release
    is_primary_product: bool = False
    confidence_score: int = 70


@dataclass
class ProductDiscoveryResult:
    """Results from product discovery for a competitor."""
    competitor_name: str
    competitor_id: Optional[int] = None
    website: str = ""
    products_found: List[DiscoveredProduct] = field(default_factory=list)
    pages_crawled: int = 0
    discovery_sources: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    crawled_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


# Healthcare product categories for classification
HEALTHCARE_PRODUCT_CATEGORIES = {
    "patient_intake": [
        "intake", "check-in", "check in", "registration", "digital front door",
        "patient access", "pre-visit", "previsit", "forms", "questionnaire"
    ],
    "practice_management": [
        "practice management", "pm", "scheduling", "appointment", "calendar",
        "office management", "workflow"
    ],
    "ehr_emr": [
        "ehr", "emr", "electronic health record", "electronic medical record",
        "clinical documentation", "charting", "medical records"
    ],
    "rcm": [
        "rcm", "revenue cycle", "billing", "claims", "collections",
        "payment processing", "charge capture", "coding"
    ],
    "patient_engagement": [
        "patient engagement", "patient communication", "messaging", "reminders",
        "recall", "outreach", "patient portal", "patient experience"
    ],
    "telehealth": [
        "telehealth", "telemedicine", "virtual care", "video visit",
        "remote patient", "virtual visit"
    ],
    "analytics": [
        "analytics", "reporting", "dashboard", "business intelligence",
        "data analytics", "insights", "metrics"
    ],
    "payments": [
        "payments", "payment", "pay", "billing", "collections",
        "patient pay", "payment processing", "merchant"
    ],
    "eligibility": [
        "eligibility", "insurance verification", "benefits verification",
        "coverage", "prior auth", "prior authorization"
    ],
    "interoperability": [
        "integration", "interoperability", "hl7", "fhir", "api",
        "ehr integration", "data exchange", "connectivity"
    ],
    "ai_automation": [
        "ai", "artificial intelligence", "automation", "machine learning",
        "intelligent", "smart", "automated"
    ],
    "population_health": [
        "population health", "care management", "chronic care",
        "value-based", "quality measures"
    ]
}


class ProductDiscoveryCrawler:
    """
    Crawls competitor websites to discover all products/services.

    Uses multiple strategies:
    1. Direct website crawl (Products/Solutions pages)
    2. AI-powered product extraction from page content
    3. Navigation menu analysis
    4. Sitemap parsing
    """

    def __init__(self, use_ai: bool = True, headless: bool = True):
        """
        Initialize the crawler.

        Args:
            use_ai: Whether to use AI for product extraction
            headless: Whether to run browser in headless mode
        """
        self.use_ai = use_ai and (GEMINI_AVAILABLE or OPENAI_AVAILABLE)
        self.headless = headless
        self.browser = None
        self.playwright = None

        # Initialize AI provider
        self.gemini_provider = None
        if GEMINI_AVAILABLE and use_ai:
            try:
                self.gemini_provider = GeminiProvider()
            except Exception as e:
                print(f"Warning: Failed to initialize Gemini: {e}")

    async def __aenter__(self):
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright not installed. Run: pip install playwright && playwright install chromium")
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def discover_products(
        self,
        competitor_name: str,
        website: str,
        competitor_id: Optional[int] = None
    ) -> ProductDiscoveryResult:
        """
        Discover all products/services for a competitor.

        Args:
            competitor_name: Name of the competitor
            website: Competitor's website URL
            competitor_id: Optional database ID

        Returns:
            ProductDiscoveryResult with all discovered products
        """
        result = ProductDiscoveryResult(
            competitor_name=competitor_name,
            competitor_id=competitor_id,
            website=website
        )

        if not self.browser:
            result.errors.append("Browser not initialized")
            return result

        # Normalize website URL
        if not website.startswith("http"):
            website = f"https://{website}"

        try:
            context = await self.browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = await context.new_page()

            # Strategy 1: Find and crawl Products/Solutions pages
            product_urls = await self._find_product_pages(page, website)
            result.discovery_sources.append("website_navigation")

            # Strategy 2: Crawl each product page
            for url in product_urls[:10]:  # Limit to 10 pages
                try:
                    products = await self._extract_products_from_page(page, url)
                    result.products_found.extend(products)
                    result.pages_crawled += 1
                except Exception as e:
                    result.errors.append(f"Error crawling {url}: {str(e)[:50]}")

            # Strategy 3: AI extraction from homepage if few products found
            if len(result.products_found) < 3 and self.use_ai:
                try:
                    ai_products = await self._ai_extract_products(page, website, competitor_name)
                    # Add products not already discovered
                    existing_names = {p.product_name.lower() for p in result.products_found}
                    for product in ai_products:
                        if product.product_name.lower() not in existing_names:
                            result.products_found.append(product)
                    result.discovery_sources.append("ai_extraction")
                except Exception as e:
                    result.errors.append(f"AI extraction error: {str(e)[:50]}")

            # Deduplicate products
            result.products_found = self._deduplicate_products(result.products_found)

            # Mark primary product (most mentioned or first in navigation)
            if result.products_found:
                result.products_found[0].is_primary_product = True

            await context.close()

        except Exception as e:
            result.errors.append(f"Crawl error: {str(e)[:100]}")

        return result

    async def _find_product_pages(self, page: Page, website: str) -> List[str]:
        """Find URLs of product/solution pages from navigation."""
        product_urls = [website]  # Always include homepage

        try:
            await page.goto(website, timeout=30000, wait_until="domcontentloaded")
            await asyncio.sleep(2)  # Wait for JS navigation to render

            # Look for product-related links in navigation
            product_keywords = [
                "products", "solutions", "services", "platform", "features",
                "offerings", "modules", "capabilities", "what we do"
            ]

            # Find all navigation links
            links = await page.query_selector_all("nav a, header a, .nav a, .menu a, .navigation a")

            for link in links:
                try:
                    href = await link.get_attribute("href")
                    text = await link.inner_text()

                    if href and text:
                        text_lower = text.lower().strip()

                        # Check if link text matches product keywords
                        if any(kw in text_lower for kw in product_keywords):
                            full_url = urljoin(website, href)
                            if full_url not in product_urls:
                                product_urls.append(full_url)
                except Exception:
                    continue

            # Also look for mega menu or dropdown items
            dropdown_links = await page.query_selector_all(
                "[class*='dropdown'] a, [class*='mega'] a, [class*='submenu'] a"
            )

            for link in dropdown_links:
                try:
                    href = await link.get_attribute("href")
                    if href:
                        full_url = urljoin(website, href)
                        # Filter to likely product pages
                        url_lower = full_url.lower()
                        if any(kw in url_lower for kw in ["product", "solution", "feature", "platform"]):
                            if full_url not in product_urls:
                                product_urls.append(full_url)
                except Exception:
                    continue

        except Exception as e:
            print(f"Navigation discovery error: {e}")

        return product_urls

    async def _extract_products_from_page(
        self,
        page: Page,
        url: str
    ) -> List[DiscoveredProduct]:
        """Extract product information from a page."""
        products = []

        try:
            await page.goto(url, timeout=30000, wait_until="domcontentloaded")
            await asyncio.sleep(1)

            # Get page content
            content = await page.evaluate("document.body.innerText")
            title = await page.title()

            # Look for product cards or sections
            # Common patterns: cards, tiles, features sections
            selectors = [
                "[class*='product']",
                "[class*='solution']",
                "[class*='feature']",
                "[class*='service']",
                "[class*='offering']",
                "[class*='card']",
                "[class*='tile']"
            ]

            for selector in selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    for elem in elements[:10]:  # Limit per selector
                        try:
                            elem_text = await elem.inner_text()
                            elem_text = elem_text.strip()

                            if len(elem_text) > 10 and len(elem_text) < 500:
                                # Try to extract product name from heading
                                heading = await elem.query_selector("h1, h2, h3, h4, [class*='title']")
                                if heading:
                                    product_name = await heading.inner_text()
                                    product_name = product_name.strip()

                                    if product_name and len(product_name) > 3:
                                        category = self._classify_product(product_name + " " + elem_text)

                                        products.append(DiscoveredProduct(
                                            product_name=product_name,
                                            product_category=category,
                                            description=elem_text[:300],
                                            product_page_url=url,
                                            discovery_source="website_crawl",
                                            confidence_score=60
                                        ))
                        except Exception:
                            continue
                except Exception:
                    continue

            # If no structured products found, try to extract from page content
            if not products:
                products = self._extract_products_from_text(content, title, url)

        except Exception as e:
            print(f"Page extraction error for {url}: {e}")

        return products

    def _extract_products_from_text(
        self,
        content: str,
        title: str,
        url: str
    ) -> List[DiscoveredProduct]:
        """Extract products from unstructured page text."""
        products = []

        # Look for patterns like "Product Name: Description" or "Our Products: X, Y, Z"
        content_lower = content.lower()

        # Find sentences mentioning products/solutions
        for category, keywords in HEALTHCARE_PRODUCT_CATEGORIES.items():
            for keyword in keywords:
                if keyword in content_lower:
                    # Try to extract a product name near this keyword
                    pattern = rf'([A-Z][a-zA-Z\s]+(?:{keyword}|Platform|Suite|Solution|System))'
                    matches = re.findall(pattern, content, re.IGNORECASE)

                    for match in matches[:3]:
                        product_name = match.strip()
                        if 3 < len(product_name) < 50:
                            products.append(DiscoveredProduct(
                                product_name=product_name,
                                product_category=category.replace("_", " ").title(),
                                product_page_url=url,
                                discovery_source="website_crawl",
                                confidence_score=40
                            ))

        return products

    async def _ai_extract_products(
        self,
        page: Page,
        website: str,
        competitor_name: str
    ) -> List[DiscoveredProduct]:
        """Use AI to extract products from page content."""
        products = []

        try:
            await page.goto(website, timeout=30000, wait_until="domcontentloaded")
            content = await page.evaluate("document.body.innerText")
            content = content[:8000]  # Limit content for AI

            prompt = f"""Analyze this healthcare software company's website content and extract ALL their products/services.

Company: {competitor_name}
Website Content:
{content}

For each product/service, provide:
1. Product name (exact name as marketed)
2. Category (one of: Patient Intake, Practice Management, EHR/EMR, RCM/Billing, Patient Engagement, Telehealth, Analytics, Payments, Eligibility, Interoperability, AI/Automation, Population Health)
3. Brief description (1-2 sentences)
4. Target segment (SMB, Mid-Market, Enterprise, or All)

Return as JSON array:
[{{"name": "Product Name", "category": "Category", "description": "Description", "target": "Target"}}]

Return ONLY the JSON array, no other text."""

            if self.gemini_provider and self.gemini_provider.is_available:
                result = self.gemini_provider.generate_json(
                    prompt=prompt,
                    temperature=0.1
                )

                if isinstance(result, list):
                    for item in result:
                        if isinstance(item, dict) and item.get("name"):
                            products.append(DiscoveredProduct(
                                product_name=item.get("name", ""),
                                product_category=item.get("category", "Unknown"),
                                description=item.get("description", ""),
                                target_segment=item.get("target", ""),
                                discovery_source="ai_extraction",
                                confidence_score=75
                            ))

            elif OPENAI_AVAILABLE:
                client = openai.OpenAI()
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a healthcare IT analyst. Extract products from website content."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=1500,
                    response_format={"type": "json_object"}
                )

                result = json.loads(response.choices[0].message.content)
                if isinstance(result, list):
                    for item in result:
                        if isinstance(item, dict) and item.get("name"):
                            products.append(DiscoveredProduct(
                                product_name=item.get("name", ""),
                                product_category=item.get("category", "Unknown"),
                                description=item.get("description", ""),
                                target_segment=item.get("target", ""),
                                discovery_source="ai_extraction",
                                confidence_score=75
                            ))

        except Exception as e:
            print(f"AI extraction error: {e}")

        return products

    def _classify_product(self, text: str) -> str:
        """Classify a product into a category based on text."""
        text_lower = text.lower()

        for category, keywords in HEALTHCARE_PRODUCT_CATEGORIES.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return category.replace("_", " ").title()

        return "Other"

    def _deduplicate_products(
        self,
        products: List[DiscoveredProduct]
    ) -> List[DiscoveredProduct]:
        """Remove duplicate products, keeping highest confidence."""
        seen = {}

        for product in products:
            key = product.product_name.lower().strip()

            if key not in seen or product.confidence_score > seen[key].confidence_score:
                seen[key] = product

        return list(seen.values())


class ProductDiscoveryService:
    """
    High-level service for product discovery operations.
    Integrates with database and provides batch operations.
    """

    def __init__(self, db_session=None):
        self.db = db_session

    async def discover_all_products(
        self,
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        Discover products for all competitors in the database.

        Args:
            progress_callback: Optional callback function(competitor_name, current, total)

        Returns:
            Summary of discovery results
        """
        from database import SessionLocal, Competitor, CompetitorProduct, DataSource

        if self.db is None:
            self.db = SessionLocal()
            close_db = True
        else:
            close_db = False

        results = {
            "total_competitors": 0,
            "competitors_processed": 0,
            "total_products_discovered": 0,
            "products_created": 0,
            "products_updated": 0,
            "errors": []
        }

        try:
            # Get all competitors
            competitors = self.db.query(Competitor).filter(
                Competitor.is_deleted == False,
                Competitor.website.isnot(None)
            ).all()

            results["total_competitors"] = len(competitors)

            async with ProductDiscoveryCrawler(use_ai=True) as crawler:
                for i, comp in enumerate(competitors):
                    if progress_callback:
                        progress_callback(comp.name, i + 1, len(competitors))

                    try:
                        # Discover products
                        discovery = await crawler.discover_products(
                            competitor_name=comp.name,
                            website=comp.website,
                            competitor_id=comp.id
                        )

                        results["total_products_discovered"] += len(discovery.products_found)

                        # Save to database
                        for product in discovery.products_found:
                            created = self._save_product(comp.id, product)
                            if created:
                                results["products_created"] += 1
                            else:
                                results["products_updated"] += 1

                        # Also update competitor's product_categories field
                        if discovery.products_found:
                            categories = list(set(p.product_category for p in discovery.products_found))
                            comp.product_categories = "; ".join(categories)

                            features = []
                            for p in discovery.products_found:
                                if p.key_features:
                                    features.extend(p.key_features)
                            if features:
                                comp.key_features = ", ".join(features[:10])

                        results["competitors_processed"] += 1

                    except Exception as e:
                        results["errors"].append(f"{comp.name}: {str(e)[:50]}")

                    # Rate limiting
                    await asyncio.sleep(2)

            self.db.commit()

        except Exception as e:
            results["errors"].append(f"Service error: {str(e)}")
            self.db.rollback()

        finally:
            if close_db:
                self.db.close()

        return results

    def _save_product(self, competitor_id: int, product: DiscoveredProduct) -> bool:
        """
        Save a discovered product to the database.

        Returns:
            True if created new, False if updated existing
        """
        from database import CompetitorProduct, DataSource

        # Check if product already exists
        existing = self.db.query(CompetitorProduct).filter(
            CompetitorProduct.competitor_id == competitor_id,
            CompetitorProduct.product_name.ilike(product.product_name)
        ).first()

        if existing:
            # Update if higher confidence
            if product.confidence_score > (existing.confidence_score or 0):
                existing.product_category = product.product_category
                existing.description = product.description or existing.description
                existing.target_segment = product.target_segment or existing.target_segment
                existing.last_updated = datetime.utcnow()
            return False

        # Create new product
        new_product = CompetitorProduct(
            competitor_id=competitor_id,
            product_name=product.product_name,
            product_category=product.product_category,
            product_subcategory=product.product_subcategory,
            description=product.description,
            key_features=json.dumps(product.key_features) if product.key_features else None,
            target_segment=product.target_segment,
            is_primary_product=product.is_primary_product,
            market_position="Unknown",
            created_at=datetime.utcnow(),
            last_updated=datetime.utcnow()
        )

        self.db.add(new_product)
        self.db.flush()

        # Create DataSource record
        source = DataSource(
            competitor_id=competitor_id,
            field_name=f"product:{product.product_name}",
            current_value=product.product_name,
            source_type="website_crawl",
            source_name=f"Product Discovery ({product.discovery_source})",
            source_url=product.product_page_url,
            extraction_method="product_discovery_crawler",
            confidence_score=product.confidence_score,
            confidence_level="moderate" if product.confidence_score >= 60 else "low",
            is_verified=False,
            extracted_at=datetime.utcnow(),
            created_at=datetime.utcnow()
        )
        self.db.add(source)

        return True


# ==============================================================================
# CLI TESTING
# ==============================================================================

async def test_single_competitor(name: str, website: str):
    """Test product discovery for a single competitor."""
    print(f"\n{'='*60}")
    print(f"Product Discovery Test: {name}")
    print(f"Website: {website}")
    print(f"{'='*60}\n")

    async with ProductDiscoveryCrawler(use_ai=True) as crawler:
        result = await crawler.discover_products(name, website)

        print(f"Pages Crawled: {result.pages_crawled}")
        print(f"Sources Used: {', '.join(result.discovery_sources)}")
        print(f"Products Found: {len(result.products_found)}")

        if result.errors:
            print(f"\nErrors:")
            for error in result.errors:
                print(f"  - {error}")

        print(f"\nDiscovered Products:")
        for i, product in enumerate(result.products_found, 1):
            print(f"\n  {i}. {product.product_name}")
            print(f"     Category: {product.product_category}")
            print(f"     Confidence: {product.confidence_score}%")
            if product.description:
                print(f"     Description: {product.description[:100]}...")
            print(f"     Source: {product.discovery_source}")


if __name__ == "__main__":
    import sys

    # Test with a few known competitors
    test_competitors = [
        ("Phreesia", "https://www.phreesia.com"),
        ("Clearwave", "https://www.clearwaveinc.com"),
        ("Kareo", "https://www.kareo.com"),
    ]

    if len(sys.argv) > 2:
        # Custom competitor from command line
        test_competitors = [(sys.argv[1], sys.argv[2])]

    for name, website in test_competitors:
        asyncio.run(test_single_competitor(name, website))
