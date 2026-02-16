"""
Certify Intel - FactSet Data Provider

FactSet provides financial data, analytics, and estimates
used by institutional investors and corporate finance teams.
Strong coverage of consensus estimates, ownership data, and fundamentals.

API Docs: https://developer.factset.com/api-catalog
Auth: Basic auth (username:api_key) or OAuth2
Rate Limit: 60 requests/minute
"""

import logging
from typing import Optional, Dict, Any

import httpx

from .base_provider import BaseDataProvider

logger = logging.getLogger(__name__)


class FactSetProvider(BaseDataProvider):
    """FactSet provider for consensus estimates, fundamentals, and ownership."""

    provider_name = "FactSet"
    env_key_name = "FACTSET_API_KEY"
    base_url = "https://api.factset.com"
    rate_limit_per_minute = 60
    description = "Consensus estimates, financial fundamentals, institutional ownership, and supply chain data"

    def _get_auth_headers(self) -> Dict[str, str]:
        import os
        username = os.getenv("FACTSET_USERNAME", "")
        return {
            "Authorization": f"Basic {self.api_key}",
            "X-FactSet-Username": username,
            "Accept": "application/json",
        }

    async def search_company(self, company_name: str) -> Optional[Dict[str, Any]]:
        """Search FactSet for a company by name."""
        await self._rate_limit()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/idsearch/v1/idsearch",
                    json={
                        "input": {"query": company_name},
                        "settings": {"result_count": 5},
                    },
                    headers=self._get_auth_headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                results = data.get("typeahead", {}).get("results", [])
                if not results:
                    return None
                top = results[0]
                return {
                    "provider_id": top.get("fsymId", top.get("entityId", "")),
                    "name": top.get("name", company_name),
                    "ticker": top.get("ticker", ""),
                }
        except Exception as e:
            logger.error(f"FactSet search error: {e}")
            return None

    async def get_company_profile(self, provider_id: str) -> Optional[Dict[str, Any]]:
        """Get company fundamentals and estimates from FactSet."""
        await self._rate_limit()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/factset-fundamentals/v2/fundamentals",
                    json={
                        "ids": [provider_id],
                        "metrics": [
                            "FF_SALES", "FF_NET_INC", "FF_MKT_VAL",
                            "FF_EMP", "FF_CITY", "FF_STATE_PROV",
                            "FF_FOUND_DT", "FF_GROSS_MGN",
                            "FF_SALES_GR", "FF_EPS_EST",
                            "FF_PE_RATIO", "FF_DIV_YLD",
                        ],
                        "periodicity": "ANN",
                        "currency": "USD",
                    },
                    headers=self._get_auth_headers(),
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"FactSet profile error: {e}")
            return None

    def map_to_competitor_fields(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map FactSet data to Competitor model columns."""
        fields = {}

        # FactSet responses nest data under 'data' array
        data_rows = raw_data.get("data", [])
        if isinstance(data_rows, list) and data_rows:
            fd = data_rows[0] if isinstance(data_rows[0], dict) else {}
        elif isinstance(data_rows, dict):
            fd = data_rows
        else:
            fd = raw_data

        # Revenue
        revenue = fd.get("FF_SALES")
        if revenue:
            fields["annual_revenue"] = str(revenue)
            fields["estimated_revenue"] = str(revenue)

        # Net income
        net_income = fd.get("FF_NET_INC")
        if net_income:
            fields["net_income"] = str(net_income)

        # Gross margin
        margin = fd.get("FF_GROSS_MGN")
        if margin:
            fields["profit_margin"] = f"{margin}%"

        # Market value (proxy for valuation)
        market_val = fd.get("FF_MKT_VAL")
        if market_val:
            fields["estimated_valuation"] = str(market_val)

        # Revenue growth
        sales_growth = fd.get("FF_SALES_GR")
        if sales_growth:
            fields["revenue_growth_rate"] = f"{sales_growth}%"

        # Employees
        employees = fd.get("FF_EMP")
        if employees:
            fields["employee_count"] = str(employees)

        # Revenue per employee
        if revenue and employees:
            try:
                rpe = float(revenue) / float(employees)
                fields["revenue_per_employee"] = f"${rpe:,.0f}"
            except (ValueError, ZeroDivisionError):
                pass

        # Headquarters
        city = fd.get("FF_CITY", "")
        state = fd.get("FF_STATE_PROV", "")
        if city or state:
            hq_parts = [p for p in [city, state] if p]
            fields["headquarters"] = ", ".join(hq_parts)

        # Founded
        founded = fd.get("FF_FOUND_DT")
        if founded:
            fields["year_founded"] = str(founded)[:4] if len(str(founded)) >= 4 else str(founded)

        return fields

    def get_source_url(self, provider_id: str) -> str:
        """Deep link to FactSet company page."""
        return f"https://open.factset.com/company/{provider_id}"
