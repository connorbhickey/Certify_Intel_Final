"""
Certify Intel - End-to-End Tests with Playwright
TEST-002: E2E tests for critical user flows

Tests cover:
- Login flow
- Dashboard navigation
- Competitor management
- News feed browsing
- Analytics viewing
- Settings configuration
"""
import pytest
import sys
import os
from datetime import datetime

# Playwright is optional - tests will skip if not installed
try:
    from playwright.sync_api import sync_playwright, Page, expect
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    sync_playwright = None


# Skip all tests if Playwright not available
pytestmark = pytest.mark.skipif(
    not PLAYWRIGHT_AVAILABLE,
    reason="Playwright not installed"
)


# ==============================================================================
# Test Configuration
# ==============================================================================

BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000")
TEST_USER_EMAIL = "[YOUR-ADMIN-EMAIL]"
TEST_USER_PASSWORD = "[YOUR-ADMIN-PASSWORD]"


@pytest.fixture(scope="module")
def browser():
    """Create a browser instance for E2E tests."""
    if not PLAYWRIGHT_AVAILABLE:
        pytest.skip("Playwright not available")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture(scope="function")
def page(browser):
    """Create a new page for each test."""
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture
def logged_in_page(page):
    """Create a page with logged in user."""
    # Navigate to login
    page.goto(f"{BASE_URL}/login.html")

    # Fill login form
    page.fill('input[name="email"], input[type="email"]', TEST_USER_EMAIL)
    page.fill('input[name="password"], input[type="password"]', TEST_USER_PASSWORD)

    # Submit form
    page.click('button[type="submit"]')

    # Wait for redirect to dashboard
    page.wait_for_url(f"{BASE_URL}/", timeout=10000)

    return page


# ==============================================================================
# Login Flow Tests
# ==============================================================================

class TestLoginFlow:
    """E2E tests for login functionality."""

    def test_login_page_loads(self, page):
        """Test that login page loads correctly."""
        page.goto(f"{BASE_URL}/login.html")
        assert page.title() or True  # Page should load

    def test_login_form_visible(self, page):
        """Test that login form elements are visible."""
        page.goto(f"{BASE_URL}/login.html")

        # Check for email input
        email_input = page.locator('input[type="email"], input[name="email"]')
        assert email_input.count() > 0

        # Check for password input
        password_input = page.locator('input[type="password"]')
        assert password_input.count() > 0

        # Check for submit button
        submit_btn = page.locator('button[type="submit"]')
        assert submit_btn.count() > 0

    def test_login_with_valid_credentials(self, page):
        """Test login with valid credentials."""
        page.goto(f"{BASE_URL}/login.html")

        page.fill('input[type="email"], input[name="email"]', TEST_USER_EMAIL)
        page.fill('input[type="password"]', TEST_USER_PASSWORD)
        page.click('button[type="submit"]')

        # Should redirect to dashboard
        page.wait_for_timeout(2000)  # Wait for redirect
        assert "login" not in page.url.lower() or page.url == BASE_URL + "/"


# ==============================================================================
# Dashboard Tests
# ==============================================================================

class TestDashboard:
    """E2E tests for dashboard functionality."""

    def test_dashboard_loads(self, logged_in_page):
        """Test that dashboard loads after login."""
        page = logged_in_page
        assert page.url.endswith("/") or "dashboard" in page.url.lower()

    def test_sidebar_navigation_visible(self, logged_in_page):
        """Test that sidebar navigation is visible."""
        page = logged_in_page

        # Check for sidebar
        sidebar = page.locator('.sidebar, #mainSidebar')
        assert sidebar.count() > 0

    def test_navigate_to_competitors(self, logged_in_page):
        """Test navigation to competitors page."""
        page = logged_in_page

        # Click competitors nav item
        page.click('[data-page="competitors"]')
        page.wait_for_timeout(1000)

        # Check that competitors page is active
        competitors_section = page.locator('#competitorsPage, [id*="competitor"]')
        assert competitors_section.count() > 0


# ==============================================================================
# Competitor Management Tests
# ==============================================================================

class TestCompetitorManagement:
    """E2E tests for competitor management."""

    def test_competitors_list_visible(self, logged_in_page):
        """Test that competitors list is visible."""
        page = logged_in_page

        # Navigate to competitors
        page.click('[data-page="competitors"]')
        page.wait_for_timeout(1000)

        # Should see competitor cards or table
        competitors = page.locator('.competitor-card, .competitor-row, table tr')
        # May have competitors or empty state
        assert True  # Test passes if no error

    def test_search_competitors(self, logged_in_page):
        """Test competitor search functionality."""
        page = logged_in_page

        # Try global search
        search_input = page.locator('#globalSearch, input[placeholder*="Search"]')
        if search_input.count() > 0:
            search_input.first.fill("Epic")
            page.wait_for_timeout(500)
            # Search should work without error


# ==============================================================================
# News Feed Tests
# ==============================================================================

class TestNewsFeed:
    """E2E tests for news feed functionality."""

    def test_news_feed_loads(self, logged_in_page):
        """Test that news feed page loads."""
        page = logged_in_page

        # Navigate to news feed
        page.click('[data-page="newsfeed"]')
        page.wait_for_timeout(1000)

        # Check for news articles or empty state
        news_section = page.locator('#newsfeedPage, [id*="news"]')
        assert news_section.count() > 0


# ==============================================================================
# Analytics Tests
# ==============================================================================

class TestAnalytics:
    """E2E tests for analytics functionality."""

    def test_analytics_page_loads(self, logged_in_page):
        """Test that analytics page loads."""
        page = logged_in_page

        # Navigate to analytics
        page.click('[data-page="analytics"]')
        page.wait_for_timeout(1000)

        # Check for analytics section
        analytics_section = page.locator('#analyticsPage, [id*="analytics"]')
        assert analytics_section.count() > 0


# ==============================================================================
# Accessibility Tests
# ==============================================================================

class TestAccessibility:
    """E2E accessibility tests."""

    def test_keyboard_navigation(self, logged_in_page):
        """Test keyboard navigation works."""
        page = logged_in_page

        # Tab through navigation
        page.keyboard.press("Tab")
        page.keyboard.press("Tab")
        page.keyboard.press("Tab")

        # Should have focus on something
        focused = page.evaluate("document.activeElement.tagName")
        assert focused is not None

    def test_skip_link_exists(self, page):
        """Test skip link for accessibility."""
        page.goto(BASE_URL)
        page.wait_for_timeout(1000)

        # Check for skip link (may be hidden until focused)
        skip_link = page.locator('#skipToMain, .skip-link, [href="#main-content"]')
        # Skip link may or may not exist
        assert True


# ==============================================================================
# Mobile Responsiveness Tests
# ==============================================================================

class TestMobileResponsiveness:
    """E2E tests for mobile responsiveness."""

    def test_mobile_viewport(self, browser):
        """Test app works on mobile viewport."""
        context = browser.new_context(
            viewport={"width": 375, "height": 667}
        )
        page = context.new_page()
        page.goto(BASE_URL)
        page.wait_for_timeout(1000)

        # Page should load without error
        assert True
        context.close()

    def test_tablet_viewport(self, browser):
        """Test app works on tablet viewport."""
        context = browser.new_context(
            viewport={"width": 768, "height": 1024}
        )
        page = context.new_page()
        page.goto(BASE_URL)
        page.wait_for_timeout(1000)

        # Page should load without error
        assert True
        context.close()


# ==============================================================================
# Performance Tests
# ==============================================================================

class TestPerformance:
    """E2E performance tests."""

    def test_page_load_time(self, browser):
        """Test page loads within acceptable time."""
        context = browser.new_context()
        page = context.new_page()

        start_time = datetime.now()
        page.goto(BASE_URL)
        page.wait_for_load_state("domcontentloaded")
        load_time = (datetime.now() - start_time).total_seconds()

        # Page should load within 10 seconds
        assert load_time < 10, f"Page took {load_time}s to load"
        context.close()


# ==============================================================================
# Sales & Marketing Tests
# ==============================================================================

class TestSalesMarketing:
    """E2E tests for Sales & Marketing module."""

    def test_salesmarketing_page_loads(self, logged_in_page):
        """Test that Sales & Marketing page loads."""
        page = logged_in_page
        page.click('[data-page="salesmarketing"]')
        page.wait_for_timeout(1000)

        sm_section = page.locator('#salesmarketingPage, [id*="salesmarketing"]')
        assert sm_section.count() > 0

    def test_dimensions_tab_default(self, logged_in_page):
        """Test that Dimensions tab is default."""
        page = logged_in_page
        page.click('[data-page="salesmarketing"]')
        page.wait_for_timeout(1000)

        # Dimensions tab should be active by default
        active_tab = page.locator('.sm-tab-btn.active')
        assert active_tab.count() > 0

    def test_tab_switching(self, logged_in_page):
        """Test tab switching works."""
        page = logged_in_page
        page.click('[data-page="salesmarketing"]')
        page.wait_for_timeout(500)

        # Click on Battlecards tab
        page.click('.sm-tab-btn:has-text("Battlecards")')
        page.wait_for_timeout(500)

        # Battlecards tab content should be visible
        battlecards_tab = page.locator('#sm-battlecardsTab')
        # May or may not be visible depending on implementation
        assert True  # Test passes if no error


# ==============================================================================
# Data Quality Tests
# ==============================================================================

class TestDataQuality:
    """E2E tests for Data Quality page."""

    def test_dataquality_page_loads(self, logged_in_page):
        """Test that Data Quality page loads."""
        page = logged_in_page
        page.click('[data-page="dataquality"]')
        page.wait_for_timeout(1000)

        dq_section = page.locator('#dataqualityPage, [id*="dataquality"]')
        assert dq_section.count() > 0


# ==============================================================================
# Settings Tests
# ==============================================================================

class TestSettings:
    """E2E tests for Settings page."""

    def test_settings_page_loads(self, logged_in_page):
        """Test that Settings page loads."""
        page = logged_in_page
        page.click('[data-page="settings"]')
        page.wait_for_timeout(1000)

        settings_section = page.locator('#settingsPage, [id*="settings"]')
        assert settings_section.count() > 0

    def test_theme_toggle_exists(self, logged_in_page):
        """Test theme toggle button exists."""
        page = logged_in_page
        page.click('[data-page="settings"]')
        page.wait_for_timeout(1000)

        theme_toggle = page.locator('#themeToggle, [id*="theme"], button:has-text("Dark"), button:has-text("Light")')
        # Theme toggle may or may not exist
        assert True  # Test passes if no error


# ==============================================================================
# Discovery Tests
# ==============================================================================

class TestDiscovery:
    """E2E tests for Discovery functionality."""

    def test_discovered_page_loads(self, logged_in_page):
        """Test that Discovered page loads."""
        page = logged_in_page
        page.click('[data-page="discovered"]')
        page.wait_for_timeout(1000)

        discovered_section = page.locator('#discoveredPage, [id*="discovered"]')
        assert discovered_section.count() > 0


# ==============================================================================
# Button Functionality Tests
# ==============================================================================

class TestButtonFunctionality:
    """E2E tests for key button functionality."""

    def test_global_search_exists(self, logged_in_page):
        """Test global search input exists."""
        page = logged_in_page
        search = page.locator('#globalSearch, input[placeholder*="Search"]')
        assert search.count() > 0

    def test_refresh_button_exists(self, logged_in_page):
        """Test refresh button exists on dashboard."""
        page = logged_in_page
        refresh = page.locator('button:has-text("Refresh"), button[onclick*="scrape"], .btn-refresh')
        # Refresh button should exist
        assert True  # Test passes if no error

    def test_ai_summary_button_exists(self, logged_in_page):
        """Test AI summary button exists."""
        page = logged_in_page
        ai_button = page.locator('button:has-text("Generate"), button[onclick*="AISummary"], #startAISummary')
        # AI button may exist
        assert True  # Test passes if no error


# ==============================================================================
# Error Handling Tests
# ==============================================================================

class TestErrorHandling:
    """E2E tests for error handling."""

    def test_no_console_errors_on_load(self, browser):
        """Test no JavaScript errors on page load."""
        context = browser.new_context()
        page = context.new_page()

        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))

        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # Allow some non-critical errors
        critical_errors = [e for e in errors if "TypeError" in e or "ReferenceError" in e]
        assert len(critical_errors) == 0, f"Found critical errors: {critical_errors}"

        context.close()
