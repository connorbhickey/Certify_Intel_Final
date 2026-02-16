"""
Certify Intel - Dealroom Data Provider

Dealroom is a European-focused platform for startup and scale-up
intelligence, providing funding data, employee counts, tech stack
information, and growth signals via a GraphQL API.

API Docs: https://docs.dealroom.co/
Auth: API key in header (Authorization: Bearer)
Rate Limit: 120 requests/minute
"""

import logging
from typing import Optional, Dict, Any

import httpx

from .base_provider import BaseDataProvider

logger = logging.getLogger(__name__)


class DealroomProvider(BaseDataProvider):
    """Dealroom provider for startup funding, employee data, and tech stack."""

    provider_name = "Dealroom"
    env_key_name = "DEALROOM_API_KEY"
    base_url = "https://api.dealroom.co/api/v2"
    rate_limit_per_minute = 120
    description = "European startup intelligence: funding, employee counts, tech stack, and growth signals (GraphQL)"

    def _get_auth_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def search_company(self, company_name: str) -> Optional[Dict[str, Any]]:
        """Search Dealroom for a company by name via GraphQL."""
        await self._rate_limit()
        try:
            query = {
                "query": """
                    query SearchCompanies($name: String!) {
                        companies(name: $name, limit: 5) {
                            id
                            name
                            slug
                        }
                    }
                """,
                "variables": {"name": company_name},
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/graphql",
                    json=query,
                    headers=self._get_auth_headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                companies = data.get("data", {}).get("companies", [])
                if not companies:
                    return None
                top = companies[0]
                return {
                    "provider_id": str(top.get("id", "")),
                    "name": top.get("name", company_name),
                    "slug": top.get("slug", ""),
                }
        except Exception as e:
            logger.error(f"Dealroom search error: {e}")
            return None

    async def get_company_profile(self, provider_id: str) -> Optional[Dict[str, Any]]:
        """Get full company profile from Dealroom via GraphQL."""
        await self._rate_limit()
        try:
            query = {
                "query": """
                    query GetCompany($id: ID!) {
                        company(id: $id) {
                            id
                            name
                            slug
                            tagline
                            totalFunding
                            lastFundingRound { type amount date }
                            employees
                            employeeGrowth
                            headquarters { city country }
                            foundedDate
                            technologies
                            investors { name }
                            revenue
                            valuation
                            industries
                            websiteUrl
                        }
                    }
                """,
                "variables": {"id": provider_id},
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/graphql",
                    json=query,
                    headers=self._get_auth_headers(),
                )
                resp.raise_for_status()
                return resp.json().get("data", {}).get("company", {})
        except Exception as e:
            logger.error(f"Dealroom profile error: {e}")
            return None

    def map_to_competitor_fields(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map Dealroom data to Competitor model columns."""
        fields = {}

        # Funding
        total_funding = raw_data.get("totalFunding")
        if total_funding:
            fields["funding_total"] = str(total_funding)

        last_round = raw_data.get("lastFundingRound", {})
        if isinstance(last_round, dict):
            round_type = last_round.get("type")
            if round_type:
                fields["latest_round"] = str(round_type)
            round_date = last_round.get("date")
            if round_date:
                fields["last_funding_date"] = str(round_date)

        # Investors
        investors = raw_data.get("investors", [])
        if investors:
            names = [i.get("name", "") if isinstance(i, dict) else str(i) for i in investors[:10]]
            fields["pe_vc_backers"] = "; ".join(n for n in names if n)

        # Employees
        employees = raw_data.get("employees")
        if employees:
            fields["employee_count"] = str(employees)

        emp_growth = raw_data.get("employeeGrowth")
        if emp_growth:
            fields["employee_growth_rate"] = f"{emp_growth}%"

        # Headquarters
        hq = raw_data.get("headquarters", {})
        if isinstance(hq, dict):
            city = hq.get("city", "")
            country = hq.get("country", "")
            if city or country:
                hq_parts = [p for p in [city, country] if p]
                fields["headquarters"] = ", ".join(hq_parts)

        # Founded
        founded = raw_data.get("foundedDate")
        if founded:
            fields["year_founded"] = str(founded)[:4] if len(str(founded)) >= 4 else str(founded)

        # Tech stack
        technologies = raw_data.get("technologies", [])
        if technologies:
            fields["tech_stack"] = "; ".join(str(t) for t in technologies[:10])

        # Revenue
        revenue = raw_data.get("revenue")
        if revenue:
            fields["estimated_revenue"] = str(revenue)

        # Valuation
        valuation = raw_data.get("valuation")
        if valuation:
            fields["estimated_valuation"] = str(valuation)

        # Industries / categories
        industries = raw_data.get("industries", [])
        if industries:
            fields["product_categories"] = "; ".join(str(i) for i in industries[:5])

        return fields

    def get_source_url(self, provider_id: str) -> str:
        """Deep link to Dealroom company page."""
        return f"https://app.dealroom.co/companies/{provider_id}"
