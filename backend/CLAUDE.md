# Backend - Certify Intel

FastAPI backend with 150+ endpoints, 26+ SQLAlchemy models, 17 extracted routers, and a 7-agent LangGraph AI system.

## Quick Reference

```bash
# Start server
python main.py

# Run CI-safe tests (no API keys needed)
python -m pytest -xvs tests/test_api_endpoints.py tests/test_ai_router.py tests/test_hallucination_prevention.py tests/test_cost_comparison.py tests/test_sales_marketing.py

# Run all tests (616 pass, 12 skip, 5 pre-existing failures)
python -m pytest -x --tb=short --ignore=tests/test_all_endpoints.py --ignore=tests/test_e2e.py --ignore=tests/e2e/ --ignore=tests/test_e2e_workflows.py

# Lint
python -m flake8 --max-line-length=120 main.py ai_router.py agents/ routers/ middleware/
```

## Architecture (v9.0.0)

| Component | File(s) | Lines |
|-----------|---------|-------|
| API + Endpoints | `main.py` | ~16,617 |
| Extracted Routers | `routers/*.py` (17 files) | ~7,607 |
| Shared Dependencies | `dependencies.py` | ~85 |
| Constants | `constants.py` | ~57 |
| Pydantic Schemas | `schemas/*.py` (5 files) | ~455 |
| AI Router | `ai_router.py` | ~788 |
| Database ORM | `database.py` | ~1,547 |
| Knowledge Base | `knowledge_base.py` | ~828 |
| Vector Store | `vector_store.py` | ~906 |
| Agents (7) | `agents/*.py` | ~6,482 |
| Caching | `cache.py` | ~149 |
| Metrics | `metrics.py` | ~177 |
| MFA | `mfa.py` | ~106 |
| Middleware | `middleware/*.py` | ~144 |
| Services | `services/task_service.py` | ~128 |

### Router Files
| Router | Prefix | Key Endpoints |
|--------|--------|---------------|
| `routers/auth.py` | `/api/auth` | Login, register, refresh, MFA, password change |
| `routers/health.py` | `/health`, `/readiness` | Liveness/readiness probes |
| `routers/competitors.py` | `/api/competitors` | CRUD, relationships |
| `routers/dashboard.py` | `/api/dashboard` | Threats, trends |
| `routers/chat.py` | `/api/chat` | Sessions, messages |
| `routers/admin.py` | `/api/admin` | Prompts, audit logs |
| `routers/data_quality.py` | `/api/data-quality` | Quality overview |
| `routers/ai_cost.py` | `/api/ai/cost` | AI cost analytics |
| `routers/webhooks.py` | `/api/webhooks` | Webhook CRUD |
| `routers/winloss.py` | `/api/winloss` | Deal tracking |

## Key Conventions

- **Async**: All new endpoints and DB operations must use async/await
- **Imports**: Add local imports inside endpoint functions (flake8 CI catches undefined names)
- **Imports (routers)**: Import `get_db`, `get_current_user` from `dependencies.py`, not `main.py`
- **Models**: SQLAlchemy 2.0 `select()` pattern, not legacy `query()`
- **Schemas**: Pydantic models go in `schemas/` directory, not inline in endpoints
- **Migrations**: Manual ALTER TABLE in `init_db()` with try/except for duplicate columns
- **Auth**: JWT (15-min access + 7-day refresh tokens), PBKDF2-HMAC-SHA256 passwords, optional TOTP MFA
- **AI Routing**: Claude Opus 4.5 (complex) → GPT-4o (fallback) → Gemini (bulk/cheap)
- **XSS**: Sanitize all user inputs before storage or rendering
- **No hardcoded data**: Always use dynamic DB lookups
- **Caching**: Use `get_cache()` from `cache.py` - returns Redis or InMemoryCache based on env
- **Metrics**: Use `track_request()`, `track_ai_call()` from `metrics.py` - no-ops when disabled

## Agent System

7 LangGraph-orchestrated agents in `agents/`:
- All inherit from `BaseAgent` (`agents/base_agent.py`)
- Orchestrator routes via keyword scoring (`agents/orchestrator.py`)
- Citation validation prevents hallucinations (`agents/citation_validator.py`)
- New agents must be registered in `agents/__init__.py`

## Database

26+ SQLAlchemy models. Key: `Competitor` (115+ fields), `ChangeLog`, `User` (+ MFA columns), `RefreshToken`, `Battlecard`, `CompetitorProduct`, `KnowledgeBaseItem`.

**Critical**: SQLite won't auto-create columns added to ORM models. Always add ALTER TABLE migration in `init_db()`.

## For Agent Team Teammates

If you are a teammate working on the backend:
- Your changes should stay within `backend/` files
- New endpoints should go in the appropriate `routers/*.py` file, not `main.py`
- Import shared deps from `dependencies.py` and `constants.py`
- Coordinate with frontend teammate if API response shape changes
- Run `python -m flake8 --max-line-length=120` on changed files before finishing
- Run CI-safe tests to verify nothing breaks

## Default Login

`[YOUR-ADMIN-EMAIL]` / `[YOUR-ADMIN-PASSWORD]`
