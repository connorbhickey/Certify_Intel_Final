# Roadmap & Future Development

This document outlines suggested next steps, known limitations, and enhancement ideas for continuing development of Certify Intel.

---

## Suggested Priority: High

### 1. Alembic Database Migrations
**Current state**: Database migrations are done via manual `ALTER TABLE` in `init_db()` with try/except for duplicate columns. This works but is fragile.

**Recommendation**: Implement Alembic for proper migration management.
- Auto-generate migrations from model changes
- Track migration history
- Support rollbacks
- Required for team development (multiple devs making schema changes)

**Effort**: Medium (2-3 days)

### 2. Frontend Page Splitting
**Current state**: `app_v2.js` is ~24,000 lines containing all 11 pages in one file.

**Recommendation**: Extract each page into `frontend/pages/*.js` modules.
- `pages/dashboard.js`, `pages/competitors.js`, etc.
- Lazy-load pages on navigation (faster initial load)
- Easier for multiple developers to work in parallel

**Effort**: Medium-Large (3-5 days)

### 3. Continue Backend Router Extraction
**Current state**: 17 routers extracted from `main.py`, but ~16,600 lines remain with discovery, sales-marketing, news, verification, and scraping endpoints inline.

**Recommendation**: Extract remaining endpoints to:
- `routers/discovery.py`
- `routers/sales_marketing.py`
- `routers/news.py`
- `routers/verification.py`
- `routers/scraping.py`

**Effort**: Medium (2-3 days per router)

---

## Suggested Priority: Medium

### 4. Celery Task Queue
**Current state**: Heavy AI operations (discovery pipeline, batch verification, news refresh) run as async tasks in the main process.

**Recommendation**: Move to Celery with Redis broker for:
- Better reliability (tasks survive server restarts)
- Horizontal scaling (multiple workers)
- Task retry with backoff
- Progress tracking via Celery result backend

**Effort**: Large (1 week)

### 5. WebSocket Real-Time Updates
**Current state**: Frontend polls APIs for background task progress.

**Recommendation**: Implement WebSocket connections for:
- Real-time discovery progress
- Live news feed updates
- Background task completion notifications
- Multi-user collaboration awareness

FastAPI has built-in WebSocket support.

**Effort**: Medium (3-4 days)

### 6. User Role System
**Current state**: Two roles - "admin" and "user". Admins can do everything, users can do most things.

**Recommendation**: Implement granular permissions:
- Role-based access control (RBAC)
- Custom roles (analyst, manager, executive, viewer)
- Per-page and per-feature permissions
- Team-based competitor ownership

**Effort**: Medium (3-4 days)

### 7. Load Testing
**Current state**: No load testing has been performed.

**Recommendation**: Use k6 for baseline performance testing:
- Target: 50 concurrent users, P95 < 500ms
- Identify bottlenecks (likely AI API calls and DB queries)
- Set up performance regression detection in CI

**Effort**: Small (1-2 days)

---

## Suggested Priority: Low

### 8. macOS Desktop App
**Current state**: Desktop app builds for Windows only (requires macOS machine for macOS builds).

**Recommendation**: If macOS is needed, set up a macOS CI runner or use a Mac for local builds. The Electron code is already cross-platform.

**Effort**: Small (1 day with a Mac)

### 9. Multi-Tenancy
**Current state**: Single-tenant application. All users share the same competitor database.

**Recommendation**: If multiple organizations need separate data:
- Add `organization_id` to key tables
- Filter all queries by org
- Separate admin per org
- Consider separate databases per tenant for data isolation

**Effort**: Large (1-2 weeks)

### 10. Advanced Analytics
**Current state**: Basic market quadrant chart, win/loss tracking, threat trends.

**Recommendation**: Add:
- Competitor movement tracking over time
- Market share estimation models
- Predictive threat scoring (ML-based)
- Custom report builder
- Scheduled report delivery via email

**Effort**: Large (varies per feature)

---

## Known Limitations

### Technical
- **SQLite concurrency**: Write operations lock the entire database. Use PostgreSQL for multi-user production.
- **app_v2.js size**: 24,000 lines in one file impacts developer productivity. See page splitting above.
- **main.py size**: 16,600 lines remaining. See router extraction above.
- **No Alembic**: Schema changes require manual ALTER TABLE. See migrations above.
- **Polling, not WebSockets**: Background operations use HTTP polling, not real-time push.

### Data
- **74 competitors loaded**: Healthcare technology space. Adding competitors outside healthcare may need search query adjustments in `news_monitor.py` (healthcare-specific filtering).
- **News relevance**: Single-word company names (e.g., "Access") require domain-based filtering to avoid false positives. The `_filter_irrelevant_articles()` function handles this but may need tuning for new companies.
- **AI verification accuracy**: Data verification depends on AI provider quality and web search availability. Gemini Pro with grounded search provides the best results.

### Infrastructure
- **No auto-scaling**: Single-instance deployment. For high traffic, add a load balancer + multiple backend instances + shared PostgreSQL + Redis.
- **No email integration**: News alerts and reports are shown in-app only. Email delivery requires SMTP configuration (not yet implemented).
- **No SSO**: Authentication is email/password + optional MFA. SAML/OIDC SSO would need to be added for enterprise environments.

---

## Architecture Decisions for Future Reference

| Decision | Rationale | Alternatives Considered |
|----------|-----------|------------------------|
| Vanilla JS (no framework) | Fast development, no build step, full control | React, Vue - rejected for simplicity |
| SQLAlchemy + SQLite default | Zero-config setup, easy distribution | PostgreSQL-only - too complex for local dev |
| LangGraph for agents | State machine orchestration, built-in persistence | CrewAI, AutoGen - less mature |
| Multi-provider AI routing | Cost optimization, reliability, no vendor lock-in | Single provider - too risky |
| JWT + refresh tokens | Stateless auth, standard pattern | Session cookies - less flexible for API |
| Docker Compose (not K8s) | Right-sized for expected scale | Kubernetes - overkill for < 100 users |

---

## File Size Reference

For planning refactoring work:

| File | Lines | Priority to Split |
|------|-------|-------------------|
| `frontend/app_v2.js` | ~24,000 | High |
| `backend/main.py` | ~16,600 | High |
| `frontend/styles.css` | ~6,000 | Medium |
| `backend/database.py` | ~1,550 | Low |
| `backend/ai_router.py` | ~788 | Low |
