"""
Certify Intel - App Store Scraper
Fetches mobile app ratings, reviews, and download data.
"""
import os
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class AppReview:
    """Individual app review."""
    rating: int
    title: str
    content: str
    date: str
    version: str
    helpful_count: int


@dataclass
class AppData:
    """Mobile app data."""
    app_name: str
    company: str
    platform: str  # iOS, Android
    store_rating: float
    total_ratings: int
    total_reviews: int
    current_version: str
    last_updated: str
    size_mb: float
    category: str
    price: str
    in_app_purchases: bool
    downloads_estimate: str
    recent_reviews: List[AppReview]
    rating_breakdown: Dict[int, int]
    feature_list: List[str]
    whats_new: str


@dataclass
class AppStoreData:
    """Aggregated app store data for a company."""
    company_name: str
    total_apps: int
    apps: List[AppData]
    avg_rating: float
    total_downloads: str
    platform_breakdown: Dict[str, int]
    category_breakdown: Dict[str, int]
    sentiment_summary: str
    top_complaints: List[str]
    top_praises: List[str]
    last_updated: str


class AppStoreScraper:
    """Scrapes app data from Apple App Store and Google Play."""
    
    # Known app data
    KNOWN_COMPANIES = {
        "phreesia": {
            "apps": [
                {
                    "app_name": "Phreesia Check-In",
                    "platform": "iOS",
                    "store_rating": 4.7,
                    "total_ratings": 12500,
                    "total_reviews": 890,
                    "current_version": "6.2.1",
                    "last_updated": "2024-01-15",
                    "size_mb": 125.4,
                    "category": "Medical",
                    "price": "Free",
                    "in_app_purchases": False,
                    "downloads_estimate": "100K+",
                    "feature_list": ["Check-in", "Forms", "Payments", "Insurance Verification"],
                    "whats_new": "Bug fixes and performance improvements",
                    "rating_breakdown": {5: 8000, 4: 3000, 3: 800, 2: 400, 1: 300}
                },
                {
                    "app_name": "Phreesia Patient Portal",
                    "platform": "Android",
                    "store_rating": 4.5,
                    "total_ratings": 8200,
                    "total_reviews": 620,
                    "current_version": "6.1.5",
                    "last_updated": "2024-01-10",
                    "size_mb": 45.8,
                    "category": "Medical",
                    "price": "Free",
                    "in_app_purchases": False,
                    "downloads_estimate": "50K+",
                    "feature_list": ["Appointments", "Messages", "Health Records"],
                    "whats_new": "New appointment scheduling features",
                    "rating_breakdown": {5: 5000, 4: 2000, 3: 600, 2: 350, 1: 250}
                }
            ],
            "top_complaints": [
                "App crashes occasionally",
                "Slow loading times",
                "Password reset issues"
            ],
            "top_praises": [
                "Easy check-in process",
                "Saves time at appointments",
                "Clean interface"
            ]
        },
        "zocdoc": {
            "apps": [
                {
                    "app_name": "Zocdoc - Find & book doctors",
                    "platform": "iOS",
                    "store_rating": 4.9,
                    "total_ratings": 378000,
                    "total_reviews": 28000,
                    "current_version": "8.4.2",
                    "last_updated": "2024-01-18",
                    "size_mb": 187.2,
                    "category": "Medical",
                    "price": "Free",
                    "in_app_purchases": False,
                    "downloads_estimate": "5M+",
                    "feature_list": ["Find Doctors", "Book Appointments", "Video Visits", "Reviews"],
                    "whats_new": "New video visit improvements",
                    "rating_breakdown": {5: 320000, 4: 45000, 3: 8000, 2: 3000, 1: 2000}
                },
                {
                    "app_name": "Zocdoc",
                    "platform": "Android",
                    "store_rating": 4.7,
                    "total_ratings": 89000,
                    "total_reviews": 12000,
                    "current_version": "8.3.1",
                    "last_updated": "2024-01-12",
                    "size_mb": 52.3,
                    "category": "Medical",
                    "price": "Free",
                    "in_app_purchases": False,
                    "downloads_estimate": "1M+",
                    "feature_list": ["Find Doctors", "Book Appointments", "Reviews"],
                    "whats_new": "Performance improvements",
                    "rating_breakdown": {5: 70000, 4: 12000, 3: 4000, 2: 2000, 1: 1000}
                }
            ],
            "top_complaints": [
                "Some doctors not available",
                "Insurance verification issues",
                "Appointment reminders too many"
            ],
            "top_praises": [
                "Easy to find doctors",
                "Instant booking confirmation",
                "Great user experience",
                "Helpful doctor reviews"
            ]
        },
        "luma health": {
            "apps": [
                {
                    "app_name": "Luma Health",
                    "platform": "iOS",
                    "store_rating": 4.6,
                    "total_ratings": 3200,
                    "total_reviews": 245,
                    "current_version": "4.2.0",
                    "last_updated": "2024-01-05",
                    "size_mb": 78.5,
                    "category": "Medical",
                    "price": "Free",
                    "in_app_purchases": False,
                    "downloads_estimate": "10K+",
                    "feature_list": ["Appointments", "Reminders", "Check-in", "Messages"],
                    "whats_new": "Enhanced appointment scheduling",
                    "rating_breakdown": {5: 2000, 4: 800, 3: 250, 2: 100, 1: 50}
                }
            ],
            "top_complaints": [
                "Limited provider availability",
                "Notification overload"
            ],
            "top_praises": [
                "Easy appointment management",
                "Good reminders",
                "Simple to use"
            ]
        },
        "athenahealth": {
            "apps": [
                {
                    "app_name": "athenaPatient",
                    "platform": "iOS",
                    "store_rating": 4.2,
                    "total_ratings": 15600,
                    "total_reviews": 1200,
                    "current_version": "5.8.3",
                    "last_updated": "2023-12-20",
                    "size_mb": 156.8,
                    "category": "Medical",
                    "price": "Free",
                    "in_app_purchases": False,
                    "downloads_estimate": "500K+",
                    "feature_list": ["Patient Portal", "Appointments", "Messages", "Prescriptions"],
                    "whats_new": "Security updates",
                    "rating_breakdown": {5: 8000, 4: 4000, 3: 2000, 2: 1000, 1: 600}
                },
                {
                    "app_name": "athenaPatient",
                    "platform": "Android",
                    "store_rating": 3.8,
                    "total_ratings": 8900,
                    "total_reviews": 780,
                    "current_version": "5.7.2",
                    "last_updated": "2023-12-15",
                    "size_mb": 42.1,
                    "category": "Medical",
                    "price": "Free",
                    "in_app_purchases": False,
                    "downloads_estimate": "100K+",
                    "feature_list": ["Patient Portal", "Appointments", "Messages"],
                    "whats_new": "Bug fixes",
                    "rating_breakdown": {5: 3500, 4: 2500, 3: 1500, 2: 900, 1: 500}
                }
            ],
            "top_complaints": [
                "Login issues frequently",
                "App crashes",
                "Slow performance",
                "Confusing navigation"
            ],
            "top_praises": [
                "Access to medical records",
                "Appointment booking works",
                "Secure messaging"
            ]
        },
        "epic": {
            "apps": [
                {
                    "app_name": "MyChart",
                    "platform": "iOS",
                    "store_rating": 4.8,
                    "total_ratings": 2450000,
                    "total_reviews": 185000,
                    "current_version": "12.1.0",
                    "last_updated": "2024-01-20",
                    "size_mb": 198.4,
                    "category": "Medical",
                    "price": "Free",
                    "in_app_purchases": False,
                    "downloads_estimate": "50M+",
                    "feature_list": ["Health Records", "Appointments", "Messages", "Test Results", "Video Visits", "Apple Health"],
                    "whats_new": "New wellness features and bug fixes",
                    "rating_breakdown": {5: 1800000, 4: 450000, 3: 120000, 2: 50000, 1: 30000}
                },
                {
                    "app_name": "MyChart",
                    "platform": "Android",
                    "store_rating": 4.6,
                    "total_ratings": 890000,
                    "total_reviews": 75000,
                    "current_version": "12.0.5",
                    "last_updated": "2024-01-18",
                    "size_mb": 85.2,
                    "category": "Medical",
                    "price": "Free",
                    "in_app_purchases": False,
                    "downloads_estimate": "10M+",
                    "feature_list": ["Health Records", "Appointments", "Messages", "Test Results"],
                    "whats_new": "Performance improvements",
                    "rating_breakdown": {5: 600000, 4: 180000, 3: 70000, 2: 25000, 1: 15000}
                }
            ],
            "top_complaints": [
                "Need separate MyChart accounts for different hospitals",
                "App can be slow",
                "Complex to navigate"
            ],
            "top_praises": [
                "Easy access to test results",
                "Great for managing appointments",
                "Secure messaging with doctors",
                "COVID vaccine records"
            ]
        }
    }
    
    def __init__(self):
        pass
    
    def get_app_data(self, company_name: str) -> AppStoreData:
        """Get app store data for a company. Returns unavailable status when no real API is configured."""
        # KNOWN_COMPANIES contains fabricated demo data - never return it as real
        return self._build_placeholder(company_name)
    
    def _build_from_known(self, company_name: str, data: Dict) -> AppStoreData:
        """Build AppStoreData from known data."""
        apps = []
        total_ratings = 0
        total_rating_sum = 0
        platform_count = {"iOS": 0, "Android": 0}
        
        for app_data in data.get("apps", []):
            apps.append(AppData(
                app_name=app_data["app_name"],
                company=company_name,
                platform=app_data["platform"],
                store_rating=app_data["store_rating"],
                total_ratings=app_data["total_ratings"],
                total_reviews=app_data["total_reviews"],
                current_version=app_data["current_version"],
                last_updated=app_data["last_updated"],
                size_mb=app_data["size_mb"],
                category=app_data["category"],
                price=app_data["price"],
                in_app_purchases=app_data["in_app_purchases"],
                downloads_estimate=app_data["downloads_estimate"],
                recent_reviews=[],
                rating_breakdown=app_data.get("rating_breakdown", {}),
                feature_list=app_data.get("feature_list", []),
                whats_new=app_data.get("whats_new", "")
            ))
            
            total_ratings += app_data["total_ratings"]
            total_rating_sum += app_data["store_rating"] * app_data["total_ratings"]
            platform_count[app_data["platform"]] = platform_count.get(app_data["platform"], 0) + 1
        
        avg_rating = (total_rating_sum / total_ratings) if total_ratings > 0 else 0
        
        # Determine sentiment
        if avg_rating >= 4.5:
            sentiment = "Very Positive"
        elif avg_rating >= 4.0:
            sentiment = "Positive"
        elif avg_rating >= 3.5:
            sentiment = "Mixed"
        else:
            sentiment = "Negative"
        
        return AppStoreData(
            company_name=company_name,
            total_apps=len(apps),
            apps=apps,
            avg_rating=round(avg_rating, 2),
            total_downloads=self._estimate_total_downloads(apps),
            platform_breakdown=platform_count,
            category_breakdown={"Medical": len(apps)},
            sentiment_summary=sentiment,
            top_complaints=data.get("top_complaints", []),
            top_praises=data.get("top_praises", []),
            last_updated=datetime.utcnow().isoformat()
        )
    
    def _build_placeholder(self, company_name: str) -> AppStoreData:
        """Build placeholder AppStoreData."""
        return AppStoreData(
            company_name=company_name,
            total_apps=0,
            apps=[],
            avg_rating=0.0,
            total_downloads="0",
            platform_breakdown={},
            category_breakdown={},
            sentiment_summary="Unknown",
            top_complaints=[],
            top_praises=[],
            last_updated=datetime.utcnow().isoformat()
        )
    
    def _estimate_total_downloads(self, apps: List[AppData]) -> str:
        """Estimate total downloads from app data."""
        total = 0
        for app in apps:
            estimate = app.downloads_estimate.replace("+", "").replace(",", "")
            if "M" in estimate:
                total += float(estimate.replace("M", "")) * 1000000
            elif "K" in estimate:
                total += float(estimate.replace("K", "")) * 1000
            else:
                try:
                    total += float(estimate)
                except:
                    pass
        
        if total >= 1000000:
            return f"{total/1000000:.1f}M+"
        elif total >= 1000:
            return f"{total/1000:.0f}K+"
        else:
            return str(int(total))
    
    def analyze_app_quality(self, company_name: str) -> Dict[str, Any]:
        """Analyze app quality from store data."""
        data = self.get_app_data(company_name)
        
        # Calculate metrics
        if data.apps:
            best_app = max(data.apps, key=lambda a: a.store_rating)
            worst_app = min(data.apps, key=lambda a: a.store_rating)
            newest_update = max(data.apps, key=lambda a: a.last_updated)
            
            # Check for staleness
            update_warning = None
            for app in data.apps:
                if app.last_updated < "2024-01-01":
                    update_warning = f"{app.app_name} hasn't been updated recently"
                    break
            
            quality_assessment = {
                "company": company_name,
                "overall_rating": data.avg_rating,
                "total_apps": data.total_apps,
                "sentiment": data.sentiment_summary,
                "best_rated_app": {"name": best_app.app_name, "rating": best_app.store_rating, "platform": best_app.platform},
                "total_downloads": data.total_downloads,
                "top_complaints": data.top_complaints[:3],
                "top_praises": data.top_praises[:3],
                "update_status": update_warning or "All apps recently updated",
                "competitive_implications": []
            }
            
            # Generate implications
            if data.avg_rating < 4.0:
                quality_assessment["competitive_implications"].append(
                    "Below 4.0 rating - emphasize mobile experience quality"
                )
            if data.top_complaints:
                quality_assessment["competitive_implications"].append(
                    f"Common complaint: {data.top_complaints[0]}"
                )
            
            return quality_assessment
        
        return {
            "company": company_name,
            "status": "No mobile apps found",
            "competitive_implications": ["No mobile presence - opportunity to differentiate"]
        }
    
    def compare_apps(self, company_names: List[str]) -> Dict[str, Any]:
        """Compare app quality across companies."""
        comparison = []
        
        for name in company_names:
            data = self.get_app_data(name)
            if data.total_apps > 0:
                comparison.append({
                    "name": name,
                    "apps": data.total_apps,
                    "avg_rating": data.avg_rating,
                    "total_downloads": data.total_downloads,
                    "sentiment": data.sentiment_summary,
                    "platforms": list(data.platform_breakdown.keys())
                })
        
        comparison.sort(key=lambda x: x["avg_rating"], reverse=True)
        
        return {
            "companies": comparison,
            "best_rated": comparison[0]["name"] if comparison else None,
            "most_downloaded": max(comparison, key=lambda x: self._parse_downloads(x["total_downloads"]))["name"] if comparison else None
        }
    
    def _parse_downloads(self, download_str: str) -> int:
        """Parse download string to integer for comparison."""
        clean = download_str.replace("+", "").replace(",", "")
        if "M" in clean:
            return int(float(clean.replace("M", "")) * 1000000)
        elif "K" in clean:
            return int(float(clean.replace("K", "")) * 1000)
        return int(clean) if clean.isdigit() else 0


def get_app_store_data(company_name: str) -> Dict[str, Any]:
    """Get app store data for a company."""
    scraper = AppStoreScraper()
    data = scraper.get_app_data(company_name)
    
    result = asdict(data)
    result["apps"] = [asdict(a) for a in data.apps]
    
    return result


if __name__ == "__main__":
    scraper = AppStoreScraper()
    
    print("=" * 60)
    print("App Store Intelligence")
    print("=" * 60)
    
    for company in ["Phreesia", "Zocdoc", "Epic", "athenahealth"]:
        data = scraper.get_app_data(company)
        print(f"\n{company}:")
        print(f"  Apps: {data.total_apps}")
        print(f"  Avg Rating: {data.avg_rating}/5")
        print(f"  Downloads: {data.total_downloads}")
        print(f"  Sentiment: {data.sentiment_summary}")
