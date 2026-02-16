"""
Certify Intel - Risk & Management Scraper
Analyzes management pedigree and company risk signals.
"""
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

@dataclass
class RiskManagementData:
    """Management and Risk Data."""
    company_name: str
    founder_exits: bool
    avg_executive_tenure: str # e.g. "4.5 years"
    tier_1_investors: bool # Sequoia, Benchmark, etc.
    warn_notices: int
    soc2_compliant: bool
    patent_expirations_soon: int
    broken_link_pct: float
    last_updated: str

class RiskManagementScraper:
    """Scrapes risk and management data."""
    
    # Known data for demo
    KNOWN_COMPANIES = {
        "phreesia": {
            "founder_exits": True,
            "avg_executive_tenure": "6.2 years",
            "tier_1_investors": True,
            "warn_notices": 0,
            "soc2_compliant": True,
            "patent_expirations_soon": 2,
            "broken_link_pct": 1.5
        },
        "cedar": {
            "founder_exits": True,
            "avg_executive_tenure": "3.5 years",
            "tier_1_investors": True, # Andreessen Horowitz
            "warn_notices": 0,
            "soc2_compliant": True,
            "patent_expirations_soon": 0,
            "broken_link_pct": 0.5
        },
        "zocdoc": {
            "founder_exits": False,
            "avg_executive_tenure": "4.1 years",
            "tier_1_investors": True,
            "warn_notices": 1, # Past structuring
            "soc2_compliant": True,
            "patent_expirations_soon": 1,
            "broken_link_pct": 2.2
        }
    }

    def __init__(self):
        pass

    def get_risk_data(self, company_name: str) -> RiskManagementData:
        """Get Risk & Management data."""
        name_lower = company_name.lower()
        if name_lower in self.KNOWN_COMPANIES:
            return self._build_from_known(company_name, self.KNOWN_COMPANIES[name_lower])
        return self._build_placeholder(company_name)

    def _build_from_known(self, company_name: str, data: Dict) -> RiskManagementData:
        return RiskManagementData(
            company_name=company_name,
            founder_exits=data["founder_exits"],
            avg_executive_tenure=data["avg_executive_tenure"],
            tier_1_investors=data["tier_1_investors"],
            warn_notices=data["warn_notices"],
            soc2_compliant=data["soc2_compliant"],
            patent_expirations_soon=data["patent_expirations_soon"],
            broken_link_pct=data["broken_link_pct"],
            last_updated=datetime.utcnow().isoformat()
        )

    def _build_placeholder(self, company_name: str) -> RiskManagementData:
        return RiskManagementData(
            company_name=company_name,
            founder_exits=False,
            avg_executive_tenure="Unknown",
            tier_1_investors=False,
            warn_notices=0,
            soc2_compliant=False,
            patent_expirations_soon=0,
            broken_link_pct=0.0,
            last_updated=datetime.utcnow().isoformat()
        )

if __name__ == "__main__":
    scraper = RiskManagementScraper()
    print("="*60)
    print("Risk & Management Intelligence")
    print("="*60)
    for company in ["Phreesia", "Cedar"]:
        data = scraper.get_risk_data(company)
        print(f"\n{company}:")
        print(f"  Founder Exits: {data.founder_exits}")
        print(f"  Avg Exec Tenure: {data.avg_executive_tenure}")
        print(f"  SOC2: {data.soc2_compliant}, WARN Notices: {data.warn_notices}")
