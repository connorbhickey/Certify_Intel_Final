"""
Certify Intel - URL Refinement Engine (v8.3.0)

Converts generic homepage source URLs to exact page URLs with text fragment
deep links. Uses a three-strategy pipeline:
  1. Pattern-based URL construction (fastest, no API calls)
  2. Sitemap parsing (medium cost, cached 24hrs)
  3. AI-powered search via Gemini grounded search (most accurate, API cost)

Author: Certify Health
Date: February 13, 2026
"""

import re
import asyncio
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote, urlparse

import httpx

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Data types
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class RefinedSource:
    """Result of URL refinement for a single data source."""
    source_page_url: Optional[str] = None
    source_anchor_text: Optional[str] = None
    source_css_selector: Optional[str] = None
    source_section: Optional[str] = None
    deep_link_url: Optional[str] = None
    url_status: str = "pending"           # pending/verified/broken/redirected
    strategy_used: Optional[str] = None   # pattern/sitemap/ai_search/none
    confidence: int = 0                   # 0-100

    @property
    def found(self) -> bool:
        return self.source_page_url is not None and self.url_status == "verified"


# ─────────────────────────────────────────────────────────────────────────────
# Field-to-page-type mapping
# ─────────────────────────────────────────────────────────────────────────────

# Maps Competitor field names to the type of website page where the data
# is most likely to be found.  Values match keys in PAGE_PATTERNS below.
FIELD_TO_PAGE_TYPE: Dict[str, str] = {
    # Leadership / About
    "ceo_name": "about",
    "cto_name": "about",
    "cfo_name": "about",
    "founder_background": "about",
    "headquarters": "about",
    "year_founded": "about",
    "employee_count": "about",
    "employee_growth_rate": "about",
    "geographic_focus": "about",
    "markets_served": "about",
    "primary_market": "about",

    # Pricing
    "pricing_model": "pricing",
    "base_price": "pricing",
    "enterprise_price": "pricing",
    "price_range": "pricing",
    "pricing_transparency": "pricing",

    # Products
    "key_products": "products",
    "product_categories": "products",
    "key_features": "products",
    "latest_product_launch": "products",
    "product_count": "products",
    "target_segments": "products",
    "customer_size_focus": "products",

    # Customers / Case Studies
    "customer_count": "customers",
    "key_customers": "customers",
    "notable_customer_wins": "customers",
    "customer_case_studies": "customers",
    "nps_score": "customers",

    # Integrations
    "integration_partners": "integrations",
    "strategic_partners": "integrations",
    "reseller_partners": "integrations",
    "api_available": "integrations",
    "api_documentation_url": "integrations",

    # Tech / Security
    "tech_stack": "products",
    "cloud_provider": "security",
    "soc2_certified": "security",
    "hitrust_certified": "security",
    "iso27001_certified": "security",
    "hipaa_compliant": "security",
    "certifications": "security",

    # Careers (employee-related)
    "glassdoor_rating": "careers",
    "glassdoor_reviews_count": "careers",

    # Resources (general)
    "open_source_contributions": "resources",
    "rd_investment_pct": "resources",
    "recent_patents": "resources",
    "patent_count": "resources",

    # Social (external URLs, no page type on competitor site)
    "linkedin_followers": "about",
    "linkedin_employees": "about",
    "twitter_followers": "about",
    "facebook_followers": "about",
    "youtube_subscribers": "about",

    # Financial (usually not on company site — external sources)
    "annual_revenue": "about",
    "net_income": "about",
    "funding_total": "about",
    "last_funding_date": "about",
    "funding_stage": "about",
    "pe_vc_backers": "about",
    "estimated_market_share": "about",
    "revenue_per_employee": "about",

    # Dimension evidence fields
    "dim_feature_breadth_evidence": "products",
    "dim_product_packaging_evidence": "pricing",
    "dim_integration_depth_evidence": "integrations",
    "dim_support_service_evidence": "contact",
    "dim_retention_stickiness_evidence": "customers",
    "dim_user_adoption_evidence": "customers",
    "dim_implementation_ttv_evidence": "resources",
    "dim_reliability_enterprise_evidence": "security",
    "dim_pricing_flexibility_evidence": "pricing",
    "dim_reporting_analytics_evidence": "products",
}

# Page patterns matching scraper.py:96 (kept in sync)
PAGE_PATTERNS: Dict[str, List[str]] = {
    "homepage": [""],
    "pricing": ["pricing", "plans", "price", "packages", "cost", "subscription"],
    "about": ["about", "about-us", "company", "who-we-are", "our-story", "team"],
    "products": [
        "products", "product", "solutions", "platform", "features", "capabilities",
    ],
    "features": [
        "features", "functionality", "capabilities", "what-we-offer",
    ],
    "customers": [
        "customers", "case-studies", "clients", "success-stories", "testimonials",
    ],
    "integrations": [
        "integrations", "partners", "marketplace", "apps", "ecosystem", "connect",
    ],
    "resources": [
        "resources", "blog", "insights", "news", "knowledge-base", "help",
    ],
    "contact": [
        "contact", "contact-us", "get-in-touch", "demo", "request-demo",
        "get-started",
    ],
    "careers": ["careers", "jobs", "join-us", "work-with-us"],
    "security": [
        "security", "compliance", "trust", "privacy", "hipaa", "soc2",
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# Sitemap cache (module-level, shared across calls)
# ─────────────────────────────────────────────────────────────────────────────

_sitemap_cache: Dict[str, Tuple[datetime, List[str]]] = {}
_SITEMAP_TTL = timedelta(hours=24)


# ─────────────────────────────────────────────────────────────────────────────
# Text-fragment builder
# ─────────────────────────────────────────────────────────────────────────────


def build_text_fragment(
    value: str,
    context_before: Optional[str] = None,
    context_after: Optional[str] = None,
) -> str:
    """Build a Scroll-to-Text Fragment (``#:~:text=``) for the given value.

    Spec: https://wicg.github.io/scroll-to-text-fragment/

    Args:
        value: The text to highlight.  Trimmed to first 200 chars.
        context_before: Optional prefix text for disambiguation.
        context_after:  Optional suffix text for disambiguation.

    Returns:
        Fragment string starting with ``#:~:text=`` (ready to append to URL).
        Returns empty string if *value* is falsy.
    """
    if not value or not value.strip():
        return ""

    value = value.strip()
    # Truncate very long values — browsers have length limits
    if len(value) > 200:
        value = value[:200]

    def _encode(text: str) -> str:
        """Percent-encode per the Text Fragment spec."""
        # Encode everything except unreserved characters
        return quote(text, safe="")

    parts: List[str] = []

    if context_before:
        parts.append(f"{_encode(context_before.strip())}-,")

    parts.append(_encode(value))

    if context_after:
        parts.append(f",-{_encode(context_after.strip())}")

    return "#:~:text=" + "".join(parts)


def _make_deep_link(base_url: str, fragment: str) -> str:
    """Combine a base URL with a text fragment.

    Strips any existing fragment from the base URL before appending.
    """
    if not fragment:
        return base_url
    # Remove existing fragment
    base = base_url.split("#")[0]
    return base + fragment


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────


def _normalize_base_url(website: str) -> str:
    """Ensure the website string is a full URL with scheme."""
    if not website:
        return ""
    website = website.strip().rstrip("/")
    if not website.startswith(("http://", "https://")):
        website = "https://" + website
    return website


def _get_page_type(field_name: str) -> str:
    """Resolve field name to page type via FIELD_TO_PAGE_TYPE."""
    return FIELD_TO_PAGE_TYPE.get(field_name, "about")


async def _head_check(
    client: httpx.AsyncClient,
    url: str,
    timeout: float = 3.0,
) -> Tuple[bool, Optional[str]]:
    """Send a HEAD request to *url*.

    Returns ``(reachable, final_url)`` where *final_url* is the URL after
    redirects (or None if the request failed).
    """
    try:
        resp = await client.head(url, follow_redirects=True, timeout=timeout)
        if resp.status_code < 400:
            return True, str(resp.url)
        return False, None
    except (httpx.HTTPError, httpx.InvalidURL, Exception):
        return False, None


# ─────────────────────────────────────────────────────────────────────────────
# Strategy 1 — Pattern-based URL construction
# ─────────────────────────────────────────────────────────────────────────────


async def _strategy_pattern(
    client: httpx.AsyncClient,
    base_url: str,
    field_name: str,
    max_patterns: int = 6,
) -> Optional[Tuple[str, str]]:
    """Try common URL patterns for *field_name*.

    Returns ``(verified_url, section_name)`` or ``None``.
    """
    page_type = _get_page_type(field_name)
    patterns = PAGE_PATTERNS.get(page_type, [page_type])

    for slug in patterns[:max_patterns]:
        candidate = f"{base_url}/{slug}" if slug else base_url
        ok, final_url = await _head_check(client, candidate)
        if ok and final_url:
            logger.debug("Pattern hit: %s -> %s", candidate, final_url)
            return final_url, page_type

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Strategy 2 — Sitemap parsing
# ─────────────────────────────────────────────────────────────────────────────


async def _fetch_sitemap(
    client: httpx.AsyncClient,
    base_url: str,
) -> List[str]:
    """Fetch and parse sitemap URLs for *base_url*, with 24-hour caching."""
    domain = urlparse(base_url).netloc
    now = datetime.utcnow()

    # Check cache
    if domain in _sitemap_cache:
        cached_at, urls = _sitemap_cache[domain]
        if now - cached_at < _SITEMAP_TTL:
            return urls

    urls: List[str] = []

    # Try /sitemap.xml first, then /sitemap_index.xml
    for path in ["/sitemap.xml", "/sitemap_index.xml"]:
        sitemap_url = base_url + path
        try:
            resp = await client.get(sitemap_url, timeout=4.0, follow_redirects=True)
            if resp.status_code < 400 and resp.headers.get(
                "content-type", ""
            ).startswith(("text/xml", "application/xml")):
                urls = _parse_sitemap_xml(resp.text, client, base_url)
                if urls:
                    break
        except (httpx.HTTPError, Exception):
            continue

    # Fallback: check robots.txt for sitemap directive
    if not urls:
        try:
            resp = await client.get(
                base_url + "/robots.txt", timeout=3.0, follow_redirects=True
            )
            if resp.status_code < 400:
                for line in resp.text.splitlines():
                    if line.lower().startswith("sitemap:"):
                        sm_url = line.split(":", 1)[1].strip()
                        try:
                            sm_resp = await client.get(
                                sm_url, timeout=4.0, follow_redirects=True
                            )
                            if sm_resp.status_code < 400:
                                urls = _parse_sitemap_xml(
                                    sm_resp.text, client, base_url
                                )
                                if urls:
                                    break
                        except (httpx.HTTPError, Exception):
                            continue
        except (httpx.HTTPError, Exception):
            pass

    # Cache the result (even if empty — avoids repeated fetches)
    _sitemap_cache[domain] = (now, urls)
    logger.debug("Sitemap for %s: %d URLs cached", domain, len(urls))
    return urls


def _parse_sitemap_xml(
    xml_text: str,
    client: httpx.AsyncClient,
    base_url: str,
) -> List[str]:
    """Parse a sitemap XML document and return a flat list of ``<loc>`` URLs."""
    urls: List[str] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return urls

    # Handle namespace
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"

    for loc in root.iter(f"{ns}loc"):
        if loc.text:
            urls.append(loc.text.strip())

    return urls


async def _strategy_sitemap(
    client: httpx.AsyncClient,
    base_url: str,
    field_name: str,
) -> Optional[Tuple[str, str]]:
    """Search the sitemap for a URL matching the page type for *field_name*.

    Returns ``(url, section_name)`` or ``None``.
    """
    page_type = _get_page_type(field_name)
    patterns = PAGE_PATTERNS.get(page_type, [page_type])
    keywords = set(patterns)

    sitemap_urls = await _fetch_sitemap(client, base_url)
    if not sitemap_urls:
        return None

    # Score each sitemap URL against keywords
    best_url: Optional[str] = None
    best_score: int = 0

    for url in sitemap_urls:
        path = urlparse(url).path.lower()
        score = 0
        for kw in keywords:
            if kw and kw in path:
                # Prefer exact path segments over substrings
                segments = [s for s in path.split("/") if s]
                if kw in segments:
                    score += 10
                else:
                    score += 3
        if score > best_score:
            best_score = score
            best_url = url

    if best_url and best_score >= 3:
        # Verify it's actually reachable
        ok, final_url = await _head_check(client, best_url)
        if ok and final_url:
            logger.debug("Sitemap hit: %s (score %d)", final_url, best_score)
            return final_url, page_type

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Strategy 3 — AI-powered search (Gemini grounded)
# ─────────────────────────────────────────────────────────────────────────────


async def _strategy_ai_search(
    client: httpx.AsyncClient,
    competitor_name: str,
    field_name: str,
    current_value: Optional[str],
) -> Optional[Tuple[str, str]]:
    """Use Gemini grounded search to find the exact page URL.

    Returns ``(url, section_name)`` or ``None``.
    """
    try:
        from source_discovery_engine import SourceDiscoveryEngine
    except ImportError:
        logger.warning("source_discovery_engine not importable; skipping AI search")
        return None

    engine = SourceDiscoveryEngine()
    if not engine.gemini:
        logger.debug("Gemini not available for AI URL refinement")
        return None

    human_field = field_name.replace("_", " ")
    value_hint = f" (current value: {current_value})" if current_value else ""

    query = (
        f"Find the EXACT page URL on {competitor_name}'s website that shows "
        f"their {human_field}{value_hint}. "
        f"Do NOT give me the homepage — give me the specific sub-page URL "
        f"(e.g., /pricing, /about, /customers). "
        f"Return ONLY the full URL, nothing else."
    )

    try:
        result = engine.gemini.search_and_ground(
            query=query,
            competitor_name=competitor_name,
            search_type="general",
        )
    except Exception as exc:
        logger.warning("AI search failed for %s/%s: %s", competitor_name, field_name, exc)
        return None

    if "error" in result:
        return None

    response_text = result.get("response", "")
    # Extract first URL from response
    url_match = re.search(r'https?://[^\s<>"\')\]]+', response_text)
    if not url_match:
        return None

    candidate = url_match.group(0).rstrip(".,;:")
    ok, final_url = await _head_check(client, candidate)
    if ok and final_url:
        page_type = _get_page_type(field_name)
        logger.debug("AI search hit: %s", final_url)
        return final_url, page_type

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────


async def refine_source_url(
    competitor_name: str,
    website: str,
    field_name: str,
    current_value: Optional[str] = None,
    current_url: Optional[str] = None,
    skip_ai_search: bool = False,
) -> RefinedSource:
    """Run the three-strategy pipeline to refine a source URL.

    Strategies run in order of cost (cheapest first).  The pipeline stops
    as soon as a strategy succeeds.

    Args:
        competitor_name: Display name of the competitor.
        website: Competitor website (domain or full URL).
        field_name: The ORM field name (e.g., ``"pricing_model"``).
        current_value: Current stored value for the field (used for text
            fragment generation and AI context).
        current_url: The existing generic source URL (may be homepage).
        skip_ai_search: If True, skip Strategy 3 (AI/Gemini search) for
            faster batch processing.

    Returns:
        A :class:`RefinedSource` with as much detail as could be determined.
    """
    base_url = _normalize_base_url(website)
    if not base_url:
        return RefinedSource(url_status="broken", strategy_used="none")

    result = RefinedSource()

    async with httpx.AsyncClient(
        timeout=5.0,
        follow_redirects=True,
        headers={"User-Agent": "CertifyIntel/8.3.0 URLRefiner"},
    ) as client:

        # ── Strategy 1: Pattern construction ────────────────────────
        hit = await _strategy_pattern(client, base_url, field_name)
        if hit:
            result.source_page_url = hit[0]
            result.source_section = hit[1]
            result.url_status = "verified"
            result.strategy_used = "pattern"
            result.confidence = 70

        # ── Strategy 2: Sitemap parsing ─────────────────────────────
        if not result.found:
            hit = await _strategy_sitemap(client, base_url, field_name)
            if hit:
                result.source_page_url = hit[0]
                result.source_section = hit[1]
                result.url_status = "verified"
                result.strategy_used = "sitemap"
                result.confidence = 75

        # ── Strategy 3: AI search (Gemini grounded) ─────────────────
        if not result.found and not skip_ai_search:
            hit = await _strategy_ai_search(
                client, competitor_name, field_name, current_value,
            )
            if hit:
                result.source_page_url = hit[0]
                result.source_section = hit[1]
                result.url_status = "verified"
                result.strategy_used = "ai_search"
                result.confidence = 85

        # ── Fallback: keep existing URL ─────────────────────────────
        if not result.found and current_url:
            ok, final_url = await _head_check(client, current_url)
            if ok:
                result.source_page_url = final_url
                result.url_status = "verified"
                result.strategy_used = "none"
                result.confidence = 30
            else:
                result.source_page_url = current_url
                result.url_status = "broken"
                result.strategy_used = "none"
                result.confidence = 0

    # ── Build deep link with text fragment ───────────────────────────
    if result.source_page_url and current_value:
        fragment = build_text_fragment(current_value)
        if fragment:
            result.source_anchor_text = current_value[:200]
            result.deep_link_url = _make_deep_link(result.source_page_url, fragment)

    result.source_section = result.source_section or _get_page_type(field_name)

    logger.info(
        "URL refinement for %s/%s: strategy=%s status=%s url=%s",
        competitor_name,
        field_name,
        result.strategy_used,
        result.url_status,
        result.source_page_url,
    )

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Batch helper
# ─────────────────────────────────────────────────────────────────────────────


async def refine_sources_batch(
    competitor_name: str,
    website: str,
    fields: List[Dict],
    concurrency: int = 3,
) -> List[Dict]:
    """Refine URLs for multiple fields with concurrency control.

    Args:
        competitor_name: Display name of the competitor.
        website: Competitor domain or full URL.
        fields: List of dicts with keys ``field_name``, ``current_value``,
            ``current_url``.
        concurrency: Maximum parallel refinements.

    Returns:
        List of dicts with original field info merged with RefinedSource data.
    """
    sem = asyncio.Semaphore(concurrency)
    results: List[Dict] = []

    async def _refine(item: Dict) -> Dict:
        async with sem:
            refined = await refine_source_url(
                competitor_name=competitor_name,
                website=website,
                field_name=item["field_name"],
                current_value=item.get("current_value"),
                current_url=item.get("current_url"),
            )
            return {
                "field_name": item["field_name"],
                "source_page_url": refined.source_page_url,
                "source_anchor_text": refined.source_anchor_text,
                "source_css_selector": refined.source_css_selector,
                "source_section": refined.source_section,
                "deep_link_url": refined.deep_link_url,
                "url_status": refined.url_status,
                "strategy_used": refined.strategy_used,
                "confidence": refined.confidence,
            }

    tasks = [_refine(f) for f in fields]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Replace exceptions with error entries
    clean: List[Dict] = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            logger.error("Batch refinement error for %s: %s", fields[i]["field_name"], r)
            clean.append({
                "field_name": fields[i]["field_name"],
                "url_status": "broken",
                "strategy_used": "none",
                "error": str(r),
            })
        else:
            clean.append(r)

    return clean
