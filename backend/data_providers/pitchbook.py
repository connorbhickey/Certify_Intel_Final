"""
Certify Intel - PitchBook Data Provider

PitchBook is the premier source for PE/VC deal data, revenue estimates,
and investor information for private companies.

API Docs: https://pitchbook.com/data/api
Auth: API key in header (X-PB-API-Key)
Rate Limit: 100 requests/minute (enterprise tier)
"""

import logging
from typing import Optional, Dict, Any

import httpx

from .base_provider import BaseDataProvider

logger = logging.getLogger(__name__)


class PitchBookProvider(BaseDataProvider):
    """PitchBook Data provider for PE/VC, revenue, and deal data."""

    provider_name = "PitchBook"
    env_key_name = "PITCHBOOK_API_KEY"
    base_url = "https://api.pitchbook.com/v1"
    rate_limit_per_minute = 100
    description = "Private equity, venture capital deal data, revenue estimates, and investor profiles"

    def _get_auth_headers(self) -> Dict[str, str]:
        return {
            "X-PB-API-Key": self.api_key,
            "Accept": "application/json",
        }

    async def search_company(self, company_name: str) -> Optional[Dict[str, Any]]:
        """Search PitchBook for a company by name."""
        await self._rate_limit()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.base_url}/companies/search",
                    params={"q": company_name, "limit": 5},
                    headers=self._get_auth_headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                companies = data.get("companies", [])
                if not companies:
                    return None
                top = companies[0]
                return {
                    "provider_id": top.get("companyId", ""),
                    "name": top.get("companyName", company_name),
                }
        except Exception as e:
            logger.error(f"PitchBook search error: {e}")
            return None

    async def get_company_profile(self, provider_id: str) -> Optional[Dict[str, Any]]:
        """Get full company profile from PitchBook."""
        await self._rate_limit()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.base_url}/companies/{provider_id}",
                    headers=self._get_auth_headers(),
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"PitchBook profile error: {e}")
            return None

    def map_to_competitor_fields(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map PitchBook data to Competitor model columns."""
        fields = {}

        # Revenue estimates
        revenue = raw_data.get("revenueEstimate") or raw_data.get("revenue")
        if revenue:
            fields["estimated_revenue"] = str(revenue)

        annual_rev = raw_data.get("annualRevenue")
        if annual_rev:
            fields["annual_revenue"] = str(annual_rev)

        revenue_growth = raw_data.get("revenueGrowth")
        if revenue_growth:
            fields["revenue_growth_rate"] = str(revenue_growth)

        # Funding
        total_raised = raw_data.get("totalRaised") or raw_data.get("totalFunding")
        if total_raised:
            fields["funding_total"] = str(total_raised)

        latest_round = raw_data.get("lastDealType") or raw_data.get("latestRound")
        if latest_round:
            fields["latest_round"] = str(latest_round)

        funding_stage = raw_data.get("fundingStatus") or raw_data.get("stage")
        if funding_stage:
            fields["funding_stage"] = str(funding_stage)

        last_deal_date = raw_data.get("lastDealDate")
        if last_deal_date:
            fields["last_funding_date"] = str(last_deal_date)

        # Investors / PE-VC backers
        investors = raw_data.get("investors", [])
        if investors:
            names = [inv.get("investorName", "") for inv in investors[:10]]
            fields["pe_vc_backers"] = "; ".join(n for n in names if n)

        # Company basics
        employee_count = raw_data.get("employeeCount")
        if employee_count:
            fields["employee_count"] = str(employee_count)

        hq = raw_data.get("headquarters") or raw_data.get("hqLocation")
        if hq:
            fields["headquarters"] = str(hq)

        founded = raw_data.get("yearFounded")
        if founded:
            fields["year_founded"] = str(founded)

        # Valuation
        valuation = raw_data.get("postValuation") or raw_data.get("latestValuation")
        if valuation:
            fields["estimated_valuation"] = str(valuation)

        return fields

    def get_source_url(self, provider_id: str) -> str:
        """Deep link to PitchBook company profile."""
        return f"https://pitchbook.com/profiles/company/{provider_id}"
