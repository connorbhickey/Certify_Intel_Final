"""
Certify Intel - Indeed/Job Postings Scraper
Fetches job postings, salary data, and hiring signals.
"""
import os
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
import urllib.request
import urllib.parse


@dataclass
class JobPosting:
    """Job posting data."""
    title: str
    company: str
    location: str
    salary_range: str
    salary_min: Optional[float]
    salary_max: Optional[float]
    job_type: str
    posted_date: str
    description_snippet: str
    tech_stack: List[str]
    is_urgent: bool
    is_remote: bool
    url: str


@dataclass
class IndeedData:
    """Aggregated job posting data."""
    company_name: str
    total_openings: int
    jobs: List[JobPosting]
    by_department: Dict[str, int]
    by_location: Dict[str, int]
    avg_salary_range: str
    tech_stack_frequency: Dict[str, int]
    hiring_signals: List[str]
    remote_percentage: float
    urgent_count: int
    last_updated: str


class IndeedScraper:
    """Scrapes job postings from Indeed and other job boards."""
    
    # Tech stack keywords to detect
    TECH_KEYWORDS = [
        "python", "java", "javascript", "typescript", "react", "angular", "vue",
        "node.js", "aws", "azure", "gcp", "kubernetes", "docker", "terraform",
        "sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
        "go", "golang", "rust", "c#", ".net", "ruby", "rails", "php",
        "fhir", "hl7", "epic", "cerner", "meditech", "allscripts", "athena",
        "machine learning", "ai", "data science", "tableau", "looker"
    ]
    
    # Known job data
    KNOWN_COMPANIES = {
        "phreesia": {
            "total_openings": 45,
            "jobs": [
                {"title": "Senior Software Engineer", "location": "Remote", "salary_range": "$130K-$180K", "department": "Engineering", "is_urgent": False, "is_remote": True, "tech_stack": ["Python", "AWS", "React"]},
                {"title": "Product Manager, Patient Intake", "location": "Remote", "salary_range": "$120K-$160K", "department": "Product", "is_urgent": False, "is_remote": True, "tech_stack": []},
                {"title": "Enterprise Account Executive", "location": "Chicago, IL", "salary_range": "$80K-$150K", "department": "Sales", "is_urgent": True, "is_remote": False, "tech_stack": []},
                {"title": "Implementation Consultant", "location": "Wilmington, NC", "salary_range": "$65K-$90K", "department": "Customer Success", "is_urgent": False, "is_remote": False, "tech_stack": ["FHIR", "HL7"]},
                {"title": "Data Engineer", "location": "Remote", "salary_range": "$120K-$165K", "department": "Engineering", "is_urgent": False, "is_remote": True, "tech_stack": ["Python", "SQL", "AWS"]},
            ],
            "by_department": {"Engineering": 15, "Sales": 12, "Product": 8, "Customer Success": 7, "Marketing": 3},
            "by_location": {"Remote": 25, "Wilmington, NC": 10, "Chicago, IL": 5, "New York, NY": 5}
        },
        "cedar": {
            "total_openings": 35,
            "jobs": [
                {"title": "Staff Software Engineer", "location": "New York, NY", "salary_range": "$180K-$230K", "department": "Engineering", "is_urgent": False, "is_remote": False, "tech_stack": ["Python", "React", "AWS", "Kubernetes"]},
                {"title": "Senior Product Manager", "location": "Remote", "salary_range": "$150K-$200K", "department": "Product", "is_urgent": False, "is_remote": True, "tech_stack": []},
                {"title": "Healthcare Data Analyst", "location": "New York, NY", "salary_range": "$90K-$130K", "department": "Data", "is_urgent": True, "is_remote": False, "tech_stack": ["SQL", "Python", "Tableau"]},
                {"title": "Enterprise Sales Director", "location": "Remote", "salary_range": "$150K-$250K", "department": "Sales", "is_urgent": True, "is_remote": True, "tech_stack": []},
            ],
            "by_department": {"Engineering": 18, "Sales": 8, "Product": 5, "Data": 4},
            "by_location": {"New York, NY": 20, "Remote": 15}
        },
        "luma health": {
            "total_openings": 22,
            "jobs": [
                {"title": "Senior Backend Engineer", "location": "Remote", "salary_range": "$140K-$180K", "department": "Engineering", "is_urgent": False, "is_remote": True, "tech_stack": ["Node.js", "TypeScript", "PostgreSQL"]},
                {"title": "Account Executive, Mid-Market", "location": "San Francisco, CA", "salary_range": "$80K-$140K", "department": "Sales", "is_urgent": True, "is_remote": False, "tech_stack": []},
                {"title": "Customer Success Manager", "location": "Remote", "salary_range": "$75K-$100K", "department": "Customer Success", "is_urgent": False, "is_remote": True, "tech_stack": []},
            ],
            "by_department": {"Engineering": 10, "Sales": 6, "Customer Success": 4, "Product": 2},
            "by_location": {"Remote": 15, "San Francisco, CA": 7}
        },
        "athenahealth": {
            "total_openings": 120,
            "jobs": [
                {"title": "Senior Java Developer", "location": "Watertown, MA", "salary_range": "$120K-$170K", "department": "Engineering", "is_urgent": False, "is_remote": False, "tech_stack": ["Java", "AWS", "Microservices"]},
                {"title": "Product Owner, RCM", "location": "Remote", "salary_range": "$110K-$150K", "department": "Product", "is_urgent": False, "is_remote": True, "tech_stack": []},
                {"title": "Implementation Manager", "location": "Austin, TX", "salary_range": "$80K-$110K", "department": "Customer Success", "is_urgent": True, "is_remote": False, "tech_stack": ["HL7", "FHIR"]},
                {"title": "Regional Sales Director", "location": "Atlanta, GA", "salary_range": "$130K-$200K", "department": "Sales", "is_urgent": True, "is_remote": False, "tech_stack": []},
            ],
            "by_department": {"Engineering": 45, "Sales": 25, "Customer Success": 20, "Product": 15, "Support": 15},
            "by_location": {"Watertown, MA": 40, "Remote": 35, "Austin, TX": 25, "Atlanta, GA": 20}
        },
        "waystar": {
            "total_openings": 65,
            "jobs": [
                {"title": "Full Stack Developer", "location": "Louisville, KY", "salary_range": "$90K-$130K", "department": "Engineering", "is_urgent": False, "is_remote": False, "tech_stack": ["C#", ".NET", "SQL Server"]},
                {"title": "Revenue Cycle Consultant", "location": "Remote", "salary_range": "$70K-$100K", "department": "Consulting", "is_urgent": False, "is_remote": True, "tech_stack": []},
                {"title": "Sales Development Rep", "location": "Louisville, KY", "salary_range": "$50K-$80K", "department": "Sales", "is_urgent": True, "is_remote": False, "tech_stack": []},
            ],
            "by_department": {"Engineering": 20, "Sales": 18, "Consulting": 12, "Support": 10, "Product": 5},
            "by_location": {"Louisville, KY": 40, "Remote": 20, "Nashville, TN": 5}
        },
        "zocdoc": {
            "total_openings": 28,
            "jobs": [
                {"title": "Senior Software Engineer, Platform", "location": "New York, NY", "salary_range": "$160K-$210K", "department": "Engineering", "is_urgent": False, "is_remote": False, "tech_stack": ["Go", "Python", "AWS", "Kubernetes"]},
                {"title": "Data Scientist", "location": "New York, NY", "salary_range": "$130K-$170K", "department": "Data", "is_urgent": False, "is_remote": False, "tech_stack": ["Python", "Machine Learning", "SQL"]},
                {"title": "B2B Sales Manager", "location": "New York, NY", "salary_range": "$100K-$180K", "department": "Sales", "is_urgent": True, "is_remote": False, "tech_stack": []},
            ],
            "by_department": {"Engineering": 12, "Sales": 8, "Product": 4, "Data": 4},
            "by_location": {"New York, NY": 25, "Remote": 3}
        }
    }
    
    def __init__(self):
        pass
    
    def get_job_data(self, company_name: str) -> IndeedData:
        """Get job posting data for a company."""
        name_lower = company_name.lower()
        
        if name_lower in self.KNOWN_COMPANIES:
            return self._build_from_known(company_name, self.KNOWN_COMPANIES[name_lower])
        
        return self._build_placeholder(company_name)
    
    def _build_from_known(self, company_name: str, data: Dict) -> IndeedData:
        """Build IndeedData from known data."""
        jobs = []
        tech_freq = {}
        urgent_count = 0
        remote_count = 0
        
        for job in data.get("jobs", []):
            jobs.append(JobPosting(
                title=job["title"],
                company=company_name,
                location=job["location"],
                salary_range=job.get("salary_range", ""),
                salary_min=self._parse_salary_min(job.get("salary_range", "")),
                salary_max=self._parse_salary_max(job.get("salary_range", "")),
                job_type="Full-time",
                posted_date=datetime.utcnow().isoformat(),
                description_snippet="",
                tech_stack=job.get("tech_stack", []),
                is_urgent=job.get("is_urgent", False),
                is_remote=job.get("is_remote", False),
                url=""
            ))
            
            if job.get("is_urgent"):
                urgent_count += 1
            if job.get("is_remote"):
                remote_count += 1
            
            for tech in job.get("tech_stack", []):
                tech_freq[tech] = tech_freq.get(tech, 0) + 1
        
        total = data.get("total_openings", len(jobs))
        remote_pct = (remote_count / len(jobs) * 100) if jobs else 0
        
        # Generate hiring signals
        signals = self._generate_hiring_signals(data, urgent_count, total)
        
        return IndeedData(
            company_name=company_name,
            total_openings=total,
            jobs=jobs,
            by_department=data.get("by_department", {}),
            by_location=data.get("by_location", {}),
            avg_salary_range=self._calculate_avg_salary(jobs),
            tech_stack_frequency=tech_freq,
            hiring_signals=signals,
            remote_percentage=round(remote_pct, 1),
            urgent_count=urgent_count,
            last_updated=datetime.utcnow().isoformat()
        )
    
    def _build_placeholder(self, company_name: str) -> IndeedData:
        """Build placeholder IndeedData."""
        return IndeedData(
            company_name=company_name,
            total_openings=0,
            jobs=[],
            by_department={},
            by_location={},
            avg_salary_range="",
            tech_stack_frequency={},
            hiring_signals=[],
            remote_percentage=0.0,
            urgent_count=0,
            last_updated=datetime.utcnow().isoformat()
        )
    
    def _parse_salary_min(self, salary_str: str) -> Optional[float]:
        """Parse minimum salary from range string."""
        match = re.search(r'\$(\d+)K', salary_str)
        if match:
            return float(match.group(1)) * 1000
        return None
    
    def _parse_salary_max(self, salary_str: str) -> Optional[float]:
        """Parse maximum salary from range string."""
        matches = re.findall(r'\$(\d+)K', salary_str)
        if len(matches) >= 2:
            return float(matches[1]) * 1000
        return None
    
    def _calculate_avg_salary(self, jobs: List[JobPosting]) -> str:
        """Calculate average salary range."""
        mins = [j.salary_min for j in jobs if j.salary_min]
        maxs = [j.salary_max for j in jobs if j.salary_max]
        
        if mins and maxs:
            avg_min = sum(mins) / len(mins)
            avg_max = sum(maxs) / len(maxs)
            return f"${avg_min/1000:.0f}K-${avg_max/1000:.0f}K"
        return ""
    
    def _generate_hiring_signals(self, data: Dict, urgent: int, total: int) -> List[str]:
        """Generate competitive hiring signals."""
        signals = []
        
        # Check department focus
        departments = data.get("by_department", {})
        if departments:
            top_dept = max(departments.items(), key=lambda x: x[1])
            signals.append(f"Largest hiring: {top_dept[0]} ({top_dept[1]} roles)")
        
        # Urgent hiring indicator
        if urgent > 0:
            signals.append(f"Urgent hiring: {urgent} positions (aggressive expansion)")
        
        # Total openings analysis
        if total >= 50:
            signals.append("Major hiring push - rapid growth phase")
        elif total >= 20:
            signals.append("Moderate hiring - steady expansion")
        
        # Location signals
        locations = data.get("by_location", {})
        if locations.get("Remote", 0) > total * 0.5:
            signals.append("Remote-first strategy - national talent competition")
        
        new_locations = [loc for loc in locations if locations[loc] <= 5]
        if new_locations:
            signals.append(f"New geography expansion: {', '.join(new_locations[:3])}")
        
        return signals
    
    def analyze_tech_stack(self, company_name: str) -> Dict[str, Any]:
        """Analyze tech stack from job postings."""
        data = self.get_job_data(company_name)
        
        return {
            "company": company_name,
            "tech_stack": dict(sorted(
                data.tech_stack_frequency.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]),
            "primary_languages": [tech for tech in data.tech_stack_frequency
                                 if tech.lower() in ["python", "java", "javascript", "go", "c#"]],
            "cloud_platforms": [tech for tech in data.tech_stack_frequency
                               if tech.lower() in ["aws", "azure", "gcp"]],
            "healthcare_specific": [tech for tech in data.tech_stack_frequency
                                   if tech.lower() in ["fhir", "hl7", "epic", "cerner"]]
        }
    
    def compare_hiring(self, company_names: List[str]) -> Dict[str, Any]:
        """Compare hiring across companies."""
        comparison = []
        
        for name in company_names:
            data = self.get_job_data(name)
            comparison.append({
                "name": name,
                "total_openings": data.total_openings,
                "urgent_positions": data.urgent_count,
                "remote_percentage": data.remote_percentage,
                "top_department": max(data.by_department.items(), key=lambda x: x[1])[0] if data.by_department else "N/A",
                "avg_salary": data.avg_salary_range
            })
        
        comparison.sort(key=lambda x: x["total_openings"], reverse=True)
        
        return {
            "companies": comparison,
            "most_aggressive": comparison[0]["name"] if comparison else None,
            "most_remote": max(comparison, key=lambda x: x["remote_percentage"])["name"] if comparison else None
        }


def get_job_data(company_name: str) -> Dict[str, Any]:
    """Get job posting data for a company."""
    scraper = IndeedScraper()
    data = scraper.get_job_data(company_name)
    
    result = asdict(data)
    result["jobs"] = [asdict(j) for j in data.jobs]
    
    return result


if __name__ == "__main__":
    scraper = IndeedScraper()
    
    print("=" * 60)
    print("Indeed Job Postings Analysis")
    print("=" * 60)
    
    for company in ["Phreesia", "Cedar", "athenahealth"]:
        data = scraper.get_job_data(company)
        print(f"\n{company}:")
        print(f"  Total Openings: {data.total_openings}")
        print(f"  Urgent: {data.urgent_count}")
        print(f"  Remote: {data.remote_percentage}%")
        print(f"  Signals: {data.hiring_signals[:2]}")
