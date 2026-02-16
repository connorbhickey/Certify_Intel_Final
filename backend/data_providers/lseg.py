"""
Certify Intel - LSEG (Refinitiv) Data Provider

LSEG (formerly Refinitiv / Thomson Reuters) provides financial
data, ESG scores, and market analytics for public and private companies.

API Docs: https://developers.lseg.com/en/api-catalog
Auth: OAuth2 bearer token
Rate Limit: 60 requests/minute
"""

import logging
from typing import Optional, Dict, Any

import httpx

from .base_provider import BaseDataProvider

logger = logging.getLogger(__name__)


class LSEGProvider(BaseDataProvider):
    """LSEG (Refinitiv) provider for financial data and ESG scores."""

    provider_name = "LSEG"
    env_key_name = "LSEG_API_KEY"
    base_url = "https://api.refinitiv.com/data/v1"
    rate_limit_per_minute = 60
    description = "Financial data, ESG scores, ownership structure, and analyst estimates (formerly Refinitiv)"

    def _get_auth_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

    async def search_company(self, company_name: str) -> Optional[Dict[str, Any]]:
        """Search LSEG for a company by name."""
        await self._rate_limit()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.base_url}/search",
                    params={"query": company_name, "entityType": "company", "top": 5},
                    headers=self._get_auth_headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                hits = data.get("hits", [])
                if not hits:
                    return None
                top = hits[0]
                return {
                    "provider_id": top.get("PermID", top.get("RIC", "")),
                    "name": top.get("DTSubjectName", company_name),
                }
        except Exception as e:
            logger.error(f"LSEG search error: {e}")
            return None

    async def get_company_profile(self, provider_id: str) -> Optional[Dict[str, Any]]:
        """Get company profile and financial data from LSEG."""
        await self._rate_limit()
        try:
            fields = [
                "TR.Revenue", "TR.NetIncome", "TR.CompanyMarketCap",
                "TR.EmployeesTotal", "TR.HeadquartersCountry",
                "TR.HeadquartersCity", "TR.FoundedYear",
                "TR.ESGScore", "TR.ESGEnvironmentPillarScore",
                "TR.GrossMargin", "TR.RevenueGrowth",
            ]
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.base_url}/fundamentals/{provider_id}",
                    params={"fields": ",".join(fields)},
                    headers=self._get_auth_headers(),
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"LSEG profile error: {e}")
            return None

    def map_to_competitor_fields(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map LSEG data to Competitor model columns."""
        fields = {}

        # Flatten data rows
        data_rows = raw_data.get("data", [])
        if isinstance(data_rows, list) and data_rows:
            fd = data_rows[0] if isinstance(data_rows[0], dict) else {}
        elif isinstance(data_rows, dict):
            fd = data_rows
        else:
            fd = raw_data

        revenue = fd.get("TR.Revenue")
        if revenue:
            fields["annual_revenue"] = str(revenue)
            fields["estimated_revenue"] = str(revenue)

        net_income = fd.get("TR.NetIncome")
        if net_income:
            fields["net_income"] = str(net_income)

        margin = fd.get("TR.GrossMargin")
        if margin:
            fields["profit_margin"] = f"{margin}%"

        market_cap = fd.get("TR.CompanyMarketCap")
        if market_cap:
            fields["estimated_valuation"] = str(market_cap)

        employees = fd.get("TR.EmployeesTotal")
        if employees:
            fields["employee_count"] = str(employees)

        city = fd.get("TR.HeadquartersCity", "")
        country = fd.get("TR.HeadquartersCountry", "")
        if city or country:
            hq_parts = [p for p in [city, country] if p]
            fields["headquarters"] = ", ".join(hq_parts)

        founded = fd.get("TR.FoundedYear")
        if founded:
            fields["year_founded"] = str(founded)

        rev_growth = fd.get("TR.RevenueGrowth")
        if rev_growth:
            fields["revenue_growth_rate"] = f"{rev_growth}%"

        return fields

    def get_source_url(self, provider_id: str) -> str:
        """Deep link to LSEG Workspace company page."""
        return f"https://www.refinitiv.com/en/products/refinitiv-workspace/company/{provider_id}"
