"""
Certify Intel - Sentiment Scraper
Fetches product reviews and sentiment from G2, Capterra, Trustpilot, and Reddit.
"""
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

@dataclass
class SentimentData:
    """Aggregated Sentiment Data."""
    company_name: str
    g2_score: float
    g2_badges: List[str]  # e.g., "High Performer", "Leader"
    capterra_score: float
    trustpilot_score: float
    reddit_sentiment: str # Positive, Neutral, Negative
    reddit_mentions_30d: int
    top_complaints: List[str]
    last_updated: str

class SentimentScraper:
    """Scrapes sentiment data."""
    
    # Known data for demo
    KNOWN_COMPANIES = {
        "phreesia": {
            "g2_score": 4.2,
            "g2_badges": ["Leader Winter 2024", "Easiest To Use"],
            "capterra_score": 4.1,
            "trustpilot_score": 2.8,  # Often billing complaints
            "reddit_sentiment": "Mixed",
            "reddit_mentions_30d": 12,
            "top_complaints": ["Billing transparency", "Integration speed"]
        },
        "cedar": {
            "g2_score": 4.5,
            "g2_badges": ["High Performer", "Best Support"],
            "capterra_score": 4.6,
            "trustpilot_score": 4.2,
            "reddit_sentiment": "Positive",
            "reddit_mentions_30d": 8,
            "top_complaints": ["Pricing for small practices"]
        },
        "zocdoc": {
            "g2_score": 3.8,
            "g2_badges": ["Market Presence"],
            "capterra_score": 3.9,
            "trustpilot_score": 4.5, # Strong consumer brand
            "reddit_sentiment": "Mixed",
            "reddit_mentions_30d": 45,
            "top_complaints": ["Provider cancellation fees", "Availability accuracy"]
        }
    }

    def __init__(self):
        pass

    def get_sentiment_data(self, company_name: str) -> SentimentData:
        """Get combined sentiment data. Returns unavailable status when no real API is configured."""
        # KNOWN_COMPANIES contains fabricated demo data - never return it as real
        return self._build_placeholder(company_name)

    def _build_from_known(self, company_name: str, data: Dict) -> SentimentData:
        return SentimentData(
            company_name=company_name,
            g2_score=data["g2_score"],
            g2_badges=data["g2_badges"],
            capterra_score=data["capterra_score"],
            trustpilot_score=data["trustpilot_score"],
            reddit_sentiment=data["reddit_sentiment"],
            reddit_mentions_30d=data["reddit_mentions_30d"],
            top_complaints=data["top_complaints"],
            last_updated=datetime.utcnow().isoformat()
        )

    def _build_placeholder(self, company_name: str) -> SentimentData:
        return SentimentData(
            company_name=company_name,
            g2_score=0.0,
            g2_badges=[],
            capterra_score=0.0,
            trustpilot_score=0.0,
            reddit_sentiment="Unknown",
            reddit_mentions_30d=0,
            top_complaints=[],
            last_updated=datetime.utcnow().isoformat()
        )

if __name__ == "__main__":
    scraper = SentimentScraper()
    print("="*60)
    print("Sentiment Intelligence")
    print("="*60)
    for company in ["Phreesia", "Cedar"]:
        data = scraper.get_sentiment_data(company)
        print(f"\n{company}:")
        print(f"  G2: {data.g2_score}/5 {data.g2_badges}")
        print(f"  Trustpilot: {data.trustpilot_score}/5")
        print(f"  Reddit: {data.reddit_sentiment} ({data.reddit_mentions_30d} callouts)")
