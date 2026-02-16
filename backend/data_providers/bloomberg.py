"""
Certify Intel - Bloomberg Data Provider

Bloomberg provides institutional-grade market data, financial
analytics, and news for public and private companies.

API Docs: https://www.bloomberg.com/professional/support/api-library/
Auth: API key in header (api-key)
Rate Limit: 30 requests/minute (standard terminal license)
"""

import logging
from typing import Optional, Dict, Any

import httpx

from .base_provider import BaseDataProvider

logger = logging.getLogger(__name__)


class BloombergProvider(BaseDataProvider):
    """Bloomberg provider for market data, financials, and news."""

    provider_name = "Bloomberg"
    env_key_name = "BLOOMBERG_API_KEY"
    base_url = "https://api.bloomberg.com/eap/catalogs/bbg/data"
    rate_limit_per_minute = 30
    description = "Market data, financial statements, analyst estimates, ESG scores, and company news"

    def _get_auth_headers(self) -> Dict[str, str]:
        return {
            "api-key": self.api_key,
            "Accept": "application/json",
        }

    async def search_company(self, company_name: str) -> Optional[Dict[str, Any]]:
        """Search Bloomberg for a company by name."""
        await self._rate_limit()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.base_url}/search",
                    params={"query": company_name, "type": "EQUITY", "limit": 5},
                    headers=self._get_auth_headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                results = data.get("results", [])
                if not results:
                    return None
                top = results[0]
                return {
                    "provider_id": top.get("figi", top.get("id", "")),
                    "name": top.get("name", company_name),
                    "ticker": top.get("ticker", ""),
                }
        except Exception as e:
            logger.error(f"Bloomberg search error: {e}")
            return None

    async def get_company_profile(self, provider_id: str) -> Optional[Dict[str, Any]]:
        """Get company financial profile from Bloomberg."""
        await self._rate_limit()
        try:
            fields = [
                "SALES_REV_TURN", "NET_INCOME", "CUR_MKT_CAP",
                "NUM_OF_EMPLOYEES", "COUNTRY_ISO", "CITY_OF_DOMICILE",
                "YEAR_FOUNDED", "EBITDA", "TOT_DEBT_TO_TOT_ASSET",
                "TRAIL_12M_GROSS_MARGIN", "EPS_GROWTH",
                "BEST_EST_SALES", "ESG_DISCLOSURE_SCORE",
            ]
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/fields",
                    json={"securities": [provider_id], "fields": fields},
                    headers=self._get_auth_headers(),
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"Bloomberg profile error: {e}")
            return None

    def map_to_competitor_fields(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map Bloomberg financial data to Competitor model columns."""
        fields = {}

        # Bloomberg responses can be nested; flatten to field map
        field_data = raw_data.get("data", [{}])
        if isinstance(field_data, list) and field_data:
            fd = field_data[0] if isinstance(field_data[0], dict) else {}
        elif isinstance(field_data, dict):
            fd = field_data
        else:
            fd = raw_data

        # Revenue
        revenue = fd.get("SALES_REV_TURN") or fd.get("BEST_EST_SALES")
        if revenue:
            fields["annual_revenue"] = str(revenue)
            fields["estimated_revenue"] = str(revenue)

        # Net income
        net_income = fd.get("NET_INCOME")
        if net_income:
            fields["net_income"] = str(net_income)

        # Margin
        margin = fd.get("TRAIL_12M_GROSS_MARGIN")
        if margin:
            fields["profit_margin"] = f"{margin}%"

        # Market cap
        mkt_cap = fd.get("CUR_MKT_CAP")
        if mkt_cap:
            fields["estimated_valuation"] = str(mkt_cap)

        # Employees
        employees = fd.get("NUM_OF_EMPLOYEES")
        if employees:
            fields["employee_count"] = str(employees)

        # Location
        city = fd.get("CITY_OF_DOMICILE", "")
        country = fd.get("COUNTRY_ISO", "")
        if city or country:
            hq_parts = [p for p in [city, country] if p]
            fields["headquarters"] = ", ".join(hq_parts)

        # Founded
        founded = fd.get("YEAR_FOUNDED")
        if founded:
            fields["year_founded"] = str(founded)

        return fields

    def get_source_url(self, provider_id: str) -> str:
        """Deep link to Bloomberg Terminal company page."""
        return f"https://www.bloomberg.com/profile/company/{provider_id}"
