"""
Certify Intel - Bureau van Dijk Orbis Data Provider

Orbis (by Bureau van Dijk / Moody's) is the world's largest
database of private company information, covering 400M+ companies
with corporate structure, financials, and beneficial ownership.

API Docs: https://www.bvdinfo.com/en-gb/our-products/data/international/orbis
Auth: API key + user credentials
Rate Limit: 30 requests/minute
"""

import logging
from typing import Optional, Dict, Any

import httpx

from .base_provider import BaseDataProvider

logger = logging.getLogger(__name__)


class OrbisProvider(BaseDataProvider):
    """Orbis provider for corporate structure, financials, and ownership data."""

    provider_name = "Orbis"
    env_key_name = "ORBIS_API_KEY"
    base_url = "https://api.bvdinfo.com/v1"
    rate_limit_per_minute = 30
    description = "Corporate structure, global financials, beneficial ownership, and 400M+ company profiles"

    def _get_auth_headers(self) -> Dict[str, str]:
        import os
        return {
            "ApiToken": self.api_key,
            "X-Orbis-Username": os.getenv("ORBIS_USERNAME", ""),
            "Accept": "application/json",
        }

    async def search_company(self, company_name: str) -> Optional[Dict[str, Any]]:
        """Search Orbis for a company by name."""
        await self._rate_limit()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/Companies/Search",
                    json={
                        "WHERE": [
                            {"Name": company_name, "MatchType": "Contains"}
                        ],
                        "LIMIT": 5,
                    },
                    headers=self._get_auth_headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                companies = data.get("Data", [])
                if not companies:
                    return None
                top = companies[0]
                return {
                    "provider_id": top.get("BvDID", ""),
                    "name": top.get("Name", company_name),
                }
        except Exception as e:
            logger.error(f"Orbis search error: {e}")
            return None

    async def get_company_profile(self, provider_id: str) -> Optional[Dict[str, Any]]:
        """Get full company profile from Orbis."""
        await self._rate_limit()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/Companies/Data",
                    json={
                        "BvDID": provider_id,
                        "SelectionCriteria": [
                            "Name", "Country", "City", "Postcode",
                            "OperatingRevenue", "NetIncome", "TotalAssets",
                            "NumberOfEmployees", "DateOfIncorporation",
                            "NationalId", "BvDSector", "ConsolidationCode",
                            "GlobalUltimateOwner", "Shareholders",
                        ],
                    },
                    headers=self._get_auth_headers(),
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"Orbis profile error: {e}")
            return None

    def map_to_competitor_fields(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map Orbis data to Competitor model columns."""
        fields = {}

        data = raw_data.get("Data", raw_data)
        if isinstance(data, list) and data:
            data = data[0] if isinstance(data[0], dict) else {}

        # Revenue
        revenue = data.get("OperatingRevenue")
        if revenue:
            fields["annual_revenue"] = str(revenue)
            fields["estimated_revenue"] = str(revenue)

        # Net income
        net_income = data.get("NetIncome")
        if net_income:
            fields["net_income"] = str(net_income)

        # Profit margin
        if revenue and net_income:
            try:
                margin = float(net_income) / float(revenue) * 100
                fields["profit_margin"] = f"{margin:.1f}%"
            except (ValueError, ZeroDivisionError):
                pass

        # Employees
        employees = data.get("NumberOfEmployees")
        if employees:
            fields["employee_count"] = str(employees)

        # Headquarters
        city = data.get("City", "")
        country = data.get("Country", "")
        if city or country:
            hq_parts = [p for p in [city, country] if p]
            fields["headquarters"] = ", ".join(hq_parts)

        # Founded / Incorporated
        inc_date = data.get("DateOfIncorporation")
        if inc_date:
            fields["year_founded"] = str(inc_date)[:4] if len(str(inc_date)) >= 4 else str(inc_date)

        # Sector / industry
        sector = data.get("BvDSector")
        if sector:
            fields["product_categories"] = str(sector)

        # Ultimate owner (useful for acquisition_history)
        guo = data.get("GlobalUltimateOwner")
        if guo:
            guo_name = guo.get("Name", "") if isinstance(guo, dict) else str(guo)
            if guo_name:
                fields["notes"] = f"Global Ultimate Owner: {guo_name}"

        return fields

    def get_source_url(self, provider_id: str) -> str:
        """Deep link to Orbis company page (requires subscription)."""
        return f"https://orbis.bvdinfo.com/version-2024/orbis/Companies/CompanyProfile?bvdId={provider_id}"
