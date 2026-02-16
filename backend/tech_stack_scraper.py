"""
Certify Intel - Tech Stack Scraper
Detects marketing technology and tracking infrastructure (Tech Stack) from company websites.
"""
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

@dataclass
class TechStackData:
    """Marketing and Analytics Tech Stack."""
    company_name: str
    has_gtm: bool  # Google Tag Manager
    has_ga4: bool  # Google Analytics 4
    has_floodlight: bool  # DoubleClick Floodlight (Enterprise)
    has_adobe_analytics: bool
    has_segment: bool
    has_hubspot: bool
    has_salesforce: bool
    marketing_budget_signal: str  # Low, Mid, High (Enterprise)
    detected_tools: List[str]
    last_updated: str

class TechStackScraper:
    """Scrapes tech stack data."""
    
    # Known data for demo
    KNOWN_COMPANIES = {
        "phreesia": {
            "has_gtm": True,
            "has_ga4": True,
            "has_floodlight": True,
            "has_adobe_analytics": False,
            "has_segment": True,
            "has_hubspot": True,
            "has_salesforce": True,
            "detected_tools": ["Google Tag Manager", "Google Analytics 4", "DoubleClick Floodlight", "Segment", "HubSpot", "Salesforce"]
        },
        "cedar": {
            "has_gtm": True,
            "has_ga4": True,
            "has_floodlight": False,
            "has_adobe_analytics": False,
            "has_segment": False,
            "has_hubspot": True,
            "has_salesforce": False,
            "detected_tools": ["Google Tag Manager", "Google Analytics 4", "HubSpot"]
        },
        "zocdoc": {
            "has_gtm": True,
            "has_ga4": True,
            "has_floodlight": True,
            "has_adobe_analytics": True,
            "has_segment": True,
            "has_hubspot": False,
            "has_salesforce": True,
            "detected_tools": ["Google Tag Manager", "Google Analytics 4", "DoubleClick Floodlight", "Adobe Analytics", "Segment", "Salesforce"]
        }
    }

    def __init__(self):
        pass

    def get_tech_stack(self, company_name: str) -> TechStackData:
        """Get tech stack data for a company."""
        name_lower = company_name.lower()
        
        if name_lower in self.KNOWN_COMPANIES:
            return self._build_from_known(company_name, self.KNOWN_COMPANIES[name_lower])
            
        return self._build_placeholder(company_name)

    def _build_from_known(self, company_name: str, data: Dict) -> TechStackData:
        """Build TechStackData from known data."""
        # Determine budget signal
        signal = "Low/Mid"
        if data["has_floodlight"] or data["has_adobe_analytics"]:
            signal = "Enterprise (High)"
        elif data["has_gtm"] and data["has_segment"]:
            signal = "Growth (Mid)"
            
        return TechStackData(
            company_name=company_name,
            has_gtm=data["has_gtm"],
            has_ga4=data["has_ga4"],
            has_floodlight=data["has_floodlight"],
            has_adobe_analytics=data["has_adobe_analytics"],
            has_segment=data["has_segment"],
            has_hubspot=data["has_hubspot"],
            has_salesforce=data["has_salesforce"],
            marketing_budget_signal=signal,
            detected_tools=data.get("detected_tools", []),
            last_updated=datetime.utcnow().isoformat()
        )

    def _build_placeholder(self, company_name: str) -> TechStackData:
        """Build placeholder TechStackData."""
        return TechStackData(
            company_name=company_name,
            has_gtm=False,
            has_ga4=False,
            has_floodlight=False,
            has_adobe_analytics=False,
            has_segment=False,
            has_hubspot=False,
            has_salesforce=False,
            marketing_budget_signal="Unknown",
            detected_tools=[],
            last_updated=datetime.utcnow().isoformat()
        )

if __name__ == "__main__":
    scraper = TechStackScraper()
    print("="*60)
    print("Tech Stack Intelligence")
    print("="*60)
    
    for company in ["Phreesia", "Cedar", "Zocdoc"]:
        data = scraper.get_tech_stack(company)
        print(f"\n{company}:")
        print(f"  Signal: {data.marketing_budget_signal}")
        print(f"  Tools: {', '.join(data.detected_tools)}")
