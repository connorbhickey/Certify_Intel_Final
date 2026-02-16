"""
Certify Intel - Google Ecosystem Scraper
Fetches digital footprint data from Google Ads, Trends, and Maps.
"""
import os
import random
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

@dataclass
class GoogleAdsData:
    """Google Ads Transparency data."""
    active_creative_count: int
    formats: List[str]  # Video, Image, Text
    last_launched: str
    regions: List[str]

@dataclass
class GoogleTrendsData:
    """Google Trends brand interest."""
    interest_index_12mo: List[int]  # Monthly index 0-100
    current_index: int
    trend_direction: str  # Rising, Stable, Falling
    related_queries: List[str]

@dataclass
class GoogleMapsData:
    """Google Maps location data."""
    review_count: int
    rating: float
    reviews_last_month: int  # Velocity proxy
    popular_times_peak: str  # e.g., "Wednesday 6pm"
    busyness_score: int  # 0-100 relative to max

@dataclass
class GoogleEcosystemData:
    """Aggregated Google data."""
    company_name: str
    ads: GoogleAdsData
    trends: GoogleTrendsData
    maps: GoogleMapsData
    last_updated: str

class GoogleEcosystemScraper:
    """Scrapes Google ecosystem data."""
    
    # Known data for demo
    KNOWN_COMPANIES = {
        "phreesia": {
            "ads": {
                "active_creative_count": 45,
                "formats": ["Image", "Text"],
                "last_launched": "2024-01-15",
                "regions": ["United States"]
            },
            "trends": {
                "interest_index_12mo": [45, 48, 52, 50, 55, 60, 58, 62, 65, 70, 72, 75],
                "current_index": 75,
                "trend_direction": "Rising",
                "related_queries": ["phreesia check in", "phreesia pad", "phreesia careers"]
            },
            "maps": {
                "review_count": 128,
                "rating": 3.8,
                "reviews_last_month": 5,
                "popular_times_peak": "Tuesday 10am",
                "busyness_score": 65
            }
        },
        "cedar": {
            "ads": {
                "active_creative_count": 12,
                "formats": ["Text"],
                "last_launched": "2023-11-20",
                "regions": ["United States"]
            },
            "trends": {
                "interest_index_12mo": [20, 22, 25, 24, 26, 28, 30, 32, 35, 38, 40, 42],
                "current_index": 42,
                "trend_direction": "Rising",
                "related_queries": ["cedar pay", "cedar health", "cedar jobs"]
            },
            "maps": {
                "review_count": 45,
                "rating": 4.1,
                "reviews_last_month": 2,
                "popular_times_peak": "Monday 9am",
                "busyness_score": 40
            }
        },
        "zocdoc": {
            "ads": {
                "active_creative_count": 150,
                "formats": ["Video", "Image", "Text"],
                "last_launched": "2024-01-19",
                "regions": ["United States", "India"]
            },
            "trends": {
                "interest_index_12mo": [80, 82, 85, 88, 90, 85, 88, 92, 95, 90, 92, 94],
                "current_index": 94,
                "trend_direction": "Stable",
                "related_queries": ["zocdoc dentist", "zocdoc login", "zocdoc reviews"]
            },
            "maps": {
                "review_count": 2500,
                "rating": 4.5,
                "reviews_last_month": 120,
                "popular_times_peak": "Monday 10am",
                "busyness_score": 85
            }
        }
    }

    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.cx = os.getenv("GOOGLE_CSE_ID")

    def get_ecosystem_data(self, company_name: str) -> GoogleEcosystemData:
        """Get Google ecosystem data for a company. Returns unavailable status when no real API is configured."""
        # KNOWN_COMPANIES contains fabricated demo data - never return it as real
        return self._build_placeholder(company_name)

    def _build_from_known(self, company_name: str, data: Dict) -> GoogleEcosystemData:
        """Build GoogleEcosystemData from known data."""
        ads = GoogleAdsData(**data["ads"])
        trends = GoogleTrendsData(**data["trends"])
        maps = GoogleMapsData(**data["maps"])
        
        return GoogleEcosystemData(
            company_name=company_name,
            ads=ads,
            trends=trends,
            maps=maps,
            last_updated=datetime.utcnow().isoformat()
        )

    def _build_placeholder(self, company_name: str) -> GoogleEcosystemData:
        """Build placeholder GoogleEcosystemData."""
        return GoogleEcosystemData(
            company_name=company_name,
            ads=GoogleAdsData(0, [], "", []),
            trends=GoogleTrendsData([], 0, "Unknown", []),
            maps=GoogleMapsData(0, 0.0, 0, "", 0),
            last_updated=datetime.utcnow().isoformat()
        )

if __name__ == "__main__":
    scraper = GoogleEcosystemScraper()
    print("="*60)
    print("Google Ecosystem Intelligence")
    print("="*60)
    
    for company in ["Phreesia", "Zocdoc"]:
        data = scraper.get_ecosystem_data(company)
        print(f"\n{company}:")
        print(f"  Ads: {data.ads.active_creative_count} active creatives ({', '.join(data.ads.formats)})")
        print(f"  Brand Index: {data.trends.current_index} ({data.trends.trend_direction})")
        print(f"  Maps Reviews: {data.maps.review_count} ({data.maps.reviews_last_month}/mo velocity)")
