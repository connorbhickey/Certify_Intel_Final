"""
Enterprise Data Provider Registry for Certify Intel.

Provides a unified interface to 10 enterprise data providers for
competitor intelligence enrichment. Each provider is an adapter that
inherits from BaseDataProvider and maps external API data to
Competitor model columns.

Usage:
    from data_providers import get_active_providers, get_provider

    # Get all providers whose API keys are configured
    active = get_active_providers()

    # Get a specific provider by name
    pb = get_provider("pitchbook")
    if pb:
        result = await pb.query_for_competitor("Epic Systems")
"""

from typing import List, Optional

from .base_provider import BaseDataProvider, ProviderResult  # noqa: F401

# Import all provider adapter classes
from .pitchbook import PitchBookProvider  # noqa: F401
from .crunchbase import CrunchbaseProvider  # noqa: F401
from .sp_capital_iq import SPCapitalIQProvider  # noqa: F401
from .bloomberg import BloombergProvider  # noqa: F401
from .lseg import LSEGProvider  # noqa: F401
from .cb_insights import CBInsightsProvider  # noqa: F401
from .dealroom import DealroomProvider  # noqa: F401
from .preqin import PreqinProvider  # noqa: F401
from .orbis import OrbisProvider  # noqa: F401
from .factset import FactSetProvider  # noqa: F401

ALL_PROVIDERS = [
    PitchBookProvider,
    CrunchbaseProvider,
    SPCapitalIQProvider,
    BloombergProvider,
    LSEGProvider,
    CBInsightsProvider,
    DealroomProvider,
    PreqinProvider,
    OrbisProvider,
    FactSetProvider,
]


def get_active_providers() -> List[BaseDataProvider]:
    """Return only providers whose API keys are configured."""
    return [ProviderClass() for ProviderClass in ALL_PROVIDERS if ProviderClass.is_configured()]


def get_provider(name: str) -> Optional[BaseDataProvider]:
    """
    Get a specific provider by name (case-insensitive).

    Args:
        name: Provider name, e.g. "pitchbook", "crunchbase".

    Returns:
        Provider instance if configured, None otherwise.
    """
    for ProviderClass in ALL_PROVIDERS:
        if ProviderClass.provider_name.lower() == name.lower():
            if ProviderClass.is_configured():
                return ProviderClass()
    return None


def get_all_provider_status() -> List[dict]:
    """
    Return configuration status of all providers.

    Useful for the settings UI and health checks.
    """
    return [
        {
            "name": P.provider_name,
            "env_key": P.env_key_name,
            "configured": P.is_configured(),
            "description": P.description,
            "base_url": P.base_url,
            "rate_limit": P.rate_limit_per_minute,
        }
        for P in ALL_PROVIDERS
    ]
