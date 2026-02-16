"""
Certify Intel - Crunchbase Data Provider

Crunchbase is the leading source for startup funding data, company
profiles, founding dates, and organizational information.

API Docs: https://data.crunchbase.com/docs/using-the-api
Auth: API key in header (X-cb-user-key)
Rate Limit: 200 requests/minute (enterprise tier)
"""

import logging
from typing import Optional, Dict, Any

import httpx

from .base_provider import BaseDataProvider

logger = logging.getLogger(__name__)


class CrunchbaseProvider(BaseDataProvider):
    """Crunchbase provider for funding, founding, and organizational data."""

    provider_name = "Crunchbase"
    env_key_name = "CRUNCHBASE_API_KEY"
    base_url = "https://api.crunchbase.com/api/v4"
    rate_limit_per_minute = 200
    description = "Startup funding rounds, founding dates, employee counts, and organizational data"

    def _get_auth_headers(self) -> Dict[str, str]:
        return {
            "X-cb-user-key": self.api_key,
            "Accept": "application/json",
        }

    async def search_company(self, company_name: str) -> Optional[Dict[str, Any]]:
        """Search Crunchbase for a company by name."""
        await self._rate_limit()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.base_url}/autocompletes",
                    params={
                        "query": company_name,
                        "collection_ids": "organizations",
                        "limit": 5,
                    },
                    headers=self._get_auth_headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                entities = data.get("entities", [])
                if not entities:
                    return None
                top = entities[0]
                identifier = top.get("identifier", {})
                return {
                    "provider_id": identifier.get("permalink", ""),
                    "name": identifier.get("value", company_name),
                }
        except Exception as e:
            logger.error(f"Crunchbase search error: {e}")
            return None

    async def get_company_profile(self, provider_id: str) -> Optional[Dict[str, Any]]:
        """Get full company profile from Crunchbase."""
        await self._rate_limit()
        try:
            field_ids = (
                "short_description,founded_on,num_employees_enum,funding_total,"
                "last_funding_type,last_funding_at,ipo_status,headquarters_location,"
                "categories,investor_identifiers,revenue_range,contact_email,"
                "website,linkedin,twitter"
            )
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.base_url}/entities/organizations/{provider_id}",
                    params={"field_ids": field_ids},
                    headers=self._get_auth_headers(),
                )
                resp.raise_for_status()
                return resp.json().get("properties", resp.json())
        except Exception as e:
            logger.error(f"Crunchbase profile error: {e}")
            return None

    def map_to_competitor_fields(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map Crunchbase data to Competitor model columns."""
        fields = {}

        # Funding
        funding = raw_data.get("funding_total", {})
        if isinstance(funding, dict):
            value = funding.get("value")
            currency = funding.get("currency", "USD")
            if value:
                fields["funding_total"] = f"${value:,.0f} {currency}" if isinstance(value, (int, float)) else str(value)
        elif funding:
            fields["funding_total"] = str(funding)

        last_type = raw_data.get("last_funding_type")
        if last_type:
            fields["latest_round"] = str(last_type)

        last_date = raw_data.get("last_funding_at")
        if last_date:
            fields["last_funding_date"] = str(last_date)

        ipo_status = raw_data.get("ipo_status")
        if ipo_status:
            fields["funding_stage"] = str(ipo_status)

        # Employees
        emp_enum = raw_data.get("num_employees_enum")
        if emp_enum:
            fields["employee_count"] = str(emp_enum)

        # Company basics
        founded = raw_data.get("founded_on")
        if founded:
            fields["year_founded"] = str(founded)[:4] if len(str(founded)) >= 4 else str(founded)

        hq = raw_data.get("headquarters_location", {})
        if isinstance(hq, dict):
            city = hq.get("value", "")
            if city:
                fields["headquarters"] = str(city)
        elif hq:
            fields["headquarters"] = str(hq)

        # Revenue range
        rev_range = raw_data.get("revenue_range")
        if rev_range:
            fields["estimated_revenue"] = str(rev_range)

        # Categories / product focus
        categories = raw_data.get("categories", [])
        if categories:
            cat_names = [c.get("value", "") if isinstance(c, dict) else str(c) for c in categories[:5]]
            fields["product_categories"] = "; ".join(n for n in cat_names if n)

        # Social
        linkedin = raw_data.get("linkedin", {})
        if isinstance(linkedin, dict) and linkedin.get("value"):
            fields["linkedin_url"] = str(linkedin["value"])
        elif linkedin and isinstance(linkedin, str):
            fields["linkedin_url"] = linkedin

        # Investors
        investors = raw_data.get("investor_identifiers", [])
        if investors:
            inv_names = [i.get("value", "") if isinstance(i, dict) else str(i) for i in investors[:10]]
            fields["pe_vc_backers"] = "; ".join(n for n in inv_names if n)

        return fields

    def get_source_url(self, provider_id: str) -> str:
        """Deep link to Crunchbase organization page."""
        return f"https://www.crunchbase.com/organization/{provider_id}"
