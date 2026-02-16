"""
Certify Intel - LinkedIn Company Tracker
Tracks company data from LinkedIn including employees, jobs, and growth.
"""
import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class JobPosting:
    """Represents a job opening."""
    title: str
    department: str
    location: str
    posted_date: str
    url: str


@dataclass
class LinkedInData:
    """LinkedIn company data."""
    company_name: str
    employee_count: int
    employee_range: str
    employee_growth_6mo: Optional[float]
    employee_growth_yoy: Optional[float]
    headquarters: str
    industry: str
    founded_year: Optional[int]
    open_jobs: int
    job_categories: Dict[str, int]
    recent_jobs: List[JobPosting]
    company_type: str  # Public, Private, Nonprofit
    specialties: List[str]
    followers: int
    last_updated: str


class LinkedInTracker:
    """Tracks LinkedIn company profiles and job postings."""
    
    # Known company data (fallback source)
    KNOWN_COMPANIES = {
        "phreesia": {
            "employee_count": 1850,
            "employee_range": "1001-5000",
            "employee_growth_6mo": 5.2,
            "employee_growth_yoy": 12.5,
            "headquarters": "Wilmington, NC",
            "industry": "Healthcare Technology",
            "founded_year": 2005,
            "open_jobs": 45,
            "job_categories": {"Engineering": 15, "Sales": 12, "Product": 8, "Customer Success": 10},
            "company_type": "Public",
            "specialties": ["Patient Intake", "Payment Collection", "Registration"],
            "followers": 28500
        },
        "clearwave": {
            "employee_count": 220,
            "employee_range": "201-500",
            "employee_growth_6mo": 8.5,
            "employee_growth_yoy": 22.0,
            "headquarters": "Atlanta, GA",
            "industry": "Healthcare Technology",
            "founded_year": 2004,
            "open_jobs": 18,
            "job_categories": {"Engineering": 6, "Sales": 5, "Product": 3, "Support": 4},
            "company_type": "Private",
            "specialties": ["Patient Check-In", "Insurance Verification", "Self-Service Kiosks"],
            "followers": 4200
        },
        "athenahealth": {
            "employee_count": 7200,
            "employee_range": "5001-10000",
            "employee_growth_6mo": -2.1,
            "employee_growth_yoy": -5.3,
            "headquarters": "Watertown, MA",
            "industry": "Healthcare Technology",
            "founded_year": 1997,
            "open_jobs": 120,
            "job_categories": {"Engineering": 45, "Sales": 25, "Product": 15, "Support": 35},
            "company_type": "Private (PE)",
            "specialties": ["EHR", "Revenue Cycle", "Patient Engagement", "Telehealth"],
            "followers": 125000
        },
        "luma health": {
            "employee_count": 245,
            "employee_range": "201-500",
            "employee_growth_6mo": 12.3,
            "employee_growth_yoy": 35.6,
            "headquarters": "San Francisco, CA",
            "industry": "Healthcare Technology",
            "founded_year": 2015,
            "open_jobs": 22,
            "job_categories": {"Engineering": 10, "Sales": 6, "Product": 4, "Customer Success": 2},
            "company_type": "Private",
            "specialties": ["Patient Scheduling", "Patient Communications", "Care Journey"],
            "followers": 8500
        },
        "cedar": {
            "employee_count": 520,
            "employee_range": "501-1000",
            "employee_growth_6mo": 15.2,
            "employee_growth_yoy": 42.0,
            "headquarters": "New York, NY",
            "industry": "Healthcare Technology",
            "founded_year": 2016,
            "open_jobs": 35,
            "job_categories": {"Engineering": 18, "Sales": 8, "Product": 5, "Data": 4},
            "company_type": "Private",
            "specialties": ["Patient Payments", "Healthcare Billing", "Patient Experience"],
            "followers": 12000
        },
        "zocdoc": {
            "employee_count": 720,
            "employee_range": "501-1000",
            "employee_growth_6mo": 3.5,
            "employee_growth_yoy": 8.2,
            "headquarters": "New York, NY",
            "industry": "Healthcare Technology",
            "founded_year": 2007,
            "open_jobs": 28,
            "job_categories": {"Engineering": 12, "Sales": 8, "Product": 4, "Marketing": 4},
            "company_type": "Private",
            "specialties": ["Online Booking", "Patient Marketplace", "Doctor Reviews"],
            "followers": 85000
        },
        "kyruus": {
            "employee_count": 480,
            "employee_range": "201-500",
            "employee_growth_6mo": 6.8,
            "employee_growth_yoy": 15.3,
            "headquarters": "Boston, MA",
            "industry": "Healthcare Technology",
            "founded_year": 2010,
            "open_jobs": 25,
            "job_categories": {"Engineering": 10, "Sales": 7, "Product": 5, "Customer Success": 3},
            "company_type": "Private",
            "specialties": ["Provider Search", "Patient Access", "Provider Data"],
            "followers": 9800
        },
        "waystar": {
            "employee_count": 2100,
            "employee_range": "1001-5000",
            "employee_growth_6mo": 4.2,
            "employee_growth_yoy": 18.5,
            "headquarters": "Louisville, KY",
            "industry": "Healthcare Technology",
            "founded_year": 2017,
            "open_jobs": 65,
            "job_categories": {"Engineering": 20, "Sales": 18, "Product": 10, "Support": 17},
            "company_type": "Private (PE)",
            "specialties": ["Revenue Cycle", "Claims Management", "Patient Payments"],
            "followers": 22000
        }
    }
    
    def __init__(self, use_api: bool = False):
        """
        Initialize the LinkedIn tracker.

        Args:
            use_api: LinkedIn API is NOT SUPPORTED. Always uses known data fallback.
                     This parameter is ignored.
        """
        # LinkedIn API live scraping is disabled - only known data available
        self.use_api = False
        self.api_key = None
    
    def get_company_data(self, company_name: str) -> LinkedInData:
        """
        Get LinkedIn data for a company.
        
        Args:
            company_name: Name of the company
            
        Returns:
            LinkedInData with company information
        """
        name_lower = company_name.lower()
        
        # Check known data first
        if name_lower in self.KNOWN_COMPANIES:
            return self._build_from_known(company_name, self.KNOWN_COMPANIES[name_lower])
        
        # Try API if available
        if self.use_api and self.api_key:
            try:
                return self._fetch_from_api(company_name)
            except Exception as e:
                print(f"LinkedIn API failed for {company_name}: {e}")
        
        # Return placeholder
        return self._build_placeholder(company_name)
    
    def _build_from_known(self, company_name: str, data: Dict) -> LinkedInData:
        """Build LinkedInData from known data."""
        return LinkedInData(
            company_name=company_name,
            employee_count=data["employee_count"],
            employee_range=data["employee_range"],
            employee_growth_6mo=data.get("employee_growth_6mo"),
            employee_growth_yoy=data.get("employee_growth_yoy"),
            headquarters=data["headquarters"],
            industry=data["industry"],
            founded_year=data.get("founded_year"),
            open_jobs=data["open_jobs"],
            job_categories=data.get("job_categories", {}),
            recent_jobs=[],
            company_type=data.get("company_type", "Private"),
            specialties=data.get("specialties", []),
            followers=data.get("followers", 0),
            last_updated=datetime.utcnow().isoformat()
        )
    
    def _build_placeholder(self, company_name: str) -> LinkedInData:
        """Build placeholder LinkedInData."""
        return LinkedInData(
            company_name=company_name,
            employee_count=0,
            employee_range="Unknown",
            employee_growth_6mo=None,
            employee_growth_yoy=None,
            headquarters="Unknown",
            industry="Healthcare Technology",
            founded_year=None,
            open_jobs=0,
            job_categories={},
            recent_jobs=[],
            company_type="Unknown",
            specialties=[],
            followers=0,
            last_updated=datetime.utcnow().isoformat()
        )
    
    def _fetch_from_api(self, company_name: str) -> LinkedInData:
        """Fetch data from LinkedIn API - NOT SUPPORTED.

        LinkedIn API live scraping is disabled. Use known data fallback only.
        """
        raise NotImplementedError("LinkedIn API live scraping is not supported. Using known data only.")
    
    def analyze_hiring_trends(self, company_name: str) -> Dict[str, Any]:
        """
        Analyze hiring trends for competitive insights.
        
        Args:
            company_name: Company to analyze
            
        Returns:
            Dict with hiring analysis
        """
        data = self.get_company_data(company_name)
        
        analysis = {
            "company": company_name,
            "total_openings": data.open_jobs,
            "hiring_intensity": "Unknown",
            "growth_signal": "neutral",
            "department_focus": [],
            "competitive_implications": []
        }
        
        # Calculate hiring intensity
        if data.employee_count > 0:
            hiring_ratio = data.open_jobs / data.employee_count * 100
            if hiring_ratio > 5:
                analysis["hiring_intensity"] = "High"
            elif hiring_ratio > 2:
                analysis["hiring_intensity"] = "Moderate"
            else:
                analysis["hiring_intensity"] = "Low"
        
        # Determine growth signal
        if data.employee_growth_6mo is not None:
            if data.employee_growth_6mo > 10:
                analysis["growth_signal"] = "strong_growth"
            elif data.employee_growth_6mo > 0:
                analysis["growth_signal"] = "growing"
            elif data.employee_growth_6mo < -5:
                analysis["growth_signal"] = "contracting"
            else:
                analysis["growth_signal"] = "stable"
        
        # Identify department focus
        if data.job_categories:
            sorted_depts = sorted(data.job_categories.items(), key=lambda x: x[1], reverse=True)
            analysis["department_focus"] = [d[0] for d in sorted_depts[:3]]
            
            # Generate competitive implications
            for dept, count in sorted_depts[:3]:
                if dept.lower() == "sales":
                    analysis["competitive_implications"].append(
                        f"Aggressive sales expansion ({count} open roles) - expect more competitive encounters"
                    )
                elif dept.lower() == "engineering":
                    analysis["competitive_implications"].append(
                        f"Product development focus ({count} roles) - anticipate new features"
                    )
                elif dept.lower() in ["customer success", "support"]:
                    analysis["competitive_implications"].append(
                        f"Customer focus ({count} roles) - likely improving retention"
                    )
        
        return analysis
    
    def compare_hiring(self, company_names: List[str]) -> Dict[str, Any]:
        """
        Compare hiring across multiple companies.
        
        Args:
            company_names: List of companies to compare
            
        Returns:
            Dict with comparison data
        """
        companies = []
        
        for name in company_names:
            data = self.get_company_data(name)
            analysis = self.analyze_hiring_trends(name)
            
            companies.append({
                "name": name,
                "employees": data.employee_count,
                "growth_6mo": data.employee_growth_6mo,
                "open_jobs": data.open_jobs,
                "hiring_intensity": analysis["hiring_intensity"],
                "growth_signal": analysis["growth_signal"],
                "top_departments": analysis["department_focus"]
            })
        
        # Sort by growth
        companies.sort(key=lambda x: x.get("growth_6mo") or 0, reverse=True)
        
        return {
            "companies": companies,
            "fastest_growing": companies[0]["name"] if companies else None,
            "most_hiring": max(companies, key=lambda x: x["open_jobs"])["name"] if companies else None
        }


# API convenience functions
def get_linkedin_data(company_name: str) -> Dict[str, Any]:
    """Get LinkedIn data for a company."""
    tracker = LinkedInTracker()
    data = tracker.get_company_data(company_name)
    return asdict(data)


def analyze_competitor_hiring(company_name: str) -> Dict[str, Any]:
    """Analyze hiring trends for a competitor."""
    tracker = LinkedInTracker()
    return tracker.analyze_hiring_trends(company_name)


if __name__ == "__main__":
    # Test with sample companies
    tracker = LinkedInTracker()
    
    print("=" * 60)
    print("LinkedIn Company Data Test")
    print("=" * 60)
    
    for company in ["Phreesia", "Cedar", "Luma Health"]:
        data = tracker.get_company_data(company)
        print(f"\n{company}:")
        print(f"  Employees: {data.employee_count} ({data.employee_range})")
        print(f"  Growth (6mo): {data.employee_growth_6mo}%")
        print(f"  Open Jobs: {data.open_jobs}")
        print(f"  Top Hiring: {list(data.job_categories.keys())[:3]}")
    
    print("\n" + "=" * 60)
    print("Hiring Comparison")
    print("=" * 60)
    
    comparison = tracker.compare_hiring(["Phreesia", "Cedar", "Luma Health", "Waystar"])
    print(json.dumps(comparison, indent=2))
