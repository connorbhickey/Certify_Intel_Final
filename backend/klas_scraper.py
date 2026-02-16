"""
Certify Intel - KLAS Research Scraper
Fetches healthcare IT vendor ratings and satisfaction scores.
"""
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class KLASRating:
    """KLAS rating for a product."""
    product_name: str
    category: str
    overall_score: float
    culture_score: float
    operations_score: float
    relationship_score: float
    product_score: float
    value_score: float
    total_evaluations: int
    would_buy_again: float
    rank_in_category: int


@dataclass
class KLASData:
    """Company data from KLAS Research."""
    company_name: str
    overall_klas_score: float
    vendor_grade: str  # A+, A, B+, B, C, etc.
    products_rated: List[KLASRating]
    best_in_klas_awards: List[str]
    category_leader: List[str]
    peer_insights: List[str]
    customer_sentiment: str
    implementation_score: float
    support_score: float
    upgrade_score: float
    last_updated: str


class KLASResearchScraper:
    """Scrapes healthcare IT ratings from KLAS Research."""
    
    # Known KLAS data (simulated - real KLAS requires subscription)
    KNOWN_COMPANIES = {
        "phreesia": {
            "overall_klas_score": 84.2,
            "vendor_grade": "A",
            "products_rated": [
                {
                    "product_name": "Phreesia Patient Intake",
                    "category": "Patient Intake Management",
                    "overall_score": 85.1,
                    "culture_score": 86.0,
                    "operations_score": 83.5,
                    "relationship_score": 87.2,
                    "product_score": 84.0,
                    "value_score": 82.5,
                    "total_evaluations": 127,
                    "would_buy_again": 89,
                    "rank_in_category": 2
                },
                {
                    "product_name": "Phreesia Payment Assurance",
                    "category": "Patient Payments",
                    "overall_score": 83.5,
                    "culture_score": 85.0,
                    "operations_score": 82.0,
                    "relationship_score": 86.0,
                    "product_score": 82.5,
                    "value_score": 81.0,
                    "total_evaluations": 89,
                    "would_buy_again": 85,
                    "rank_in_category": 3
                }
            ],
            "best_in_klas_awards": [],
            "category_leader": ["Patient Intake Management"],
            "peer_insights": [
                "Strong patient adoption rates",
                "Easy to configure workflows",
                "Good EHR integrations",
                "Support responsive to issues"
            ],
            "customer_sentiment": "Positive",
            "implementation_score": 81.5,
            "support_score": 85.0,
            "upgrade_score": 79.5
        },
        "clearwave": {
            "overall_klas_score": 88.5,
            "vendor_grade": "A+",
            "products_rated": [
                {
                    "product_name": "Clearwave Patient Engagement",
                    "category": "Patient Intake Management",
                    "overall_score": 88.5,
                    "culture_score": 90.0,
                    "operations_score": 87.5,
                    "relationship_score": 91.0,
                    "product_score": 86.5,
                    "value_score": 87.0,
                    "total_evaluations": 78,
                    "would_buy_again": 94,
                    "rank_in_category": 1
                }
            ],
            "best_in_klas_awards": ["Best in KLAS 2023 - Patient Intake"],
            "category_leader": ["Patient Intake Management", "Self-Service Patient Check-In"],
            "peer_insights": [
                "Exceptional customer service",
                "Easy implementation",
                "Great kiosk interface",
                "Proactive account management"
            ],
            "customer_sentiment": "Very Positive",
            "implementation_score": 89.0,
            "support_score": 92.0,
            "upgrade_score": 86.0
        },
        "epic": {
            "overall_klas_score": 86.8,
            "vendor_grade": "A",
            "products_rated": [
                {
                    "product_name": "Epic EHR",
                    "category": "Acute Care EMR",
                    "overall_score": 87.5,
                    "culture_score": 85.0,
                    "operations_score": 88.0,
                    "relationship_score": 84.5,
                    "product_score": 89.5,
                    "value_score": 80.5,
                    "total_evaluations": 452,
                    "would_buy_again": 91,
                    "rank_in_category": 1
                },
                {
                    "product_name": "MyChart",
                    "category": "Patient Portal",
                    "overall_score": 88.0,
                    "culture_score": 86.0,
                    "operations_score": 87.5,
                    "relationship_score": 85.0,
                    "product_score": 90.0,
                    "value_score": 82.0,
                    "total_evaluations": 312,
                    "would_buy_again": 93,
                    "rank_in_category": 1
                }
            ],
            "best_in_klas_awards": ["Best in KLAS 2023 - Large Health System EMR", "Best in KLAS 2023 - Patient Portal"],
            "category_leader": ["Acute Care EMR", "Patient Portal", "Revenue Cycle", "Population Health"],
            "peer_insights": [
                "Industry-leading functionality",
                "Strong clinical workflows",
                "Continuous innovation",
                "High total cost of ownership"
            ],
            "customer_sentiment": "Positive",
            "implementation_score": 78.0,
            "support_score": 82.0,
            "upgrade_score": 84.0
        },
        "athenahealth": {
            "overall_klas_score": 77.5,
            "vendor_grade": "B+",
            "products_rated": [
                {
                    "product_name": "athenaOne",
                    "category": "Small Practice Ambulatory EMR/PM",
                    "overall_score": 78.0,
                    "culture_score": 76.0,
                    "operations_score": 77.5,
                    "relationship_score": 75.5,
                    "product_score": 80.0,
                    "value_score": 74.0,
                    "total_evaluations": 289,
                    "would_buy_again": 72,
                    "rank_in_category": 4
                }
            ],
            "best_in_klas_awards": [],
            "category_leader": [],
            "peer_insights": [
                "Cloud-based convenience",
                "Good RCM services",
                "Support response time issues",
                "Implementation challenges"
            ],
            "customer_sentiment": "Mixed",
            "implementation_score": 72.0,
            "support_score": 71.0,
            "upgrade_score": 75.0
        },
        "waystar": {
            "overall_klas_score": 82.3,
            "vendor_grade": "A-",
            "products_rated": [
                {
                    "product_name": "Waystar Revenue Cycle",
                    "category": "Claims & Clearinghouse",
                    "overall_score": 82.5,
                    "culture_score": 81.0,
                    "operations_score": 83.0,
                    "relationship_score": 82.0,
                    "product_score": 84.0,
                    "value_score": 80.0,
                    "total_evaluations": 198,
                    "would_buy_again": 84,
                    "rank_in_category": 2
                }
            ],
            "best_in_klas_awards": [],
            "category_leader": ["Healthcare Claims & Clearinghouse"],
            "peer_insights": [
                "Strong claims management",
                "Good analytics dashboards",
                "Post-merger integration issues",
                "Multiple legacy platforms"
            ],
            "customer_sentiment": "Mostly Positive",
            "implementation_score": 79.0,
            "support_score": 80.0,
            "upgrade_score": 77.0
        }
    }
    
    def __init__(self):
        pass
    
    def get_klas_data(self, company_name: str) -> KLASData:
        """Get KLAS Research data for a company. Returns unavailable status when no real API is configured."""
        # KNOWN_COMPANIES contains fabricated demo data - never return it as real
        return self._build_placeholder(company_name)
    
    def _build_from_known(self, company_name: str, data: Dict) -> KLASData:
        """Build KLASData from known data."""
        products = [
            KLASRating(**p) for p in data.get("products_rated", [])
        ]
        
        return KLASData(
            company_name=company_name,
            overall_klas_score=data["overall_klas_score"],
            vendor_grade=data["vendor_grade"],
            products_rated=products,
            best_in_klas_awards=data.get("best_in_klas_awards", []),
            category_leader=data.get("category_leader", []),
            peer_insights=data.get("peer_insights", []),
            customer_sentiment=data.get("customer_sentiment", "Unknown"),
            implementation_score=data.get("implementation_score", 0),
            support_score=data.get("support_score", 0),
            upgrade_score=data.get("upgrade_score", 0),
            last_updated=datetime.utcnow().isoformat()
        )
    
    def _build_placeholder(self, company_name: str) -> KLASData:
        """Build placeholder KLASData."""
        return KLASData(
            company_name=company_name,
            overall_klas_score=0.0,
            vendor_grade="Not Rated",
            products_rated=[],
            best_in_klas_awards=[],
            category_leader=[],
            peer_insights=[],
            customer_sentiment="Unknown",
            implementation_score=0.0,
            support_score=0.0,
            upgrade_score=0.0,
            last_updated=datetime.utcnow().isoformat()
        )
    
    def analyze_competitive_position(self, company_name: str) -> Dict[str, Any]:
        """Analyze competitive position from KLAS data."""
        data = self.get_klas_data(company_name)
        
        strengths = []
        weaknesses = []
        
        # Analyze scores
        if data.overall_klas_score >= 85:
            strengths.append("Industry-leading customer satisfaction")
        elif data.overall_klas_score >= 80:
            strengths.append("Above-average customer satisfaction")
        elif data.overall_klas_score < 75:
            weaknesses.append("Below-average customer satisfaction")
        
        if data.support_score >= 85:
            strengths.append("Excellent customer support")
        elif data.support_score < 75:
            weaknesses.append("Support rated below expectations")
        
        if data.implementation_score >= 85:
            strengths.append("Smooth implementation experiences")
        elif data.implementation_score < 75:
            weaknesses.append("Implementation challenges reported")
        
        if data.best_in_klas_awards:
            strengths.append(f"Best in KLAS winner: {', '.join(data.best_in_klas_awards)}")
        
        # Generate sales implications
        implications = []
        if weaknesses:
            implications.append(f"Competitive vulnerability: {'; '.join(weaknesses[:2])}")
        if data.customer_sentiment in ["Mixed", "Negative"]:
            implications.append("Customer churn opportunity - sentiment is mixed")
        if data.support_score < 80:
            implications.append("Emphasize Certify's support quality in competitive deals")
        
        return {
            "company": company_name,
            "klas_score": data.overall_klas_score,
            "grade": data.vendor_grade,
            "sentiment": data.customer_sentiment,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "peer_insights": data.peer_insights[:3],
            "sales_implications": implications,
            "awards": data.best_in_klas_awards,
            "category_positions": data.category_leader
        }
    
    def compare_klas_scores(self, company_names: List[str]) -> Dict[str, Any]:
        """Compare KLAS scores across companies."""
        comparison = []
        
        for name in company_names:
            data = self.get_klas_data(name)
            if data.overall_klas_score > 0:
                comparison.append({
                    "name": name,
                    "score": data.overall_klas_score,
                    "grade": data.vendor_grade,
                    "support": data.support_score,
                    "implementation": data.implementation_score,
                    "would_buy_again": max([p.would_buy_again for p in data.products_rated]) if data.products_rated else 0,
                    "awards": len(data.best_in_klas_awards)
                })
        
        comparison.sort(key=lambda x: x["score"], reverse=True)
        
        return {
            "companies": comparison,
            "highest_rated": comparison[0]["name"] if comparison else None,
            "best_support": max(comparison, key=lambda x: x["support"])["name"] if comparison else None,
            "easiest_implementation": max(comparison, key=lambda x: x["implementation"])["name"] if comparison else None
        }


def get_klas_data(company_name: str) -> Dict[str, Any]:
    """Get KLAS Research data for a company."""
    scraper = KLASResearchScraper()
    data = scraper.get_klas_data(company_name)
    
    result = asdict(data)
    result["products_rated"] = [asdict(p) for p in data.products_rated]
    
    return result


if __name__ == "__main__":
    scraper = KLASResearchScraper()
    
    print("=" * 60)
    print("KLAS Research Healthcare IT Ratings")
    print("=" * 60)
    
    for company in ["Phreesia", "Clearwave", "Epic", "athenahealth"]:
        data = scraper.get_klas_data(company)
        print(f"\n{company}:")
        print(f"  KLAS Score: {data.overall_klas_score}/100 (Grade: {data.vendor_grade})")
        print(f"  Support: {data.support_score}, Implementation: {data.implementation_score}")
        print(f"  Sentiment: {data.customer_sentiment}")
        if data.best_in_klas_awards:
            print(f"  Awards: {', '.join(data.best_in_klas_awards)}")
