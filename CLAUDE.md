# Certify Intel v9.0.0 - Project Instructions

> **CRITICAL**: Ensure you are in the correct local project folder and GitHub repo.
> **Local Folder Path** = `[PROJECT_ROOT]/`
> **GitHub Repo URL** = `https://github.com/[YOUR-GITHUB-ORG]/Project_Intel_v6.1.1`

---

## MANDATORY INSTRUCTIONS FOR ALL AI AGENTS

> Every AI agent (Claude, GPT, Copilot, Cursor, etc.) working on this project MUST follow these rules.
> These instructions apply whether working from GitHub repo or local folder.

### File Save Locations

| File Type | Save Location | Example |
|-----------|---------------|---------|
| **Documentation** (plans, notes, guides) | `docs/` | `docs/PLAN_*.md` |
| **Archived docs** (completed plans) | `docs/Archived_Docs/` | `docs/Archived_Docs/DEBUG_PLAN_v7.md` |
| **Code files** | Respective folders | `backend/`, `frontend/`, `desktop-app/` |
| **Desktop app builds** | `desktop-app/dist/` | `desktop-app/dist/Certify_Intel_vX.X.X_Setup.exe` |
| **Scripts/utilities** | `docs/` or `scripts/` | `docs/CLEANUP_OLD_INSTALL.ps1` |

**NEVER save files to hidden folders** like `.claude-worktrees` or `.claude/plans` - users cannot find them.

---

### Desktop App Build Protocol (11 Steps)

**MANDATORY: Before building/installing ANY new desktop app version, you MUST follow ALL steps:**

#### Step 1: Bump Version in ALL 6 Files (If New Version)
> Skip this step if version is already correct (e.g., hotfix to same version).
```
backend/main.py               -> __version__ = "X.X.X"
frontend/index.html            -> <span class="app-version">vX.X.X</span>
desktop-app/frontend/index.html -> <span class="app-version">vX.X.X</span>
desktop-app/package.json        -> "version": "X.X.X"
frontend/service-worker.js      -> const CACHE_VERSION = 'vX.X.X'
desktop-app/frontend/service-worker.js -> const CACHE_VERSION = 'vX.X.X'
```

#### Step 2: Sync Frontend to Desktop-App (CRITICAL)
```powershell
# Core files
Copy-Item "frontend\app_v2.js" "desktop-app\frontend\app_v2.js" -Force
Copy-Item "frontend\styles.css" "desktop-app\frontend\styles.css" -Force
Copy-Item "frontend\index.html" "desktop-app\frontend\index.html" -Force
# ES6 modules (v9.0.0+)
Copy-Item "frontend\app.js" "desktop-app\frontend\app.js" -Force
Copy-Item -Recurse "frontend\core" "desktop-app\frontend\core" -Force
Copy-Item -Recurse "frontend\components" "desktop-app\frontend\components" -Force
# Verify byte-identical
fc /b frontend\app_v2.js desktop-app\frontend\app_v2.js
```

#### Step 3: Run Cleanup Script (Kill Processes, Clear Installed App)
```powershell
powershell -ExecutionPolicy Bypass -File "[PROJECT_ROOT]/docs\CLEANUP_OLD_INSTALL.ps1"
```

#### Step 4: Clear ALL Build Caches (CRITICAL - Prevents Stale Code)
```powershell
# Electron caches
Remove-Item -Recurse -Force "[PROJECT_ROOT]/desktop-app\dist" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "[PROJECT_ROOT]/desktop-app\node_modules\.cache" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\electron-builder" -ErrorAction SilentlyContinue
# PyInstaller caches (stale .pyc files cause issues)
Remove-Item -Recurse -Force "[PROJECT_ROOT]/backend\dist" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "[PROJECT_ROOT]/backend\build" -ErrorAction SilentlyContinue
```

#### Step 5: Verify Source Files Have Your Fix (Before Building)
```powershell
grep -n "YOUR_FIX_PATTERN" "[PROJECT_ROOT]/desktop-app\frontend\app_v2.js"
grep "__version__" backend/main.py
grep "app-version" frontend/index.html desktop-app/frontend/index.html
grep '"version"' desktop-app/package.json
grep "CACHE_VERSION" frontend/service-worker.js desktop-app/frontend/service-worker.js
```

#### Step 6: Rebuild PyInstaller Backend
```powershell
cd [PROJECT_ROOT]/backend
.\venv\Scripts\Activate.ps1
pyinstaller certify_backend.spec --clean --noconfirm
```

#### Step 7: Copy Backend Files to Bundle
```powershell
Copy-Item "backend\dist\certify_backend.exe" "desktop-app\backend-bundle\" -Force
Copy-Item "backend\certify_intel.db" "desktop-app\backend-bundle\" -Force
Copy-Item "backend\.env" "desktop-app\backend-bundle\" -Force
```

#### Step 8: Build Electron Installer
```powershell
cd [PROJECT_ROOT]/desktop-app
npm run build:win
```

#### Step 9: VERIFY Built App Contains Your Fix (CRITICAL)
```powershell
grep -n "YOUR_FIX_PATTERN" "[PROJECT_ROOT]/desktop-app\dist\win-unpacked\resources\frontend\app_v2.js"
# Verify all 3 release files exist (required for auto-updates)
ls desktop-app\dist\Certify_Intel_v*_Setup.exe
ls desktop-app\dist\Certify_Intel_v*_Setup.exe.blockmap
ls desktop-app\dist\latest.yml
```

#### Step 10: Tell User Where Installer Is
```
[PROJECT_ROOT]/desktop-app\dist\Certify_Intel_vX.X.X_Setup.exe
```

#### Step 11: Commit, Push, Update GitHub Release
```bash
git add -A
git commit -m "[Build] vX.X.X desktop app"
git push origin master
git tag -f vX.X.X HEAD
git push origin vX.X.X --force
gh release edit vX.X.X --notes "..."
gh release upload vX.X.X desktop-app/dist/Certify_Intel_vX.X.X_Setup.exe --clobber
gh release upload vX.X.X desktop-app/dist/Certify_Intel_vX.X.X_Setup.exe.blockmap --clobber
gh release upload vX.X.X desktop-app/dist/latest.yml --clobber
```

---

## SYNC PROTOCOL - REQUIRED AFTER EVERY TASK

**MANDATORY: After completing ANY task (no matter how minor), sync local to GitHub:**

```bash
cd "[PROJECT_ROOT]/"
git status
git add -A
git commit -m "[Category] Brief description"
git push origin master
```

| Category | Use For |
|----------|---------|
| `[Fix]` | Bug fixes |
| `[Feature]` | New functionality |
| `[Docs]` | Documentation |
| `[Build]` | Desktop app releases |
| `[Refactor]` | Code restructuring |
| `[Chore]` | Maintenance |

---

## CI/CD PIPELINE

1. **GitHub Actions (On Push)** - Tests run automatically on ALL branches
2. **Auto-Create PR (Feature Branches)** - PR auto-created when tests pass
3. **Auto-Merge** - PRs with `auto-pr` label auto-merge when checks pass

### Direct to Master (Quick Fixes)
```bash
git checkout master && git add -A && git commit -m "[Fix] Quick bug fix" && git push origin master
```

### Local Testing (Optional, Before Push)
```powershell
.\scripts\pre-push-tests.ps1
```

---

## Key Paths

### Local Development
| Purpose | Path |
|---------|------|
| **Main project folder** | `[PROJECT_ROOT]/` |
| **Documentation** | `[PROJECT_ROOT]/docs\` |
| **Backend code** | `[PROJECT_ROOT]/backend\` |
| **Frontend code** | `[PROJECT_ROOT]/frontend\` |
| **Desktop app source** | `[PROJECT_ROOT]/desktop-app\` |
| **Desktop app builds** | `[PROJECT_ROOT]/desktop-app\dist\` |
| **Cleanup script** | `[PROJECT_ROOT]/docs\CLEANUP_OLD_INSTALL.ps1` |

### Installed App Locations (Windows)
| Purpose | Path |
|---------|------|
| **Installed application** | `[INSTALL_DIR]/` |
| **App data/settings** | `[APP_DATA]/` |
| **Updater cache** | `[UPDATER_CACHE]/` |

---

## Troubleshooting: Desktop App Won't Start

If the Desktop App shows "Failed to start the backend server":

**Step 1: Kill all processes**
```powershell
taskkill /F /IM "Certify Intel.exe"
taskkill /F /IM "certify_backend.exe"
netstat -ano | findstr :8000
# If port is in use: taskkill /F /PID <pid_number>
```

**Step 2: Clean old installations**
```powershell
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\Programs\Certify Intel" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "$env:APPDATA\Certify Intel" -ErrorAction SilentlyContinue
```

**Step 3: Reinstall from** `desktop-app/dist/Certify_Intel_v8.0.8_Setup.exe`

---

## Project Overview

**Certify Intel** is a production-ready Competitive Intelligence Platform designed to track, analyze, and counter 74 active competitors in the healthcare technology space.

**Version**: v9.0.0 (current)
**Status**: Web Version Production-Ready | CI/CD Pipeline Active
**Last Updated**: February 15, 2026

### Quick Start
```bash
cd backend
python main.py
```
Then open: http://localhost:8000

**Default Login:** `[YOUR-ADMIN-EMAIL]` / `[YOUR-ADMIN-PASSWORD]`

---

## Current State (v9.0.0 - February 15, 2026)

### Release Status
| Component | Version | Status |
|-----------|---------|--------|
| **Web Version** | v9.0.0 | Production-ready |
| **Desktop App (Windows)** | v9.0.0 | Pending build |
| **Desktop App (macOS)** | N/A | Requires macOS machine to build |
| **CI/CD Pipeline** | - | All checks passing |

### Data Coverage
| Metric | Value |
|--------|-------|
| **Competitors** | 74 active (8 soft-deleted from original 82: 7 duplicates + Apple) |
| **Products** | 789 (100% coverage) |
| **News Articles** | 920 active (1,951 irrelevant archived from 2,871 total) |
| **Data Sources** | 512 (86% verified) |

### Test Suite
- **Backend: 616 passed, 12 skipped** across 29 test files (including E2E workflow suite)
- **Frontend: 55 passed** (Jest unit tests for utils, API, formatters)
- Run backend: `python -m pytest -x --tb=short --ignore=tests/test_all_endpoints.py --ignore=tests/test_e2e.py --ignore=tests/e2e/ --ignore=tests/test_e2e_workflows.py` from `backend/`
- Run frontend: `npm test` from `frontend/`
- `test_all_endpoints.py` and `test_e2e.py` require running server (connection-dependent)

---

## Technology Stack

### Backend
| Component | Technology |
|-----------|------------|
| Framework | FastAPI (Python 3.9+) with Uvicorn |
| Architecture | Modular routers (17 extracted from main.py) + shared dependencies |
| Database | SQLite with SQLAlchemy ORM (26+ tables) |
| Caching | Redis (optional, REDIS_ENABLED) with InMemoryCache fallback |
| AI/ML | Anthropic Claude Opus 4.5 (primary), OpenAI GPT-4o (fallback), Google Gemini 3 Flash (speed/bulk) + Gemini 3 Pro (quality/grounding), DeepSeek V3.2 |
| AI Gateway | LiteLLM proxy (optional, 100+ providers) |
| Local AI | Ollama (optional, $0 cost, Llama 3.1/Mistral/Qwen) |
| Embeddings | OpenAI text-embedding-3-small (default), sentence-transformers all-MiniLM-L6-v2 (optional, free) |
| AI Evaluation | Opik (optional, hallucination/groundedness scoring) |
| Vector Store | PostgreSQL + pgvector (Docker) |
| Orchestration | LangGraph (7-agent StateGraph) |
| Observability | Langfuse v3 (Docker), Prometheus metrics (optional) |
| Rate Limiting | slowapi (configurable per-endpoint limits) |
| Authentication | JWT (15-min access + 7-day refresh tokens), PBKDF2-HMAC-SHA256, optional TOTP MFA |
| Security | CSP, HSTS, X-Frame-Options middleware; Bandit SAST in CI |
| Task Scheduling | APScheduler |
| PDF Generation | ReportLab, WeasyPrint |
| Compression | GZip middleware |

### Frontend
| Component | Technology |
|-----------|------------|
| Architecture | Single Page Application (SPA), ES6 modules in `core/` + `components/` |
| Languages | HTML5, Vanilla JavaScript (ES6+), CSS3 |
| Visualization | Chart.js |
| Export | jsPDF + jspdf-autotable (PDF), SheetJS/xlsx (Excel) |
| Search | Command palette (Ctrl+K) with fuzzy matching |
| Design | Glassmorphism, dark-mode aesthetic, WCAG 2.1 AA accessible |
| Testing | Jest (unit), ESLint, Prettier |
| Features | Offline support (Service Worker), responsive, keyboard navigation |

### Desktop App
| Component | Technology |
|-----------|------------|
| Framework | Electron |
| Build Tools | electron-builder, PyInstaller |
| Platform | Windows (.exe) - macOS requires macOS machine |
| Cache Management | Auto-clear on startup |

### Infrastructure (v9.0.0)
| Component | Technology |
|-----------|------------|
| Container | Docker + docker-compose (prod, monitoring, AI stacks) |
| Reverse Proxy | nginx (static files + API proxy) |
| Monitoring | Prometheus + Grafana dashboards |
| CI/CD | GitHub Actions (backend tests, frontend tests, security scanning) |
| Backups | Automated SQLite backup script with 30-day retention |

---

## Backend Architecture (v9.0.0)

### Modular Structure
main.py was refactored from 18,749 lines to ~16,617 lines by extracting shared modules and routers.

#### Shared Modules
| Module | Purpose |
|--------|---------|
| `backend/dependencies.py` | `get_db()`, `get_current_user()`, `get_async_db()` - shared FastAPI dependencies |
| `backend/constants.py` | `__version__`, `NO_HALLUCINATION_INSTRUCTION`, `KNOWN_TICKERS` |
| `backend/utils/prompt_utils.py` | `resolve_system_prompt()` helper |
| `backend/schemas/` | Pydantic models: `auth.py`, `common.py`, `competitors.py`, `products.py`, `prompts.py` |
| `backend/cache.py` | Redis + InMemoryCache with TTL (gated by REDIS_ENABLED) |
| `backend/metrics.py` | Prometheus counters/histograms with NoOp fallback (gated by METRICS_ENABLED) |
| `backend/mfa.py` | TOTP MFA: `generate_mfa_secret()`, `verify_totp()`, `generate_backup_codes()` |
| `backend/middleware/security.py` | Security headers middleware (CSP, HSTS, X-Frame-Options) |
| `backend/middleware/metrics.py` | HTTP request metrics middleware |
| `backend/services/task_service.py` | Cache-backed AI task service (replaces in-memory dict) |

#### Extracted Routers (17 files, ~7,607 lines)
| Router | Prefix | Endpoints |
|--------|--------|-----------|
| `routers/auth.py` | `/token`, `/api/auth` | Login, register, refresh, MFA, password change |
| `routers/health.py` | `/health`, `/readiness` | Liveness/readiness probes |
| `routers/webhooks.py` | `/api/webhooks` | Webhook CRUD |
| `routers/winloss.py` | `/api/winloss` | Win/loss deal tracking |
| `routers/competitors.py` | `/api/competitors` | Competitor CRUD, relationships |
| `routers/dashboard.py` | `/api/dashboard` | Threats, trends, corporate profile |
| `routers/chat.py` | `/api/chat` | Chat sessions and messages |
| `routers/admin.py` | `/api/admin` | System prompts, audit logs |
| `routers/data_quality.py` | `/api/data-quality` | Quality overview, triangulation |
| `routers/ai_cost.py` | `/api/ai/cost` | AI cost analytics (NEW) |
| `routers/agents.py` | `/api/agents` | LangGraph agent endpoints (existing) |

**Note:** Some endpoints remain in main.py (discovery, sales-marketing, news, verification, scraping). These can be extracted in future refactoring.

## Frontend Architecture (v9.0.0)

### ES6 Module Structure
Frontend was modularized with ES6 modules alongside the existing `app_v2.js` monolith:

```
frontend/app.js                    - Module entry point (imports core + components)
frontend/core/api.js               - fetchAPI, auth token handling
frontend/core/utils.js             - escapeHtml, formatters, debounce
frontend/core/state.js             - Global polling state variables
frontend/core/navigation.js        - showPage, routing
frontend/core/keyboard.js          - Keyboard shortcuts, focus trap, Ctrl+K/Escape
frontend/core/export.js            - PDFExporter + ExcelExporter classes
frontend/components/toast.js       - Toast notifications
frontend/components/modals.js      - Modal create/show/hide/focus-trap
frontend/components/chat.js        - Chat widget
frontend/components/command_palette.js - Ctrl+K global search across pages/competitors/actions
frontend/components/notification_center.js - Bell icon + notification panel
```

**Backward compatibility:** `app_v2.js` still works standalone. ES6 modules export to `window.*` for onclick handlers. Both can coexist.

### Frontend Testing
```
frontend/package.json              - Jest + ESLint + Prettier config
frontend/jest.config.js            - jsdom test environment
frontend/testable-utils.js         - Testable utility exports
frontend/__tests__/utils.test.js   - escapeHtml, formatters (25 tests)
frontend/__tests__/api.test.js     - fetchAPI, auth handling (15 tests)
frontend/__tests__/formatters.test.js - Date/number formatting (15 tests)
```

### WCAG 2.1 AA Accessibility
- Skip-to-content link on every page
- ARIA landmarks (`role="main"`, `role="navigation"`, `aria-label`)
- Focus-visible indicators on all interactive elements
- `.sr-only` class for screen reader text
- Keyboard navigation: Ctrl+1-9 pages, Ctrl+K search, Escape close modals

---

## AI Agents (All Operational)

| Agent | File |
|-------|------|
| Dashboard | `backend/agents/dashboard_agent.py` |
| Discovery | `backend/agents/discovery_agent.py` |
| Battlecard | `backend/agents/battlecard_agent.py` |
| News | `backend/agents/news_agent.py` |
| Analytics | `backend/agents/analytics_agent.py` |
| Validation | `backend/agents/validation_agent.py` |
| Records | `backend/agents/records_agent.py` |
| Orchestrator | `backend/agents/orchestrator.py` |
| Citation Validator | `backend/agents/citation_validator.py` |

---

## Database Models (26+ Tables)

### Core Models
| Model | Purpose |
|-------|---------|
| `Competitor` | Main entity (115+ fields including dimensions, social, financial) |
| `ChangeLog` | All data changes with old/new values |
| `ActivityLog` | User activity audit trail |
| `DataSource` | Data provenance & confidence scoring |
| `RefreshSession` | Scrape session history |

### Sales & Marketing
| Model | Purpose |
|-------|---------|
| `CompetitorDimensionHistory` | Dimension score history |
| `Battlecard` | Generated sales battlecards |
| `TalkingPoint` | Sales talking points |
| `DimensionNewsTag` | News tagged by dimension |

### Data Quality
| Model | Purpose |
|-------|---------|
| `CompetitorProduct` | Product-level tracking |
| `ProductPricingTier` | Tiered pricing models |
| `ProductFeatureMatrix` | Feature comparison |
| `CustomerCountEstimate` | Customer count with verification |

### User & Auth
| Model | Purpose |
|-------|---------|
| `User` | User accounts with roles (+ `mfa_enabled`, `mfa_secret`, `mfa_backup_codes` columns) |
| `UserSettings` | Per-user preferences |
| `UserSavedPrompt` | Saved AI prompts |
| `SystemPrompt` | System-level AI prompts (41 seeded, 6 categories, user-overridable) |
| `RefreshToken` | JWT refresh tokens (token, user_id, expires_at, revoked) - **v9.0.0** |

### Chat & AI
| Model | Purpose |
|-------|---------|
| `ChatSession` | Persistent AI chat sessions (user_id, page_context, competitor_id, title) |
| `ChatMessage` | Individual chat messages (session_id, role, content, metadata_json) |

### Intelligence
| Model | Purpose |
|-------|---------|
| `WinLossDeal` | Competitive deal tracking |
| `KnowledgeBaseItem` | Internal knowledge base |
| `WebhookConfig` | Webhook integrations |
| `DiscoveryProfile` | Saved discovery scout qualification criteria |

---

## Key API Endpoints

### Authentication (v9.0.0 - refresh tokens + MFA)
```
POST /token                          # Login
POST /api/auth/register              # Register new user
GET  /api/auth/me                    # Current user info
POST /api/auth/refresh               # Refresh access token (7-day refresh tokens)
POST /api/auth/logout                # Revoke refresh token
POST /api/auth/change-password       # Change password (requires old password)
POST /api/auth/mfa/enable            # Enable TOTP MFA (returns QR code URI)
POST /api/auth/mfa/verify            # Verify TOTP code
POST /api/auth/mfa/disable           # Disable MFA
GET  /api/auth/mfa/backup-codes      # Get backup recovery codes
```

### Competitors
```
GET    /api/competitors              # List all
POST   /api/competitors              # Create new
GET    /api/competitors/{id}         # Get details
PUT    /api/competitors/{id}         # Update
DELETE /api/competitors/{id}         # Delete
```

### AI Agents (LangGraph)
```
POST /api/agents/dashboard           # Dashboard agent query
POST /api/agents/discovery           # Discovery agent
POST /api/agents/battlecard          # Battlecard generation
POST /api/agents/news                # News analysis
POST /api/agents/analytics           # Analytics query
```

### Discovery Scout
```
POST /api/discovery/run-ai           # Run 4-stage AI discovery pipeline
GET  /api/discovery/profiles         # List saved profiles
POST /api/discovery/profiles         # Create profile
GET  /api/discovery/default-prompt   # Get global default prompt
PUT  /api/discovery/default-prompt   # Set global default prompt (admin)
GET  /api/discovery/provider-status  # AI provider diagnostic
GET  /api/discovery/progress/{id}    # Poll discovery progress
POST /api/discovery/summarize        # Generate executive summary
POST /api/discovery/send-to-battlecard  # Send results to battlecards
POST /api/discovery/send-to-comparison  # Send results to comparison
```

### Sales & Marketing (30+ endpoints)
```
GET  /api/sales-marketing/dimensions
GET  /api/sales-marketing/competitors/{id}/dimensions
POST /api/sales-marketing/competitors/{id}/dimensions/ai-suggest  # ?prompt_key= supported
POST /api/sales-marketing/battlecards/generate
POST /api/sales-marketing/compare/dimensions
```

### Data Quality
```
GET  /api/data-quality/overview
GET  /api/data-quality/low-confidence
POST /api/triangulate/{competitor_id}
```

### Prompt Management
```
GET  /api/admin/system-prompts              # List prompts (optionally by ?category=)
GET  /api/admin/system-prompts/categories   # List all prompt categories
GET  /api/admin/system-prompts/{key}        # Get specific prompt by key
POST /api/admin/system-prompts              # Create/update user prompt override
```

### Chat Persistence
```
GET    /api/chat/sessions              # List user's chat sessions
POST   /api/chat/sessions              # Create new chat session
GET    /api/chat/sessions/{id}         # Get session with messages
PUT    /api/chat/sessions/{id}         # Update session (title, is_active)
DELETE /api/chat/sessions/{id}         # Delete session
GET    /api/chat/sessions/{id}/messages # Get session messages
```

### Source Verification
```
POST /api/sources/batch                          # Batch source lookup
GET  /api/competitors/{id}/verification-summary   # Verification percentage
GET  /api/competitors/{id}/source-links           # Source URLs for fields
```

### Background AI Tasks
```
POST /api/ai/tasks                   # Create background AI task
GET  /api/ai/tasks/{task_id}         # Get task status/result
PUT  /api/ai/tasks/{task_id}/dismiss # Dismiss completed task notification
```

### Data Verification
```
POST /api/verification/run-all          # Batch verify all competitors (background)
GET  /api/verification/progress         # Poll verification progress + ETA
POST /api/verification/run/{id}         # Verify single competitor
```

### Dashboard
```
GET  /api/dashboard/top-threats      # Top 5 competitive threats (dynamic)
GET  /api/dashboard/threat-trends    # Threat level changes over 90 days (weekly aggregates)
GET  /api/corporate-profile          # Dynamic counts (competitors, products, sources, news)
```

### Analytics (v8.2.0)
```
GET  /api/analytics/market-quadrant  # Market position bubble chart (strength vs momentum)
```

### Sales Playbook (v8.2.0)
```
POST /api/sales-marketing/playbook/generate  # AI-generated sales playbook with deal context
```

### Observability (v8.2.0)
```
GET  /api/observability/status       # Langfuse health and connection status
```

### Health & Readiness (v8.3.1)
```
GET  /health                         # Liveness probe (DB ping, version)
GET  /readiness                      # Full dependency check (DB, AI providers, Langfuse, Ollama, LiteLLM)
```

### News Feed
```
GET  /api/news-feed
GET  /api/competitors/{id}/news
POST /api/news-feed/cleanup-irrelevant  # Archive irrelevant articles (non-healthcare noise)
```

### AI Cost Analytics (v9.0.0)
```
GET  /api/ai/cost/summary            # Cost breakdown by provider/model
GET  /api/ai/cost/daily              # Daily cost time series
GET  /api/ai/cost/by-feature         # Cost by feature (discovery, battlecards, etc.)
```

### Audit Logs (v9.0.0)
```
GET  /api/audit/logs                 # Searchable activity log (?user_id=&action=&start_date=&end_date=)
```

### Competitor Relationships (v9.0.0)
```
POST /api/competitors/{id}/relationships  # Add parent/subsidiary/partner relationship
GET  /api/competitors/{id}/relationships  # Get competitor relationships
```

### Prometheus Metrics (v9.0.0)
```
GET  /metrics                        # Prometheus scrape endpoint (when METRICS_ENABLED=true)
```

---

## Configuration

Copy `backend/.env.example` to `backend/.env`:

```env
# Required
SECRET_KEY=your-secret-key-here

# AI Features - Anthropic Claude (PRIMARY for complex tasks)
ANTHROPIC_API_KEY=your-anthropic-key

# AI Features - OpenAI (fallback)
OPENAI_API_KEY=your-openai-key
OPENAI_MODEL=gpt-4.1

# AI Features - Gemini (two-tier: Flash for speed, Pro for quality)
GOOGLE_AI_API_KEY=your-gemini-key
GOOGLE_AI_MODEL=gemini-3-flash-preview
# Gemini model routing:
#   gemini-3-flash-preview  → chat, summarization, RAG, bulk extraction, classification
#   gemini-3-pro-preview    → grounded search, deep research, complex analysis, executive summaries

# AI Features - DeepSeek (optional, cheap bulk)
DEEPSEEK_API_KEY=your-deepseek-key

# AI Provider Routing
AI_PROVIDER=hybrid
AI_BULK_TASKS=gemini
AI_QUALITY_TASKS=anthropic
AI_FALLBACK_ENABLED=true
```

---

## Frontend Pages (11)

| Page | Key Features |
|------|--------------|
| Dashboard | AI summary, threat stats, configurable date range picker, configurable threat count, PDF export |
| Competitors | CRUD, grid/list view toggle, sort dropdown, advanced filter panel, bulk actions, CSV import |
| Discovery Scout | AI-driven competitor discovery with 4-stage pipeline, collapsible criteria, bulk import, history |
| Battlecards | Sales-ready one-pagers with AI verification, PDF export, version history |
| Comparisons | 2-4 competitor side-by-side, feature matrix |
| Sales & Marketing | 9-dimension scoring, radar chart, talking points, PDF playbook export |
| News Feed | Real-time news, sentiment trend chart, email alerts, mark read/unread |
| Analytics | Market map, win/loss tracking UI, deal modal, win rate chart |
| Records | Data records management |
| Validation | Data validation workflows |
| Settings | User preferences, API keys, AI provider status, password change, MFA setup, audit log viewer |

### Cross-Cutting Features (v9.0.0)
- **Command Palette** (Ctrl+K): Search across pages, competitors, actions with fuzzy matching
- **PDF/Excel Export**: Available on Dashboard, Competitors, Battlecards, Analytics, News, Data Quality
- **Bulk Actions**: Multi-select with toolbar for export, delete, update threat level
- **Notification Center**: Bell icon with unread badge, real-time via WebSocket

**Version Display**: Every release must show `v{major}.{minor}.{patch}` below the sidebar logo (10-12px, white/light gray).

---

## Key Lessons Learned

### Build & Release
1. **Electron + PyInstaller cache aggressively** - Must clear ALL caches before building (Step 4)
2. **Always verify built output** - Check the BUILT app, not just source files (Step 9)
3. **Version must be bumped in 6 files BEFORE building** - Electron reads package.json at build time
4. **Sync frontend<->desktop-app BEFORE building** - Forgetting this = old frontend in build
5. **Verify all 3 release files exist** - Setup.exe + blockmap + latest.yml ALL required for auto-updates
6. **PyInstaller spec must handle missing files gracefully** - CI lacks certify_intel.db; use `os.path.exists()`
7. **PowerShell `Copy-Item` more reliable than `cmd /c copy`** on Windows

### Backend
8. **Always `await` async methods** - Missing `await` silently returns coroutine objects (#1 bug category)
9. **Check ORM column names match model attributes** - `content` vs `content_text`, always verify
10. **SystemPrompt model has NO `is_active` column** - don't filter on it
11. **Use `get_ai_router()` singleton** - not `AIRouter()` per request (memory leak)
12. **Wrap SessionLocal() in try/finally** - Or use `Depends(get_db)` to prevent connection leaks
13. **Never return str(e) in HTTP responses** - Use generic error messages, log details server-side
14. **python-jose uses `jwt.JWTError`** not `jwt.InvalidTokenError`
15. **_ai_tasks dict must auto-prune** - Prune completed tasks after 1 hour to prevent memory leaks
16. **All AI background tasks need asyncio.wait_for() timeouts** - 45s for most, 120s for pipelines
17. **Competitor.threat_level is a String** ("High"/"Medium"/"Low"), never compare with integers
18. **Battlecard fields: Competitor has NO dim_product_score etc.** - Use getattr() with defaults
19. **ThreadPoolExecutor workers need own DB session + event loop** - SQLite not thread-safe
20. **Gemini prompts must request JSON-only output** - Without it, Gemini wraps in ```json blocks
21. **Background verification needs 1s delay between Gemini calls** - Rate limit prevention
22. **Use `fetch_news_async()` not `fetch_news()`** - Async uses `asyncio.gather()` (~8s vs ~50s/competitor)
23. **Gemini model IDs are `gemini-3-flash-preview` and `gemini-3-pro-preview`** - `gemini-2.0-flash` deprecated Mar 31 2026. Flash for speed/cost tasks, Pro for quality/grounding tasks. Two-tier routing in `TASK_ROUTING` dict.
24. **When upgrading model IDs, update ALL test files too** - Tests assert on model names in cost calculations, routing assertions, and mock return values. Search all `tests/` for old model strings.

### Frontend
23. **Run `node -c` syntax check on app_v2.js after EVERY edit** - A single missing `}` broke all 11 pages
24. **createChatWidget endpoint must NOT include API_BASE** - `fetchAPI()` already prepends it
25. **Always use escapeHtml() for innerHTML with dynamic content** - Prevents XSS
26. **window.onerror must return false** - Returning `true` suppresses ALL errors silently
27. **Every showPage() case needs try/catch** - Error boundaries prevent blank pages
28. **Frontend modals are dynamically created by JS** - Don't add HTML for missing modal IDs
29. **fetchAPI without `{ silent: true }` shows error toast** - Use silent flag for non-critical fetches
30. **Chat by-context API returns `{session: {...}}`** - Must unwrap the session key
31. **SPA navigation destroys DOM but not global JS state** - Use globals for long-running polling
32. **Short generic company names need healthcare context in search** - Use `"Name" healthcare OR "domain"` pattern, not just appending domain
33. **NO_HALLUCINATION_INSTRUCTION must be prepended to all AI system prompts**
34. **All background operations need global polling state** - `setInterval` inside `Promise` dies on SPA navigation; use global flags + `while` loop pattern (see news fetch, discovery, refresh)
35. **Resume functions must check DOM exists before updating** - User may be on another page; guard all `getElementById` calls
36. **Google News RSS returns garbage for generic single-word names** - Must add "healthcare" context + quote the name in search queries
37. **News articles need post-fetch relevance filtering** - `_filter_irrelevant_articles()` in news_monitor.py
38. **Single-word generic names need domain-based filtering** - Healthcare keywords alone catch false positives (e.g., "healthcare access" != "Access" the company). For single-word names, require the company's domain (e.g., "accessefm") to appear in the article. Pass `real_name` and `website` through `fetch_news_async()` to the filter.
39. **Search term != company name in filter** - `fetch_news_async()` receives the full search term (e.g., `'"Access" healthcare OR "accessefm"'`), not the raw company name. The filter must use the original name via `real_name` parameter.
40. **Discovery results must use single renderer** - Never render results in two places (list + grid). Use `renderDiscoveryResults()` for both fresh and cached results. The old `renderDiscoveredGrid()` / `discoveredGrid` div was removed in v8.1.0.
41. **Normalize score fields on backend before returning** - Discovery candidates may have `qualification_score`, `relevance_score`, or `score`. Backend `_normalize_candidate_scores()` adds `match_score` to every candidate. Frontend `getMatchScore()` handles fallback chain.
42. **Collapsible panels need both summary and expanded state** - Use `#criteriaSummaryBar` (collapsed) and `#criteriaExpandedContent` (expanded). Auto-collapse when results exist, auto-expand when cleared.
43. **Discovery empty state is a separate div** - `#discoveryEmptyState` (not inside `discoveryResults`). Must be shown/hidden independently from the results panel.
44. **Chart.js Canvas 2D cannot resolve CSS variables** - Never use `var(--text-primary)` in Chart.js configs. Use hardcoded hex values (#e2e8f0, #94a3b8) matching the dark theme.
45. **Backend API response shapes must match frontend expectations** - When building backend+frontend in parallel, verify field names match. Common mismatches: `x/y/size` vs `market_strength/growth_momentum/company_size`, nested `datasets.high` vs flat `high`.
46. **Optional integrations should default to OFF** - Use env var checks (VERTEX_AI_ENABLED, LANGFUSE_ENABLED) defaulting to false. Zero overhead when disabled.
47. **`_resolve_system_prompt()` helper for prompt_key** - Reusable helper at main.py line ~209. Checks user-specific prompt first, then global, then fallback default.
48. **Service workers cache aggressively** - SW can serve stale JS/CSS even after deploy. Use CACHE_VERSION checks + auto-purge on mismatch. The `/clear-cache` endpoint provides manual cache reset. Inline cache-purge script in `index.html` runs before SW can intercept.
49. **DimensionAnalyzer prompt_key uses _resolve_prompt() not main.py import** - To avoid circular imports, DimensionAnalyzer has its own `_resolve_prompt()` static method that queries SystemPrompt directly from database.py. Default prompt keys: `dimension_classification`, `dimension_scoring`.
50. **escapeHtml() is available globally from app_v2.js** - All lazily-loaded JS modules (enhanced_analytics.js, sales_marketing.js, etc.) can use `escapeHtml()` since app_v2.js loads first.
51. **Langfuse v3 requires 6 Docker services** - Web, Worker, ClickHouse, Redis, MinIO, PostgreSQL. The v2 compose (just web+postgres) fails with `CLICKHOUSE_URL is not configured`. Each batch event needs top-level `id` and `timestamp` fields (not just inside `body`).
52. **Langfuse SDK broken on Python 3.14** - `pydantic.v1` is incompatible with Python 3.14. Use `LangfuseHTTPClient` fallback in `observability.py` that posts to `/api/public/ingestion` REST API directly. `get_langfuse()` tries SDK first, falls back automatically.
53. **BattlecardAgent needs db_session for BattlecardGenerator** - `BattlecardGenerator.__init__()` requires `db_session`. Pass it through: `BattlecardAgent(db_session=db)` → `BattlecardGenerator(self.db_session)`. Both `routers/agents.py` and `orchestrator.py` must create+close SessionLocal.
54. **url_quality field must be mapped before sending to frontend** - Backend stores `url_status` as "verified"/"pending"/"broken" but frontend expects "exact_page"/"page_level"/"homepage_only"/"broken". Use `_map_url_quality()` helper in main.py to translate.
55. **Phase 1 URL refinement sets "pending" not "verified"** - Phase 1 finds page URLs. Phase 2 does content matching and sets final status. Setting "verified" in Phase 1 causes quality-summary to over-count exact_page.
56. **New AI providers all default to OFF** - `LITELLM_ENABLED`, `OLLAMA_ENABLED`, `USE_LOCAL_EMBEDDINGS`, `OPIK_ENABLED` all default false. Zero overhead when disabled. Same env-var gating pattern as Vertex AI.
57. **Rate limiting uses slowapi** - `RATE_LIMIT_ENABLED=true` by default. Uses `rate_limit()` decorator helper that no-ops when limiter is None (package not installed).
58. **Health/readiness endpoints are unauthenticated** - `/health` and `/readiness` don't require JWT. `/health` is a quick DB ping, `/readiness` checks all dependencies.

### v9.0.0 Architecture
59. **Router extraction: import from dependencies.py not main.py** - Extracted routers import `get_db`, `get_current_user` from `backend/dependencies.py`. Never import these from `main.py` (circular import risk).
60. **Redis cache defaults to InMemoryCache** - When `REDIS_ENABLED=false` (default), `get_cache()` returns `InMemoryCache` with TTL + max 1000 entries. Zero Redis dependency required.
61. **Prometheus metrics use NoOp pattern** - When `prometheus_client` not installed or `METRICS_ENABLED=false`, all metric operations are no-ops. Import `track_request()` etc. safely from `metrics.py`.
62. **ES6 modules must export to window.\*** - Frontend ES6 modules in `core/` and `components/` must attach functions to `window` for `onclick` handlers in HTML strings to work. Pure ES6 import/export only works between modules.
63. **MFA backup codes are hashed** - `mfa.py` stores bcrypt-hashed backup codes. Each code is single-use. Generate 10 codes on MFA enable.
64. **conftest.py must set SECRET_KEY before main.py imports** - Test fixtures that create `TestClient(app)` trigger main.py lifespan which checks `SECRET_KEY`. Set `os.environ.setdefault('SECRET_KEY', ...)` early in conftest.py.
65. **Security headers middleware must check SECURITY_HEADERS_ENABLED** - Middleware is always registered but checks env var per-request to allow runtime toggle.
66. **Refresh token rotation: invalidate old on use** - `POST /api/auth/refresh` revokes the used refresh token and issues a new pair (access + refresh). Frontend must store the new refresh token.

---

## Configuration (v9.0.0 Features)

All new features default to OFF for zero overhead:

```env
# AI Gateway
LITELLM_ENABLED=false              # Set true + run LiteLLM Docker
LITELLM_PROXY_URL=http://localhost:4000

# Local AI
OLLAMA_ENABLED=false               # Set true + run Ollama
OLLAMA_URL=http://localhost:11434
OLLAMA_DEFAULT_MODEL=llama3.1:8b

# Free Embeddings
USE_LOCAL_EMBEDDINGS=false         # Set true for free sentence-transformers

# AI Evaluation
OPIK_ENABLED=false                 # Set true for hallucination detection

# Infrastructure
RATE_LIMIT_ENABLED=true            # Rate limiting on by default
JSON_LOGGING=false                 # Set true for structured JSON logs

# v9.0.0 Security & Infrastructure
SECURITY_HEADERS_ENABLED=true      # CSP, HSTS, X-Frame-Options middleware
REDIS_ENABLED=false                # Set true + run Redis for caching
REDIS_URL=redis://localhost:6379/0
METRICS_ENABLED=false              # Set true for Prometheus /metrics endpoint
REFRESH_TOKEN_EXPIRE_DAYS=7        # JWT refresh token lifetime
ACCESS_TOKEN_EXPIRE_MINUTES=15     # JWT access token lifetime (was 24h)
```

---

## Version History (Feb 6+)

| Version | Date | Key Changes |
|---------|------|-------------|
| **v9.0.0** | Feb 15 | Major architecture overhaul. **Backend:** Extracted 17 routers from main.py (18,749 → 16,617 lines), shared dependencies module, Pydantic schemas, Redis caching with InMemoryCache fallback, Prometheus metrics, GZip compression, security headers middleware (CSP/HSTS/X-Frame-Options), JWT refresh tokens (15-min access + 7-day refresh), TOTP MFA with backup codes, AI cost analytics endpoints, audit log API, competitor relationships. **Frontend:** ES6 module system (6 core + 5 component modules), Jest test suite (55 tests), WCAG 2.1 AA accessibility (skip-to-content, ARIA, keyboard nav), command palette (Ctrl+K), PDF/Excel export engine, notification center, bulk actions framework. Page enhancements: dashboard date range picker, competitor sort/filter/CSV import, battlecard PDF export/history, news sentiment trends, analytics win/loss UI, settings MFA/password/audit. **Infrastructure:** Docker production stack (nginx + Redis), Prometheus + Grafana monitoring, Bandit SAST CI, frontend test CI, automated backup script. 616 backend tests + 55 frontend tests passing. |
| **v8.3.1** | Feb 14 | Deep link bug fixes + enterprise-grade free OSS upgrades. Bug fixes: url_quality field mapping mismatch (frontend expected exact_page/page_level/homepage_only, backend sent verified/pending/broken), Phase 1 pipeline prematurely marking "verified" before content matching, empty source quality dashboard, re-run button hidden. New providers: LiteLLM unified AI gateway (100+ LLM providers, cost tracking), Ollama local LLM ($0 cost, Llama 3.1/Mistral/Qwen), sentence-transformers free embeddings (all-MiniLM-L6-v2, 384-dim), Opik AI evaluation (hallucination/groundedness scoring). Infrastructure: /health and /readiness endpoints (Kubernetes-ready), slowapi rate limiting, structured JSON logging with correlation IDs, docker-compose.ai.yml for LiteLLM+Ollama. Frontend: ::target-text CSS styling, AI provider status panel in Settings, Firefox 131+ Text Fragment support. All new features default OFF (zero overhead). 543 tests passing (68 new). |
| **v8.3.0** | Feb 14 | Source quality & enterprise provider integration + content-aware deep link highlighting. |
| **v8.2.0** | Feb 12-13 | Enhancement sprint + client handoff prep: 20 XSS fixes total (5 initial + 15 in enhanced_analytics.js/sales_marketing.js), console.log cleanup (78 removed), Chart.js memory leak fixes, backend error sanitization (6 str(e) leaks), error boundaries on all pages. New features: threat trend chart (Dashboard), market quadrant chart (Analytics), news subscription management UI, sales playbook generator, prompt_key on all AI endpoints + DimensionAnalyzer. Optional integrations: Vertex AI provider, **Langfuse v3 observability activated** (6-service Docker stack, Python 3.14-compatible HTTP client fallback). PostgreSQL migration tooling (Docker + script). Service worker cache purge mechanism. E2E test suite (88 workflow + 14 live API tests). BattlecardGenerator db_session bug fix. 43 system prompts seeded. 442 tests passing. |
| **v8.1.0** | Feb 11 | Discovery Scout UI/UX overhaul: removed duplicate grid, unified results renderer, score normalization (backend + frontend), collapsible criteria panel, info box moved to top, Advanced Options section, dominant Start button, enhanced empty state. 368 tests passing. |
| **v8.0.9** | Feb 11 | Gemini model upgrade: `gemini-2.0-flash` (deprecated) replaced with `gemini-3-flash-preview` (speed) + `gemini-3-pro-preview` (quality). Two-tier routing across 21 files. All 368 tests passing. |
| **v8.0.8** | Feb 11 | News relevance filter: healthcare context queries, post-fetch filtering, domain-based filtering for generic names, cleanup endpoint. Archived 1,951 irrelevant articles. Soft-deleted Apple. AI result persistence (discovery, battlecards, dashboard summary). |
| **v8.0.7** | Feb 11 | Tab-resilient background operations: discovery, refresh, verification survive navigation + persistent results |
| **v8.0.6** | Feb 11 | Generic company name disambiguation + tab-resilient news fetch polling |
| **v8.0.5** | Feb 10 | Parallel news fetch (ThreadPoolExecutor 10 workers), AI classification (Gemini sentiment + event_type), 15min->1min for 75 competitors |
| **v8.0.4** | Feb 10 | AI data verification agent (Gemini grounded search), clickable source links, batch verification with progress |
| **v8.0.3** | Feb 9 | Discovery Scout overhaul: real progress, background mode, AI summary, battlecard/comparison integration |
| **v8.0.2** | Feb 9 | Chat widget doubled-URL fix, jwt.JWTError fix, prompt editor fix |
| **v8.0.1** | Feb 8 | Post-demo emergency stability: DB session leaks, AI router memory leak, desktop watchdog, XSS hardening, error boundaries |
| **v8.0.0** | Feb 8 | Client delivery: 12 new endpoints, 9 bug fixes, desktop app rebuilt |
| **v7.2.0** | Feb 7 | Major overhaul: dashboard fake data elimination, conversational AI on 9 pages, source verification dots |
| **v7.1.6** | Feb 7 | Production demo release: 16 bug fixes, full build protocol |
| **v7.1.3** | Feb 7 | Prompt selector feature: 41 AI prompts, SystemPrompt model |
| **v7.1.2** | Feb 6 | Comprehensive AI audit: 52 bugs fixed across 26 files |

> Versions before v7.1.2 (Feb 6) archived. Project history: v7.0.0 (Feb 2) introduced LangGraph + pgvector + 7 agents. Early builds (v2-v6) and data population (82 competitors, 789 products) completed in Jan 2026.

---

## Next Steps / Remaining Items

| # | Item | Priority | Notes |
|---|------|----------|-------|
| 1 | ~~Cloud deployment (Docker + nginx)~~ | ~~Medium~~ | **DONE** - docker-compose.prod.yml + nginx config ready. Needs server provisioning + SSL cert. |
| 2 | macOS desktop app build | Low | Requires macOS machine with Xcode |
| 3 | ~~End-to-end integration testing with live API keys~~ | ~~Medium~~ | **DONE** - 11/14 live E2E tests passing. |
| 4 | Activate Vertex AI provider | Low | Code wired, needs GCP credentials (VERTEX_AI_ENABLED=true) |
| 5 | ~~Activate Langfuse observability~~ | ~~Low~~ | **DONE** - Langfuse v3 running locally. |
| 6 | Continue main.py router extraction | Medium | ~16,617 lines remain - discovery, sales-marketing, news, verification, scraping endpoints still inline |
| 7 | Alembic migration system | Medium | Replace manual ALTER TABLE in init_db() with proper migrations |
| 8 | Frontend app_v2.js page splitting | Medium | 24,239 lines - extract page logic into `frontend/pages/*.js` modules |
| 9 | Celery task queue | Low | Replace in-process asyncio for heavy tasks (discovery, verification, news) |
| 10 | Load testing (k6) | Low | k6 baseline: 50 concurrent users, P95 < 500ms target |
| 11 | Desktop app v9.0.0 build | Medium | Needs full 11-step build protocol with new frontend modules |

---

**Last Updated**: February 15, 2026 (Session 94 - v9.0.0 architecture overhaul: backend router extraction, frontend ES6 modules, security hardening, feature enhancements, Docker/CI infrastructure)
**Current Version**: v9.0.0
