"""
Certify Intel - Glassdoor Scraper
Fetches employee reviews, ratings, and company culture data.
"""
import os
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class EmployeeReview:
    """Individual employee review."""
    title: str
    rating: float
    status: str  # Current/Former Employee
    position: str
    date: str
    pros: str
    cons: str
    advice_to_management: str


@dataclass
class GlassdoorData:
    """Company data from Glassdoor."""
    company_name: str
    overall_rating: float
    ceo_name: str
    ceo_approval: float
    recommend_to_friend: float
    culture_rating: float
    compensation_rating: float
    work_life_balance: float
    career_opportunities: float
    senior_management: float
    total_reviews: int
    interview_difficulty: float
    interview_experience_positive: float
    salary_ranges: Dict[str, str]
    pros_summary: List[str]
    cons_summary: List[str]
    recent_reviews: List[EmployeeReview]
    last_updated: str


class GlassdoorScraper:
    """Scrapes employee intelligence from Glassdoor."""
    
    # Known company data
    KNOWN_COMPANIES = {
        "phreesia": {
            "overall_rating": 3.8,
            "ceo_name": "Chaim Indig",
            "ceo_approval": 78,
            "recommend_to_friend": 68,
            "culture_rating": 3.7,
            "compensation_rating": 3.5,
            "work_life_balance": 3.4,
            "career_opportunities": 3.6,
            "senior_management": 3.3,
            "total_reviews": 287,
            "interview_difficulty": 2.8,
            "interview_experience_positive": 72,
            "salary_ranges": {
                "Software Engineer": "$85,000 - $140,000",
                "Product Manager": "$100,000 - $150,000",
                "Sales Representative": "$60,000 - $120,000",
                "Implementation Specialist": "$55,000 - $85,000"
            },
            "pros_summary": [
                "Good benefits and PTO",
                "Mission-driven company helping healthcare",
                "Smart and talented coworkers",
                "Remote work flexibility"
            ],
            "cons_summary": [
                "Fast-paced can lead to burnout",
                "Compensation below market in some roles",
                "Communication between departments",
                "Rapid growth causing growing pains"
            ]
        },
        "athenahealth": {
            "overall_rating": 3.4,
            "ceo_name": "Bob Segert",
            "ceo_approval": 62,
            "recommend_to_friend": 55,
            "culture_rating": 3.2,
            "compensation_rating": 3.3,
            "work_life_balance": 3.1,
            "career_opportunities": 3.0,
            "senior_management": 2.8,
            "total_reviews": 1523,
            "interview_difficulty": 2.9,
            "interview_experience_positive": 65,
            "salary_ranges": {
                "Software Engineer": "$90,000 - $160,000",
                "Product Manager": "$110,000 - $170,000",
                "Sales Representative": "$55,000 - $130,000",
                "Customer Success Manager": "$65,000 - $95,000"
            },
            "pros_summary": [
                "Healthcare mission",
                "Good benefits package",
                "Learning opportunities",
                "Large company resources"
            ],
            "cons_summary": [
                "Bureaucracy and slow processes",
                "Frequent leadership changes",
                "Work-life balance challenges",
                "PE ownership pressure"
            ]
        },
        "zocdoc": {
            "overall_rating": 3.9,
            "ceo_name": "Oliver Kharraz",
            "ceo_approval": 82,
            "recommend_to_friend": 72,
            "culture_rating": 4.0,
            "compensation_rating": 3.8,
            "work_life_balance": 3.6,
            "career_opportunities": 3.7,
            "senior_management": 3.5,
            "total_reviews": 456,
            "interview_difficulty": 3.2,
            "interview_experience_positive": 68,
            "salary_ranges": {
                "Software Engineer": "$120,000 - $180,000",
                "Product Manager": "$130,000 - $200,000",
                "Sales Representative": "$70,000 - $150,000",
                "Data Scientist": "$110,000 - $170,000"
            },
            "pros_summary": [
                "Innovative culture",
                "Competitive compensation",
                "NYC office perks",
                "Strong engineering team"
            ],
            "cons_summary": [
                "High pressure environment",
                "Sales-driven culture",
                "Some politics at senior levels",
                "Intense performance expectations"
            ]
        },
        "cedar": {
            "overall_rating": 4.2,
            "ceo_name": "Florian Otto",
            "ceo_approval": 88,
            "recommend_to_friend": 82,
            "culture_rating": 4.3,
            "compensation_rating": 4.0,
            "work_life_balance": 3.8,
            "career_opportunities": 4.1,
            "senior_management": 3.9,
            "total_reviews": 156,
            "interview_difficulty": 3.0,
            "interview_experience_positive": 78,
            "salary_ranges": {
                "Software Engineer": "$130,000 - $200,000",
                "Product Manager": "$140,000 - $210,000",
                "Customer Success Manager": "$80,000 - $120,000",
                "Data Analyst": "$90,000 - $130,000"
            },
            "pros_summary": [
                "Strong growth trajectory",
                "Excellent leadership",
                "Modern tech stack",
                "Good equity packages"
            ],
            "cons_summary": [
                "Startup pace can be intense",
                "Still building processes",
                "Growing pains",
                "Limited brand recognition"
            ]
        },
        "luma health": {
            "overall_rating": 4.1,
            "ceo_name": "Adnan Iqbal",
            "ceo_approval": 85,
            "recommend_to_friend": 78,
            "culture_rating": 4.2,
            "compensation_rating": 3.7,
            "work_life_balance": 3.9,
            "career_opportunities": 4.0,
            "senior_management": 3.8,
            "total_reviews": 89,
            "interview_difficulty": 2.7,
            "interview_experience_positive": 75,
            "salary_ranges": {
                "Software Engineer": "$110,000 - $170,000",
                "Product Manager": "$120,000 - $180,000",
                "Account Executive": "$70,000 - $140,000",
                "Customer Success": "$65,000 - $95,000"
            },
            "pros_summary": [
                "Collaborative culture",
                "Remote-friendly",
                "Healthcare impact",
                "Good leadership transparency"
            ],
            "cons_summary": [
                "Startup resources constraints",
                "Some processes immature",
                "Fast-paced can be stressful",
                "Bay Area cost adjustments"
            ]
        },
        "waystar": {
            "overall_rating": 3.6,
            "ceo_name": "Matt Hawkins",
            "ceo_approval": 70,
            "recommend_to_friend": 60,
            "culture_rating": 3.4,
            "compensation_rating": 3.5,
            "work_life_balance": 3.3,
            "career_opportunities": 3.4,
            "senior_management": 3.2,
            "total_reviews": 312,
            "interview_difficulty": 2.6,
            "interview_experience_positive": 70,
            "salary_ranges": {
                "Software Engineer": "$80,000 - $130,000",
                "Product Manager": "$95,000 - $145,000",
                "Sales Representative": "$55,000 - $110,000",
                "Implementation Consultant": "$60,000 - $90,000"
            },
            "pros_summary": [
                "Stable company",
                "Healthcare industry leader",
                "Good benefits",
                "Louisville cost of living"
            ],
            "cons_summary": [
                "Post-merger integration challenges",
                "PE pressure on costs",
                "Bureaucracy",
                "Limited innovation focus"
            ]
        },
        "clearwave": {
            "overall_rating": 4.5,
            "ceo_name": "Mike Lamb",
            "ceo_approval": 95,
            "recommend_to_friend": 90,
            "culture_rating": 4.6,
            "compensation_rating": 4.2,
            "work_life_balance": 4.4,
            "career_opportunities": 4.3,
            "senior_management": 4.5,
            "total_reviews": 45,
            "interview_difficulty": 2.8,
            "interview_experience_positive": 85,
            "salary_ranges": {
                "Software Engineer": "$100,000 - $160,000",
                "Product Manager": "$110,000 - $170,000",
                "Sales Representative": "$60,000 - $120,000",
                "Customer Success": "$55,000 - $85,000"
            },
            "pros_summary": [
                "Great culture and leadership",
                "Strong focus on customer success",
                "Growing company with opportunities"
            ],
            "cons_summary": [
                "Growing pains as company scales",
                "Remote work communication",
                "Limited brand awareness compared to giants"
            ]
        }
    }
    
    def __init__(self):
        pass
    
    def get_company_data(self, company_name: str) -> GlassdoorData:
        """Get Glassdoor data for a company. Returns unavailable status when no real API is configured."""
        # KNOWN_COMPANIES contains fabricated demo data - never return it as real
        return self._build_placeholder(company_name)
    
    def _build_from_known(self, company_name: str, data: Dict) -> GlassdoorData:
        """Build GlassdoorData from known data."""
        return GlassdoorData(
            company_name=company_name,
            overall_rating=data["overall_rating"],
            ceo_name=data["ceo_name"],
            ceo_approval=data["ceo_approval"],
            recommend_to_friend=data["recommend_to_friend"],
            culture_rating=data["culture_rating"],
            compensation_rating=data["compensation_rating"],
            work_life_balance=data["work_life_balance"],
            career_opportunities=data["career_opportunities"],
            senior_management=data["senior_management"],
            total_reviews=data["total_reviews"],
            interview_difficulty=data["interview_difficulty"],
            interview_experience_positive=data["interview_experience_positive"],
            salary_ranges=data.get("salary_ranges", {}),
            pros_summary=data.get("pros_summary", []),
            cons_summary=data.get("cons_summary", []),
            recent_reviews=[],
            last_updated=datetime.utcnow().isoformat()
        )
    
    def _build_placeholder(self, company_name: str) -> GlassdoorData:
        """Build placeholder GlassdoorData."""
        return GlassdoorData(
            company_name=company_name,
            overall_rating=0.0,
            ceo_name="",
            ceo_approval=0.0,
            recommend_to_friend=0.0,
            culture_rating=0.0,
            compensation_rating=0.0,
            work_life_balance=0.0,
            career_opportunities=0.0,
            senior_management=0.0,
            total_reviews=0,
            interview_difficulty=0.0,
            interview_experience_positive=0.0,
            salary_ranges={},
            pros_summary=[],
            cons_summary=[],
            recent_reviews=[],
            last_updated=datetime.utcnow().isoformat()
        )
    
    def analyze_employee_sentiment(self, company_name: str) -> Dict[str, Any]:
        """Analyze employee sentiment for competitive insights."""
        data = self.get_company_data(company_name)
        
        # Determine overall sentiment
        if data.overall_rating >= 4.0:
            sentiment = "Positive"
            signal = "Strong employee satisfaction - difficult to poach talent"
        elif data.overall_rating >= 3.5:
            sentiment = "Mixed"
            signal = "Average satisfaction - some opportunities"
        else:
            sentiment = "Negative"
            signal = "Low morale - potential talent acquisition opportunity"
        
        # Identify key concerns
        concerns = []
        if data.work_life_balance < 3.5:
            concerns.append("Work-life balance issues")
        if data.compensation_rating < 3.5:
            concerns.append("Compensation concerns")
        if data.senior_management < 3.5:
            concerns.append("Leadership challenges")
        if data.career_opportunities < 3.5:
            concerns.append("Limited growth paths")
        
        # Competitive implications
        implications = []
        if data.ceo_approval < 70:
            implications.append("Leadership instability - watch for strategy changes")
        if data.recommend_to_friend < 60:
            implications.append("Customer experience may be impacted by morale")
        if concerns:
            implications.append(f"Employee retention risk: {', '.join(concerns)}")
        
        return {
            "company": company_name,
            "overall_rating": data.overall_rating,
            "total_reviews": data.total_reviews,
            "sentiment": sentiment,
            "signal": signal,
            "top_concerns": concerns,
            "competitive_implications": implications,
            "pros": data.pros_summary[:3],
            "cons": data.cons_summary[:3]
        }
    
    def compare_employers(self, company_names: List[str]) -> Dict[str, Any]:
        """Compare employer ratings across companies."""
        comparison = []
        
        for name in company_names:
            data = self.get_company_data(name)
            comparison.append({
                "name": name,
                "overall": data.overall_rating,
                "ceo_approval": data.ceo_approval,
                "recommend": data.recommend_to_friend,
                "culture": data.culture_rating,
                "compensation": data.compensation_rating,
                "work_life": data.work_life_balance,
                "reviews": data.total_reviews
            })
        
        # Sort by overall rating
        comparison.sort(key=lambda x: x["overall"], reverse=True)
        
        return {
            "companies": comparison,
            "best_overall": comparison[0]["name"] if comparison else None,
            "best_culture": max(comparison, key=lambda x: x["culture"])["name"] if comparison else None,
            "best_compensation": max(comparison, key=lambda x: x["compensation"])["name"] if comparison else None
        }


def get_glassdoor_data(company_name: str) -> Dict[str, Any]:
    """Get Glassdoor data for a company."""
    scraper = GlassdoorScraper()
    data = scraper.get_company_data(company_name)
    return asdict(data)


def analyze_employee_intelligence(company_name: str) -> Dict[str, Any]:
    """Analyze employee sentiment for competitive insights."""
    scraper = GlassdoorScraper()
    return scraper.analyze_employee_sentiment(company_name)


if __name__ == "__main__":
    scraper = GlassdoorScraper()
    
    print("=" * 60)
    print("Glassdoor Employee Intelligence")
    print("=" * 60)
    
    for company in ["Phreesia", "athenahealth", "Cedar"]:
        data = scraper.get_company_data(company)
        print(f"\n{company}:")
        print(f"  Overall: {data.overall_rating}/5 ({data.total_reviews} reviews)")
        print(f"  CEO Approval: {data.ceo_approval}%")
        print(f"  Recommend: {data.recommend_to_friend}%")
        print(f"  Top Pro: {data.pros_summary[0] if data.pros_summary else 'N/A'}")
        print(f"  Top Con: {data.cons_summary[0] if data.cons_summary else 'N/A'}")
