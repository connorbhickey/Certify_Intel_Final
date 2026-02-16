"""
Certify Intel - Content Matcher Tests

Tests for the content_matcher module which fetches web page content and
finds real text matches for DB values, enabling W3C Text Fragment deep links.

Run: python -m pytest -xvs tests/test_content_matcher.py
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from content_matcher import (
    _is_year,
    _normalize_number,
    _page_cache,
    build_content_aware_fragment,
    clear_cache,
    extract_text_from_html,
    fetch_page_text,
    find_value_on_page,
)


# ──────────────────────────────────────────────────────────────────────────────
# HTML Text Extraction Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_extract_text_basic():
    """Test basic HTML extraction with paragraphs."""
    html = "<html><body><p>Hello world</p><p>Second paragraph</p></body></html>"
    text = extract_text_from_html(html)
    assert "Hello world" in text
    assert "Second paragraph" in text


def test_extract_text_strips_scripts():
    """Verify <script> tags are removed."""
    html = "<p>Visible</p><script>alert('xss');</script><p>Also visible</p>"
    text = extract_text_from_html(html)
    assert "Visible" in text
    assert "Also visible" in text
    assert "alert" not in text
    assert "xss" not in text


def test_extract_text_strips_styles():
    """Verify <style> tags are removed."""
    html = "<p>Visible</p><style>body { color: red; }</style><p>End</p>"
    text = extract_text_from_html(html)
    assert "Visible" in text
    assert "End" in text
    assert "color" not in text
    assert "red" not in text


def test_extract_text_strips_noscript():
    """Verify <noscript> is removed."""
    html = "<p>Content</p><noscript>Enable JS</noscript><p>More</p>"
    text = extract_text_from_html(html)
    assert "Content" in text
    assert "More" in text
    assert "Enable JS" not in text


def test_extract_text_preserves_block_newlines():
    """Block-level tags (<br>, <p>, <div>) produce newlines."""
    html = "<p>Line one</p><p>Line two</p><div>Line three</div>"
    text = extract_text_from_html(html)
    # Each block tag inserts a newline, so lines should be separate
    assert "Line one" in text
    assert "Line two" in text
    assert "Line three" in text
    # They should not be concatenated on a single line without separator
    assert "Line oneLine two" not in text


def test_extract_text_collapses_whitespace():
    """Multiple spaces are collapsed to one."""
    html = "<p>Multiple     spaces    here</p>"
    text = extract_text_from_html(html)
    assert "Multiple spaces here" in text
    assert "     " not in text


def test_extract_text_handles_entities():
    """HTML entities &amp; &lt; &gt; are decoded."""
    html = "<p>A &amp; B &lt; C &gt; D</p>"
    text = extract_text_from_html(html)
    assert "A & B" in text
    assert "< C" in text
    assert "> D" in text


def test_extract_text_handles_invalid_html():
    """Malformed HTML does not crash the extractor."""
    html = "<p>Unclosed <b>tags <div>mixed</p>"
    text = extract_text_from_html(html)
    # Should return something without crashing
    assert isinstance(text, str)
    assert "Unclosed" in text


# ──────────────────────────────────────────────────────────────────────────────
# Number Normalization Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_normalize_number_plain():
    """Plain number '1500' normalizes to '1500'."""
    assert _normalize_number("1500") == "1500"


def test_normalize_number_with_commas():
    """'1,500' normalizes to '1500'."""
    assert _normalize_number("1,500") == "1500"


def test_normalize_number_with_dollar_m():
    """'$2.5M' normalizes to '2500000'."""
    assert _normalize_number("$2.5M") == "2500000"


def test_normalize_number_word_form():
    """'3.2 million' normalizes to '3200000'."""
    assert _normalize_number("3.2 million") == "3200000"


def test_normalize_number_percent():
    """'45%' normalizes to '45'."""
    assert _normalize_number("45%") == "45"


def test_normalize_number_k_suffix():
    """'$150K' normalizes to '150000'."""
    assert _normalize_number("$150K") == "150000"


def test_normalize_number_not_a_number():
    """Non-numeric text returns None."""
    assert _normalize_number("hello") is None


def test_is_year_valid():
    """Valid years return True."""
    assert _is_year("2019") is True
    assert _is_year("1990") is True
    assert _is_year("2026") is True


def test_is_year_invalid():
    """Non-year values return False."""
    assert _is_year("1500") is False
    assert _is_year("abc") is False
    assert _is_year("20190") is False
    assert _is_year("") is False


# ──────────────────────────────────────────────────────────────────────────────
# find_value_on_page Strategy Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_exact_match():
    """Direct substring found on page."""
    page = "Our pricing starts at $99/month for the basic plan."
    result = find_value_on_page(page, "$99/month")
    assert result is not None
    assert result.matched_text == "$99/month"
    assert result.strategy_used == "exact"
    assert result.confidence == 100


def test_exact_match_with_context():
    """Context before/after is populated for exact match."""
    page = "Our pricing starts at $99/month for the basic plan."
    result = find_value_on_page(page, "$99/month")
    assert result is not None
    assert result.context_before != ""
    assert result.context_after != ""


def test_number_normalized_match():
    """'1,500' matches '1500' on page via number normalization."""
    page = "We have 1500 employees worldwide."
    result = find_value_on_page(page, "1,500")
    assert result is not None
    assert result.strategy_used in ("exact", "number_normalized")


def test_number_normalized_match_dollar_m():
    """'$2.5M' matches '2,500,000' on page."""
    page = "Annual revenue is approximately 2,500,000 dollars."
    result = find_value_on_page(page, "$2.5M")
    assert result is not None
    assert result.strategy_used == "number_normalized"
    assert result.confidence == 90


def test_case_insensitive_match():
    """'saas' matches 'SaaS' on page via case-insensitive strategy."""
    page = "We offer a cloud-based SaaS platform for healthcare."
    result = find_value_on_page(page, "saas")
    assert result is not None
    assert result.matched_text == "SaaS"
    assert result.strategy_used == "case_insensitive"
    assert result.confidence == 85


def test_word_expanded_match():
    """'Epic Systems' expands to 'Epic Systems Corporation'."""
    page = "Our main competitor is Epic Systems Corporation in Madison."
    result = find_value_on_page(page, "Epic Systems")
    assert result is not None
    # Exact match should find it first since "Epic Systems" is in the text
    # But word_expanded would find the longer form
    assert "Epic Systems" in result.matched_text


def test_fuzzy_match():
    """Slight spelling difference still matches via fuzzy strategy."""
    page = "The company provides cloud-based healthcaer solutions."
    result = find_value_on_page(page, "healthcare")
    assert result is not None
    assert result.strategy_used == "fuzzy"
    assert result.confidence > 0


def test_no_match_found():
    """Value not present on page returns None."""
    page = "This page is about sports equipment and outdoor gear."
    result = find_value_on_page(page, "electronic health records")
    assert result is None


def test_empty_value_returns_none():
    """Empty string value returns None."""
    page = "Some content on the page."
    assert find_value_on_page(page, "") is None
    assert find_value_on_page(page, "   ") is None


def test_empty_page_returns_none():
    """Empty page text returns None."""
    assert find_value_on_page("", "some value") is None
    assert find_value_on_page(None, "some value") is None


def test_year_exact_match_only():
    """Years use exact match only, not number normalization."""
    page = "We were founded in 2019 and have grown rapidly."
    result = find_value_on_page(page, "2019")
    assert result is not None
    # Should match via exact strategy, not number normalization
    assert result.strategy_used == "exact"


# ──────────────────────────────────────────────────────────────────────────────
# Page Cache Tests
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_page_cache_hit():
    """Second call to same URL uses cache (no second HTTP call)."""
    clear_cache()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html><body><p>Cached content</p></body></html>"

    mock_client_instance = AsyncMock()
    mock_client_instance.get = AsyncMock(return_value=mock_response)
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=False)

    with patch("content_matcher.httpx.AsyncClient", return_value=mock_client_instance):
        # First call fetches from network
        text1 = await fetch_page_text("https://example.com/test")
        assert text1 is not None
        assert "Cached content" in text1

        # Second call should use cache
        text2 = await fetch_page_text("https://example.com/test")
        assert text2 == text1

        # httpx.AsyncClient.get should only be called once
        assert mock_client_instance.get.call_count == 1

    clear_cache()


@pytest.mark.asyncio
async def test_page_cache_clear():
    """clear_cache() empties the page cache."""
    _page_cache["https://test.com"] = (datetime.utcnow(), "cached text")
    assert len(_page_cache) > 0

    clear_cache()
    assert len(_page_cache) == 0


# ──────────────────────────────────────────────────────────────────────────────
# build_content_aware_fragment Tests
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_build_content_aware_fragment_success():
    """Returns dict with matched_text when value found on page."""
    page_html = "<html><body><p>Our pricing is $99/month per user.</p></body></html>"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = page_html

    mock_client_instance = AsyncMock()
    mock_client_instance.get = AsyncMock(return_value=mock_response)
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=False)

    clear_cache()

    with patch("content_matcher.httpx.AsyncClient", return_value=mock_client_instance):
        result = await build_content_aware_fragment(
            url="https://example.com/pricing",
            db_value="$99/month",
        )

    assert result is not None
    assert "matched_text" in result
    assert "$99/month" in result["matched_text"]
    assert "confidence" in result
    assert "strategy_used" in result
    assert result["confidence"] == 100

    clear_cache()


@pytest.mark.asyncio
async def test_build_content_aware_fragment_no_match():
    """Returns None when value not found on page."""
    page_html = "<html><body><p>This page has no pricing info.</p></body></html>"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = page_html

    mock_client_instance = AsyncMock()
    mock_client_instance.get = AsyncMock(return_value=mock_response)
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=False)

    clear_cache()

    with patch("content_matcher.httpx.AsyncClient", return_value=mock_client_instance):
        result = await build_content_aware_fragment(
            url="https://example.com/pricing",
            db_value="$99/month",
        )

    assert result is None

    clear_cache()


@pytest.mark.asyncio
async def test_build_content_aware_fragment_fetch_fails():
    """Returns None when page fetch fails."""
    mock_client_instance = AsyncMock()
    mock_client_instance.get = AsyncMock(
        side_effect=httpx.ConnectError("Connection refused")
    )
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=False)

    clear_cache()

    with patch("content_matcher.httpx.AsyncClient", return_value=mock_client_instance):
        result = await build_content_aware_fragment(
            url="https://unreachable.example.com/pricing",
            db_value="$99/month",
        )

    assert result is None

    clear_cache()
