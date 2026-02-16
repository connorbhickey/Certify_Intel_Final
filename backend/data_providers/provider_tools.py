"""
Certify Intel - Enterprise Data Provider Query Tools

High-level functions for querying enterprise data providers.
Used by:
- LangGraph agents (via BaseAgent.enterprise_lookup)
- Source discovery engine (before Gemini fallback)
- Data triangulator (for cross-referencing)
- API endpoints (direct provider queries)

These functions handle:
- Querying all active (configured) providers in parallel
- Merging results with source attribution
- Single-field lookups for the source discovery pipeline
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List

from .base_provider import ProviderResult

logger = logging.getLogger(__name__)


async def query_enterprise_sources(
    company_name: str,
    fields: Optional[List[str]] = None,
    providers: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Query all active enterprise providers for a company, return merged results.

    Results are merged with source attribution: each field value includes
    which provider supplied it and a deep-link source URL.

    Args:
        company_name: Name of the company to look up.
        fields: Optional list of Competitor field names to filter results to.
            If None, all mapped fields from all providers are returned.
        providers: Optional list of provider names to query (case-insensitive).
            If None, all configured providers are queried.

    Returns:
        Dict with:
        - merged_fields: Dict[field_name, {value, provider, source_url}]
        - provider_results: List of per-provider result summaries
        - providers_queried: int
        - providers_with_data: int
        - errors: List[str]
    """
    from . import get_active_providers, get_provider

    # Determine which providers to query
    if providers:
        active = []
        for name in providers:
            p = get_provider(name)
            if p:
                active.append(p)
            else:
                logger.warning(f"Provider '{name}' not available (not configured or unknown)")
    else:
        active = get_active_providers()

    if not active:
        return {
            "merged_fields": {},
            "provider_results": [],
            "providers_queried": 0,
            "providers_with_data": 0,
            "errors": ["No enterprise data providers configured"],
        }

    # Query all providers in parallel
    tasks = [provider.query_for_competitor(company_name) for provider in active]
    results: List[ProviderResult] = await asyncio.gather(*tasks, return_exceptions=True)

    merged_fields: Dict[str, Dict[str, Any]] = {}
    provider_summaries = []
    errors = []
    providers_with_data = 0

    # Provider authority order for conflict resolution (first = highest authority)
    authority_order = [
        "PitchBook", "S&P Capital IQ", "Bloomberg", "FactSet", "LSEG",
        "Orbis", "Crunchbase", "CB Insights", "Dealroom", "Preqin",
    ]

    def provider_priority(name: str) -> int:
        try:
            return authority_order.index(name)
        except ValueError:
            return len(authority_order)

    # Process results in authority order
    sorted_results = []
    for r in results:
        if isinstance(r, Exception):
            errors.append(str(r))
            continue
        sorted_results.append(r)

    sorted_results.sort(key=lambda r: provider_priority(r.provider_name))

    for result in sorted_results:
        summary = {
            "provider": result.provider_name,
            "fields_returned": len(result.fields),
            "latency_ms": round(result.latency_ms, 1),
            "error": result.error,
        }
        provider_summaries.append(summary)

        if result.error:
            errors.append(f"{result.provider_name}: {result.error}")
            continue

        if result.fields:
            providers_with_data += 1

        for field_name, value in result.fields.items():
            # Filter to requested fields if specified
            if fields and field_name not in fields:
                continue

            # Only take the first (highest authority) value for each field
            if field_name not in merged_fields:
                merged_fields[field_name] = {
                    "value": value,
                    "provider": result.provider_name,
                    "source_url": result.source_urls.get(field_name, ""),
                }

    return {
        "merged_fields": merged_fields,
        "provider_results": provider_summaries,
        "providers_queried": len(active),
        "providers_with_data": providers_with_data,
        "errors": errors,
    }


async def query_enterprise_for_field(
    company_name: str,
    field_name: str,
    current_value: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Query enterprise sources for a single field value.

    This is the lightweight entry point used by the source discovery engine
    to check enterprise providers BEFORE falling back to Gemini search.

    Args:
        company_name: Company name to look up.
        field_name: Specific Competitor model field to retrieve.
        current_value: The current stored value (for comparison, not used in query).

    Returns:
        Dict with {value, provider, source_url, source_type} if found, None otherwise.
    """
    result = await query_enterprise_sources(
        company_name=company_name,
        fields=[field_name],
    )

    merged = result.get("merged_fields", {})
    if field_name in merged:
        entry = merged[field_name]
        return {
            "value": entry["value"],
            "provider": entry["provider"],
            "source_url": entry["source_url"],
            "source_type": "enterprise_api",
        }

    return None
