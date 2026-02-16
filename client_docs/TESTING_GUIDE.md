# Testing Guide

---

## Test Suite Overview

| Suite | Location | Count | Framework |
|-------|----------|-------|-----------|
| Backend unit/integration | `backend/tests/` | 616 pass, 12 skip | pytest |
| Frontend unit | `frontend/__tests__/` | 55 pass | Jest |
| E2E workflow | `backend/tests/test_e2e_workflows.py` | 88 tests | pytest + TestClient |
| E2E live API | `backend/tests/e2e/` | 14 tests | pytest (requires running server) |

---

## Running Tests

### Backend Tests (Primary)

```bash
cd backend

# Run all CI-safe tests (recommended)
python -m pytest -x --tb=short \
  --ignore=tests/test_all_endpoints.py \
  --ignore=tests/test_e2e.py \
  --ignore=tests/e2e/ \
  --ignore=tests/test_e2e_workflows.py

# Run specific test file
python -m pytest tests/test_api_endpoints.py -xvs

# Run tests matching a pattern
python -m pytest -k "test_battlecard" -xvs

# CI-safe subset (no API keys needed)
python -m pytest -xvs \
  tests/test_api_endpoints.py \
  tests/test_ai_router.py \
  tests/test_hallucination_prevention.py \
  tests/test_cost_comparison.py \
  tests/test_sales_marketing.py
```

### Frontend Tests

```bash
cd frontend
npm test                    # Run all Jest tests
npm test -- --watch         # Watch mode
npm test -- --coverage      # Coverage report
```

### E2E Tests (Requires Running Server)

```bash
# Start server first
cd backend && python main.py

# In another terminal
cd backend
python -m pytest tests/test_e2e_workflows.py -xvs
python -m pytest tests/e2e/ -xvs
```

### Linting

```bash
# Backend
cd backend
python -m flake8 --max-line-length=120 main.py ai_router.py agents/ routers/ middleware/

# Frontend
cd frontend
npx eslint app_v2.js
npx prettier --check "**/*.js"
```

---

## Test File Reference

| File | What It Tests |
|------|--------------|
| `test_api_endpoints.py` | Core API endpoints (competitors, dashboard, auth) |
| `test_ai_router.py` | AI provider routing and fallback logic |
| `test_hallucination_prevention.py` | NO_HALLUCINATION_INSTRUCTION enforcement |
| `test_cost_comparison.py` | AI cost tracking and comparison |
| `test_sales_marketing.py` | Dimensions, battlecards, talking points |
| `test_agent_integration.py` | LangGraph agent orchestration |
| `test_discovery.py` | Discovery Scout pipeline |
| `test_data_quality.py` | Data quality scoring and triangulation |
| `test_news_feed.py` | News fetching and classification |
| `test_auth.py` | Authentication, JWT, MFA |
| `test_chat.py` | Chat sessions and messages |
| `test_vector_store.py` | Vector store and embedding operations |
| `test_source_verification.py` | Source URL verification pipeline |
| `test_content_matcher.py` | Content matching strategies |
| `test_url_refinement.py` | URL refinement engine |
| `test_observability.py` | Langfuse integration |
| `test_infrastructure.py` | Health, readiness, rate limiting |
| `test_new_providers.py` | LiteLLM, Ollama, local embeddings |
| `test_routers.py` | Extracted router endpoints |
| `test_cache.py` | Redis + InMemoryCache |

### Frontend Tests
| File | What It Tests |
|------|--------------|
| `utils.test.js` | escapeHtml, formatters, debounce (25 tests) |
| `api.test.js` | fetchAPI, auth token handling (15 tests) |
| `formatters.test.js` | Date/number formatting (15 tests) |

---

## Writing New Tests

### Backend Test Pattern

```python
# tests/test_my_feature.py
import pytest
from unittest.mock import patch, MagicMock

# Tests use the shared conftest.py fixtures (test DB, auth tokens, etc.)

class TestMyFeature:
    """Tests for my new feature."""

    def test_basic_functionality(self, client, auth_headers):
        """Test the happy path."""
        response = client.get("/api/my-endpoint", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "expected_field" in data

    def test_unauthorized_access(self, client):
        """Test that unauthenticated requests are rejected."""
        response = client.get("/api/my-endpoint")
        assert response.status_code == 401

    @patch("main.get_ai_router")
    def test_ai_integration(self, mock_router, client, auth_headers):
        """Test with mocked AI provider."""
        mock_router.return_value.route_request.return_value = {
            "content": "AI response"
        }
        response = client.post(
            "/api/my-ai-endpoint",
            json={"query": "test"},
            headers=auth_headers
        )
        assert response.status_code == 200
```

### Frontend Test Pattern

```javascript
// __tests__/my_feature.test.js
const { myFunction } = require('../testable-utils');

describe('myFunction', () => {
    test('handles normal input', () => {
        expect(myFunction('test')).toBe('expected');
    });

    test('handles edge cases', () => {
        expect(myFunction('')).toBe('');
        expect(myFunction(null)).toBe(null);
    });
});
```

---

## Test Configuration

### `conftest.py` Key Fixtures
- `client` - FastAPI TestClient instance
- `auth_headers` - `{"Authorization": "Bearer <token>"}` for authenticated requests
- `db` - Test database session (uses same SQLite DB)
- `mock_ai_router` - Mocked AI provider (no API keys needed)

### Environment Variables for Tests
```bash
SECRET_KEY=test-secret-key-for-testing    # Set automatically by conftest.py
TEST_ADMIN_EMAIL=admin@test.com           # Override default test admin
TEST_ADMIN_PASSWORD=testpass123           # Override default test password
```

---

## Known Test Behaviors

- `test_e2e_workflows.py` has a pre-existing timeout issue with Starlette test client
- `test_all_endpoints.py` and `test_e2e.py` require a running server (not CI-safe)
- Vector store tests log harmless "invalid DSN" errors (tests use SQLite, not PostgreSQL)
- Pydantic v1 deprecation warnings appear on Python 3.14+ (safe to ignore)
