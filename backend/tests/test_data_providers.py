"""
Certify Intel - Data Provider Tests

Tests for the 10 enterprise data provider adapters, base class,
and provider registry functions.

Run: python -m pytest -xvs tests/test_data_providers.py
"""

import os
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from data_providers import (
    BaseDataProvider,
    ProviderResult,
    get_active_providers,
    get_provider,
    get_all_provider_status,
)
from data_providers.pitchbook import PitchBookProvider
from data_providers.crunchbase import CrunchbaseProvider
from data_providers.factset import FactSetProvider
from data_providers.sp_capital_iq import SPCapitalIQProvider
from data_providers.bloomberg import BloombergProvider
from data_providers.lseg import LSEGProvider
from data_providers.cb_insights import CBInsightsProvider
from data_providers.dealroom import DealroomProvider
from data_providers.preqin import PreqinProvider
from data_providers.orbis import OrbisProvider


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_provider_env():
    """Mock environment with PitchBook and Crunchbase configured."""
    return {
        "PITCHBOOK_API_KEY": "test_pb_key_12345",
        "CRUNCHBASE_API_KEY": "test_cb_key_67890",
    }


@pytest.fixture
def all_providers_env():
    """Mock environment with all 10 providers configured."""
    return {
        "PITCHBOOK_API_KEY": "test_pb_key",
        "CRUNCHBASE_API_KEY": "test_cb_key",
        "SP_CAPITAL_IQ_API_KEY": "test_sp_key",
        "BLOOMBERG_API_KEY": "test_bb_key",
        "LSEG_API_KEY": "test_lseg_key",
        "CB_INSIGHTS_API_KEY": "test_cbi_key",
        "DEALROOM_API_KEY": "test_dr_key",
        "PREQIN_API_KEY": "test_pq_key",
        "ORBIS_API_KEY": "test_orb_key",
        "FACTSET_API_KEY": "test_fs_key",
    }


# ──────────────────────────────────────────────────────────────────────────────
# BaseDataProvider Interface Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_all_adapters_inherit_from_base():
    """Verify all 10 provider adapters inherit from BaseDataProvider."""
    adapters = [
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

    for adapter_class in adapters:
        assert issubclass(adapter_class, BaseDataProvider), (
            f"{adapter_class.__name__} must inherit from BaseDataProvider"
        )


def test_all_adapters_define_required_attributes():
    """Verify all adapters define the required class attributes."""
    adapters = [
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

    for adapter_class in adapters:
        assert adapter_class.provider_name, f"{adapter_class.__name__}.provider_name not set"
        assert adapter_class.env_key_name, f"{adapter_class.__name__}.env_key_name not set"
        assert adapter_class.base_url, f"{adapter_class.__name__}.base_url not set"
        assert adapter_class.rate_limit_per_minute > 0, (
            f"{adapter_class.__name__}.rate_limit_per_minute must be > 0"
        )
        assert adapter_class.description, f"{adapter_class.__name__}.description not set"


def test_all_adapters_implement_required_methods():
    """Verify all adapters implement the required abstract methods."""
    adapters = [
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

    required_methods = ["search_company", "get_company_profile", "map_to_competitor_fields"]

    for adapter_class in adapters:
        for method_name in required_methods:
            assert hasattr(adapter_class, method_name), (
                f"{adapter_class.__name__} missing {method_name}()"
            )
            method = getattr(adapter_class, method_name)
            assert callable(method), f"{adapter_class.__name__}.{method_name} not callable"


# ──────────────────────────────────────────────────────────────────────────────
# is_configured() Tests
# ──────────────────────────────────────────────────────────────────────────────


@patch.dict(os.environ, {"PITCHBOOK_API_KEY": "test_key"}, clear=True)
def test_is_configured_returns_true_when_key_set():
    """Test is_configured() returns True when env var is set."""
    assert PitchBookProvider.is_configured() is True


@patch.dict(os.environ, {}, clear=True)
def test_is_configured_returns_false_when_key_missing():
    """Test is_configured() returns False when env var is not set."""
    assert PitchBookProvider.is_configured() is False


@patch.dict(os.environ, {"PITCHBOOK_API_KEY": ""}, clear=True)
def test_is_configured_returns_false_for_empty_string():
    """Test is_configured() returns False when env var is empty string."""
    assert PitchBookProvider.is_configured() is False


@patch.dict(os.environ, {"CRUNCHBASE_API_KEY": "key123"}, clear=True)
def test_is_configured_multiple_providers_independently():
    """Test different providers check their own env keys independently."""
    assert CrunchbaseProvider.is_configured() is True
    assert PitchBookProvider.is_configured() is False


# ──────────────────────────────────────────────────────────────────────────────
# map_to_competitor_fields() Tests
# ──────────────────────────────────────────────────────────────────────────────


@patch.dict(os.environ, {"PITCHBOOK_API_KEY": "test_key"}, clear=True)
def test_pitchbook_map_to_competitor_fields_returns_valid_fields():
    """Test PitchBook map_to_competitor_fields() returns Competitor model fields."""
    provider = PitchBookProvider()

    raw_data = {
        "revenueEstimate": "$50M",
        "employeeCount": 250,
        "totalRaised": "$10M Series A",
        "yearFounded": 2018,
        "headquarters": "Boston, MA",
    }

    result = provider.map_to_competitor_fields(raw_data)

    # Verify result is a dict
    assert isinstance(result, dict)

    # Verify keys are valid Competitor field names
    valid_field_names = [
        "estimated_revenue",
        "employee_count",
        "funding_total",
        "year_founded",
        "headquarters",
        "latest_round",
        "funding_stage",
        "annual_revenue",
        "revenue_growth_rate",
        "estimated_valuation",
        "pe_vc_backers",
        "last_funding_date",
    ]
    for key in result.keys():
        assert key in valid_field_names, f"Unknown field: {key}"

    # Verify values are strings (as per ORM requirements)
    for value in result.values():
        assert isinstance(value, str), "All field values must be strings"


@patch.dict(os.environ, {"CRUNCHBASE_API_KEY": "test_key"}, clear=True)
def test_crunchbase_map_to_competitor_fields_handles_nested_dicts():
    """Test Crunchbase map_to_competitor_fields() handles nested dict structures."""
    provider = CrunchbaseProvider()

    raw_data = {
        "funding_total": {"value": 25000000, "currency": "USD"},
        "num_employees_enum": "51-100",
        "founded_on": "2019-03-15",
        "headquarters_location": {"value": "San Francisco, CA"},
    }

    result = provider.map_to_competitor_fields(raw_data)

    assert "funding_total" in result
    assert "USD" in result["funding_total"]
    assert "employee_count" in result
    assert result["employee_count"] == "51-100"
    assert "year_founded" in result
    assert result["year_founded"] == "2019"
    assert "headquarters" in result
    assert "San Francisco" in result["headquarters"]


@patch.dict(os.environ, {"FACTSET_API_KEY": "test_key"}, clear=True)
def test_factset_map_to_competitor_fields_handles_data_array():
    """Test FactSet map_to_competitor_fields() extracts from nested data arrays."""
    provider = FactSetProvider()

    raw_data = {
        "data": [
            {
                "FF_SALES": 100000000,
                "FF_EMP": 500,
                "FF_CITY": "Austin",
                "FF_STATE_PROV": "TX",
            }
        ]
    }

    result = provider.map_to_competitor_fields(raw_data)

    assert "annual_revenue" in result or "estimated_revenue" in result
    assert "employee_count" in result
    assert "headquarters" in result
    assert "Austin" in result["headquarters"]
    assert "TX" in result["headquarters"]


def test_map_to_competitor_fields_handles_empty_dict():
    """Test map_to_competitor_fields() returns empty dict for empty input."""
    with patch.dict(os.environ, {"PITCHBOOK_API_KEY": "test_key"}, clear=True):
        provider = PitchBookProvider()
        result = provider.map_to_competitor_fields({})
        assert isinstance(result, dict)
        assert len(result) == 0


# ──────────────────────────────────────────────────────────────────────────────
# get_source_metadata() Tests
# ──────────────────────────────────────────────────────────────────────────────


@patch.dict(os.environ, {"PITCHBOOK_API_KEY": "test_key"}, clear=True)
def test_get_source_metadata_returns_required_keys():
    """Test get_source_metadata() returns all required metadata keys."""
    provider = PitchBookProvider()
    metadata = provider.get_source_metadata()

    assert isinstance(metadata, dict)
    assert "provider_name" in metadata
    assert "description" in metadata
    assert "base_url" in metadata
    assert "is_configured" in metadata
    assert "rate_limit_per_minute" in metadata

    # Verify types
    assert isinstance(metadata["provider_name"], str)
    assert isinstance(metadata["description"], str)
    assert isinstance(metadata["base_url"], str)
    assert isinstance(metadata["is_configured"], bool)
    assert isinstance(metadata["rate_limit_per_minute"], int)


@patch.dict(os.environ, {"CRUNCHBASE_API_KEY": "test_key"}, clear=True)
def test_get_source_metadata_reflects_configured_status():
    """Test get_source_metadata() reflects is_configured status correctly."""
    provider = CrunchbaseProvider()
    metadata = provider.get_source_metadata()

    assert metadata["is_configured"] is True

    # Now test without env var
    with patch.dict(os.environ, {}, clear=True):
        provider2 = CrunchbaseProvider()
        metadata2 = provider2.get_source_metadata()
        assert metadata2["is_configured"] is False


# ──────────────────────────────────────────────────────────────────────────────
# Provider Registry Tests
# ──────────────────────────────────────────────────────────────────────────────


@patch.dict(os.environ, {"PITCHBOOK_API_KEY": "test_key", "CRUNCHBASE_API_KEY": "test_key"}, clear=True)
def test_get_active_providers_returns_only_configured():
    """Test get_active_providers() returns only providers with API keys set."""
    active = get_active_providers()

    assert len(active) == 2
    names = [p.provider_name for p in active]
    assert "PitchBook" in names
    assert "Crunchbase" in names


@patch.dict(os.environ, {}, clear=True)
def test_get_active_providers_returns_empty_when_none_configured():
    """Test get_active_providers() returns empty list when no keys set."""
    active = get_active_providers()
    assert len(active) == 0


def test_get_active_providers_with_all_providers_configured(all_providers_env):
    """Test get_active_providers() with all 10 providers configured."""
    with patch.dict(os.environ, all_providers_env, clear=True):
        active = get_active_providers()
        assert len(active) == 10


@patch.dict(os.environ, {"PITCHBOOK_API_KEY": "test_key"}, clear=True)
def test_get_provider_by_name_returns_provider():
    """Test get_provider() returns provider instance by name."""
    provider = get_provider("pitchbook")
    assert provider is not None
    assert isinstance(provider, PitchBookProvider)
    assert provider.provider_name == "PitchBook"


@patch.dict(os.environ, {"CRUNCHBASE_API_KEY": "test_key"}, clear=True)
def test_get_provider_case_insensitive():
    """Test get_provider() is case-insensitive."""
    provider_lower = get_provider("crunchbase")
    provider_upper = get_provider("CRUNCHBASE")
    provider_mixed = get_provider("CrunchBase")

    assert all([provider_lower, provider_upper, provider_mixed])
    assert provider_lower.provider_name == provider_upper.provider_name


@patch.dict(os.environ, {}, clear=True)
def test_get_provider_returns_none_when_not_configured():
    """Test get_provider() returns None when provider not configured."""
    provider = get_provider("pitchbook")
    assert provider is None


@patch.dict(os.environ, {"PITCHBOOK_API_KEY": "test_key"}, clear=True)
def test_get_provider_returns_none_for_nonexistent_provider():
    """Test get_provider() returns None for non-existent provider name."""
    provider = get_provider("nonexistent_provider")
    assert provider is None


def test_get_all_provider_status_returns_all_providers():
    """Test get_all_provider_status() returns status for all 10 providers."""
    with patch.dict(os.environ, {}, clear=True):
        statuses = get_all_provider_status()
        assert len(statuses) == 10

        for status in statuses:
            assert "name" in status
            assert "env_key" in status
            assert "configured" in status
            assert "description" in status
            assert "base_url" in status
            assert "rate_limit" in status

            # Verify types
            assert isinstance(status["name"], str)
            assert isinstance(status["env_key"], str)
            assert isinstance(status["configured"], bool)
            assert isinstance(status["description"], str)
            assert isinstance(status["base_url"], str)
            assert isinstance(status["rate_limit"], int)


@patch.dict(os.environ, {"PITCHBOOK_API_KEY": "test_key"}, clear=True)
def test_get_all_provider_status_reflects_configured_state():
    """Test get_all_provider_status() correctly shows which are configured."""
    statuses = get_all_provider_status()

    pitchbook_status = next(s for s in statuses if s["name"] == "PitchBook")
    crunchbase_status = next(s for s in statuses if s["name"] == "Crunchbase")

    assert pitchbook_status["configured"] is True
    assert crunchbase_status["configured"] is False


# ──────────────────────────────────────────────────────────────────────────────
# ProviderResult Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_provider_result_dataclass_creation():
    """Test ProviderResult dataclass can be created with required fields."""
    result = ProviderResult(
        provider_name="PitchBook",
        company_name="Epic Systems",
    )

    assert result.provider_name == "PitchBook"
    assert result.company_name == "Epic Systems"
    assert result.fields == {}
    assert result.source_urls == {}
    assert result.raw_data is None
    assert result.error is None
    assert result.latency_ms == 0.0


def test_provider_result_with_all_fields():
    """Test ProviderResult with all fields populated."""
    result = ProviderResult(
        provider_name="Crunchbase",
        company_name="Test Company",
        fields={"funding_total": "$10M"},
        source_urls={"funding_total": "https://crunchbase.com/company/test"},
        raw_data={"some": "data"},
        error=None,
        latency_ms=125.5,
    )

    assert result.provider_name == "Crunchbase"
    assert result.fields["funding_total"] == "$10M"
    assert result.latency_ms == 125.5


# ──────────────────────────────────────────────────────────────────────────────
# Integration Tests (Mocked HTTP)
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@patch.dict(os.environ, {"PITCHBOOK_API_KEY": "test_key"}, clear=True)
async def test_query_for_competitor_full_pipeline():
    """Test query_for_competitor() runs full pipeline with mocked HTTP."""
    provider = PitchBookProvider()

    # Mock search_company
    search_result = {"provider_id": "pb_12345", "name": "Epic Systems"}

    # Mock get_company_profile
    profile_data = {
        "revenueEstimate": "$3.8B",
        "employeeCount": 10000,
        "yearFounded": 1979,
    }

    with patch.object(provider, "search_company", new_callable=AsyncMock) as mock_search:
        with patch.object(provider, "get_company_profile", new_callable=AsyncMock) as mock_profile:
            mock_search.return_value = search_result
            mock_profile.return_value = profile_data

            result = await provider.query_for_competitor("Epic Systems")

            # Verify pipeline steps were called
            mock_search.assert_called_once_with("Epic Systems")
            mock_profile.assert_called_once_with("pb_12345")

            # Verify result structure
            assert result.provider_name == "PitchBook"
            assert result.company_name == "Epic Systems"
            assert result.error is None
            assert len(result.fields) > 0
            assert "estimated_revenue" in result.fields or "employee_count" in result.fields
            assert result.latency_ms > 0


@pytest.mark.asyncio
@patch.dict(os.environ, {"CRUNCHBASE_API_KEY": "test_key"}, clear=True)
async def test_query_for_competitor_company_not_found():
    """Test query_for_competitor() handles company not found gracefully."""
    provider = CrunchbaseProvider()

    with patch.object(provider, "search_company", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = None  # Company not found

        result = await provider.query_for_competitor("NonExistent Company")

        assert result.error is not None
        assert "not found" in result.error
        assert len(result.fields) == 0


@pytest.mark.asyncio
@patch.dict(os.environ, {}, clear=True)
async def test_query_for_competitor_not_configured():
    """Test query_for_competitor() returns error when provider not configured."""
    provider = PitchBookProvider()

    result = await provider.query_for_competitor("Test Company")

    assert result.error is not None
    assert "not configured" in result.error
    assert len(result.fields) == 0


@pytest.mark.asyncio
@patch.dict(os.environ, {"FACTSET_API_KEY": "test_key"}, clear=True)
async def test_query_for_competitor_generates_source_urls():
    """Test query_for_competitor() generates source URLs for all fields."""
    provider = FactSetProvider()

    search_result = {"provider_id": "factset_123", "name": "Test Corp"}
    profile_data = {
        "data": [
            {
                "FF_SALES": 100000000,
                "FF_EMP": 500,
            }
        ]
    }

    with patch.object(provider, "search_company", new_callable=AsyncMock) as mock_search:
        with patch.object(provider, "get_company_profile", new_callable=AsyncMock) as mock_profile:
            mock_search.return_value = search_result
            mock_profile.return_value = profile_data

            result = await provider.query_for_competitor("Test Corp")

            # Verify source URLs generated for each field
            assert len(result.source_urls) > 0
            for field_name in result.fields.keys():
                assert field_name in result.source_urls
                assert result.source_urls[field_name].startswith("http")


# ──────────────────────────────────────────────────────────────────────────────
# get_source_url() Tests
# ──────────────────────────────────────────────────────────────────────────────


@patch.dict(os.environ, {"PITCHBOOK_API_KEY": "test_key"}, clear=True)
def test_get_source_url_returns_deep_link():
    """Test get_source_url() returns provider-specific deep link."""
    provider = PitchBookProvider()
    url = provider.get_source_url("pb_12345")

    assert url.startswith("http")
    assert "pb_12345" in url or "12345" in url
    assert "pitchbook.com" in url


@patch.dict(os.environ, {"CRUNCHBASE_API_KEY": "test_key"}, clear=True)
def test_crunchbase_get_source_url_format():
    """Test Crunchbase get_source_url() returns correct URL format."""
    provider = CrunchbaseProvider()
    url = provider.get_source_url("epic-systems")

    assert url == "https://www.crunchbase.com/organization/epic-systems"


@patch.dict(os.environ, {"FACTSET_API_KEY": "test_key"}, clear=True)
def test_factset_get_source_url_format():
    """Test FactSet get_source_url() returns correct URL format."""
    provider = FactSetProvider()
    url = provider.get_source_url("EPIC-US")

    assert "factset.com" in url
    assert "EPIC-US" in url
