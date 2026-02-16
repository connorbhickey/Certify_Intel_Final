"""
Certify Intel - Base Data Provider Abstract Class

Abstract base for all enterprise data provider integrations.
Each provider adapter inherits from this class and implements
the abstract methods for company search, profile retrieval,
and field mapping to Competitor model columns.

All providers:
- Check configuration via environment variables
- Use httpx.AsyncClient for HTTP calls
- Map external data to Competitor ORM field names
- Generate deep-linkable source URLs
- Rate limit themselves per provider specs
"""

import os
import logging
import time
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ProviderResult:
    """Result from a single provider query."""
    provider_name: str
    company_name: str
    fields: Dict[str, Any] = field(default_factory=dict)
    source_urls: Dict[str, str] = field(default_factory=dict)
    raw_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    latency_ms: float = 0.0


class BaseDataProvider(ABC):
    """
    Abstract base class for enterprise data provider integrations.

    Subclasses must define class attributes:
        provider_name: str - Human-readable name (e.g., "PitchBook")
        env_key_name: str - Environment variable for API key (e.g., "PITCHBOOK_API_KEY")
        base_url: str - API base URL
        rate_limit_per_minute: int - Max requests per minute
        description: str - Brief description of the provider

    And implement abstract methods:
        search_company() - Search for a company by name
        get_company_profile() - Get full company profile by provider ID
        map_to_competitor_fields() - Map raw API data to Competitor model columns
    """

    # Subclasses MUST override these
    provider_name: str = ""
    env_key_name: str = ""
    base_url: str = ""
    rate_limit_per_minute: int = 60
    description: str = ""

    def __init__(self):
        """Initialize provider with API key from environment."""
        self.api_key = os.getenv(self.env_key_name, "")
        self._last_request_time = 0.0
        self._request_count = 0
        self._minute_start = 0.0

    @classmethod
    def is_configured(cls) -> bool:
        """Check if this provider's API key is set in the environment."""
        return bool(os.getenv(cls.env_key_name, ""))

    @abstractmethod
    async def search_company(self, company_name: str) -> Optional[Dict[str, Any]]:
        """
        Search for a company by name.

        Args:
            company_name: Name of the company to search for.

        Returns:
            Dict with at least 'provider_id' and 'name' keys, or None if not found.
        """
        pass

    @abstractmethod
    async def get_company_profile(self, provider_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full company profile by provider-specific ID.

        Args:
            provider_id: The provider's internal company identifier.

        Returns:
            Dict with raw company data from the provider, or None on error.
        """
        pass

    @abstractmethod
    def map_to_competitor_fields(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map raw provider data to Competitor model column names.

        Must return a dict where:
        - Keys are valid Competitor model column names
          (e.g., 'employee_count', 'funding_total', 'headquarters')
        - Values are strings or appropriate types for those columns

        Args:
            raw_data: Raw data dict from get_company_profile().

        Returns:
            Dict mapping Competitor column names to values.
        """
        pass

    def get_source_url(self, provider_id: str) -> str:
        """
        Generate a deep-linkable URL for a company on this provider's platform.

        Args:
            provider_id: The provider's internal company identifier.

        Returns:
            A URL string that links directly to the company's profile.
        """
        return f"{self.base_url}/company/{provider_id}"

    def get_source_metadata(self) -> Dict[str, Any]:
        """
        Return metadata about this provider for source attribution.

        Returns:
            Dict with provider_name, description, base_url, and configured status.
        """
        return {
            "provider_name": self.provider_name,
            "description": self.description,
            "base_url": self.base_url,
            "is_configured": self.is_configured(),
            "rate_limit_per_minute": self.rate_limit_per_minute,
        }

    async def test_connection(self) -> Dict[str, Any]:
        """
        Test connectivity to the provider API.

        Returns:
            Dict with 'success' bool, 'message' string, and 'latency_ms'.
        """
        if not self.is_configured():
            return {
                "success": False,
                "message": f"{self.env_key_name} not set",
                "latency_ms": 0,
            }

        import httpx

        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    self.base_url,
                    headers=self._get_auth_headers(),
                )
                latency = (time.time() - start) * 1000
                return {
                    "success": resp.status_code < 500,
                    "message": f"HTTP {resp.status_code}",
                    "latency_ms": round(latency, 1),
                }
        except Exception as e:
            latency = (time.time() - start) * 1000
            return {
                "success": False,
                "message": str(e),
                "latency_ms": round(latency, 1),
            }

    def _get_auth_headers(self) -> Dict[str, str]:
        """
        Get authentication headers for API requests.

        Override in subclasses for provider-specific auth patterns.
        Default: Bearer token in Authorization header.
        """
        return {"Authorization": f"Bearer {self.api_key}"}

    async def _rate_limit(self):
        """
        Enforce rate limiting. Call before each API request.

        Uses a simple sliding window: tracks request count per minute.
        """
        import asyncio

        now = time.time()

        # Reset counter each minute
        if now - self._minute_start > 60:
            self._minute_start = now
            self._request_count = 0

        self._request_count += 1

        if self._request_count > self.rate_limit_per_minute:
            wait_time = 60 - (now - self._minute_start)
            if wait_time > 0:
                logger.info(
                    f"{self.provider_name}: Rate limit reached, waiting {wait_time:.1f}s"
                )
                await asyncio.sleep(wait_time)
                self._minute_start = time.time()
                self._request_count = 1

    async def query_for_competitor(self, company_name: str) -> ProviderResult:
        """
        Full pipeline: search company, get profile, map to Competitor fields.

        This is the main entry point for querying a provider about a company.

        Args:
            company_name: Name of the company to look up.

        Returns:
            ProviderResult with mapped fields, source URLs, and any errors.
        """
        start = time.time()
        result = ProviderResult(
            provider_name=self.provider_name,
            company_name=company_name,
        )

        if not self.is_configured():
            result.error = f"{self.provider_name} not configured ({self.env_key_name} not set)"
            return result

        try:
            # Step 1: Search for the company
            search_result = await self.search_company(company_name)
            if not search_result:
                result.error = f"Company '{company_name}' not found on {self.provider_name}"
                result.latency_ms = (time.time() - start) * 1000
                return result

            provider_id = search_result.get("provider_id", "")

            # Step 2: Get full profile
            raw_data = await self.get_company_profile(provider_id)
            if not raw_data:
                result.error = f"Could not retrieve profile from {self.provider_name}"
                result.latency_ms = (time.time() - start) * 1000
                return result

            result.raw_data = raw_data

            # Step 3: Map to Competitor fields
            result.fields = self.map_to_competitor_fields(raw_data)

            # Step 4: Generate source URLs for each mapped field
            source_url = self.get_source_url(provider_id)
            for field_name in result.fields:
                result.source_urls[field_name] = source_url

        except Exception as e:
            logger.error(f"{self.provider_name} query error for '{company_name}': {e}")
            result.error = f"{self.provider_name} error: {e}"

        result.latency_ms = (time.time() - start) * 1000
        return result
