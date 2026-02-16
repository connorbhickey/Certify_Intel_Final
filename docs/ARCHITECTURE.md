# Certify Intel v8.2.0 - System Architecture

## Table of Contents

1. [System Overview](#system-overview)
2. [Backend Architecture](#backend-architecture)
3. [AI Agent System](#ai-agent-system)
4. [AI Router & Model Routing](#ai-router--model-routing)
5. [Database Schema](#database-schema)
6. [Frontend Architecture](#frontend-architecture)
7. [Authentication Flow](#authentication-flow)
8. [Background Task System](#background-task-system)
9. [Data Pipeline](#data-pipeline)
10. [Desktop Application](#desktop-application)
11. [Deployment Architecture](#deployment-architecture)

---

## System Overview

```
                    +-------------------+
                    |   Desktop App     |
                    |   (Electron)      |
                    +--------+----------+
                             |
                    +--------v----------+
                    |   Frontend SPA    |
                    |   (Vanilla JS)    |
                    +--------+----------+
                             |
                    +--------v----------+
                    |   FastAPI Backend  |
                    |   (main.py)       |
                    +---+----+-----+----+
                        |    |     |
            +-----------+    |     +-----------+
            |                |                 |
    +-------v------+  +-----v------+  +-------v-------+
    |  AI Router   |  |  Database  |  |  Schedulers   |
    |  (ai_router) |  |  (SQLite/  |  |  (APScheduler)|
    +---+---+---+--+  |  Postgres) |  +---------------+
        |   |   |      +-----+-----+
        |   |   |            |
   +----+   |   +----+  +---v---------+
   |        |        |  | Vector Store|
   v        v        v  | (pgvector)  |
 Claude   GPT-4o  Gemini +------------+
 Opus 4.5         3 Flash/Pro
```

---

## Backend Architecture

### Module Map

The backend is organized into the following modules:

| Module | File | Lines | Purpose |
|--------|------|-------|---------|
| **Main Application** | `main.py` | ~17,000 | FastAPI app, 100+ endpoints, startup/shutdown |
| **AI Router** | `ai_router.py` | ~900 | Multi-model routing, cost tracking, budget enforcement |
| **Database ORM** | `database.py` | ~1,600 | 24+ SQLAlchemy models, sync/async sessions, CRUD helpers |
| **Knowledge Base** | `knowledge_base.py` | ~830 | RAG pipeline, document processing, entity extraction |
| **Vector Store** | `vector_store.py` | ~910 | pgvector integration, semantic search, embedding |
| **Observability** | `observability.py` | ~510 | Langfuse tracing, cost logging, health checks |
| **Input Sanitizer** | `input_sanitizer.py` | ~200 | XSS/injection prevention for user inputs |
| **News Monitor** | `news_monitor.py` | ~500 | Google News RSS fetching, relevance filtering |
| **Vertex AI** | `vertex_ai_provider.py` | ~810 | Optional Google Cloud Vertex AI integration |
| **Extended Features** | `extended_features.py` | ~400 | Auth manager, classification workflows |
| **AI Research** | `ai_research.py` | ~600 | Battlecard generation, competitor research |
| **Analytics** | `analytics.py` | ~400 | Dashboard insight generation |
| **Discovery Engine** | `discovery_engine.py` | ~500 | 4-stage competitor discovery pipeline |

### Router Modules

Supplementary route modules included via `app.include_router()`:

| Router | File | Prefix | Purpose |
|--------|------|--------|---------|
| Discovery | `routers/discovery.py` | `/api/discovery` | Discovery scout endpoints |
| API Routes | `api_routes.py` | — | Auth (`/token`), analytics, win/loss |
| Teams | `routers/teams.py` | `/api/teams` | Team collaboration features |
| Reports | `routers/reports.py` | `/api/reports` | PDF report generation |
| Sales Marketing | `routers/sales_marketing.py` | `/api/sales-marketing` | Dimension scoring, battlecards |
| Knowledge Base | `routers/knowledge_base.py` | `/api/kb` | Document import/extraction |
| Products | `routers/products.py` | `/api/products` | Product discovery system |
| Agents | `routers/agents.py` | `/api/agents` | LangGraph agent endpoints |

### Scraper Modules

Specialized data collection scrapers (most use fallback data for demo):

| Scraper | File | Data Source |
|---------|------|-------------|
| Base Scraper | `scraper.py` | Playwright website extraction |
| SEC Edgar | `sec_edgar_scraper.py` | Public company financials (yfinance) |
| News Monitor | `news_monitor.py` | Google News RSS (free) |
| Comprehensive News | `comprehensive_news_scraper.py` | Multi-source aggregation |
| Firecrawl | `firecrawl_integration.py` | Website crawling API |
| SEO | `seo_scraper.py` | Search engine optimization data |
| Review | `review_scraper.py` | G2, Capterra review monitoring |
| Social Media | `social_media_monitor.py` | Social platform metrics |
| KLAS | `klas_scraper.py` | Healthcare IT ratings |
| USPTO | `uspto_scraper.py` | Patent filings |
| Glassdoor | `glassdoor_scraper.py` | Employee reviews |

---

## AI Agent System

### Architecture

The AI system uses a LangGraph StateGraph to orchestrate 7 specialized agents:

```
                    User Query
                        |
                   +----v----+
                   |Orchestrator|
                   | (keyword  |
                   |  scoring) |
                   +----+-----+
                        |
         +---------+----+----+---------+
         |         |         |         |
    +----v---+ +---v---+ +--v----+ +--v------+
    |Dashboard| | News  | |Battle | |Discovery|
    | Agent   | | Agent | | card  | |  Agent  |
    +----+----+ +---+---+ +--+----+ +--+------+
         |         |         |         |
    +----v---+ +---v---+ +--v----+
    |Analytics| |Valida | |Records|
    | Agent   | | tion  | | Agent |
    +---------+ +-------+ +-------+
```

### Agent Details

| Agent | File | Specialization |
|-------|------|----------------|
| **Orchestrator** | `agents/orchestrator.py` | Routes queries via keyword scoring to the best agent |
| **Dashboard** | `agents/dashboard_agent.py` | Executive summaries, threat analysis, market overview |
| **Discovery** | `agents/discovery_agent.py` | Competitor discovery and qualification |
| **Battlecard** | `agents/battlecard_agent.py` | Sales battlecard generation with competitive positioning |
| **News** | `agents/news_agent.py` | News monitoring, sentiment analysis, event detection |
| **Analytics** | `agents/analytics_agent.py` | Market analysis, trend identification, reporting |
| **Validation** | `agents/validation_agent.py` | Data validation with Admiralty Code confidence scoring |
| **Records** | `agents/records_agent.py` | Change tracking, audit logs, historical analysis |

### Base Agent

All agents inherit from `BaseAgent` (`agents/base_agent.py`):

- Provides standardized response format (`AgentResponse`)
- Citation validation to prevent hallucinations
- Budget tracking per agent
- Knowledge base context retrieval (RAG)
- Error handling and fallback behavior

### Citation Validator

`agents/citation_validator.py` ensures AI responses reference only provided data:

- Validates that claims have supporting evidence
- Flags potential hallucinations
- Scores citation quality (0-100)

---

## AI Router & Model Routing

### Multi-Model Strategy

The AI Router (`ai_router.py`) implements cost-optimized model selection:

```
Task Types:
  BULK_EXTRACTION ──────> Gemini 3 Flash ($0.50/$3.00)
  CLASSIFICATION ───────> Gemini 3 Flash
  CHAT ─────────────────> Gemini 3 Flash
  SUMMARIZATION ────────> Gemini 3 Flash
  RAG ──────────────────> Gemini 3 Flash
  ANALYSIS ─────────────> Claude Opus 4.5 ($15.00/$75.00)
  BATTLECARD ───────────> Claude Opus 4.5
  STRATEGY ─────────────> Claude Opus 4.5
  COMPLEX_REASONING ────> Claude Opus 4.5
  DISCOVERY ────────────> Claude Opus 4.5
```

### Fallback Chain

```
Claude Opus 4.5  ──fail──>  GPT-4o  ──fail──>  Gemini 3 Flash  ──fail──>  Error
```

### Cost Tracking

Every AI call records:
- Model used
- Input/output token counts
- Cost in USD
- Latency in milliseconds
- User ID and agent type

Daily budget enforcement prevents runaway costs.

### Singleton Pattern

```python
from ai_router import get_ai_router

router = get_ai_router()  # Always use this, never AIRouter() directly
result = await router.generate(
    prompt="Analyze competitor X",
    task_type=TaskType.ANALYSIS,
    system_prompt="You are a competitive intelligence analyst...",
    max_tokens=4096
)
```

---

## Database Schema

### Entity Relationship Diagram (Simplified)

```
Competitor (115+ fields)
  |-- ChangeLog (change tracking)
  |-- DataSource (source attribution + confidence)
  |-- CompetitorProduct
  |     |-- ProductPricingTier
  |     |-- ProductFeatureMatrix
  |-- CustomerCountEstimate
  |-- Battlecard
  |-- TalkingPoint
  |-- CompetitorDimensionHistory
  |-- DimensionNewsTag
  |-- NewsArticleCache
  |-- CompetitorSubscription
  |-- CompetitorAnnotation
  |     |-- AnnotationReply
  |-- KBEntityLink
  |-- KBDataExtraction

User
  |-- ChatSession
  |     |-- ChatMessage
  |-- UserSettings
  |-- UserSavedPrompt
  |-- WinLossDeal
  |-- ActivityLog
  |-- TeamMembership
  |-- CompetitorSubscription
  |-- DiscoveryProfile

Team
  |-- TeamMembership
  |-- TeamActivity
  |-- CompetitorAnnotation

SystemPrompt (41 seeded, 6 categories)
SystemSetting (key-value config)
PersistentCache (ephemeral AI results)
RefreshSession (scrape audit trail)
DashboardConfiguration (role-based layouts)
WebhookConfig (outbound integrations)
```

### Key Tables

**Competitor** - The central entity with 115+ fields across these domains:
- Basic info (name, website, status, threat_level)
- Pricing (model, base_price, unit)
- Products (categories, features, integrations, certifications)
- Market (segments, geography, customer count, G2 rating)
- Company (employees, founded, funding, PE/VC backers)
- Digital (traffic, social, launches, news)
- Stock (public/private, ticker, exchange)
- Market verticals (11 healthcare segments mapped)
- Product overlap (7 Certify Health products)
- 9 competitive dimensions (1-5 scores with evidence)
- Social media metrics (8 platforms)
- Financial metrics (10 fields)
- Leadership (8 fields)
- Employee & culture (6 fields)
- Product & technology (8 fields)
- Market & competitive (6 fields)
- Regulatory & compliance (4 fields)
- Patents & IP (4 fields)
- Partnerships (4 fields)
- Customer intelligence (2 fields)

**DataSource** - Admiralty Code confidence scoring:
- Source reliability: A-F scale (A = completely reliable)
- Information credibility: 1-6 scale (1 = confirmed)
- Composite confidence score: 0-100
- Verification tracking with triangulation support

### Performance Optimizations

- 30+ composite indexes for common query patterns
- SQLite WAL mode for concurrent read/write
- 64MB cache, 256MB memory-mapped I/O
- Foreign key enforcement enabled
- Connection pooling (10 connections, 20 overflow for PostgreSQL)

---

## Frontend Architecture

### Single Page Application (SPA)

The frontend is a vanilla JavaScript SPA with no framework dependencies.

```
frontend/
  index.html          # Shell HTML with sidebar navigation
  app_v2.js           # Main application (~15,000 lines)
  styles.css           # All CSS styles
  service-worker.js    # Offline support and cache management
```

### Page Navigation

Navigation is handled by the `showPage(page)` function which:
1. Updates the URL hash
2. Hides all page containers
3. Shows the target page container
4. Calls the page's initialization function
5. Each page has try/catch error boundaries

### Key Frontend Patterns

| Pattern | Description |
|---------|-------------|
| `fetchAPI(url, options)` | Centralized fetch wrapper with auth headers, error toasts |
| `escapeHtml(str)` | XSS prevention for dynamic content |
| `showToast(message, type)` | User notification system |
| `createChatWidget(config)` | AI chat widget factory for any page |
| Global polling state | Background operations survive SPA navigation |
| `API_BASE` | Base URL for all API calls (configurable) |

### Chart Management

All charts use Chart.js with proper lifecycle management:
- Every chart instance is tracked for `.destroy()` on page navigation
- Prevents memory leaks from orphaned canvas contexts
- Charts are recreated on each page visit

### Offline Support

The service worker provides:
- Static asset caching (HTML, CSS, JS)
- Cache-first strategy for known assets
- Network-first for API calls
- Version-based cache invalidation

---

## Authentication Flow

### JWT Token Flow

```
1. User submits email + password
   POST /token (form data)

2. Backend verifies credentials
   PBKDF2-HMAC-SHA256 password hash comparison

3. Backend issues JWT token
   Payload: {sub: email, user_id: id, role: role, exp: expiry}

4. Frontend stores token in localStorage

5. All subsequent requests include:
   Authorization: Bearer <token>

6. Backend validates token on each request
   get_current_user() dependency extracts user from JWT
```

### Role-Based Access

| Role | API Access | UI Access |
|------|-----------|-----------|
| `admin` | All endpoints | All pages, user management, settings |
| `analyst` | Most endpoints (no user management) | All pages except user management |
| `viewer` | Read-only endpoints | View-only on all pages |

---

## Background Task System

### APScheduler Jobs

The backend runs scheduled tasks via APScheduler:

| Job | Schedule | Purpose |
|-----|----------|---------|
| News refresh | Configurable (default: daily) | Fetch latest news for all competitors |
| Data verification | Configurable | Run AI verification on stale data |
| Cache cleanup | Hourly | Prune expired persistent cache entries |

### Long-Running AI Tasks

For operations that take longer than a typical HTTP request:

```
1. Client sends POST /api/ai/tasks
   -> Backend creates task entry in _ai_tasks dict
   -> Returns task_id immediately

2. Client polls GET /api/ai/tasks/{task_id}
   -> Returns status: "pending" | "running" | "completed" | "failed"

3. When complete, response includes result data

4. Tasks auto-prune after 1 hour
```

### Background Operations with SPA Resilience

Operations like news fetch, discovery, and verification use a global polling pattern that survives SPA navigation:

```javascript
// Global state (not destroyed by navigation)
window._discoveryRunning = true;
window._discoveryTaskId = taskId;

// Polling loop (continues across page switches)
while (window._discoveryRunning) {
    const progress = await fetchAPI(`/api/discovery/progress/${taskId}`);
    // Update UI only if DOM element exists
    const el = document.getElementById('discoveryProgress');
    if (el) el.textContent = progress.message;
    await new Promise(r => setTimeout(r, 2000));
}
```

---

## Data Pipeline

### Competitor Data Flow

```
External Sources                    Internal Processing
+------------------+               +-------------------+
| Google News RSS  |──┐            | AI Classification |
| SEC Edgar (free) |──┤   Fetch    | (Gemini Flash)    |
| Company Websites |──┼──────────> +--------+----------+
| Known Data       |──┤                     |
| Knowledge Base   |──┘              +------v------+
                                     | Data Store  |
                                     | (SQLite/PG) |
                                     +------+------+
                                            |
                              +-------------+-------------+
                              |             |             |
                        +-----v----+  +-----v----+  +----v-----+
                        |Confidence|  | Change   |  | News     |
                        |Scoring   |  | Tracking |  | Cache    |
                        +----------+  +----------+  +----------+
```

### Discovery Pipeline (4 Stages)

```
Stage 1: Search
  AI generates search queries based on qualification criteria
  -> Returns candidate company names

Stage 2: Qualify
  AI evaluates each candidate against criteria
  -> Returns qualification scores (0-100)

Stage 3: Analyze
  AI performs deep analysis on qualified candidates
  -> Returns structured competitor profiles

Stage 4: Summarize
  AI generates executive summary of all discoveries
  -> Returns narrative summary with recommendations
```

### Data Verification Pipeline

```
1. For each competitor field:
   a. Send to Gemini Pro with grounded search
   b. AI searches the web for current data
   c. Compare AI-found value with stored value
   d. Return: match/mismatch/unverifiable + source URLs

2. Results update DataSource confidence scores
3. Source links stored for clickable verification
4. 1-second delay between Gemini calls (rate limiting)
```

---

## Desktop Application

### Architecture

```
+-------------------------+
|     Electron Shell      |
|  (main.js, preload.js)  |
|                         |
|  +-------------------+  |
|  | BrowserWindow     |  |
|  | (frontend SPA)    |  |
|  +--------+----------+  |
|           |              |
|  +--------v----------+  |
|  | PyInstaller Bundle |  |
|  | (certify_backend   |  |
|  |  .exe)             |  |
|  +--------------------+  |
+-------------------------+
```

### Startup Sequence

1. Electron main process starts
2. Spawns `certify_backend.exe` as child process
3. Waits for backend to report healthy on port 8000
4. Opens BrowserWindow pointing to `http://localhost:8000`
5. Watchdog monitors backend process health

### Build Pipeline

```
Source Files
  backend/*.py ──> PyInstaller ──> certify_backend.exe
  frontend/*   ──> Copy to desktop-app/frontend/

Packaging
  certify_backend.exe + frontend/ + .env + db
    ──> electron-builder ──> Certify_Intel_vX.X.X_Setup.exe
```

---

## Deployment Architecture

### Development (Single Machine)

```
localhost:8000
  FastAPI + SQLite + All AI providers via API keys
```

### Production (Docker)

```
                   nginx (reverse proxy, SSL)
                         |
              +----------+----------+
              |                     |
        FastAPI (x4 workers)   Langfuse (optional)
              |                     |
     +--------+--------+      PostgreSQL
     |                  |      (Langfuse DB)
 PostgreSQL         pgvector
 (main DB)        (vector store)
```

### Docker Compose Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Basic development setup |
| `docker-compose.prod.yml` | Production with nginx, workers |
| `docker-compose.postgres.yml` | PostgreSQL + pgvector |
| `docker-compose.langfuse.yml` | Langfuse observability |

---

*Architecture document for Certify Intel v8.2.0 - February 2026*
