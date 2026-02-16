"""
Certify Intel - Preqin Data Provider

Preqin is the leading source for alternative assets data including
private equity, venture capital, private debt, hedge funds, and
infrastructure investments.

API Docs: https://developer.preqin.com/
Auth: API key in header (X-Preqin-API-Key)
Rate Limit: 40 requests/minute
"""

import logging
from typing import Optional, Dict, Any

import httpx

from .base_provider import BaseDataProvider

logger = logging.getLogger(__name__)


class PreqinProvider(BaseDataProvider):
    """Preqin provider for PE/VC fund data and alternative asset intelligence."""

    provider_name = "Preqin"
    env_key_name = "PREQIN_API_KEY"
    base_url = "https://api.preqin.com/api/v3"
    rate_limit_per_minute = 40
    description = "Private equity and venture capital fund data, investor profiles, and deal flow"

    def _get_auth_headers(self) -> Dict[str, str]:
        return {
            "X-Preqin-API-Key": self.api_key,
            "Accept": "application/json",
        }

    async def search_company(self, company_name: str) -> Optional[Dict[str, Any]]:
        """Search Preqin for a company (as a portfolio company or fund manager)."""
        await self._rate_limit()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.base_url}/portfolio-companies/search",
                    params={"name": company_name, "limit": 5},
                    headers=self._get_auth_headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                companies = data.get("portfolioCompanies", [])
                if not companies:
                    return None
                top = companies[0]
                return {
                    "provider_id": str(top.get("portfolioCompanyId", "")),
                    "name": top.get("name", company_name),
                }
        except Exception as e:
            logger.error(f"Preqin search error: {e}")
            return None

    async def get_company_profile(self, provider_id: str) -> Optional[Dict[str, Any]]:
        """Get portfolio company profile from Preqin."""
        await self._rate_limit()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.base_url}/portfolio-companies/{provider_id}",
                    params={"include": "deals,investors,financials"},
                    headers=self._get_auth_headers(),
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"Preqin profile error: {e}")
            return None

    def map_to_competitor_fields(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map Preqin data to Competitor model columns."""
        fields = {}

        # Deals / funding
        deals = raw_data.get("deals", [])
        if deals:
            # Most recent deal first
            latest_deal = deals[0] if isinstance(deals[0], dict) else {}
            deal_type = latest_deal.get("dealType") or latest_deal.get("type")
            if deal_type:
                fields["latest_round"] = str(deal_type)

            deal_size = latest_deal.get("dealSize") or latest_deal.get("size")
            if deal_size:
                fields["funding_total"] = str(deal_size)

            deal_date = latest_deal.get("dealDate") or latest_deal.get("date")
            if deal_date:
                fields["last_funding_date"] = str(deal_date)

        # Investors
        investors = raw_data.get("investors", [])
        if investors:
            names = [i.get("name", "") if isinstance(i, dict) else str(i) for i in investors[:10]]
            fields["pe_vc_backers"] = "; ".join(n for n in names if n)

        # Financials
        financials = raw_data.get("financials", {})
        if isinstance(financials, dict):
            revenue = financials.get("revenue")
            if revenue:
                fields["estimated_revenue"] = str(revenue)

            ebitda = financials.get("ebitda")
            if ebitda and revenue:
                try:
                    margin = float(ebitda) / float(revenue) * 100
                    fields["profit_margin"] = f"{margin:.1f}%"
                except (ValueError, ZeroDivisionError):
                    pass

        # Company basics
        hq = raw_data.get("headquarters") or raw_data.get("location")
        if hq:
            fields["headquarters"] = str(hq)

        sector = raw_data.get("sector") or raw_data.get("industry")
        if sector:
            fields["product_categories"] = str(sector)

        valuation = raw_data.get("latestValuation") or raw_data.get("valuation")
        if valuation:
            fields["estimated_valuation"] = str(valuation)

        funding_stage = raw_data.get("fundingStage") or raw_data.get("stage")
        if funding_stage:
            fields["funding_stage"] = str(funding_stage)

        return fields

    def get_source_url(self, provider_id: str) -> str:
        """Deep link to Preqin portfolio company page."""
        return f"https://www.preqin.com/data/portfolio-companies/{provider_id}"
