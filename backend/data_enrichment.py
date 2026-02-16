"""
Data Enrichment Module - Free API Integrations
Certify Intel Competitive Intelligence Platform

Integrates:
- Clearbit Logo API (free unlimited)
- SEC EDGAR API (free unlimited)
- Google Custom Search API (free 100/day)
- Hunter.io API (free 25/month)
"""

import os
import json
import httpx
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)


class ClearbitLogoService:
    """
    Clearbit Logo API - Free unlimited usage
    Returns company logos by domain
    """
    
    BASE_URL = "https://logo.clearbit.com"
    
    @staticmethod
    def get_logo_url(website: str) -> str:
        """Generate Clearbit logo URL from website."""
        if not website:
            return None
        
        # Clean domain
        domain = website.replace("https://", "").replace("http://", "").replace("www.", "")
        domain = domain.split("/")[0]  # Remove path
        
        return f"{ClearbitLogoService.BASE_URL}/{domain}"
    
    @staticmethod
    async def verify_logo_exists(website: str) -> Optional[str]:
        """Verify logo exists and return URL if valid."""
        logo_url = ClearbitLogoService.get_logo_url(website)
        if not logo_url:
            return None
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.head(logo_url, timeout=5.0)
                if response.status_code == 200:
                    return logo_url
        except Exception as e:
            logger.debug(f"Logo check failed for {website}: {e}")
        
        return None


class SECEdgarService:
    """
    SEC EDGAR API - Free unlimited usage
    Provides financial data for public companies
    """
    
    BASE_URL = "https://data.sec.gov"
    HEADERS = {
        "User-Agent": "CertifyIntel/1.0 (contact@certifyhealth.com)",
        "Accept": "application/json"
    }
    
    # Known healthcare IT public companies
    KNOWN_CIKS = {
        "phreesia": "0001527166",
        "healthstream": "0001099028",
        "veeva": "0001393052",
        "teladoc": "0001477449",
        "doximity": "0001833988",
        "health catalyst": "0001707178",
        "evolent health": "0001628908",
        "omnicell": "0000926326",
        "allscripts": "0001124804",
        "nextgen healthcare": "0001228967"
    }
    
    async def lookup_cik(self, company_name: str) -> Optional[str]:
        """Look up SEC CIK by company name."""
        # Check known CIKs first
        name_lower = company_name.lower()
        for known, cik in self.KNOWN_CIKS.items():
            if known in name_lower or name_lower in known:
                return cik
        
        # Try SEC search
        try:
            async with httpx.AsyncClient(headers=self.HEADERS) as client:
                url = f"{self.BASE_URL}/cgi-bin/browse-edgar?action=getcompany&company={company_name}&type=10-K&output=atom"
                response = await client.get(url, timeout=10.0)
                if response.status_code == 200:
                    # Parse response for CIK
                    text = response.text
                    if "CIK=" in text:
                        cik = text.split("CIK=")[1].split("&")[0]
                        return cik.zfill(10)
        except Exception as e:
            logger.error(f"SEC CIK lookup failed for {company_name}: {e}")
        
        return None
    
    async def get_company_info(self, cik: str) -> Optional[Dict[str, Any]]:
        """Get company info from SEC submissions."""
        try:
            async with httpx.AsyncClient(headers=self.HEADERS) as client:
                url = f"{self.BASE_URL}/submissions/CIK{cik}.json"
                response = await client.get(url, timeout=15.0)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Extract key info
                    filings = data.get("filings", {}).get("recent", {})
                    recent_10k_idx = None
                    
                    forms = filings.get("form", [])
                    for i, form in enumerate(forms[:50]):
                        if form == "10-K":
                            recent_10k_idx = i
                            break
                    
                    return {
                        "name": data.get("name"),
                        "cik": cik,
                        "sic": data.get("sic"),
                        "sic_description": data.get("sicDescription"),
                        "fiscal_year_end": data.get("fiscalYearEnd"),
                        "ein": data.get("ein"),
                        "state": data.get("stateOfIncorporation"),
                        "recent_filings": [
                            {
                                "form": filings.get("form", [])[i],
                                "filed": filings.get("filingDate", [])[i],
                                "accession": filings.get("accessionNumber", [])[i]
                            }
                            for i in range(min(5, len(filings.get("form", []))))
                        ]
                    }
        except Exception as e:
            logger.error(f"SEC company info failed for CIK {cik}: {e}")
        
        return None
    
    async def enrich_competitor(self, company_name: str, is_public: bool) -> Dict[str, Any]:
        """Enrich competitor with SEC data if public."""
        if not is_public:
            return {}
        
        cik = await self.lookup_cik(company_name)
        if not cik:
            return {}
        
        info = await self.get_company_info(cik)
        if not info:
            return {"sec_cik": cik}
        
        return {
            "sec_cik": cik,
            "fiscal_year_end": info.get("fiscal_year_end"),
            "recent_sec_filings": json.dumps(info.get("recent_filings", []))
        }


class GoogleSearchService:
    """
    Google Custom Search API - Free 100 queries/day
    Enhanced news and press release discovery
    """
    
    BASE_URL = "https://www.googleapis.com/customsearch/v1"
    
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.cx = os.getenv("GOOGLE_CX")  # Custom Search Engine ID
    
    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.cx)
    
    async def search(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """Run Google Custom Search."""
        if not self.is_configured:
            logger.warning("Google Search API not configured")
            return []
        
        try:
            async with httpx.AsyncClient() as client:
                params = {
                    "key": self.api_key,
                    "cx": self.cx,
                    "q": query,
                    "num": num_results
                }
                response = await client.get(self.BASE_URL, params=params, timeout=10.0)
                
                if response.status_code == 200:
                    data = response.json()
                    return [
                        {
                            "title": item.get("title"),
                            "link": item.get("link"),
                            "snippet": item.get("snippet")
                        }
                        for item in data.get("items", [])
                    ]
        except Exception as e:
            logger.error(f"Google Search failed for '{query}': {e}")
        
        return []
    
    async def search_press_releases(self, company_name: str) -> List[Dict[str, Any]]:
        """Search for company press releases."""
        query = f'"{company_name}" site:prnewswire.com OR site:businesswire.com'
        return await self.search(query)
    
    async def search_partnerships(self, company_name: str) -> List[Dict[str, Any]]:
        """Search for partnership announcements."""
        query = f'"{company_name}" partnership announcement healthcare'
        return await self.search(query)
    
    async def search_product_launches(self, company_name: str) -> List[Dict[str, Any]]:
        """Search for product launches."""
        query = f'"{company_name}" new product launch feature healthcare'
        return await self.search(query)


class HunterService:
    """
    Hunter.io API - Free 25 searches/month
    Email pattern and contact discovery
    """
    
    BASE_URL = "https://api.hunter.io/v2"
    
    def __init__(self):
        self.api_key = os.getenv("HUNTER_API_KEY")
    
    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)
    
    async def domain_search(self, domain: str) -> Optional[Dict[str, Any]]:
        """Search for emails by domain."""
        if not self.is_configured:
            logger.warning("Hunter.io API not configured")
            return None
        
        # Clean domain
        domain = domain.replace("https://", "").replace("http://", "").replace("www.", "")
        domain = domain.split("/")[0]
        
        try:
            async with httpx.AsyncClient() as client:
                params = {
                    "domain": domain,
                    "api_key": self.api_key
                }
                response = await client.get(
                    f"{self.BASE_URL}/domain-search",
                    params=params,
                    timeout=15.0
                )
                
                if response.status_code == 200:
                    data = response.json().get("data", {})
                    
                    # Extract key contacts (executives)
                    emails = data.get("emails", [])
                    executives = [
                        {
                            "name": f"{e.get('first_name', '')} {e.get('last_name', '')}",
                            "email": e.get("value"),
                            "position": e.get("position"),
                            "department": e.get("department")
                        }
                        for e in emails
                        if e.get("position") and any(
                            title in e.get("position", "").lower()
                            for title in ["ceo", "cto", "cfo", "vp", "director", "head", "chief"]
                        )
                    ][:10]  # Top 10 executives
                    
                    return {
                        "email_pattern": data.get("pattern"),
                        "email_count": len(emails),
                        "key_contacts": executives,
                        "organization": data.get("organization")
                    }
        except Exception as e:
            logger.error(f"Hunter.io search failed for {domain}: {e}")
        
        return None
    
    async def enrich_competitor(self, website: str) -> Dict[str, Any]:
        """Enrich competitor with Hunter.io data."""
        if not website:
            return {}
        
        result = await self.domain_search(website)
        if not result:
            return {}
        
        return {
            "email_pattern": result.get("email_pattern"),
            "hunter_email_count": result.get("email_count"),
            "key_contacts": json.dumps(result.get("key_contacts", []))
        }


class DataEnrichmentService:
    """
    Unified data enrichment service
    Orchestrates all free API integrations
    """
    
    def __init__(self):
        self.clearbit = ClearbitLogoService()
        self.sec = SECEdgarService()
        self.google = GoogleSearchService()
        self.hunter = HunterService()
    
    async def enrich_competitor(
        self,
        name: str,
        website: str,
        is_public: bool = False,
        include_contacts: bool = False
    ) -> Dict[str, Any]:
        """
        Enrich competitor data from all available sources.
        
        Args:
            name: Company name
            website: Company website URL
            is_public: Whether company is publicly traded
            include_contacts: Whether to use Hunter.io (uses quota)
        """
        enriched = {}
        
        # 1. Clearbit Logo (always, free unlimited)
        logo_url = self.clearbit.get_logo_url(website)
        if logo_url:
            enriched["logo_url"] = logo_url
        
        # 2. SEC EDGAR (only for public companies)
        if is_public:
            sec_data = await self.sec.enrich_competitor(name, is_public)
            enriched.update(sec_data)
        
        # 3. Hunter.io (optional, uses quota)
        if include_contacts and self.hunter.is_configured:
            hunter_data = await self.hunter.enrich_competitor(website)
            enriched.update(hunter_data)
        
        return enriched
    
    async def batch_enrich_logos(self, competitors: List[Dict]) -> List[Dict]:
        """Add logo URLs to a list of competitors."""
        for comp in competitors:
            website = comp.get("website")
            if website and not comp.get("logo_url"):
                comp["logo_url"] = self.clearbit.get_logo_url(website)
        return competitors
    
    async def search_competitor_news(self, company_name: str) -> Dict[str, List]:
        """Search for competitor news from multiple sources."""
        if not self.google.is_configured:
            return {}
        
        results = await asyncio.gather(
            self.google.search_press_releases(company_name),
            self.google.search_partnerships(company_name),
            self.google.search_product_launches(company_name),
            return_exceptions=True
        )
        
        return {
            "press_releases": results[0] if not isinstance(results[0], Exception) else [],
            "partnerships": results[1] if not isinstance(results[1], Exception) else [],
            "product_launches": results[2] if not isinstance(results[2], Exception) else []
        }


# Export main service
data_enrichment = DataEnrichmentService()
