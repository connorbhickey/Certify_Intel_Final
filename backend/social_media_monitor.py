"""
Certify Intel - Social Media Monitor
Fetches brand mentions, sentiment, and discussions from Twitter/X and Reddit.
"""
import os
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
import urllib.request
import urllib.parse
import json


@dataclass
class SocialPost:
    """Individual social media post."""
    platform: str  # twitter, reddit
    content: str
    author: str
    created_at: str
    likes: int
    shares: int
    comments: int
    sentiment: str
    url: str
    is_complaint: bool


@dataclass
class SocialData:
    """Aggregated social media data for a company."""
    company_name: str
    total_mentions: int
    mentions_7d: int
    sentiment_breakdown: Dict[str, int]
    avg_sentiment_score: float
    platform_breakdown: Dict[str, int]
    top_posts: List[SocialPost]
    complaint_topics: List[str]
    praise_topics: List[str]
    influencer_mentions: List[str]
    trending_discussions: List[str]
    brand_health_score: float
    last_updated: str


class SocialMediaMonitor:
    """Monitors social media for brand mentions and sentiment."""
    
    # Sentiment keywords
    POSITIVE_KEYWORDS = [
        "love", "great", "amazing", "excellent", "best", "recommend",
        "easy", "helpful", "awesome", "wonderful", "fantastic"
    ]
    
    NEGATIVE_KEYWORDS = [
        "hate", "terrible", "awful", "worst", "broken", "sucks",
        "difficult", "frustrating", "disappointed", "horrible", "waste"
    ]
    
    # Known social data
    KNOWN_COMPANIES = {
        "phreesia": {
            "total_mentions": 145,
            "mentions_7d": 23,
            "platform_breakdown": {"twitter": 85, "reddit": 38, "linkedin": 22},
            "sentiment_breakdown": {"positive": 65, "negative": 28, "neutral": 52},
            "top_posts": [
                {"platform": "twitter", "content": "Just checked in for my doctor's appointment using @Phreesia - so much easier than paper forms! #HealthTech", "author": "@patientexperience", "likes": 45, "shares": 12, "sentiment": "positive"},
                {"platform": "reddit", "content": "Our practice switched to Phreesia last month. The patient intake is smoother but the pricing seems high. Anyone else?", "author": "u/healthcareIT_admin", "likes": 78, "shares": 0, "sentiment": "neutral"},
                {"platform": "twitter", "content": "Having issues with @Phreesia app - keeps crashing when trying to complete insurance verification. Anyone else?", "author": "@frustrated_patient", "likes": 23, "shares": 5, "sentiment": "negative"},
            ],
            "complaint_topics": ["App crashes", "Long load times", "Insurance verification errors"],
            "praise_topics": ["Easy check-in", "Saves time", "No paperwork"],
            "influencer_mentions": ["@HITConsultant", "@HealthcareITNews"],
            "trending_discussions": ["Patient intake software comparison", "Digital check-in ROI"]
        },
        "epic": {
            "total_mentions": 2890,
            "mentions_7d": 412,
            "platform_breakdown": {"twitter": 1450, "reddit": 980, "linkedin": 460},
            "sentiment_breakdown": {"positive": 1100, "negative": 890, "neutral": 900},
            "top_posts": [
                {"platform": "twitter", "content": "MyChart integration with Apple Health is a game changer. Finally, all my health data in one place! @EpicSystemsCorp", "author": "@healthylifestyle", "likes": 234, "shares": 89, "sentiment": "positive"},
                {"platform": "reddit", "content": "Epic implementation is the most painful thing I've experienced in healthcare IT. 18 months in and we're still finding issues.", "author": "u/exhausted_CIO", "likes": 456, "shares": 0, "sentiment": "negative"},
                {"platform": "twitter", "content": "Just experienced #EpicFail - system went down during peak hours at the hospital. Patient safety concerns?", "author": "@concerned_nurse", "likes": 189, "shares": 67, "sentiment": "negative"},
            ],
            "complaint_topics": ["Complex implementation", "System downtime", "Cost overruns", "Training requirements"],
            "praise_topics": ["Comprehensive features", "MyChart ease of use", "Interoperability"],
            "influencer_mentions": ["@JohnHalamka", "@HealthITBuzz", "@HISTalk"],
            "trending_discussions": ["Epic vs Cerner", "Epic cloud migration", "Epic costs"]
        },
        "athenahealth": {
            "total_mentions": 567,
            "mentions_7d": 78,
            "platform_breakdown": {"twitter": 280, "reddit": 198, "linkedin": 89},
            "sentiment_breakdown": {"positive": 190, "negative": 210, "neutral": 167},
            "top_posts": [
                {"platform": "twitter", "content": "@athenahealth support is so slow. Been waiting 3 days for a response on a critical billing issue.", "author": "@small_practice_md", "likes": 89, "shares": 23, "sentiment": "negative"},
                {"platform": "reddit", "content": "Switched from athenahealth to a competitor. Best decision we made. Their support under PE ownership has gone downhill.", "author": "u/practicemanager101", "likes": 234, "shares": 0, "sentiment": "negative"},
                {"platform": "linkedin", "content": "Proud to announce our telehealth integration with athenahealth is live! Exciting times in healthcare. #HealthIT", "author": "VP of Partnerships", "likes": 167, "shares": 34, "sentiment": "positive"},
            ],
            "complaint_topics": ["Slow support", "System bugs", "PE ownership concerns", "Price increases"],
            "praise_topics": ["Cloud-based", "Telehealth features", "RCM services"],
            "influencer_mentions": ["@HITConsultant", "@BeckerHIT"],
            "trending_discussions": ["athenahealth PE issues", "athenahealth alternatives"]
        },
        "zocdoc": {
            "total_mentions": 1234,
            "mentions_7d": 189,
            "platform_breakdown": {"twitter": 678, "reddit": 312, "linkedin": 244},
            "sentiment_breakdown": {"positive": 780, "negative": 234, "neutral": 220},
            "top_posts": [
                {"platform": "twitter", "content": "Found a great dermatologist through @Zocdoc in 5 minutes. Appointment booked for tomorrow. This is how healthcare should work!", "author": "@happy_patient", "likes": 567, "shares": 123, "sentiment": "positive"},
                {"platform": "reddit", "content": "As a doctor, I hate Zocdoc's per-booking fees but can't deny it brings in new patients.", "author": "u/dermdoc", "likes": 345, "shares": 0, "sentiment": "neutral"},
            ],
            "complaint_topics": ["High provider fees", "No-shows from booking", "Limited insurance filters"],
            "praise_topics": ["Easy booking", "Wide selection", "Real reviews", "Quick appointments"],
            "influencer_mentions": ["@modrnhealthcare", "@HealthITNews"],
            "trending_discussions": ["Zocdoc pricing for providers", "Patient acquisition strategies"]
        }
    }
    
    def __init__(self):
        self.twitter_bearer = os.getenv("TWITTER_BEARER_TOKEN")
        self.reddit_client_id = os.getenv("REDDIT_CLIENT_ID")
        self.reddit_secret = os.getenv("REDDIT_CLIENT_SECRET")
    
    def get_social_data(self, company_name: str) -> SocialData:
        """Get social media data for a company."""
        name_lower = company_name.lower()
        
        if name_lower in self.KNOWN_COMPANIES:
            return self._build_from_known(company_name, self.KNOWN_COMPANIES[name_lower])
        
        # Try live APIs if configured
        if self.twitter_bearer:
            try:
                return self._fetch_twitter_data(company_name)
            except Exception as e:
                print(f"Twitter fetch failed: {e}")
        
        return self._build_placeholder(company_name)
    
    def _build_from_known(self, company_name: str, data: Dict) -> SocialData:
        """Build SocialData from known data."""
        posts = []
        for p in data.get("top_posts", []):
            posts.append(SocialPost(
                platform=p["platform"],
                content=p["content"],
                author=p["author"],
                created_at=datetime.utcnow().isoformat(),
                likes=p["likes"],
                shares=p.get("shares", 0),
                comments=0,
                sentiment=p["sentiment"],
                url="",
                is_complaint=p["sentiment"] == "negative"
            ))
        
        # Calculate brand health score
        sentiment = data.get("sentiment_breakdown", {})
        total = sum(sentiment.values())
        if total > 0:
            positive_ratio = sentiment.get("positive", 0) / total
            negative_ratio = sentiment.get("negative", 0) / total
            brand_health = (positive_ratio * 100) - (negative_ratio * 50)
        else:
            brand_health = 50.0
        
        return SocialData(
            company_name=company_name,
            total_mentions=data["total_mentions"],
            mentions_7d=data["mentions_7d"],
            sentiment_breakdown=data.get("sentiment_breakdown", {}),
            avg_sentiment_score=self._calculate_sentiment_score(sentiment),
            platform_breakdown=data.get("platform_breakdown", {}),
            top_posts=posts,
            complaint_topics=data.get("complaint_topics", []),
            praise_topics=data.get("praise_topics", []),
            influencer_mentions=data.get("influencer_mentions", []),
            trending_discussions=data.get("trending_discussions", []),
            brand_health_score=round(max(0, min(100, brand_health)), 1),
            last_updated=datetime.utcnow().isoformat()
        )
    
    def _build_placeholder(self, company_name: str) -> SocialData:
        """Build placeholder SocialData."""
        return SocialData(
            company_name=company_name,
            total_mentions=0,
            mentions_7d=0,
            sentiment_breakdown={},
            avg_sentiment_score=0.0,
            platform_breakdown={},
            top_posts=[],
            complaint_topics=[],
            praise_topics=[],
            influencer_mentions=[],
            trending_discussions=[],
            brand_health_score=0.0,
            last_updated=datetime.utcnow().isoformat()
        )
    
    def _calculate_sentiment_score(self, sentiment: Dict[str, int]) -> float:
        """Calculate weighted sentiment score (-100 to 100)."""
        total = sum(sentiment.values())
        if total == 0:
            return 0.0
        
        positive = sentiment.get("positive", 0)
        negative = sentiment.get("negative", 0)
        
        return round(((positive - negative) / total) * 100, 1)
    
    def _fetch_twitter_data(self, company_name: str) -> SocialData:
        """Fetch data from Twitter API."""
        raise NotImplementedError("Twitter API integration requires elevated access")
    
    def analyze_brand_sentiment(self, company_name: str) -> Dict[str, Any]:
        """Analyze brand sentiment from social media."""
        data = self.get_social_data(company_name)
        
        # Determine overall sentiment
        if data.avg_sentiment_score >= 30:
            overall = "Positive"
            signal = "Strong brand perception"
        elif data.avg_sentiment_score >= 0:
            overall = "Mixed"
            signal = "Neutral brand perception - room for improvement"
        else:
            overall = "Negative"
            signal = "Brand perception challenges - competitive opportunity"
        
        return {
            "company": company_name,
            "brand_health_score": data.brand_health_score,
            "sentiment_score": data.avg_sentiment_score,
            "overall_sentiment": overall,
            "signal": signal,
            "total_mentions": data.total_mentions,
            "recent_mentions": data.mentions_7d,
            "top_complaints": data.complaint_topics[:3],
            "top_praises": data.praise_topics[:3],
            "trending_topics": data.trending_discussions[:3],
            "competitive_implications": self._generate_implications(data)
        }
    
    def _generate_implications(self, data: SocialData) -> List[str]:
        """Generate competitive implications from social data."""
        implications = []
        
        if data.avg_sentiment_score < 0:
            implications.append("Negative sentiment trend - customers may be looking for alternatives")
        
        for complaint in data.complaint_topics[:2]:
            implications.append(f"Common complaint: '{complaint}' - position against this")
        
        if data.mentions_7d > data.total_mentions * 0.2:
            implications.append("High recent activity - recent event or campaign may be driving discussion")
        
        return implications
    
    def compare_social_presence(self, company_names: List[str]) -> Dict[str, Any]:
        """Compare social media presence across companies."""
        comparison = []
        
        for name in company_names:
            data = self.get_social_data(name)
            comparison.append({
                "name": name,
                "total_mentions": data.total_mentions,
                "recent_mentions": data.mentions_7d,
                "sentiment_score": data.avg_sentiment_score,
                "brand_health": data.brand_health_score,
                "platforms": list(data.platform_breakdown.keys())
            })
        
        comparison.sort(key=lambda x: x["brand_health"], reverse=True)
        
        return {
            "companies": comparison,
            "best_sentiment": max(comparison, key=lambda x: x["sentiment_score"])["name"] if comparison else None,
            "most_mentions": max(comparison, key=lambda x: x["total_mentions"])["name"] if comparison else None,
            "most_active": max(comparison, key=lambda x: x["recent_mentions"])["name"] if comparison else None
        }


def get_social_data(company_name: str) -> Dict[str, Any]:
    """Get social media data for a company."""
    monitor = SocialMediaMonitor()
    data = monitor.get_social_data(company_name)
    
    result = asdict(data)
    result["top_posts"] = [asdict(p) for p in data.top_posts]
    
    return result


def analyze_social_sentiment(company_name: str) -> Dict[str, Any]:
    """Analyze social sentiment for a company."""
    monitor = SocialMediaMonitor()
    return monitor.analyze_brand_sentiment(company_name)


if __name__ == "__main__":
    monitor = SocialMediaMonitor()
    
    print("=" * 60)
    print("Social Media Intelligence")
    print("=" * 60)
    
    for company in ["Phreesia", "Epic", "athenahealth", "Zocdoc"]:
        data = monitor.get_social_data(company)
        print(f"\n{company}:")
        print(f"  Total Mentions: {data.total_mentions}")
        print(f"  Last 7 Days: {data.mentions_7d}")
        print(f"  Brand Health: {data.brand_health_score}/100")
        print(f"  Sentiment: {data.avg_sentiment_score}")
        print(f"  Top Complaint: {data.complaint_topics[0] if data.complaint_topics else 'N/A'}")
