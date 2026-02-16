# Contributing to Certify Intel

## Quick Start

```bash
# Clone and set up
git clone <repo-url>
cd Certify_Intel_Final/backend
python -m venv venv
source venv/bin/activate  # or .\venv\Scripts\Activate.ps1 on Windows
pip install -r requirements.txt
cp .env.example .env      # Edit with your keys
python main.py             # http://localhost:8000
```

---

## CI/CD Pipeline

All workflows run automatically via GitHub Actions.

### On Push to Master
| Workflow | What It Does |
|----------|-------------|
| **Backend Tests** | pytest (616 tests), flake8 linting |
| **Frontend Tests** | Jest (55 tests) |
| **Security Scan** | Bandit SAST analysis |

### Feature Branch Workflow
```bash
git checkout -b feature/my-feature
# ... make changes ...
git add -A && git commit -m "[Feature] Description"
git push origin feature/my-feature
# -> CI runs tests
# -> PR auto-created to master (labeled 'auto-pr')
# -> Auto-merges when all checks pass (squash merge)
```

### Direct to Master (Quick Fixes)
```bash
git checkout master
git add -A && git commit -m "[Fix] Description"
git push origin master
# -> CI runs tests automatically
```

### Releases
```bash
git tag v9.1.0
git push origin v9.1.0
# -> CI runs tests + creates GitHub Release with auto-generated notes
```

---

## Commit Categories

| Category | Use For |
|----------|---------|
| `[Fix]` | Bug fixes |
| `[Feature]` | New functionality |
| `[Docs]` | Documentation |
| `[Build]` | Desktop app releases |
| `[Refactor]` | Code restructuring |
| `[Chore]` | Maintenance |

---

## Project Structure

```
Certify_Intel_Final/
├── backend/               # FastAPI Python backend (150+ endpoints)
│   ├── agents/            # 7 LangGraph AI agents
│   ├── routers/           # 17 extracted API routers
│   ├── schemas/           # Pydantic models
│   ├── middleware/         # Security headers, metrics
│   ├── services/          # Task service
│   ├── data_providers/    # 10 enterprise data adapters
│   ├── tests/             # 616 tests
│   └── main.py            # App entry point
├── frontend/              # Vanilla JS SPA (11 pages)
│   ├── core/              # ES6 modules (api, utils, navigation)
│   ├── components/        # Shared components (chat, modals, toast)
│   ├── __tests__/         # 55 Jest tests
│   └── app_v2.js          # Main application
├── desktop-app/           # Electron wrapper for Windows builds
├── client_docs/           # Developer documentation (8 guides)
├── docs/                  # Technical reference docs
├── nginx/                 # Reverse proxy config
├── monitoring/            # Prometheus config
├── scripts/               # DB migration, backup, CI helpers
├── docker-compose*.yml    # Docker service configs
├── CLAUDE.md              # Comprehensive technical reference
└── GETTING_STARTED.md     # 5-minute setup guide
```

---

## Code Style

- **Python**: Type hints, async/await, SQLAlchemy 2.0 `select()`, Pydantic models
- **JavaScript**: ES6+, vanilla JS (no frameworks), `escapeHtml()` for all dynamic content
- **CSS**: CSS variables, flexbox/grid, dark theme

## Key Rules

- All AI system prompts must include `NO_HALLUCINATION_INSTRUCTION` from `constants.py`
- New endpoints go in `routers/*.py`, not `main.py`
- Import shared deps from `dependencies.py` (never from `main.py`)
- Use `get_ai_router()` singleton, never `AIRouter()` per request
- Use `escapeHtml()` for any innerHTML with dynamic content (XSS prevention)

---

## Documentation

| Document | Location |
|----------|----------|
| Technical reference | `CLAUDE.md` (project root) |
| Quick setup | `GETTING_STARTED.md` |
| Developer guides | `client_docs/` (8 files) |
| API reference | `docs/API_REFERENCE.md` |
| Architecture | `docs/ARCHITECTURE.md` |
