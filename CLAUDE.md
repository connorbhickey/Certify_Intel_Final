# Certify Intel v10.0.0 - Project Instructions

## Current Focus
**v10.0.0** - Desktop app stable release for Kevon (CEO of Certify Health). Fixed infinite reload loop caused by cache version mismatch between index.html and app_v2.js. Login screen pre-populates `admin@certifyhealth.com`.

---

## MANDATORY INSTRUCTIONS FOR ALL AI AGENTS

### File Save Locations

| File Type | Save Location |
|-----------|---------------|
| Documentation (plans, notes) | `docs/` |
| Archived docs | `docs/Archived_Docs/` |
| Code files | `backend/`, `frontend/`, `desktop-app/` |
| Desktop app builds | `desktop-app/dist/` |

**NEVER save files to hidden folders** like `.claude-worktrees` or `.claude/plans`.

---

### Desktop App Build Protocol (11 Steps)

**MANDATORY: Follow ALL steps before building/installing ANY desktop app version.**

#### Step 1: Bump Version in ALL 6 Files
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
Copy-Item "frontend\app_v2.js" "desktop-app\frontend\app_v2.js" -Force
Copy-Item "frontend\styles.css" "desktop-app\frontend\styles.css" -Force
Copy-Item "frontend\index.html" "desktop-app\frontend\index.html" -Force
Copy-Item "frontend\app.js" "desktop-app\frontend\app.js" -Force
Copy-Item -Recurse "frontend\core" "desktop-app\frontend\core" -Force
Copy-Item -Recurse "frontend\components" "desktop-app\frontend\components" -Force
fc /b frontend\app_v2.js desktop-app\frontend\app_v2.js
```

#### Step 3: Run Cleanup Script
```powershell
powershell -ExecutionPolicy Bypass -File "[PROJECT_ROOT]/docs\CLEANUP_OLD_INSTALL.ps1"
```

#### Step 4: Clear ALL Build Caches (Prevents Stale Code)
```powershell
Remove-Item -Recurse -Force "[PROJECT_ROOT]/desktop-app\dist" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "[PROJECT_ROOT]/desktop-app\node_modules\.cache" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\electron-builder" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "[PROJECT_ROOT]/backend\dist" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "[PROJECT_ROOT]/backend\build" -ErrorAction SilentlyContinue
```

#### Step 5: Verify Source Files Have Your Fix
```powershell
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
ls desktop-app\dist\Certify_Intel_v*_Setup.exe
ls desktop-app\dist\Certify_Intel_v*_Setup.exe.blockmap
ls desktop-app\dist\latest.yml
```

#### Step 10: Installer Location
```
[PROJECT_ROOT]/desktop-app\dist\Certify_Intel_vX.X.X_Setup.exe
```

#### Step 11: Commit, Push, Update GitHub Release
```bash
git add -A && git commit -m "[Build] vX.X.X desktop app" && git push origin master
git tag -f vX.X.X HEAD && git push origin vX.X.X --force
gh release edit vX.X.X --notes "..."
gh release upload vX.X.X desktop-app/dist/Certify_Intel_vX.X.X_Setup.exe --clobber
gh release upload vX.X.X desktop-app/dist/Certify_Intel_vX.X.X_Setup.exe.blockmap --clobber
gh release upload vX.X.X desktop-app/dist/latest.yml --clobber
```

---

## SYNC PROTOCOL - REQUIRED AFTER EVERY TASK

```bash
git add -A && git commit -m "[Category] Brief description" && git push origin master
```

Categories: `[Fix]` `[Feature]` `[Docs]` `[Build]` `[Refactor]` `[Chore]`

---

## Quick Start

```bash
cd backend && python main.py
```
Open: http://localhost:8000 — Login: `admin@certifyhealth.com` / `CertifyIntel2026!`

### Test Commands
- Backend: `python -m pytest -x --tb=short --ignore=tests/test_all_endpoints.py --ignore=tests/test_e2e.py --ignore=tests/e2e/ --ignore=tests/test_e2e_workflows.py` (from `backend/`)
- Frontend: `npm test` (from `frontend/`)
- Backend: 639 passed, 24 skipped | Frontend: 55 passed

---

## Project Overview

**Certify Intel** — Competitive Intelligence Platform tracking 74 healthcare tech competitors. Built with FastAPI + SQLite backend, vanilla JS SPA frontend, Electron desktop app.

**Stack**: FastAPI/Uvicorn, SQLAlchemy ORM (26+ tables), JWT auth (15-min access + 7-day refresh), TOTP MFA, multi-AI (Claude primary, GPT-4o fallback, Gemini Flash/Pro, DeepSeek), LangGraph 7-agent orchestration, Chart.js, jsPDF, Electron + PyInstaller.

**Data**: 74 competitors, 789 products, 920 news articles, 512 data sources.

---

## Architecture (Key Files)

### Backend
- `backend/main.py` (~16,617 lines) — Main app, many endpoints still inline
- `backend/dependencies.py` — `get_db()`, `get_current_user()` (routers import from HERE, not main.py)
- `backend/constants.py` — `__version__`, `NO_HALLUCINATION_INSTRUCTION`
- `backend/routers/` — 17 extracted routers (auth, health, competitors, dashboard, chat, admin, etc.)
- `backend/agents/` — 9 LangGraph agents (dashboard, discovery, battlecard, news, analytics, validation, records, orchestrator, citation)
- `backend/schemas/` — Pydantic models

### Frontend
- `frontend/app_v2.js` (24,239 lines) — Monolith SPA, works standalone
- `frontend/core/` — ES6 modules (api, utils, state, navigation, keyboard, export)
- `frontend/components/` — ES6 modules (toast, modals, chat, command_palette, notification_center)
- `frontend/index.html` — Entry point with inline cache-purge script

### Desktop App
- `desktop-app/package.json` — Electron config + version
- `desktop-app/frontend/` — Synced copy of frontend (Step 2)
- `desktop-app/backend-bundle/` — PyInstaller exe + db + .env

---

## Configuration

Copy `backend/.env.example` to `backend/.env`:
```env
SECRET_KEY=your-secret-key-here
ANTHROPIC_API_KEY=your-anthropic-key
OPENAI_API_KEY=your-openai-key
GOOGLE_AI_API_KEY=your-gemini-key
AI_PROVIDER=hybrid
AI_FALLBACK_ENABLED=true
# Optional (all default OFF): LITELLM_ENABLED, OLLAMA_ENABLED, USE_LOCAL_EMBEDDINGS,
# OPIK_ENABLED, REDIS_ENABLED, METRICS_ENABLED, JSON_LOGGING
```

---

## Key Lessons Learned

### Build & Release
1. **Electron + PyInstaller cache aggressively** — Must clear ALL caches before building (Step 4)
2. **Always verify built output** — Check the BUILT app, not just source files (Step 9)
3. **Version must be bumped in 6 files BEFORE building** — Electron reads package.json at build time
4. **Sync frontend→desktop-app BEFORE building** — Forgetting this = old frontend in build
5. **All 3 release files required for auto-updates** — Setup.exe + blockmap + latest.yml

### Backend
6. **Always `await` async methods** — Missing `await` silently returns coroutine objects (#1 bug)
7. **Use `get_ai_router()` singleton** — not `AIRouter()` per request (memory leak)
8. **Wrap SessionLocal() in try/finally** — Or use `Depends(get_db)` to prevent connection leaks
9. **Never return str(e) in HTTP responses** — Use generic messages, log details server-side
10. **Gemini model IDs: `gemini-3-flash-preview` (speed) + `gemini-3-pro-preview` (quality)** — Two-tier routing
11. **Gemini prompts must request JSON-only output** — Otherwise wraps in ```json blocks
12. **Router extraction: import from dependencies.py not main.py** — Circular import risk
13. **Default admin credentials hardcoded** — Desktop users lack `.env`. `ensure_default_admin()` uses `admin@certifyhealth.com` / `CertifyIntel2026!` with PBKDF2 `$` separator format
14. **conftest.py must set SECRET_KEY before main.py imports** — TestClient triggers lifespan
15. **ThreadPoolExecutor workers need own DB session + event loop** — SQLite not thread-safe

### Frontend
16. **Run `node -c` syntax check on app_v2.js after EVERY edit** — One missing `}` breaks all pages
17. **Always use escapeHtml() for innerHTML with dynamic content** — XSS prevention
18. **ES6 modules must export to window.\*** — onclick handlers in HTML strings need globals
19. **All background operations need global polling state** — setInterval inside Promise dies on SPA navigation
20. **Chart.js Canvas 2D cannot resolve CSS variables** — Use hardcoded hex values
21. **Service workers cache aggressively** — Use CACHE_VERSION + auto-purge on mismatch
22. **fetchAPI without `{ silent: true }` shows error toast** — Use silent flag for non-critical fetches
23. **Backend API response shapes must match frontend expectations** — Verify field names match
24. **Login screen must show admin@certifyhealth.com** — Not developer's personal email; check localStorage vs hardcoded default

### CI/CD
25. **CI release.yml must mirror backend-tests.yml env vars** — Missing vars cause test failures
26. **auto-merge.yml needs separate jobs per event type** — `pull_request.labels` is null on `check_suite` events

---

## Version History

| Version | Date | Key Changes |
|---------|------|-------------|
| **v10.0.0** | Feb 25 | Fixed infinite reload loop (cache version mismatch between index.html and app_v2.js). Desktop app stable release with login pre-population. |
| **v9.0.3** | Feb 25 | Login email pre-population, CLAUDE.md cleanup, admin password reset logic. |
| **v9.0.2** | Feb 25 | Login credential fix. Hardcoded default admin. PBKDF2 hash format fix. CI/CD fixes. |
| **v9.0.0** | Feb 15 | Major architecture: 17 routers, JWT refresh tokens, MFA, ES6 modules, Docker prod stack. |

> Full history: v7.x-v8.x (Feb 6-14) covered LangGraph agents, Discovery Scout, news filtering, Langfuse, XSS fixes. v2-v6 (Jan 2026) initial builds.

---

**Last Updated**: February 25, 2026
**Current Version**: v10.0.0
