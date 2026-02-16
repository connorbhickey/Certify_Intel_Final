# Development Guide

This guide covers everything you need to start developing on Certify Intel.

---

## Development Environment Setup

### Prerequisites
- Python 3.9+ (3.11+ recommended)
- Node.js 18+ (only for desktop app builds)
- Git

### First-Time Setup

```bash
# Clone the repo
git clone <repo-url>
cd Certify_Intel

# Backend
cd backend
python -m venv venv
venv\Scripts\activate         # Windows
source venv/bin/activate      # macOS/Linux
pip install -r requirements.txt

# Copy and configure environment
copy .env.example .env        # Windows
cp .env.example .env          # macOS/Linux
# Edit .env with your SECRET_KEY, ADMIN_EMAIL, ADMIN_PASSWORD, and AI keys

# Start the server
python main.py
# Server runs at http://localhost:8000
```

### Running Tests

```bash
# Backend tests (from backend/)
python -m pytest -x --tb=short --ignore=tests/test_all_endpoints.py --ignore=tests/test_e2e.py --ignore=tests/e2e/ --ignore=tests/test_e2e_workflows.py

# Frontend tests (from frontend/)
npm test

# Lint backend
python -m flake8 --max-line-length=120 main.py ai_router.py agents/ routers/ middleware/

# Lint frontend
npx eslint app_v2.js
```

---

## Project Structure

```
Certify_Intel/
  backend/
    main.py                    # FastAPI app + remaining inline endpoints (~16,600 lines)
    database.py                # SQLAlchemy models + DB init (~1,550 lines)
    extended_features.py       # Auth system (JWT, MFA, password hashing)
    ai_router.py               # AI provider routing (Claude/GPT/Gemini/DeepSeek)
    dependencies.py            # Shared FastAPI dependencies (get_db, get_current_user)
    constants.py               # App version, shared constants
    cache.py                   # Redis + InMemoryCache abstraction
    metrics.py                 # Prometheus metrics (NoOp when disabled)
    mfa.py                     # TOTP MFA implementation
    routers/                   # 17 extracted route modules
    agents/                    # 7 LangGraph AI agents + orchestrator
    middleware/                # Security headers, metrics middleware
    schemas/                   # Pydantic request/response models
    services/                  # Business logic services
    data_providers/            # 10 enterprise data provider adapters
    tests/                     # 600+ pytest tests
  frontend/
    index.html                 # Main SPA entry point
    login.html                 # Login page
    app_v2.js                  # Main application logic (~24,000 lines)
    styles.css                 # All CSS styles
    app.js                     # ES6 module entry point
    core/                      # ES6 core modules (api, utils, state, navigation)
    components/                # ES6 UI components (toast, modals, chat, command palette)
    __tests__/                 # Jest unit tests
  desktop-app/
    main.js                    # Electron main process
    package.json               # Electron config + auto-update settings
    frontend/                  # COPY of frontend/ (synced before builds)
  docs/                        # Technical documentation
  client_docs/                 # Developer documentation (you are here)
  scripts/                     # Utility scripts (DB migration, backup)
  nginx/                       # Production reverse proxy config
  monitoring/                  # Prometheus + Grafana configs
  docker-compose*.yml          # Docker configurations
```

---

## Code Conventions

### Backend (Python)
- **Async/await**: All new endpoints and DB operations must be async
- **Type hints**: Required on all function signatures
- **SQLAlchemy 2.0**: Use `select()` pattern, not legacy `query()`
- **Local imports**: Import inside endpoint functions to avoid circular imports
- **Error handling**: Never return `str(e)` in HTTP responses. Use generic messages, log details with `logger.error()`
- **Dependencies**: Import `get_db`, `get_current_user` from `dependencies.py`, not `main.py`
- **AI prompts**: Always prepend `NO_HALLUCINATION_INSTRUCTION` (from `constants.py`) to AI system prompts

### Frontend (JavaScript)
- **Vanilla JS ES6+**: No frameworks (React, Vue, etc.)
- **XSS prevention**: Use `textContent` for user/AI content, `escapeHtml()` for innerHTML
- **API calls**: Always use `fetchAPI()` which handles auth tokens automatically
- **Naming**: camelCase for JS functions/variables, kebab-case for CSS classes
- **Global state**: Long-running operations use global polling flags (not `setInterval` inside Promises)

### Git Workflow
- Commit messages: `[Category] Brief description`
- Categories: `[Fix]`, `[Feature]`, `[Docs]`, `[Build]`, `[Refactor]`, `[Chore]`

---

## How to Add a New Feature

### Adding a New Backend Endpoint

1. **Choose the right file**: Put it in the appropriate `routers/*.py` file, not `main.py`
2. **Create the router** (if new category):
   ```python
   # routers/my_feature.py
   from fastapi import APIRouter, Depends
   from dependencies import get_db, get_current_user

   router = APIRouter(prefix="/api/my-feature", tags=["My Feature"])

   @router.get("/")
   async def get_items(db=Depends(get_db), user=Depends(get_current_user)):
       ...
   ```
3. **Register in main.py**:
   ```python
   from routers.my_feature import router as my_feature_router
   app.include_router(my_feature_router)
   ```
4. **Add tests** in `tests/test_my_feature.py`
5. **Run tests**: `python -m pytest tests/test_my_feature.py -xvs`

### Adding a New Frontend Page

1. **Add navigation entry** in `app_v2.js` inside the sidebar HTML
2. **Add the `showPage()` case**:
   ```javascript
   case 'my-page':
       try {
           document.getElementById('content').innerHTML = `
               <div class="page-header">
                   <h1>My Page</h1>
               </div>
               <div id="myPageContent"></div>
           `;
           await loadMyPageData();
       } catch (err) {
           console.error('Error loading my page:', err);
       }
       break;
   ```
3. **Add the data loading function** below the case
4. **Add keyboard shortcut** if needed (Ctrl+N pattern)

### Adding a New AI Agent

1. **Create agent file**: `backend/agents/my_agent.py`
2. **Inherit from BaseAgent**:
   ```python
   from agents.base_agent import BaseAgent

   class MyAgent(BaseAgent):
       def __init__(self, db_session=None):
           super().__init__(name="my_agent", db_session=db_session)

       async def process(self, query: str, context: dict = None) -> dict:
           # Your agent logic here
           ...
   ```
3. **Register in orchestrator**: Add routing keywords in `agents/orchestrator.py`
4. **Add endpoint** in `routers/agents.py`
5. **Add tests** in `tests/test_agent_integration.py`

### Adding a New Database Column

SQLite doesn't support `ALTER TABLE ADD COLUMN` reliably. Use this pattern:

1. **Add column to model** in `database.py`:
   ```python
   class Competitor(Base):
       my_new_field = Column(String, default="")
   ```
2. **Add migration** in `database.py` `init_db()`:
   ```python
   try:
       cursor.execute("ALTER TABLE competitors ADD COLUMN my_new_field TEXT DEFAULT ''")
   except Exception:
       pass  # Column already exists
   ```
3. **For PostgreSQL**: Use proper Alembic migrations (see ROADMAP.md)

---

## Key Architectural Patterns

### AI Provider Routing
The `AIRouter` class in `ai_router.py` handles multi-provider routing:
- **Claude** (Anthropic): Complex analysis, quality tasks
- **GPT-4o** (OpenAI): Fallback
- **Gemini Flash** (Google): Speed/bulk tasks (chat, summarization, classification)
- **Gemini Pro** (Google): Grounded search, deep research
- **DeepSeek**: Optional cheap bulk tasks

Task routing is configured in `TASK_ROUTING` dict. Use `get_ai_router()` singleton (never instantiate per-request).

### Authentication Flow
1. User logs in via `POST /token` -> receives access token (15-min) + refresh token (7-day)
2. Frontend stores tokens, sends `Authorization: Bearer <access_token>` on every request
3. On 401, frontend calls `POST /api/auth/refresh` with refresh token
4. Optional TOTP MFA adds second factor

### SPA Navigation
- Single `index.html` with `<div id="content">` placeholder
- `showPage(pageName)` swaps content dynamically
- URL hash tracks current page (`#competitors`, `#dashboard`, etc.)
- Background operations survive page navigation via global polling flags

### Caching Layer
- `get_cache()` returns Redis client (if `REDIS_ENABLED=true`) or `InMemoryCache` (default)
- TTL-based expiration, max 1000 entries for in-memory
- Used for AI task results, discovery cache, etc.

---

## Debugging Tips

- **Backend logs**: Check terminal output or `backend/server.log`
- **Frontend errors**: Browser DevTools Console (F12)
- **API testing**: Use the built-in Swagger UI at `http://localhost:8000/docs`
- **Database inspection**: Use DB Browser for SQLite on `backend/certify_intel.db`
- **AI provider issues**: Check Settings > AI Providers panel for connection status
- **Docker services**: `docker compose -f <file> logs -f` for container logs
