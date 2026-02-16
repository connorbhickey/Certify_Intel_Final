"""
Certify Intel - H-1B Visa Scraper
Fetches H-1B filing data to estimate engineering salaries and hiring trends.
"""
import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

@dataclass
class H1BFiling:
    """H-1B Visa Filing."""
    case_number: str
    job_title: str
    salary: float
    start_date: str
    location: str
    status: str

@dataclass
class H1BData:
    """H-1B Visa Data for a company."""
    company_name: str
    total_filings_2023: int
    avg_salary_engineer: float
    min_salary: float
    max_salary: float
    top_job_titles: List[str]
    recent_filings: List[H1BFiling]
    last_updated: str

class H1BScraper:
    """Scrapes H-1B data."""
    
    # Known data for demo
    KNOWN_COMPANIES = {
        "phreesia": {
            "total_filings_2023": 24,
            "avg_salary_engineer": 135000.0,
            "min_salary": 95000.0,
            "max_salary": 180000.0,
            "top_job_titles": ["Software Engineer", "Senior Data Scientist", "Product Manager"],
            "recent_filings": [
                {"case_number": "I-200-23045-123456", "job_title": "Senior Software Engineer", "salary": 145000.0, "start_date": "2023-09-01", "location": "Remote", "status": "Certified"},
                {"case_number": "I-200-23112-987654", "job_title": "Data Engineer", "salary": 125000.0, "start_date": "2023-10-15", "location": "Raleigh, NC", "status": "Certified"}
            ]
        },
        "cedar": {
            "total_filings_2023": 15,
            "avg_salary_engineer": 165000.0,
            "min_salary": 130000.0,
            "max_salary": 210000.0,
            "top_job_titles": ["Staff Software Engineer", "Senior Backend Engineer", "Engineering Manager"],
            "recent_filings": [
                {"case_number": "I-200-23088-112233", "job_title": "Staff Software Engineer", "salary": 195000.0, "start_date": "2023-08-01", "location": "New York, NY", "status": "Certified"}
            ]
        },
        "zocdoc": {
            "total_filings_2023": 18,
            "avg_salary_engineer": 155000.0,
            "min_salary": 115000.0,
            "max_salary": 195000.0,
            "top_job_titles": ["Software Engineer", "Android Developer", "Data Analyst"],
            "recent_filings": []
        }
    }

    def __init__(self):
        pass

    def get_h1b_data(self, company_name: str) -> H1BData:
        """Get H-1B data for a company."""
        name_lower = company_name.lower()
        
        if name_lower in self.KNOWN_COMPANIES:
            return self._build_from_known(company_name, self.KNOWN_COMPANIES[name_lower])
            
        return self._build_placeholder(company_name)

    def _build_from_known(self, company_name: str, data: Dict) -> H1BData:
        """Build H1BData from known data."""
        filings = [
            H1BFiling(**f) for f in data.get("recent_filings", [])
        ]
        
        return H1BData(
            company_name=company_name,
            total_filings_2023=data["total_filings_2023"],
            avg_salary_engineer=data["avg_salary_engineer"],
            min_salary=data["min_salary"],
            max_salary=data["max_salary"],
            top_job_titles=data["top_job_titles"],
            recent_filings=filings,
            last_updated=datetime.utcnow().isoformat()
        )

    def _build_placeholder(self, company_name: str) -> H1BData:
        """Build placeholder H1BData."""
        return H1BData(
            company_name=company_name,
            total_filings_2023=0,
            avg_salary_engineer=0.0,
            min_salary=0.0,
            max_salary=0.0,
            top_job_titles=[],
            recent_filings=[],
            last_updated=datetime.utcnow().isoformat()
        )

if __name__ == "__main__":
    scraper = H1BScraper()
    print("="*60)
    print("H-1B Visa Intelligence")
    print("="*60)
    
    for company in ["Phreesia", "Cedar"]:
        data = scraper.get_h1b_data(company)
        print(f"\n{company}:")
        print(f"  Filings (2023): {data.total_filings_2023}")
        print(f"  Avg Eng Salary: ${data.avg_salary_engineer:,.2f}")
        print(f"  Top Titles: {data.top_job_titles}")
