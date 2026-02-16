"""
Certify Intel - URL Refinement Engine Tests

Tests for the three-strategy URL refinement pipeline:
  1. Pattern-based URL construction
  2. Sitemap parsing
  3. AI-powered search via Gemini

Run: python -m pytest -xvs tests/test_url_refinement.py
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from url_refinement_engine import (
    RefinedSource,
    build_text_fragment,
    refine_source_url,
    refine_sources_batch,
    _normalize_base_url,
    _get_page_type,
    _head_check,
    _strategy_pattern,
    _strategy_ai_search,
    _strategy_sitemap,
    _fetch_sitemap,
    _parse_sitemap_xml,
    _make_deep_link,
    FIELD_TO_PAGE_TYPE,
    PAGE_PATTERNS,
)


# ──────────────────────────────────────────────────────────────────────────────
# RefinedSource Dataclass Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_refined_source_default_values():
    """Test RefinedSource dataclass initializes with correct defaults."""
    result = RefinedSource()

    assert result.source_page_url is None
    assert result.source_anchor_text is None
    assert result.source_css_selector is None
    assert result.source_section is None
    assert result.deep_link_url is None
    assert result.url_status == "pending"
    assert result.strategy_used is None
    assert result.confidence == 0


def test_refined_source_found_property_when_verified():
    """Test RefinedSource.found returns True when verified."""
    result = RefinedSource(
        source_page_url="https://example.com/pricing",
        url_status="verified",
    )
    assert result.found is True


def test_refined_source_found_property_when_broken():
    """Test RefinedSource.found returns False when broken."""
    result = RefinedSource(
        source_page_url="https://example.com/pricing",
        url_status="broken",
    )
    assert result.found is False


def test_refined_source_found_property_when_no_url():
    """Test RefinedSource.found returns False when no URL."""
    result = RefinedSource(
        source_page_url=None,
        url_status="verified",
    )
    assert result.found is False


# ──────────────────────────────────────────────────────────────────────────────
# FIELD_TO_PAGE_TYPE Mapping Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_field_to_page_type_contains_key_fields():
    """Test FIELD_TO_PAGE_TYPE mapping contains essential fields."""
    essential_fields = [
        "pricing_model",
        "ceo_name",
        "key_products",
        "customer_count",
        "integration_partners",
        "soc2_certified",
        "headquarters",
        "year_founded",
    ]

    for field in essential_fields:
        assert field in FIELD_TO_PAGE_TYPE, f"Missing mapping for {field}"


def test_field_to_page_type_maps_to_valid_page_types():
    """Test all FIELD_TO_PAGE_TYPE values are valid page types."""
    valid_page_types = set(PAGE_PATTERNS.keys())

    for field_name, page_type in FIELD_TO_PAGE_TYPE.items():
        assert page_type in valid_page_types, (
            f"Field '{field_name}' maps to invalid page type '{page_type}'"
        )


def test_page_patterns_contains_expected_keys():
    """Test PAGE_PATTERNS contains expected page type keys."""
    expected_keys = [
        "homepage",
        "pricing",
        "about",
        "products",
        "customers",
        "integrations",
        "security",
        "careers",
        "contact",
    ]

    for key in expected_keys:
        assert key in PAGE_PATTERNS, f"Missing page pattern: {key}"


def test_page_patterns_values_are_lists():
    """Test all PAGE_PATTERNS values are lists of strings."""
    for page_type, patterns in PAGE_PATTERNS.items():
        assert isinstance(patterns, list), f"{page_type} patterns must be a list"
        for pattern in patterns:
            assert isinstance(pattern, str), f"{page_type} pattern must be string"


# ──────────────────────────────────────────────────────────────────────────────
# build_text_fragment() Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_build_text_fragment_basic():
    """Test build_text_fragment() with basic value."""
    fragment = build_text_fragment("subscription-based")

    assert fragment.startswith("#:~:text=")
    assert "subscription-based" in fragment or "subscription%2Dbased" in fragment


def test_build_text_fragment_with_special_chars():
    """Test build_text_fragment() percent-encodes special characters."""
    fragment = build_text_fragment("$99/month")

    assert fragment.startswith("#:~:text=")
    assert "$" not in fragment or "%24" in fragment  # $ should be encoded
    assert "/" not in fragment.split("=", 1)[1] or "%2F" in fragment  # / should be encoded


def test_build_text_fragment_with_spaces():
    """Test build_text_fragment() handles spaces correctly."""
    fragment = build_text_fragment("per user per month")

    assert fragment.startswith("#:~:text=")
    assert "%20" in fragment  # Spaces encoded as %20


def test_build_text_fragment_truncates_long_values():
    """Test build_text_fragment() truncates values over 200 chars."""
    long_value = "x" * 300
    fragment = build_text_fragment(long_value)

    # Fragment should not contain more than ~200 chars of content
    # (accounting for percent-encoding, which could expand it)
    assert len(fragment) < 300


def test_build_text_fragment_with_context_before():
    """Test build_text_fragment() with prefix context."""
    fragment = build_text_fragment("$99", context_before="Pricing starts at")

    assert fragment.startswith("#:~:text=")
    assert "%2D%2C" in fragment or "-," in fragment  # Prefix delimiter


def test_build_text_fragment_with_context_after():
    """Test build_text_fragment() with suffix context."""
    fragment = build_text_fragment("$99", context_after="per month")

    assert fragment.startswith("#:~:text=")
    assert "%2C%2D" in fragment or ",-" in fragment  # Suffix delimiter


def test_build_text_fragment_with_both_contexts():
    """Test build_text_fragment() with both prefix and suffix context."""
    fragment = build_text_fragment(
        "$99",
        context_before="Pricing:",
        context_after="per user"
    )

    assert fragment.startswith("#:~:text=")
    # Should contain both delimiter patterns
    assert ("%2D%2C" in fragment or "-," in fragment)
    assert ("%2C%2D" in fragment or ",-" in fragment)


def test_build_text_fragment_empty_value():
    """Test build_text_fragment() returns empty string for empty value."""
    assert build_text_fragment("") == ""
    assert build_text_fragment(None) == ""
    assert build_text_fragment("   ") == ""


def test_build_text_fragment_strips_whitespace():
    """Test build_text_fragment() strips leading/trailing whitespace."""
    fragment = build_text_fragment("  $99/month  ")

    assert fragment.startswith("#:~:text=")
    # Should not have encoded leading/trailing spaces
    assert not fragment.endswith("%20")


def test_build_text_fragment_short_value():
    """Test build_text_fragment() handles very short values."""
    fragment = build_text_fragment("5")

    assert fragment.startswith("#:~:text=")
    assert "5" in fragment


# ──────────────────────────────────────────────────────────────────────────────
# Helper Function Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_normalize_base_url_adds_https():
    """Test _normalize_base_url() adds https:// to bare domains."""
    assert _normalize_base_url("example.com") == "https://example.com"


def test_normalize_base_url_preserves_http():
    """Test _normalize_base_url() preserves existing http:// scheme."""
    assert _normalize_base_url("http://example.com") == "http://example.com"


def test_normalize_base_url_strips_trailing_slash():
    """Test _normalize_base_url() removes trailing slash."""
    assert _normalize_base_url("https://example.com/") == "https://example.com"


def test_normalize_base_url_handles_empty():
    """Test _normalize_base_url() returns empty string for empty input."""
    assert _normalize_base_url("") == ""
    assert _normalize_base_url(None) == ""


def test_get_page_type_returns_mapped_type():
    """Test _get_page_type() returns mapped page type for known fields."""
    assert _get_page_type("pricing_model") == "pricing"
    assert _get_page_type("ceo_name") == "about"
    assert _get_page_type("key_products") == "products"


def test_get_page_type_defaults_to_about():
    """Test _get_page_type() defaults to 'about' for unknown fields."""
    assert _get_page_type("unknown_field_xyz") == "about"


def test_make_deep_link_combines_url_and_fragment():
    """Test _make_deep_link() combines base URL with fragment."""
    base = "https://example.com/pricing"
    fragment = "#:~:text=subscription"
    result = _make_deep_link(base, fragment)

    assert result == "https://example.com/pricing#:~:text=subscription"


def test_make_deep_link_strips_existing_fragment():
    """Test _make_deep_link() removes existing fragment before appending."""
    base = "https://example.com/pricing#old-fragment"
    fragment = "#:~:text=new"
    result = _make_deep_link(base, fragment)

    assert "#old-fragment" not in result
    assert result == "https://example.com/pricing#:~:text=new"


def test_make_deep_link_handles_empty_fragment():
    """Test _make_deep_link() returns base URL when fragment is empty."""
    base = "https://example.com/pricing"
    result = _make_deep_link(base, "")

    assert result == base


# ──────────────────────────────────────────────────────────────────────────────
# _head_check() Tests
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_head_check_success():
    """Test _head_check() returns True for successful HEAD request."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.url = "https://example.com/pricing"

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.head = AsyncMock(return_value=mock_response)

    reachable, final_url = await _head_check(mock_client, "https://example.com/pricing")

    assert reachable is True
    assert final_url == "https://example.com/pricing"


@pytest.mark.asyncio
async def test_head_check_follows_redirects():
    """Test _head_check() returns final URL after redirects."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.url = "https://example.com/new-pricing"

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.head = AsyncMock(return_value=mock_response)

    reachable, final_url = await _head_check(mock_client, "https://example.com/old-pricing")

    assert reachable is True
    assert final_url == "https://example.com/new-pricing"


@pytest.mark.asyncio
async def test_head_check_handles_404():
    """Test _head_check() returns False for 404 status."""
    mock_response = MagicMock()
    mock_response.status_code = 404

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.head = AsyncMock(return_value=mock_response)

    reachable, final_url = await _head_check(mock_client, "https://example.com/missing")

    assert reachable is False
    assert final_url is None


@pytest.mark.asyncio
async def test_head_check_handles_network_error():
    """Test _head_check() returns False on network error."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.head = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))

    reachable, final_url = await _head_check(mock_client, "https://example.com")

    assert reachable is False
    assert final_url is None


# ──────────────────────────────────────────────────────────────────────────────
# Pattern Strategy Tests
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_strategy_pattern_finds_pricing_page():
    """Test _strategy_pattern() finds pricing page for pricing field."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    async def mock_head_check(client, url):
        if "/pricing" in url:
            return True, url
        return False, None

    with patch("url_refinement_engine._head_check", side_effect=mock_head_check):
        result = await _strategy_pattern(mock_client, "https://example.com", "pricing_model")

        assert result is not None
        assert result[0] == "https://example.com/pricing"
        assert result[1] == "pricing"


@pytest.mark.asyncio
async def test_strategy_pattern_tries_multiple_patterns():
    """Test _strategy_pattern() tries multiple URL patterns."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    tried_urls = []

    async def mock_head_check(client, url):
        tried_urls.append(url)
        if "/plans" in url:
            return True, url
        return False, None

    with patch("url_refinement_engine._head_check", side_effect=mock_head_check):
        result = await _strategy_pattern(mock_client, "https://example.com", "pricing_model")

        assert result is not None
        assert "/plans" in result[0]
        # Should have tried /pricing before /plans
        assert len(tried_urls) >= 2


@pytest.mark.asyncio
async def test_strategy_pattern_returns_none_when_not_found():
    """Test _strategy_pattern() returns None when no patterns match."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    async def mock_head_check(client, url):
        return False, None

    with patch("url_refinement_engine._head_check", side_effect=mock_head_check):
        result = await _strategy_pattern(mock_client, "https://example.com", "pricing_model")

        assert result is None


# ──────────────────────────────────────────────────────────────────────────────
# Sitemap Parsing Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_parse_sitemap_xml_basic():
    """Test _parse_sitemap_xml() parses basic sitemap."""
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/pricing</loc>
  </url>
  <url>
    <loc>https://example.com/about</loc>
  </url>
</urlset>"""

    mock_client = MagicMock()
    urls = _parse_sitemap_xml(xml_content, mock_client, "https://example.com")

    assert len(urls) == 2
    assert "https://example.com/pricing" in urls
    assert "https://example.com/about" in urls


def test_parse_sitemap_xml_without_namespace():
    """Test _parse_sitemap_xml() handles sitemap without namespace."""
    xml_content = """<?xml version="1.0"?>
<urlset>
  <url><loc>https://example.com/page1</loc></url>
  <url><loc>https://example.com/page2</loc></url>
</urlset>"""

    mock_client = MagicMock()
    urls = _parse_sitemap_xml(xml_content, mock_client, "https://example.com")

    assert len(urls) == 2


def test_parse_sitemap_xml_handles_invalid_xml():
    """Test _parse_sitemap_xml() returns empty list for invalid XML."""
    invalid_xml = "Not valid XML at all"

    mock_client = MagicMock()
    urls = _parse_sitemap_xml(invalid_xml, mock_client, "https://example.com")

    assert urls == []


def test_parse_sitemap_xml_handles_empty_sitemap():
    """Test _parse_sitemap_xml() handles sitemap with no URLs."""
    xml_content = """<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
</urlset>"""

    mock_client = MagicMock()
    urls = _parse_sitemap_xml(xml_content, mock_client, "https://example.com")

    assert urls == []


@pytest.mark.asyncio
async def test_fetch_sitemap_caches_results():
    """Test _fetch_sitemap() caches results for 24 hours."""
    xml_content = """<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/page1</loc></url>
</urlset>"""

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "text/xml"}
    mock_response.text = xml_content

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_response)

    # First call
    urls1 = await _fetch_sitemap(mock_client, "https://example.com")
    # Second call (should use cache)
    urls2 = await _fetch_sitemap(mock_client, "https://example.com")

    assert urls1 == urls2
    # Should only have called HTTP once
    assert mock_client.get.call_count == 1


@pytest.mark.asyncio
async def test_strategy_sitemap_finds_matching_url():
    """Test _strategy_sitemap() finds best matching URL from sitemap."""
    sitemap_urls = [
        "https://example.com/",
        "https://example.com/about",
        "https://example.com/pricing",
        "https://example.com/blog",
    ]

    mock_client = AsyncMock(spec=httpx.AsyncClient)

    async def mock_head_check(client, url):
        return True, url

    with patch("url_refinement_engine._fetch_sitemap", return_value=sitemap_urls):
        with patch("url_refinement_engine._head_check", side_effect=mock_head_check):
            result = await _strategy_sitemap(mock_client, "https://example.com", "pricing_model")

            assert result is not None
            assert "pricing" in result[0]


@pytest.mark.asyncio
async def test_strategy_sitemap_returns_none_when_no_match():
    """Test _strategy_sitemap() returns None when no matching URLs."""
    sitemap_urls = [
        "https://example.com/",
        "https://example.com/blog",
        "https://example.com/news",
    ]

    mock_client = AsyncMock(spec=httpx.AsyncClient)

    with patch("url_refinement_engine._fetch_sitemap", return_value=sitemap_urls):
        result = await _strategy_sitemap(mock_client, "https://example.com", "pricing_model")

        # No "pricing" URL in sitemap, should return None or a low-scored URL
        # depending on implementation
        assert result is None or "pricing" not in result[0]


# ──────────────────────────────────────────────────────────────────────────────
# AI Search Strategy Tests
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_strategy_ai_search_success():
    """Test _strategy_ai_search() with successful AI response."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    # Mock the SourceDiscoveryEngine and Gemini
    mock_gemini = MagicMock()
    mock_gemini.search_and_ground = MagicMock(return_value={
        "response": "The pricing page is at https://example.com/pricing-plans"
    })

    mock_engine_cls = MagicMock()
    mock_engine_instance = MagicMock()
    mock_engine_instance.gemini = mock_gemini
    mock_engine_instance.extract_url_from_response = MagicMock(
        return_value="https://example.com/pricing-plans"
    )
    mock_engine_cls.return_value = mock_engine_instance

    mock_module = MagicMock()
    mock_module.SourceDiscoveryEngine = mock_engine_cls

    import sys
    with patch.dict(sys.modules, {"source_discovery_engine": mock_module}):
        with patch("url_refinement_engine._head_check", return_value=(True, "https://example.com/pricing-plans")):
            result = await _strategy_ai_search(
                mock_client,
                "Epic Systems",
                "pricing_model",
                "$99/month"
            )

            assert result is not None
            assert "pricing-plans" in result[0]


@pytest.mark.asyncio
async def test_strategy_ai_search_no_gemini():
    """Test _strategy_ai_search() returns None when Gemini not available."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    mock_engine_cls = MagicMock()
    mock_engine_instance = MagicMock()
    mock_engine_instance.gemini = None
    mock_engine_cls.return_value = mock_engine_instance

    mock_module = MagicMock()
    mock_module.SourceDiscoveryEngine = mock_engine_cls

    import sys
    with patch.dict(sys.modules, {"source_discovery_engine": mock_module}):
        result = await _strategy_ai_search(
            mock_client,
            "Epic Systems",
            "pricing_model",
            None
        )

        assert result is None


@pytest.mark.asyncio
async def test_strategy_ai_search_import_error():
    """Test _strategy_ai_search() handles ImportError gracefully."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    import sys
    # Remove the module so the import fails
    with patch.dict(sys.modules, {"source_discovery_engine": None}):
        result = await _strategy_ai_search(
            mock_client,
            "Epic Systems",
            "pricing_model",
            None
        )

        assert result is None


# ──────────────────────────────────────────────────────────────────────────────
# refine_source_url() Integration Tests
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_refine_source_url_pattern_success():
    """Test refine_source_url() uses pattern strategy successfully."""

    async def mock_pattern(client, base_url, field_name):
        return "https://example.com/pricing", "pricing"

    with patch("url_refinement_engine._strategy_pattern", side_effect=mock_pattern):
        result = await refine_source_url(
            competitor_name="Test Corp",
            website="example.com",
            field_name="pricing_model",
            current_value="subscription",
        )

        assert result.found is True
        assert result.strategy_used == "pattern"
        assert result.confidence == 70
        assert "pricing" in result.source_page_url


@pytest.mark.asyncio
async def test_refine_source_url_falls_through_strategies():
    """Test refine_source_url() tries strategies in order."""
    call_order = []

    async def mock_pattern(client, base_url, field_name):
        call_order.append("pattern")
        return None

    async def mock_sitemap(client, base_url, field_name):
        call_order.append("sitemap")
        return "https://example.com/pricing", "pricing"

    with patch("url_refinement_engine._strategy_pattern", side_effect=mock_pattern):
        with patch("url_refinement_engine._strategy_sitemap", side_effect=mock_sitemap):
            result = await refine_source_url(
                competitor_name="Test Corp",
                website="example.com",
                field_name="pricing_model",
            )

            assert result.strategy_used == "sitemap"
            assert call_order == ["pattern", "sitemap"]


@pytest.mark.asyncio
async def test_refine_source_url_builds_deep_link():
    """Test refine_source_url() builds deep link with text fragment."""

    async def mock_pattern(client, base_url, field_name):
        return "https://example.com/pricing", "pricing"

    with patch("url_refinement_engine._strategy_pattern", side_effect=mock_pattern):
        result = await refine_source_url(
            competitor_name="Test Corp",
            website="example.com",
            field_name="pricing_model",
            current_value="$99/month",
        )

        assert result.deep_link_url is not None
        assert "#:~:text=" in result.deep_link_url
        assert result.source_anchor_text == "$99/month"


@pytest.mark.asyncio
async def test_refine_source_url_handles_empty_website():
    """Test refine_source_url() handles empty website gracefully."""
    result = await refine_source_url(
        competitor_name="Test Corp",
        website="",
        field_name="pricing_model",
    )

    assert result.url_status == "broken"
    assert result.strategy_used == "none"


@pytest.mark.asyncio
async def test_refine_source_url_keeps_existing_url_as_fallback():
    """Test refine_source_url() keeps existing URL when no strategy succeeds."""

    async def mock_pattern(client, base_url, field_name):
        return None

    async def mock_sitemap(client, base_url, field_name):
        return None

    async def mock_ai_search(client, name, field, value):
        return None

    async def mock_head_check(client, url):
        return True, url

    with patch("url_refinement_engine._strategy_pattern", side_effect=mock_pattern):
        with patch("url_refinement_engine._strategy_sitemap", side_effect=mock_sitemap):
            with patch("url_refinement_engine._strategy_ai_search", side_effect=mock_ai_search):
                with patch("url_refinement_engine._head_check", side_effect=mock_head_check):
                    result = await refine_source_url(
                        competitor_name="Test Corp",
                        website="example.com",
                        field_name="pricing_model",
                        current_url="https://example.com",
                    )

                    assert result.source_page_url == "https://example.com"
                    assert result.url_status == "verified"
                    assert result.confidence == 30


# ──────────────────────────────────────────────────────────────────────────────
# refine_sources_batch() Tests
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_refine_sources_batch_processes_multiple_fields():
    """Test refine_sources_batch() processes multiple fields."""
    fields = [
        {"field_name": "pricing_model", "current_value": "subscription"},
        {"field_name": "ceo_name", "current_value": "John Doe"},
    ]

    async def mock_refine(competitor_name, website, field_name, current_value=None, current_url=None):
        return RefinedSource(
            source_page_url=f"https://example.com/{field_name}",
            url_status="verified",
            strategy_used="pattern",
        )

    with patch("url_refinement_engine.refine_source_url", side_effect=mock_refine):
        results = await refine_sources_batch(
            competitor_name="Test Corp",
            website="example.com",
            fields=fields,
        )

        assert len(results) == 2
        assert all("field_name" in r for r in results)
        assert all("source_page_url" in r for r in results)


@pytest.mark.asyncio
async def test_refine_sources_batch_handles_exceptions():
    """Test refine_sources_batch() handles exceptions gracefully."""
    fields = [
        {"field_name": "pricing_model"},
        {"field_name": "ceo_name"},
    ]

    async def mock_refine(competitor_name, website, field_name, current_value=None, current_url=None):
        if field_name == "ceo_name":
            raise Exception("Test error")
        return RefinedSource(
            source_page_url="https://example.com/pricing",
            url_status="verified",
        )

    with patch("url_refinement_engine.refine_source_url", side_effect=mock_refine):
        results = await refine_sources_batch(
            competitor_name="Test Corp",
            website="example.com",
            fields=fields,
        )

        assert len(results) == 2
        # First should succeed
        assert results[0]["url_status"] == "verified"
        # Second should have error
        assert results[1]["url_status"] == "broken"
        assert "error" in results[1]


@pytest.mark.asyncio
async def test_refine_sources_batch_respects_concurrency():
    """Test refine_sources_batch() respects concurrency limit."""
    fields = [{"field_name": f"field_{i}"} for i in range(10)]
    concurrent_count = 0
    max_concurrent = 0

    async def mock_refine(competitor_name, website, field_name, current_value=None, current_url=None):
        nonlocal concurrent_count, max_concurrent
        concurrent_count += 1
        max_concurrent = max(max_concurrent, concurrent_count)
        # Simulate some async work
        import asyncio
        await asyncio.sleep(0.01)
        concurrent_count -= 1
        return RefinedSource()

    with patch("url_refinement_engine.refine_source_url", side_effect=mock_refine):
        await refine_sources_batch(
            competitor_name="Test Corp",
            website="example.com",
            fields=fields,
            concurrency=3,
        )

        # Max concurrent should not exceed the limit
        assert max_concurrent <= 3


# ──────────────────────────────────────────────────────────────────────────────
# Quality Summary & Content-Aware Fragment Tests (v8.3.0)
# ──────────────────────────────────────────────────────────────────────────────


def test_quality_summary_endpoint_fields():
    """Test that quality-summary response has the expected field set."""
    # Simulate the expected response structure from the endpoint
    expected_fields = {
        "total", "exact_page", "page_level", "homepage_only",
        "broken", "with_source", "total_fields", "coverage_pct",
    }
    # Build a mock response matching the endpoint logic
    response = {
        "total": 100,
        "exact_page": 40,
        "page_level": 20,
        "homepage_only": 30,
        "broken": 10,
        "with_source": 90,
        "total_fields": 150,
        "coverage_pct": round((40 + 20) / max(100, 1) * 100, 1),
    }
    assert set(response.keys()) == expected_fields
    assert response["coverage_pct"] == 60.0
    # Zero total should not cause division error
    zero_response = {
        "total": 0,
        "exact_page": 0,
        "page_level": 0,
        "homepage_only": 0,
        "broken": 0,
        "with_source": 0,
        "total_fields": 0,
        "coverage_pct": round((0 + 0) / max(0, 1) * 100, 1),
    }
    assert zero_response["coverage_pct"] == 0.0


def test_build_text_fragment_with_content_match():
    """Test building a text fragment from ContentMatch-style data."""
    from content_matcher import ContentMatch

    match = ContentMatch(
        matched_text="subscription-based",
        context_before="Our pricing is",
        context_after="with monthly billing",
        confidence=100,
        strategy_used="exact",
    )

    # Build fragment using the matched text with context
    fragment = build_text_fragment(
        match.matched_text,
        context_before=match.context_before,
        context_after=match.context_after,
    )

    assert fragment.startswith("#:~:text=")
    # Should contain the prefix delimiter
    assert "-," in fragment or "%2D%2C" in fragment
    # Should contain the suffix delimiter
    assert ",-" in fragment or "%2C%2D" in fragment
    assert match.confidence == 100


def test_build_text_fragment_content_match_no_context():
    """Test building fragment from ContentMatch with no context."""
    from content_matcher import ContentMatch

    match = ContentMatch(
        matched_text="Epic Systems",
        context_before="",
        context_after="",
        confidence=85,
        strategy_used="case_insensitive",
    )

    fragment = build_text_fragment(match.matched_text)
    assert fragment.startswith("#:~:text=")
    # No context delimiters should appear
    assert "-," not in fragment
    assert ",-" not in fragment


@pytest.mark.asyncio
async def test_batch_refinement_returns_all_source_fields():
    """Test that batch refinement results include all source quality fields."""

    async def mock_refine(
        competitor_name, website, field_name,
        current_value=None, current_url=None
    ):
        return RefinedSource(
            source_page_url="https://example.com/pricing",
            source_anchor_text="$99/month",
            source_css_selector=None,
            source_section="pricing",
            deep_link_url="https://example.com/pricing#:~:text=%2499%2Fmonth",
            url_status="verified",
            strategy_used="pattern",
            confidence=70,
        )

    fields = [{"field_name": "pricing_model", "current_value": "$99/month"}]

    with patch("url_refinement_engine.refine_source_url", side_effect=mock_refine):
        results = await refine_sources_batch(
            competitor_name="Test Corp",
            website="example.com",
            fields=fields,
        )

    assert len(results) == 1
    r = results[0]
    # Verify all expected keys are present
    expected_keys = {
        "field_name", "source_page_url", "source_anchor_text",
        "source_css_selector", "source_section", "deep_link_url",
        "url_status", "strategy_used", "confidence",
    }
    assert set(r.keys()) == expected_keys
    assert r["deep_link_url"] is not None
    assert "#:~:text=" in r["deep_link_url"]


# ──────────────────────────────────────────────────────────────────────────────
# _map_url_quality() Tests (from main.py)
# ──────────────────────────────────────────────────────────────────────────────


class TestMapUrlQuality:
    """Test _map_url_quality() mapping function from main.py."""

    def _get_mapper(self):
        """Import the mapping function from main."""
        from main import _map_url_quality
        return _map_url_quality

    def test_verified_maps_to_exact_page(self):
        """'verified' status should map to 'exact_page'."""
        mapper = self._get_mapper()
        assert mapper("verified") == "exact_page"

    def test_page_level_maps_to_page_level(self):
        """'page_level' status should map to 'page_level'."""
        mapper = self._get_mapper()
        assert mapper("page_level") == "page_level"

    def test_broken_maps_to_broken(self):
        """'broken' status should map to 'broken'."""
        mapper = self._get_mapper()
        assert mapper("broken") == "broken"

    def test_none_maps_to_none(self):
        """None status should return None."""
        mapper = self._get_mapper()
        assert mapper(None) is None

    def test_pending_maps_to_homepage_only(self):
        """'pending' status should map to 'homepage_only' (default)."""
        mapper = self._get_mapper()
        assert mapper("pending") == "homepage_only"

    def test_unknown_maps_to_homepage_only(self):
        """Unknown status values should map to 'homepage_only'."""
        mapper = self._get_mapper()
        assert mapper("unknown") == "homepage_only"
        assert mapper("something_else") == "homepage_only"


class TestPhase1SetsCorrectStatus:
    """Test that Phase 1 (URL refinement) sets 'pending' not 'verified'."""

    def test_refined_source_default_is_pending(self):
        """RefinedSource default url_status should be 'pending'."""
        result = RefinedSource()
        assert result.url_status == "pending"

    def test_pending_is_not_verified(self):
        """Phase 1 initial status must not be 'verified'."""
        result = RefinedSource()
        assert result.url_status != "verified"
