"""
E2E Test Configuration for Certify Intel

Provides fixtures for Playwright browser automation and API testing.
Tests run against a live server instance.
"""

import asyncio
import os
import pytest
import subprocess
import time
from typing import Generator

# Note: pytest_plugins should only be defined in the top-level conftest.py
# The pytest-asyncio plugin is configured in pyproject.toml or pytest.ini instead
# See: https://docs.pytest.org/en/latest/how-to/plugins.html#requiring-loading-plugins-in-a-test-module-or-conftest-file


# Server configuration
TEST_SERVER_HOST = os.getenv("TEST_SERVER_HOST", "localhost")
TEST_SERVER_PORT = int(os.getenv("TEST_SERVER_PORT", "8000"))
TEST_BASE_URL = f"http://{TEST_SERVER_HOST}:{TEST_SERVER_PORT}"

# Test credentials
TEST_ADMIN_EMAIL = os.getenv("TEST_ADMIN_EMAIL", "[YOUR-ADMIN-EMAIL]")
TEST_ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD", "[YOUR-ADMIN-PASSWORD]")


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def base_url() -> str:
    """Return the base URL for the test server."""
    return TEST_BASE_URL


@pytest.fixture(scope="session")
def admin_credentials() -> dict:
    """Return admin credentials for authentication."""
    return {
        "email": TEST_ADMIN_EMAIL,
        "password": TEST_ADMIN_PASSWORD
    }


@pytest.fixture(scope="session")
def server_running(base_url: str) -> bool:
    """
    Check if the test server is running.

    E2E tests require a running server. This fixture verifies connectivity.
    """
    import requests

    max_retries = 5
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            response = requests.get(f"{base_url}/health", timeout=5)
            if response.status_code == 200:
                return True
        except requests.exceptions.ConnectionError:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)

    pytest.skip(f"Test server not running at {base_url}. Start with: python main.py")
    return False


@pytest.fixture(scope="session")
def auth_token(base_url: str, admin_credentials: dict, server_running: bool) -> str:
    """
    Get authentication token for API requests.

    Returns:
        Bearer token string
    """
    import requests

    response = requests.post(
        f"{base_url}/token",
        data={
            "username": admin_credentials["email"],
            "password": admin_credentials["password"]
        }
    )

    if response.status_code != 200:
        pytest.fail(f"Authentication failed: {response.text}")

    token = response.json().get("access_token")
    return token


@pytest.fixture(scope="session")
def auth_headers(auth_token: str) -> dict:
    """Return headers with authorization token."""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


@pytest.fixture(scope="function")
def api_client(base_url: str, auth_headers: dict):
    """
    Create an authenticated API client for tests.

    Yields a simple client with get/post/put/delete methods.
    """
    import requests

    class APIClient:
        def __init__(self, base_url: str, headers: dict):
            self.base_url = base_url
            self.headers = headers
            self.session = requests.Session()
            self.session.headers.update(headers)

        def get(self, path: str, **kwargs):
            return self.session.get(f"{self.base_url}{path}", **kwargs)

        def post(self, path: str, **kwargs):
            return self.session.post(f"{self.base_url}{path}", **kwargs)

        def put(self, path: str, **kwargs):
            return self.session.put(f"{self.base_url}{path}", **kwargs)

        def delete(self, path: str, **kwargs):
            return self.session.delete(f"{self.base_url}{path}", **kwargs)

        def upload_file(self, path: str, file_path: str, **kwargs):
            """Upload a file with multipart form data."""
            with open(file_path, 'rb') as f:
                files = {'file': f}
                # Remove Content-Type for multipart
                headers = {k: v for k, v in self.headers.items() if k != 'Content-Type'}
                return self.session.post(
                    f"{self.base_url}{path}",
                    files=files,
                    headers=headers,
                    **kwargs
                )

    return APIClient(base_url, auth_headers)


@pytest.fixture(scope="function")
async def browser_page(base_url: str):
    """
    Create a Playwright browser page for UI testing.

    Yields a page object, closes browser after test.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        pytest.skip("Playwright not installed. Run: pip install playwright && playwright install")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # Navigate to app
        await page.goto(base_url)

        yield page

        await browser.close()


@pytest.fixture(scope="function")
async def authenticated_page(browser_page, admin_credentials: dict, base_url: str):
    """
    Create a browser page with user logged in.

    Performs login and yields the authenticated page.
    """
    page = browser_page

    # Navigate to login
    await page.goto(f"{base_url}/login.html")

    # Fill login form
    await page.fill('input[name="email"], input[type="email"], #email', admin_credentials["email"])
    await page.fill('input[name="password"], input[type="password"], #password', admin_credentials["password"])

    # Submit login
    await page.click('button[type="submit"], .login-btn, #loginBtn')

    # Wait for redirect to dashboard
    await page.wait_for_url(f"{base_url}/**", timeout=10000)

    yield page


# Test data fixtures
@pytest.fixture
def sample_pdf_content() -> bytes:
    """
    Generate a simple PDF for testing document upload.

    Returns raw PDF bytes.
    """
    # Minimal valid PDF
    pdf_content = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >> endobj
4 0 obj << /Length 44 >> stream
BT /F1 12 Tf 100 700 Td (Test Document) Tj ET
endstream endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000206 00000 n
trailer << /Size 5 /Root 1 0 R >>
startxref
300
%%EOF"""
    return pdf_content


@pytest.fixture
def sample_text_document() -> str:
    """
    Sample competitive intelligence document text for testing.
    """
    return """
# Competitor Analysis: Epic Systems

## Company Overview
Epic Systems Corporation is a leading healthcare software company based in Verona, Wisconsin.
Founded in 1979 by Judith Faulkner, the company has grown to serve over 250 million patients worldwide.

## Key Metrics
- Customer Count: 2,800+ healthcare organizations
- Employee Count: 12,500+ employees
- Annual Revenue: Estimated $4.2 billion (2025)
- Market Share: 38% of US hospital EHR market

## Products
- Epic EHR - Core electronic health record system
- MyChart - Patient portal with 200M+ users
- Epic Cosmos - Research data network
- Epic Community Connect - Community health solution

## Pricing Strategy
Epic uses a perpetual license model with annual maintenance fees.
Typical implementation costs range from $50-500 million for large health systems.
Base price per bed: $15,000-$30,000 depending on modules selected.

## Competitive Strengths
1. Market leading position in large health systems
2. Comprehensive interoperability via Care Everywhere
3. Strong R&D investment (15% of revenue)
4. High customer satisfaction (KLAS #1 rating)

## Competitive Weaknesses
1. High implementation costs limit SMB adoption
2. Closed ecosystem approach
3. Limited cloud-native offerings
4. Long implementation timelines (2-3 years)
"""


@pytest.fixture
def sample_competitor_data() -> dict:
    """Sample competitor data for API testing."""
    return {
        "name": "Test Competitor Inc",
        "website": "https://testcompetitor.com",
        "headquarters": "San Francisco, CA",
        "employee_count": "100-500",
        "founded_year": 2015,
        "description": "A test competitor for E2E testing",
        "threat_level": "medium"
    }
