"""
Certify Intel - S&P Capital IQ Data Provider

S&P Capital IQ is an institutional-grade financial data platform
providing comprehensive financial statements, market data, and
company credit profiles.

API Docs: https://developer.marketintelligence.spglobal.com/
Auth: API key + App ID in headers
Rate Limit: 50 requests/minute (standard tier)
"""

import logging
from typing import Optional, Dict, Any

import httpx

from .base_provider import BaseDataProvider

logger = logging.getLogger(__name__)


class SPCapitalIQProvider(BaseDataProvider):
    """S&P Capital IQ provider for financial statements and market data."""

    provider_name = "S&P Capital IQ"
    env_key_name = "SP_CAPITAL_IQ_API_KEY"
    base_url = "https://api-ciq.marketintelligence.spglobal.com/gdsapi/rest/v3"
    rate_limit_per_minute = 50
    description = "Institutional financial data: revenue, income, market cap, credit ratings, and estimates"

    def _get_auth_headers(self) -> Dict[str, str]:
        import os
        return {
            "Authorization": f"Bearer {self.api_key}",
            "X-SPGMI-Application-Id": os.getenv("SP_CAPITAL_IQ_APP_ID", "certify-intel"),
            "Accept": "application/json",
        }

    async def search_company(self, company_name: str) -> Optional[Dict[str, Any]]:
        """Search Capital IQ for a company by name."""
        await self._rate_limit()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/companies/search",
                    json={"searchTerm": company_name, "maxResults": 5},
                    headers=self._get_auth_headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                results = data.get("results", [])
                if not results:
                    return None
                top = results[0]
                return {
                    "provider_id": str(top.get("companyId", "")),
                    "name": top.get("companyName", company_name),
                }
        except Exception as e:
            logger.error(f"Capital IQ search error: {e}")
            return None

    async def get_company_profile(self, provider_id: str) -> Optional[Dict[str, Any]]:
        """Get full company financial profile from Capital IQ."""
        await self._rate_limit()
        try:
            mnemonics = [
                "IQ_TOTAL_REV", "IQ_NET_INCOME", "IQ_MARKETCAP",
                "IQ_TOTAL_EMPLOYEES", "IQ_COMPANY_HQ_CITY",
                "IQ_COMPANY_HQ_STATE", "IQ_COMPANY_FOUNDED_YEAR",
                "IQ_EBITDA", "IQ_GROSS_MARGIN", "IQ_REVENUE_EST",
            ]
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/datapoints",
                    json={
                        "companyId": provider_id,
                        "mnemonics": mnemonics,
                    },
                    headers=self._get_auth_headers(),
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"Capital IQ profile error: {e}")
            return None

    def map_to_competitor_fields(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map Capital IQ financial data to Competitor model columns."""
        fields = {}

        datapoints = raw_data.get("datapoints", raw_data)
        if isinstance(datapoints, list):
            dp_map = {}
            for dp in datapoints:
                mnemonic = dp.get("mnemonic", "")
                value = dp.get("value")
                if mnemonic and value is not None:
                    dp_map[mnemonic] = value
        elif isinstance(datapoints, dict):
            dp_map = datapoints
        else:
            dp_map = {}

        # Revenue
        total_rev = dp_map.get("IQ_TOTAL_REV")
        if total_rev:
            fields["annual_revenue"] = str(total_rev)
            fields["estimated_revenue"] = str(total_rev)

        # Net income
        net_income = dp_map.get("IQ_NET_INCOME")
        if net_income:
            fields["net_income"] = str(net_income)

        # Margin
        gross_margin = dp_map.get("IQ_GROSS_MARGIN")
        if gross_margin:
            fields["profit_margin"] = f"{gross_margin}%"

        # Market cap (proxy for valuation of public companies)
        market_cap = dp_map.get("IQ_MARKETCAP")
        if market_cap:
            fields["estimated_valuation"] = str(market_cap)

        # Employees
        employees = dp_map.get("IQ_TOTAL_EMPLOYEES")
        if employees:
            fields["employee_count"] = str(employees)

        # Headquarters
        city = dp_map.get("IQ_COMPANY_HQ_CITY", "")
        state = dp_map.get("IQ_COMPANY_HQ_STATE", "")
        if city or state:
            hq_parts = [p for p in [city, state] if p]
            fields["headquarters"] = ", ".join(hq_parts)

        # Founded
        founded = dp_map.get("IQ_COMPANY_FOUNDED_YEAR")
        if founded:
            fields["year_founded"] = str(founded)

        # Revenue estimate (consensus)
        rev_est = dp_map.get("IQ_REVENUE_EST")
        if rev_est:
            fields["estimated_revenue"] = str(rev_est)

        return fields

    def get_source_url(self, provider_id: str) -> str:
        """Deep link to Capital IQ company page."""
        return f"https://www.capitaliq.spglobal.com/web/client#company/profile?id={provider_id}"
