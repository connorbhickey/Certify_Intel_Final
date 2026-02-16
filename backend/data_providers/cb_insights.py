"""
Certify Intel - CB Insights Data Provider

CB Insights provides market intelligence including company
market positioning, competitive landscapes, funding data,
and technology adoption signals.

API Docs: https://www.cbinsights.com/api
Auth: API key in header (X-CB-API-Key)
Rate Limit: 60 requests/minute
"""

import logging
from typing import Optional, Dict, Any

import httpx

from .base_provider import BaseDataProvider

logger = logging.getLogger(__name__)


class CBInsightsProvider(BaseDataProvider):
    """CB Insights provider for market positioning and funding intelligence."""

    provider_name = "CB Insights"
    env_key_name = "CB_INSIGHTS_API_KEY"
    base_url = "https://api.cbinsights.com/v2"
    rate_limit_per_minute = 60
    description = "Market positioning, competitive landscapes, funding data, and mosaic scores"

    def _get_auth_headers(self) -> Dict[str, str]:
        return {
            "X-CB-API-Key": self.api_key,
            "Accept": "application/json",
        }

    async def search_company(self, company_name: str) -> Optional[Dict[str, Any]]:
        """Search CB Insights for a company by name."""
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
                    "name": top.get("name", company_name),
                }
        except Exception as e:
            logger.error(f"CB Insights search error: {e}")
            return None

    async def get_company_profile(self, provider_id: str) -> Optional[Dict[str, Any]]:
        """Get company profile from CB Insights."""
        await self._rate_limit()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.base_url}/companies/{provider_id}",
                    params={"include": "funding,mosaic,market,competitors"},
                    headers=self._get_auth_headers(),
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"CB Insights profile error: {e}")
            return None

    def map_to_competitor_fields(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map CB Insights data to Competitor model columns."""
        fields = {}

        # Funding data
        funding = raw_data.get("funding", {})
        total_raised = funding.get("totalRaised")
        if total_raised:
            fields["funding_total"] = str(total_raised)

        latest_round = funding.get("lastRoundType")
        if latest_round:
            fields["latest_round"] = str(latest_round)

        last_date = funding.get("lastRoundDate")
        if last_date:
            fields["last_funding_date"] = str(last_date)

        investors = funding.get("investors", [])
        if investors:
            names = [i.get("name", "") for i in investors[:10]]
            fields["pe_vc_backers"] = "; ".join(n for n in names if n)

        # Mosaic score (CB Insights proprietary)
        mosaic = raw_data.get("mosaic", {})
        mosaic_score = mosaic.get("overall")
        if mosaic_score:
            fields["data_quality_score"] = int(mosaic_score) if isinstance(mosaic_score, (int, float)) else None

        # Market / category
        market = raw_data.get("market", {})
        categories = market.get("categories", [])
        if categories:
            fields["product_categories"] = "; ".join(str(c) for c in categories[:5])

        # Company basics
        employee_range = raw_data.get("employeeRange") or raw_data.get("employees")
        if employee_range:
            fields["employee_count"] = str(employee_range)

        hq = raw_data.get("headquarters")
        if hq:
            fields["headquarters"] = str(hq)

        founded = raw_data.get("yearFounded")
        if founded:
            fields["year_founded"] = str(founded)

        # Valuation
        valuation = raw_data.get("valuation") or mosaic.get("valuation")
        if valuation:
            fields["estimated_valuation"] = str(valuation)

        return fields

    def get_source_url(self, provider_id: str) -> str:
        """Deep link to CB Insights company profile."""
        return f"https://www.cbinsights.com/company/{provider_id}"
