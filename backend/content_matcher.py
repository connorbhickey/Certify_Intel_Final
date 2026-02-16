"""
Certify Intel - Content Matcher (v8.3.0)

Fetches actual web page content and finds real text matches for DB values,
enabling accurate W3C Text Fragment deep links. The URL refinement engine
builds text fragments that must be EXACT substring matches on the visible
page text -- this module bridges the gap between raw DB values and what
actually appears on the page.

Matching strategies (tried in order):
  1. Exact substring match
  2. Number normalization (commas, abbreviations, units)
  3. Case-insensitive match
  4. Word boundary expansion (partial match -> full phrase)
  5. Fuzzy substring (for values 4+ chars)

Author: Certify Health
Date: February 14, 2026
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from html.parser import HTMLParser
from typing import Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Data types
# ─────────────────────────────────────────────────────────────────────────────

MAX_PAGE_SIZE = 500_000  # 500 KB
CACHE_TTL_HOURS = 1
MAX_CACHE_ENTRIES = 200
CONTEXT_CHARS = 30
USER_AGENT = "CertifyIntel/8.3.0 ContentMatcher"
FETCH_TIMEOUT = 8.0


@dataclass
class ContentMatch:
    """Result of matching a DB value against actual page content."""
    matched_text: str = ""
    context_before: str = ""
    context_after: str = ""
    confidence: int = 0
    strategy_used: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# HTML-to-text extraction
# ─────────────────────────────────────────────────────────────────────────────

_BLOCK_TAGS = {"br", "p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6",
               "tr", "td", "th", "blockquote", "section", "article", "header",
               "footer", "nav", "dt", "dd", "figcaption"}

_SKIP_TAGS = {"script", "style", "noscript", "svg", "template"}


class _HTMLTextExtractor(HTMLParser):
    """Extracts visible text from HTML, stripping tags and scripts."""

    def __init__(self) -> None:
        super().__init__()
        self._pieces: List[str] = []
        self._skip_depth: int = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        tag_lower = tag.lower()
        if tag_lower in _SKIP_TAGS:
            self._skip_depth += 1
        elif tag_lower in _BLOCK_TAGS and not self._skip_depth:
            self._pieces.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag_lower in _BLOCK_TAGS and not self._skip_depth:
            self._pieces.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self._pieces.append(data)

    def handle_entityref(self, name: str) -> None:
        entity_map = {"amp": "&", "lt": "<", "gt": ">", "quot": '"',
                      "apos": "'", "nbsp": " "}
        if not self._skip_depth:
            self._pieces.append(entity_map.get(name, ""))

    def handle_charref(self, name: str) -> None:
        if not self._skip_depth:
            try:
                if name.startswith("x"):
                    char = chr(int(name[1:], 16))
                else:
                    char = chr(int(name))
                self._pieces.append(char)
            except (ValueError, OverflowError):
                pass

    def get_text(self) -> str:
        raw = "".join(self._pieces)
        # Collapse multiple whitespace (but preserve single newlines)
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def extract_text_from_html(html: str) -> str:
    """Convert HTML to clean visible text.

    Strips <script>, <style>, <noscript> entirely.  Converts block-level
    tags to newlines.  Collapses excessive whitespace.
    """
    parser = _HTMLTextExtractor()
    try:
        parser.feed(html)
    except Exception:
        logger.debug("HTML parser error, returning raw text")
        # Fallback: crude tag removal
        return re.sub(r"<[^>]+>", " ", html).strip()
    return parser.get_text()


# ─────────────────────────────────────────────────────────────────────────────
# Page content cache
# ─────────────────────────────────────────────────────────────────────────────

# url -> (fetched_at, page_text)
_page_cache: Dict[str, Tuple[datetime, str]] = {}


def _prune_cache() -> None:
    """Remove expired entries and enforce max size."""
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=CACHE_TTL_HOURS)

    expired = [url for url, (ts, _) in _page_cache.items() if ts < cutoff]
    for url in expired:
        del _page_cache[url]

    # Enforce max entries by removing oldest
    if len(_page_cache) > MAX_CACHE_ENTRIES:
        sorted_entries = sorted(_page_cache.items(), key=lambda x: x[1][0])
        excess = len(_page_cache) - MAX_CACHE_ENTRIES
        for url, _ in sorted_entries[:excess]:
            del _page_cache[url]


def clear_cache() -> None:
    """Clear the entire page cache."""
    _page_cache.clear()


# ─────────────────────────────────────────────────────────────────────────────
# Page fetching
# ─────────────────────────────────────────────────────────────────────────────


async def fetch_page_text(url: str) -> Optional[str]:
    """Fetch a web page and return its visible text content.

    Uses an in-memory cache with 1-hour TTL.  Returns None on any error
    (network, timeout, non-200 status, etc.).
    """
    _prune_cache()

    # Check cache
    if url in _page_cache:
        ts, text = _page_cache[url]
        if datetime.utcnow() - ts < timedelta(hours=CACHE_TTL_HOURS):
            return text
        else:
            del _page_cache[url]

    try:
        async with httpx.AsyncClient(
            timeout=FETCH_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                logger.debug("fetch_page_text %s returned %d", url, resp.status_code)
                return None

            # Enforce max page size
            content = resp.text
            if len(content) > MAX_PAGE_SIZE:
                content = content[:MAX_PAGE_SIZE]

            page_text = extract_text_from_html(content)

            # Cache the result
            _page_cache[url] = (datetime.utcnow(), page_text)
            return page_text

    except httpx.TimeoutException:
        logger.debug("fetch_page_text timeout for %s", url)
        return None
    except Exception:
        logger.debug("fetch_page_text error for %s", url, exc_info=True)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Number normalization
# ─────────────────────────────────────────────────────────────────────────────

# Multiplier suffixes (case-insensitive)
_MULTIPLIERS = {
    "k": 1_000,
    "m": 1_000_000,
    "mm": 1_000_000,
    "b": 1_000_000_000,
    "bn": 1_000_000_000,
    "t": 1_000_000_000_000,
}

# Word-form multipliers
_WORD_MULTIPLIERS = {
    "thousand": 1_000,
    "million": 1_000_000,
    "billion": 1_000_000_000,
    "trillion": 1_000_000_000_000,
}


def _normalize_number(text: str) -> Optional[str]:
    """Normalize number strings for comparison.

    Examples:
        "1,500" -> "1500"
        "$2.5M" -> "2500000"
        "45%" -> "45"
        "3.2 million" -> "3200000"
        "$150K" -> "150000"

    Returns the normalized integer string, or None if not a number.
    """
    cleaned = text.strip()
    if not cleaned:
        return None

    # Strip leading currency symbols
    cleaned = re.sub(r'^[\$\u00a3\u20ac]+', '', cleaned)

    # Strip trailing percent sign
    cleaned = re.sub(r'%$', '', cleaned)

    # Check for word multipliers: "3.2 million", "1.5 billion"
    word_match = re.match(
        r'^([\d,]+\.?\d*)\s+(thousand|million|billion|trillion)s?$',
        cleaned, re.IGNORECASE
    )
    if word_match:
        num_str = word_match.group(1).replace(",", "")
        multiplier = _WORD_MULTIPLIERS.get(word_match.group(2).lower(), 1)
        try:
            result = float(num_str) * multiplier
            return str(int(result))
        except ValueError:
            return None

    # Check for suffix multipliers: "2.5M", "150K", "1.2B"
    suffix_match = re.match(
        r'^([\d,]+\.?\d*)\s*([kKmMbBtT](?:[mMnN])?)$', cleaned
    )
    if suffix_match:
        num_str = suffix_match.group(1).replace(",", "")
        suffix = suffix_match.group(2).lower()
        multiplier = _MULTIPLIERS.get(suffix, 1)
        try:
            result = float(num_str) * multiplier
            return str(int(result))
        except ValueError:
            return None

    # Plain number: strip commas
    plain = cleaned.replace(",", "")
    # Verify it's a valid number
    try:
        float(plain)
        # Return integer form if it's a whole number
        if "." in plain:
            val = float(plain)
            if val == int(val):
                return str(int(val))
            return plain
        return plain
    except ValueError:
        return None


def _is_year(text: str) -> bool:
    """Check if text looks like a year (4-digit number starting with 19 or 20)."""
    stripped = text.strip()
    return bool(re.match(r'^(19|20)\d{2}$', stripped))


# ─────────────────────────────────────────────────────────────────────────────
# Text matching strategies
# ─────────────────────────────────────────────────────────────────────────────


def _extract_context(page_text: str, start: int, end: int) -> Tuple[str, str]:
    """Extract context_before and context_after around a match."""
    before_start = max(0, start - CONTEXT_CHARS)
    after_end = min(len(page_text), end + CONTEXT_CHARS)

    context_before = page_text[before_start:start].strip()
    context_after = page_text[end:after_end].strip()

    return context_before, context_after


def _try_exact(page_text: str, db_value: str) -> Optional[ContentMatch]:
    """Strategy 1: Exact substring match."""
    idx = page_text.find(db_value)
    if idx == -1:
        return None

    before, after = _extract_context(page_text, idx, idx + len(db_value))
    return ContentMatch(
        matched_text=db_value,
        context_before=before,
        context_after=after,
        confidence=100,
        strategy_used="exact",
    )


def _try_number_normalized(page_text: str, db_value: str) -> Optional[ContentMatch]:
    """Strategy 2: Number normalization matching.

    Handles comma differences, abbreviations (K/M/B), word forms (million),
    currency symbols, and percentage formats.
    """
    # Years should only match exactly
    if _is_year(db_value):
        return None

    db_norm = _normalize_number(db_value)
    if db_norm is None:
        return None

    # Build patterns to search for in page text
    # Look for number-like sequences in the page
    number_pattern = re.compile(
        r'[\$\u00a3\u20ac]?\s*[\d,]+\.?\d*'
        r'(?:\s*(?:[kKmMbBtT](?:[mMnN])?|thousand|million|billion|trillion)s?)?'
        r'\s*%?',
        re.IGNORECASE
    )

    for match in number_pattern.finditer(page_text):
        candidate = match.group(0).strip()
        if not candidate:
            continue
        candidate_norm = _normalize_number(candidate)
        if candidate_norm is not None and candidate_norm == db_norm:
            before, after = _extract_context(
                page_text, match.start(), match.end()
            )
            return ContentMatch(
                matched_text=candidate,
                context_before=before,
                context_after=after,
                confidence=90,
                strategy_used="number_normalized",
            )

    return None


def _try_case_insensitive(page_text: str, db_value: str) -> Optional[ContentMatch]:
    """Strategy 3: Case-insensitive substring match."""
    lower_page = page_text.lower()
    lower_value = db_value.lower()
    idx = lower_page.find(lower_value)
    if idx == -1:
        return None

    # Use the actual text from the page (preserving its casing)
    matched = page_text[idx:idx + len(db_value)]
    before, after = _extract_context(page_text, idx, idx + len(db_value))

    return ContentMatch(
        matched_text=matched,
        context_before=before,
        context_after=after,
        confidence=85,
        strategy_used="case_insensitive",
    )


def _try_word_expanded(page_text: str, db_value: str) -> Optional[ContentMatch]:
    """Strategy 4: Word boundary expansion.

    If the DB value appears inside a larger phrase on the page, expand
    the match to include surrounding words for a more meaningful fragment.

    Examples:
        "Epic Systems" in "...at Epic Systems Corporation..." -> "Epic Systems Corporation"
        "SaaS" in "cloud-based SaaS platform" -> "cloud-based SaaS platform"
    """
    # Find the value (case-insensitive) and expand to word boundaries
    pattern = re.compile(re.escape(db_value), re.IGNORECASE)
    match = pattern.search(page_text)
    if not match:
        return None

    start = match.start()
    end = match.end()

    # Expand left to word boundary (include preceding words if partial match)
    while start > 0 and page_text[start - 1] not in "\n\r\t":
        if page_text[start - 1] == " ":
            # Check if we've expanded enough (don't grab entire paragraphs)
            expanded = page_text[start:end]
            if len(expanded) > len(db_value) * 3:
                break
            # Include this space and look for more
            start -= 1
        elif page_text[start - 1] in ".,;:!?()[]{}\"'":
            break
        else:
            start -= 1

    # Expand right to word boundary
    while end < len(page_text) and page_text[end] not in "\n\r\t":
        if page_text[end] == " ":
            expanded = page_text[start:end]
            if len(expanded) > len(db_value) * 3:
                break
            end += 1
        elif page_text[end] in ".,;:!?()[]{}\"'":
            break
        else:
            end += 1

    expanded_text = page_text[start:end].strip()

    # Only return if we actually expanded beyond the original
    if expanded_text.lower() == db_value.lower():
        return None

    before, after = _extract_context(page_text, start, end)

    return ContentMatch(
        matched_text=expanded_text,
        context_before=before,
        context_after=after,
        confidence=75,
        strategy_used="word_expanded",
    )


def _try_fuzzy(page_text: str, db_value: str) -> Optional[ContentMatch]:
    """Strategy 5: Fuzzy substring matching for values 4+ chars.

    Uses a sliding window to find the best approximate match by counting
    matching characters.  Only returns a match if similarity >= 80%.
    """
    if len(db_value) < 4:
        return None

    target = db_value.lower()
    source = page_text.lower()
    target_len = len(target)

    if target_len > len(source):
        return None

    best_score = 0.0
    best_start = -1

    # Sliding window
    for i in range(len(source) - target_len + 1):
        window = source[i:i + target_len]
        matches = sum(1 for a, b in zip(target, window) if a == b)
        score = matches / target_len
        if score > best_score:
            best_score = score
            best_start = i

    # Require >= 80% similarity
    if best_score < 0.80 or best_start == -1:
        return None

    matched = page_text[best_start:best_start + target_len]
    before, after = _extract_context(
        page_text, best_start, best_start + target_len
    )

    confidence = int(best_score * 70)  # Scale to max 70 for fuzzy

    return ContentMatch(
        matched_text=matched,
        context_before=before,
        context_after=after,
        confidence=confidence,
        strategy_used="fuzzy",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main matching function
# ─────────────────────────────────────────────────────────────────────────────


def find_value_on_page(
    page_text: str,
    db_value: str,
    field_name: str = "",
) -> Optional[ContentMatch]:
    """Find a DB value on a page using a cascade of matching strategies.

    Tries strategies in order of confidence (exact -> number_normalized ->
    case_insensitive -> word_expanded -> fuzzy) and returns the first match.

    Args:
        page_text: Visible text content of the web page.
        db_value: The value from the database to find on the page.
        field_name: Optional field name for context-aware matching hints.

    Returns:
        ContentMatch if found, None otherwise.
    """
    if not page_text or not db_value:
        return None

    db_value = db_value.strip()
    if not db_value:
        return None

    # Strategy cascade
    strategies = [
        _try_exact,
        _try_number_normalized,
        _try_case_insensitive,
        _try_word_expanded,
        _try_fuzzy,
    ]

    for strategy in strategies:
        result = strategy(page_text, db_value)
        if result is not None:
            logger.debug(
                "Matched '%s' via %s (confidence=%d)",
                db_value[:50], result.strategy_used, result.confidence,
            )
            return result

    logger.debug("No match found for '%s' on page", db_value[:50])
    return None


# ─────────────────────────────────────────────────────────────────────────────
# High-level API
# ─────────────────────────────────────────────────────────────────────────────


async def build_content_aware_fragment(
    url: str,
    db_value: str,
    field_name: str = "",
) -> Optional[Dict]:
    """Fetch a page and find the best text fragment for a DB value.

    Combines page fetching with value matching to produce a dict suitable
    for building W3C Text Fragment URLs.

    Args:
        url: The page URL to fetch and search.
        db_value: The database value to locate on the page.
        field_name: Optional field name for matching hints.

    Returns:
        Dict with matched_text, context_before, context_after, confidence,
        strategy_used -- or None if no match found.
    """
    page_text = await fetch_page_text(url)
    if page_text is None:
        logger.debug("Could not fetch page text for %s", url)
        return None

    match = find_value_on_page(page_text, db_value, field_name)
    if match is None:
        return None

    return {
        "matched_text": match.matched_text,
        "context_before": match.context_before,
        "context_after": match.context_after,
        "confidence": match.confidence,
        "strategy_used": match.strategy_used,
    }
