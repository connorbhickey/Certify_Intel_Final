
"""
Certify Intel - Public SimilarWeb Scraper
Scrapes public traffic data from SimilarWeb without an API key.
Uses Playwright to render the JS-heavy public profile pages.
"""
import asyncio
from playwright.async_api import async_playwright
from typing import Dict, Any, Optional
import random

class PublicSimilarWebScraper:
    def __init__(self):
        self.base_url = "https://www.similarweb.com/website"
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]

    async def get_traffic_data(self, domain: str) -> Dict[str, Any]:
        """Scrape public traffic stats for a domain."""
        print(f"🚦 Scraping traffic data for: {domain}")
        
        async with async_playwright() as p:
            # Launch browser with stealth args
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            context = await browser.new_context(
                user_agent=random.choice(self.user_agents),
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="America/New_York",
                permissions=["geolocation"]
            )
            
            # Injection to mask webdriver
            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            page = await context.new_page()
            
            try:
                # Go to public profile: e.g. https://www.similarweb.com/website/phreesia.com
                url = f"{self.base_url}/{domain}"
                await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                
                # Check if 404/Block
                if "404" in await page.title():
                    return self._fallback_response("Data Unavailable")

                # Selector strategy for 2024 SimilarWeb layout
                # Note: These classes change often, so we look for text markers
                
                # 1. Total Visits
                # Usually in a class like 'engagement-list__item-value' or near text "Total Visits"
                total_visits = await page.evaluate("""() => {
                    const elements = Array.from(document.querySelectorAll('*'));
                    const target = elements.find(el => el.textContent.includes('Total Visits') && el.nextElementSibling);
                    return target ? target.nextElementSibling.textContent.trim() : null;
                }""") or "N/A"

                # 2. Bounce Rate
                bounce_rate = await page.evaluate("""() => {
                    const elements = Array.from(document.querySelectorAll('*'));
                    const target = elements.find(el => el.textContent.includes('Bounce Rate') && el.nextElementSibling);
                    return target ? target.nextElementSibling.textContent.trim() : null;
                }""") or "N/A"

                # 3. Avg Visit Duration
                avg_duration = await page.evaluate("""() => {
                    const elements = Array.from(document.querySelectorAll('*'));
                    const target = elements.find(el => el.textContent.includes('Avg Visit Duration') && el.nextElementSibling);
                    return target ? target.nextElementSibling.textContent.trim() : null;
                }""") or "N/A"

                # 4. Top Countries
                top_country = await page.evaluate("""() => {
                    const el = document.querySelector('.wa-geography__country-name');
                    return el ? el.textContent.trim() : 'Global';
                }""")

                return {
                    "total_visits": total_visits,
                    "bounce_rate": bounce_rate,
                    "avg_visit_duration": avg_duration,
                    "top_country": top_country,
                    "source": "SimilarWeb Public",
                    "is_mock": False
                }

            except Exception as e:
                print(f"Error scraping {domain}: {e}")
                return self._fallback_response(str(e))
                
            finally:
                await browser.close()

    def _fallback_response(self, error: str) -> Dict[str, Any]:
        return {
            "total_visits": "N/A",
            "bounce_rate": "N/A",
            "avg_visit_duration": "N/A",
            "top_country": "Unknown",
            "error": error,
            "is_mock": True
        }

if __name__ == "__main__":
    # Test run
    scraper = PublicSimilarWebScraper()
    data = asyncio.run(scraper.get_traffic_data("phreesia.com"))
    print(data)
