"""
Certify Intel - Review Platform Scraper
Scrapes customer reviews from G2, Capterra, Trustpilot, and Google Business.
"""

import os
import re
import json
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict

import httpx
from bs4 import BeautifulSoup


@dataclass
class ReviewData:
    platform: str
    company_name: str
    company_slug: str
    overall_rating: Optional[float] = None
    review_count: Optional[int] = None
    url: Optional[str] = None
    last_scraped: Optional[str] = None
    error: Optional[str] = None


class G2Scraper:
    BASE_URL = "https://www.g2.com/products"

    async def scrape(self, company_slug: str, company_name: str = None) -> ReviewData:
        url = f"{self.BASE_URL}/{company_slug}/reviews"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                response = await client.get(url, headers=headers, follow_redirects=True)
                if response.status_code == 404:
                    return ReviewData(platform="g2", company_name=company_name or company_slug,
                        company_slug=company_slug, error="Not found", last_scraped=datetime.utcnow().isoformat())
                soup = BeautifulSoup(response.text, "html.parser")
                rating_elem = soup.select_one("[itemprop=ratingValue]")
                overall_rating = float(rating_elem.get("content")) if rating_elem else None
                count_elem = soup.select_one("[itemprop=reviewCount]")
                review_count = int(count_elem.get("content")) if count_elem else None
                return ReviewData(platform="g2", company_name=company_name or company_slug,
                    company_slug=company_slug, overall_rating=overall_rating, review_count=review_count,
                    url=url, last_scraped=datetime.utcnow().isoformat())
        except Exception as e:
            return ReviewData(platform="g2", company_name=company_name or company_slug,
                company_slug=company_slug, error=str(e), last_scraped=datetime.utcnow().isoformat())


class TrustpilotScraper:
    BASE_URL = "https://www.trustpilot.com/review"

    async def scrape(self, domain: str, company_name: str = None) -> ReviewData:
        url = f"{self.BASE_URL}/{domain}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                response = await client.get(url, headers=headers, follow_redirects=True)
                if response.status_code == 404:
                    return ReviewData(platform="trustpilot", company_name=company_name or domain,
                        company_slug=domain, error="Not found", last_scraped=datetime.utcnow().isoformat())
                soup = BeautifulSoup(response.text, "html.parser")
                overall_rating = None
                review_count = None
                scripts = soup.find_all("script", type="application/ld+json")
                for script in scripts:
                    try:
                        data = json.loads(script.string)
                        if isinstance(data, dict) and "aggregateRating" in data:
                            agg = data["aggregateRating"]
                            overall_rating = float(agg.get("ratingValue", 0))
                            review_count = int(agg.get("reviewCount", 0))
                            break
                    except:
                        pass
                return ReviewData(platform="trustpilot", company_name=company_name or domain,
                    company_slug=domain, overall_rating=overall_rating, review_count=review_count,
                    url=url, last_scraped=datetime.utcnow().isoformat())
        except Exception as e:
            return ReviewData(platform="trustpilot", company_name=company_name or domain,
                company_slug=domain, error=str(e), last_scraped=datetime.utcnow().isoformat())


class ReviewAggregator:
    def __init__(self):
        self.g2 = G2Scraper()
        self.trustpilot = TrustpilotScraper()

    async def scrape_all(self, company_name: str, g2_slug: str = None, trustpilot_domain: str = None) -> Dict[str, Any]:
        tasks = []
        if g2_slug:
            tasks.append(("g2", self.g2.scrape(g2_slug, company_name)))
        if trustpilot_domain:
            tasks.append(("trustpilot", self.trustpilot.scrape(trustpilot_domain, company_name)))
        results = {}
        if tasks:
            platform_results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)
            for i, (platform, _) in enumerate(tasks):
                result = platform_results[i]
                if isinstance(result, Exception):
                    results[platform] = {"error": str(result)}
                else:
                    results[platform] = asdict(result)
        total_reviews = 0
        weighted_sum = 0
        for data in results.values():
            if data.get("overall_rating") and data.get("review_count"):
                total_reviews += data["review_count"]
                weighted_sum += data["overall_rating"] * data["review_count"]
        return {
            "aggregate": {
                "company_name": company_name,
                "total_reviews": total_reviews,
                "weighted_average_rating": round(weighted_sum / total_reviews, 2) if total_reviews > 0 else None,
                "scraped_at": datetime.utcnow().isoformat()
            },
            "platforms": results
        }


KNOWN_REVIEW_URLS = {
    "certify_health": {"g2": "certify-health", "trustpilot": "certifyhealth.com"},
    "phreesia": {"g2": "phreesia", "trustpilot": "phreesia.com"},
    "clearwave": {"g2": "clearwave", "trustpilot": None},
    "luma_health": {"g2": "luma-health", "trustpilot": "lumahealth.io"},
    "solutionreach": {"g2": "solutionreach", "trustpilot": "solutionreach.com"},
}


async def get_certify_health_reviews() -> Dict[str, Any]:
    aggregator = ReviewAggregator()
    return await aggregator.scrape_all("Certify Health", g2_slug="certify-health", trustpilot_domain="certifyhealth.com")


async def get_competitor_reviews(competitor_key: str) -> Dict[str, Any]:
    if competitor_key not in KNOWN_REVIEW_URLS:
        return {"error": f"Unknown competitor: {competitor_key}"}
    urls = KNOWN_REVIEW_URLS[competitor_key]
    aggregator = ReviewAggregator()
    return await aggregator.scrape_all(competitor_key.replace("_", " ").title(),
        g2_slug=urls.get("g2"), trustpilot_domain=urls.get("trustpilot"))
