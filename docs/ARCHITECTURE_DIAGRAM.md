# Certify Intel v8.1.0 - Full System Architecture

---

## HIGH-LEVEL SYSTEM OVERVIEW

```
+=====================================================================================+
|                                                                                     |
|                          CERTIFY INTEL v8.1.0                                       |
|                    Competitive Intelligence Platform                                |
|                                                                                     |
|    74 Active Competitors | 789 Products | 920 News Articles | 512 Data Sources     |
|                                                                                     |
+=====================================================================================+

                    +-------------------------------+
                    |         END USERS             |
                    |  (Sales, Marketing, Analysts) |
                    +-------------------------------+
                         |                |
              +----------+                +----------+
              |                                      |
              v                                      v
+---------------------------+          +---------------------------+
|     WEB BROWSER (SPA)     |          |   DESKTOP APP (Electron)  |
|  http://localhost:8000    |          |   Windows .exe Installer  |
|                           |          |                           |
|  11 Pages | Offline PWA   |          |  Auto-Update | Tray Icon  |
|  Service Worker Caching   |          |  Crash Reporting (Sentry) |
+---------------------------+          +---------------------------+
              |                                      |
              |         HTTP / WebSocket             |
              +----------------+---------------------+
                               |
                               v
              +=====================================+
              |        FASTAPI BACKEND              |
              |     Python 3.9+ | Uvicorn           |
              |     100+ REST Endpoints             |
              |     2 WebSocket Channels            |
              +=====================================+
                               |
              +----------------+---------------------+
              |                |                     |
              v                v                     v
    +--------------+  +-----------------+  +------------------+
    |   DATABASE   |  |   AI PROVIDERS  |  |  EXTERNAL APIs   |
    |  SQLite /    |  |  Claude, GPT-4o |  |  News, SEC,      |
    |  PostgreSQL  |  |  Gemini, DeepSk |  |  USPTO, Firecrawl|
    +--------------+  +-----------------+  +------------------+
```

---

## FRONTEND ARCHITECTURE (Single Page Application)

```
+=====================================================================================+
|                              FRONTEND SPA                                            |
|                   Vanilla JS (ES6+) | HTML5 | CSS3                                  |
|                   No Frameworks - Pure DOM Manipulation                              |
+=====================================================================================+
|                                                                                     |
|  +---------------------------+    +------------------------------------------+      |
|  |      ENTRY POINTS         |    |           CORE FILES                     |      |
|  |---------------------------|    |------------------------------------------|      |
|  |  login.html  (18 KB)      |    |  app_v2.js           (795 KB) - Main SPA |      |
|  |  index.html  (213 KB)     |    |  styles.css          (289 KB) - All CSS  |      |
|  |  manifest.json (PWA)      |    |  sales_marketing.js  (133 KB) - Sales    |      |
|  +---------------------------+    |  agent_chat_widget.js  (22 KB) - Chat    |      |
|                                   |  enhanced_analytics.js (26 KB) - Charts  |      |
|                                   |  service-worker.js      (8 KB) - Offline |      |
|                                   +------------------------------------------+      |
|                                                                                     |
|  +-------------------------------------------------------------------------------+ |
|  |                         11 APPLICATION PAGES                                   | |
|  +-------------------------------------------------------------------------------+ |
|  |                                                                                | |
|  |  +-------------+  +------------------+  +---------------+  +---------------+   | |
|  |  |  DASHBOARD  |  | DISCOVERY SCOUT  |  | BATTLECARDS   |  | COMPARISONS   |   | |
|  |  |-------------|  |------------------|  |---------------|  |---------------|   | |
|  |  | AI Summary  |  | 4-Stage Pipeline |  | SWOT Analysis |  | 2-4 Compete   |   | |
|  |  | Top Threats |  | Qual. Criteria   |  | Talking Pts   |  | Feature Matrix|   | |
|  |  | KPI Charts  |  | Progress Polling |  | Source Links  |  | Heatmap View  |   | |
|  |  | Recent Chgs |  | Result Grid      |  | AI Verify     |  | Radar Charts  |   | |
|  |  +-------------+  +------------------+  +---------------+  +---------------+   | |
|  |                                                                                | |
|  |  +-------------+  +------------------+  +---------------+  +---------------+   | |
|  |  |  LIVE NEWS  |  |    ANALYTICS     |  | SALES & MKTG  |  |   RECORDS     |   | |
|  |  |-------------|  |------------------|  |---------------|  |---------------|   | |
|  |  | News Grid   |  | Market Map       |  | 9 Dimensions  |  | Change History|   | |
|  |  | Sentiment   |  | Win/Loss Track   |  | Radar Chart   |  | Audit Trail   |   | |
|  |  | Filtering   |  | Financial Charts |  | Comparisons   |  | Rollback      |   | |
|  |  | Healthcare  |  | Trend Analysis   |  | Positioning   |  | Approvals     |   | |
|  |  +-------------+  +------------------+  +---------------+  +---------------+   | |
|  |                                                                                | |
|  |  +-------------------+  +-------------------+  +-------------------+           | |
|  |  |    VALIDATION     |  |     SETTINGS      |  |   COMPETITORS     |           | |
|  |  |-------------------|  |-------------------|  |-------------------|           | |
|  |  | Confidence Scores |  | API Key Config    |  | CRUD Operations   |           | |
|  |  | Source Verify     |  | AI Provider Diag  |  | Grid / List View  |           | |
|  |  | Quality Metrics   |  | User Preferences  |  | Quick Details     |           | |
|  |  | Batch Verify      |  | Theme Toggle      |  | Threat Levels     |           | |
|  |  +-------------------+  +-------------------+  +-------------------+           | |
|  +--------------------------------------------------------------------------------+ |
|                                                                                     |
|  +-------------------------------------------------------------------------------+ |
|  |                       SHARED UI COMPONENTS                                     | |
|  +-------------------------------------------------------------------------------+ |
|  |                                                                                | |
|  |  fetchAPI()         - Auth-aware HTTP client (JWT auto-inject)                 | |
|  |  showPage()         - SPA router with error boundaries                        | |
|  |  createChatWidget() - AI chat on every page (persistent sessions)             | |
|  |  showSkeleton()     - Loading state placeholders                              | |
|  |  escapeHtml()       - XSS prevention for dynamic content                     | |
|  |  Chart.js           - All data visualizations (bar, line, radar, doughnut)    | |
|  |                                                                                | |
|  |  Glassmorphism Theme | Dark Mode | Responsive (1920/1366/768px)               | |
|  +--------------------------------------------------------------------------------+ |
|                                                                                     |
|  +-------------------------------------------------------------------------------+ |
|  |                   SERVICE WORKER (Offline PWA)                                 | |
|  +-------------------------------------------------------------------------------+ |
|  |  CACHE_VERSION = 'v8.1.0'                                                     | |
|  |  Strategy: Cache-First (static) | Network-First (API)                         | |
|  |  Background Sync for Win/Loss data                                            | |
|  +--------------------------------------------------------------------------------+ |
+=====================================================================================+
```

---

## BACKEND ARCHITECTURE (FastAPI)

```
+=====================================================================================+
|                              FASTAPI BACKEND                                         |
|                     main.py (13,400+ lines) | Python 3.9+                           |
|                     Uvicorn ASGI Server | Port 8000                                 |
+=====================================================================================+
|                                                                                     |
|  +---------------------------------------+  +-----------------------------------+  |
|  |          REQUEST PIPELINE             |  |        MIDDLEWARE STACK            |  |
|  |---------------------------------------|  |-----------------------------------|  |
|  |                                       |  |                                   |  |
|  |  Incoming HTTP Request                |  |  1. CORS (all origins dev)        |  |
|  |         |                             |  |  2. Static File Serving           |  |
|  |         v                             |  |  3. Request Logging               |  |
|  |  CORS Middleware                      |  |  4. Error Handler (500 -> JSON)   |  |
|  |         |                             |  |  5. Input Sanitization            |  |
|  |         v                             |  |                                   |  |
|  |  Route Matching (100+ endpoints)      |  +-----------------------------------+  |
|  |         |                             |                                         |
|  |         v                             |  +-----------------------------------+  |
|  |  JWT Auth: get_current_user()         |  |      AUTHENTICATION               |  |
|  |         |                             |  |-----------------------------------|  |
|  |         v                             |  |                                   |  |
|  |  Input Sanitizer (XSS/SQLi/Prompt)   |  |  POST /token                      |  |
|  |         |                             |  |    |                              |  |
|  |         v                             |  |    v                              |  |
|  |  Endpoint Handler                     |  |  PBKDF2-HMAC-SHA256 verify       |  |
|  |         |                             |  |    |                              |  |
|  |         v                             |  |    v                              |  |
|  |  DB Session (get_db / get_async_db)   |  |  Generate JWT (24hr expiry)       |  |
|  |         |                             |  |    |                              |  |
|  |         v                             |  |    v                              |  |
|  |  Business Logic / AI Agent Call       |  |  Return: {access_token, type}     |  |
|  |         |                             |  |                                   |  |
|  |         v                             |  |  All protected endpoints use:     |  |
|  |  JSON Response                        |  |  Depends(get_current_user)        |  |
|  |                                       |  |                                   |  |
|  +---------------------------------------+  +-----------------------------------+  |
|                                                                                     |
+=====================================================================================+

                              API ENDPOINT MAP
+=====================================================================================+
|                                                                                     |
|   AUTHENTICATION (3)              COMPETITORS (10+)                                 |
|   --------------------------      --------------------------                        |
|   POST /token                     GET    /api/competitors                           |
|   POST /api/auth/register         POST   /api/competitors                           |
|   GET  /api/auth/me               GET    /api/competitors/{id}                      |
|                                   PUT    /api/competitors/{id}                      |
|                                   DELETE /api/competitors/{id}                      |
|                                                                                     |
|   AI AGENTS (5)                   DISCOVERY SCOUT (10+)                             |
|   --------------------------      --------------------------                        |
|   POST /api/agents/dashboard      POST /api/discovery/run-ai                        |
|   POST /api/agents/discovery      GET  /api/discovery/progress/{id}                 |
|   POST /api/agents/battlecard     GET  /api/discovery/profiles                      |
|   POST /api/agents/news           POST /api/discovery/summarize                     |
|   POST /api/agents/analytics      POST /api/discovery/send-to-battlecard            |
|                                                                                     |
|   CHAT PERSISTENCE (7)           SALES & MARKETING (30+)                            |
|   --------------------------      --------------------------                        |
|   GET    /api/chat/sessions       GET  /api/sales-marketing/dimensions              |
|   POST   /api/chat/sessions       POST /api/sales-marketing/battlecards/generate    |
|   GET    /api/chat/sessions/{id}  POST /api/sales-marketing/compare/dimensions      |
|   DELETE /api/chat/sessions/{id}  GET  /api/sales-marketing/competitors/{id}/...    |
|                                                                                     |
|   NEWS FEED (10+)                 DATA QUALITY (20+)                                |
|   --------------------------      --------------------------                        |
|   GET  /api/news-feed             GET  /api/data-quality/overview                   |
|   GET  /api/competitors/{id}/news POST /api/triangulate/{id}                        |
|   POST /api/news-feed/cleanup     POST /api/verification/run-all                    |
|                                   GET  /api/verification/progress                   |
|                                                                                     |
|   BACKGROUND TASKS (3)           DASHBOARD (2)                                      |
|   --------------------------      --------------------------                        |
|   POST /api/ai/tasks              GET /api/dashboard/top-threats                    |
|   GET  /api/ai/tasks/{id}         GET /api/corporate-profile                        |
|   PUT  /api/ai/tasks/{id}/dismiss                                                   |
|                                                                                     |
|   WEBSOCKET CHANNELS (2)                                                            |
|   --------------------------                                                        |
|   WS /ws/updates                  (real-time competitor/news updates)               |
|   WS /ws/refresh-progress         (scrape/refresh progress tracking)                |
|                                                                                     |
+=====================================================================================+
```

---

## AI AGENT SYSTEM (LangGraph Orchestration)

```
+=====================================================================================+
|                       LANGGRAPH AGENT ORCHESTRATOR                                   |
|                    orchestrator.py (31 KB) | StateGraph                              |
+=====================================================================================+
|                                                                                     |
|    User Query                                                                       |
|        |                                                                            |
|        v                                                                            |
|   +-----------+                                                                     |
|   | ROUTE     |   Keyword matching + intent classification                         |
|   | QUERY     |   Determines which specialized agent handles the request            |
|   +-----------+                                                                     |
|        |                                                                            |
|        +------+------+------+------+------+------+------+                           |
|        |      |      |      |      |      |      |      |                           |
|        v      v      v      v      v      v      v      v                           |
|                                                                                     |
|  +----------+ +----------+ +----------+ +----------+ +----------+                   |
|  |DASHBOARD | |DISCOVERY | |BATTLECARD| |  NEWS    | |ANALYTICS |                   |
|  |  AGENT   | |  AGENT   | |  AGENT   | |  AGENT   | |  AGENT   |                   |
|  |----------| |----------| |----------| |----------| |----------|                   |
|  | 26 KB    | | 21 KB    | | 20 KB    | | 21 KB    | | 28 KB    |                   |
|  |          | |          | |          | |          | |          |                   |
|  | Executive| | Competitor| | SWOT    | | Sentiment| | Market   |                   |
|  | Summary  | | Discovery| | Analysis | | Analysis | | Trends   |                   |
|  | Threats  | | Qualify  | | Talking  | | Event    | | Win/Loss |                   |
|  | KPIs     | | Scoring  | | Points   | | Detection| | Financial|                   |
|  +----------+ +----------+ +----------+ +----------+ +----------+                   |
|                                                                                     |
|  +----------+ +----------+ +--------------------------------------------------+    |
|  |VALIDATION| | RECORDS  | |                  BASE AGENT                      |    |
|  |  AGENT   | |  AGENT   | |  base_agent.py (25 KB)                          |    |
|  |----------| |----------| |--------------------------------------------------|    |
|  | 19 KB    | | 20 KB    | |                                                  |    |
|  |          | |          | |  - Abstract base class for ALL agents            |    |
|  | Source   | | Change   | |  - Citation validation (NO_HALLUCINATION rule)   |    |
|  | Verify   | | History  | |  - Cost tracking per request                     |    |
|  | Confidence| | Audit   | |  - Langfuse observability integration            |    |
|  | Scoring  | | Rollback | |  - Error handling & fallback logic               |    |
|  +----------+ +----------+ +--------------------------------------------------+    |
|                                                                                     |
|        All Agent Outputs                                                            |
|              |                                                                      |
|              v                                                                      |
|   +--------------------+                                                            |
|   | CITATION VALIDATOR |   citation_validator.py (16 KB)                            |
|   |--------------------|                                                            |
|   | Validates ALL AI   |   Every response checked for hallucinations                |
|   | output against     |   Unverified claims flagged or removed                     |
|   | source data        |   Confidence scores attached to each fact                  |
|   +--------------------+                                                            |
|              |                                                                      |
|              v                                                                      |
|   +--------------------+                                                            |
|   | VERIFIED RESPONSE  |   JSON with citations, confidence, cost metadata           |
|   +--------------------+                                                            |
|                                                                                     |
+=====================================================================================+
```

---

## AI PROVIDER ROUTING & COST MANAGEMENT

```
+=====================================================================================+
|                          AI ROUTER (ai_router.py - 788 lines)                       |
|                     Multi-Model Selection | Cost Tracking | Budget Enforcement       |
+=====================================================================================+
|                                                                                     |
|   Incoming AI Request                                                               |
|        |                                                                            |
|        v                                                                            |
|   +-------------------+                                                             |
|   | TASK CLASSIFIER   |   Determines complexity & cost tier                         |
|   +-------------------+                                                             |
|        |                                                                            |
|        +----------+----------+----------+----------+                                |
|        |          |          |          |          |                                |
|        v          v          v          v          v                                |
|                                                                                     |
|  +-----------+ +----------+ +----------+ +----------+ +----------+                  |
|  | PREMIUM   | | STANDARD | |   FAST   | | GROUNDED | |  BUDGET  |                  |
|  | TIER      | | TIER     | |   TIER   | | TIER     | |  TIER    |                  |
|  |-----------| |----------| |----------| |----------| |----------|                  |
|  |           | |          | |          | |          | |          |                  |
|  | Claude    | | GPT-4o   | | Gemini   | | Gemini   | | DeepSeek |                  |
|  | Opus 4.5  | |          | | 3 Flash  | | 3 Pro    | | v3.2     |                  |
|  |           | |          | |          | |          | |          |                  |
|  | $15/$75   | | $2.50/$10| | $0.50/$3 | | $2/$12   | | $0.27/   |                  |
|  | per 1M tk | | per 1M tk| | per 1M tk| | per 1M tk| | $1.10    |                  |
|  +-----------+ +----------+ +----------+ +----------+ +----------+                  |
|  |           | |          | |          | |          | |          |                  |
|  | Strategy  | | Analysis | | Chat     | | Grounded | | Bulk     |                  |
|  | Battlecrd | | Fallback | | Summary  | | Search   | | Extract  |                  |
|  | Discovery | | RAG      | | RAG      | | Deep     | | Classify |                  |
|  | Complex   | |          | | Bulk     | | Research | |          |                  |
|  | Reasoning | |          | | Classify | | Exec Summ| |          |                  |
|  +-----------+ +----------+ +----------+ +----------+ +----------+                  |
|                                                                                     |
|   FALLBACK CHAIN:  Claude Opus 4.5 --> GPT-4o --> Gemini 3 Flash                   |
|                                                                                     |
|   DAILY BUDGET:    $50 default (configurable)                                       |
|   COST TRACKING:   Per-request accumulation with daily reset                        |
|   AUTO-DOWNGRADE:  Switch to cheaper model when budget threshold hit                |
|                                                                                     |
+=====================================================================================+
```

---

## DATABASE ARCHITECTURE

```
+=====================================================================================+
|                        DATABASE LAYER (database.py - 1,547 lines)                   |
|                     SQLAlchemy ORM | 28+ Tables | Sync + Async                      |
+=====================================================================================+
|                                                                                     |
|   +---------------------------------------------+                                  |
|   |          CONNECTION MANAGEMENT               |                                  |
|   |---------------------------------------------|                                  |
|   |                                             |                                  |
|   |  Development/Desktop:                       |                                  |
|   |    sqlite:///./certify_intel.db             |                                  |
|   |    SessionLocal (sync)                      |                                  |
|   |    get_db() -> yields Session               |                                  |
|   |                                             |                                  |
|   |  Production:                                |                                  |
|   |    postgresql://host/db                     |                                  |
|   |    AsyncSessionLocal (async)                |                                  |
|   |    get_async_db() -> yields AsyncSession    |                                  |
|   |                                             |                                  |
|   |  Vector Store:                              |                                  |
|   |    postgresql+asyncpg://host/db (pgvector)  |                                  |
|   +---------------------------------------------+                                  |
|                                                                                     |
|   ENTITY RELATIONSHIP MAP                                                           |
|   =======================                                                           |
|                                                                                     |
|   +------------------+     1:N     +-------------------+                            |
|   |   COMPETITOR      |----------->|  CompetitorProduct |                            |
|   |   (115+ fields)   |            |  (789 products)    |                            |
|   |                   |            +-------------------+                            |
|   |  name             |                 |                                           |
|   |  website          |            1:N  |                                           |
|   |  threat_level     |                 v                                           |
|   |  market_segment   |     +---------------------+  +-------------------------+   |
|   |  hq_city/state    |     | ProductPricingTier   |  | ProductFeatureMatrix    |   |
|   |  employee_count   |     +---------------------+  +-------------------------+   |
|   |  annual_revenue   |                                                             |
|   |  dim_product_*    |     +-------------------+                                   |
|   |  dim_market_*     |---->| CustomerCountEst  |  (1:N)                            |
|   |  social_*         |     +-------------------+                                   |
|   |  financial_*      |                                                             |
|   +------------------+     +-------------------+                                   |
|          |    |    |  +--->|    Battlecard      |  (1:N)                            |
|          |    |    |  |    +-------------------+                                   |
|          |    |    +--+                                                             |
|          |    |       |    +-------------------+                                   |
|          |    |       +--->|   TalkingPoint    |  (1:N)                            |
|          |    |            +-------------------+                                   |
|          |    |                                                                     |
|          |    |            +-------------------+                                   |
|          |    +----------->|  NewsArticleCache |  (1:N, 920 active)                |
|          |                 +-------------------+                                   |
|          |                                                                          |
|          |                 +-------------------+                                   |
|          +---------------->|    DataSource     |  (1:N, 512 sources)               |
|          |                 +-------------------+                                   |
|          |                                                                          |
|          |    +-------------------------------+                                     |
|          +--->| CompetitorDimensionHistory    |  (1:N)                              |
|          |    +-------------------------------+                                     |
|          |    +-------------------------------+                                     |
|          +--->| DimensionNewsTag              |  (M:N via competitor + news)        |
|               +-------------------------------+                                     |
|                                                                                     |
|                                                                                     |
|   +-----------+    1:N    +-------------+    1:N    +--------------+                |
|   |   USER    |---------->| ChatSession |---------->| ChatMessage  |                |
|   |-----------|           |-------------|           |--------------|                |
|   | email     |           | page_context|           | role         |                |
|   | role      |           | competitor_id           | content      |                |
|   | hashed_pw |           | title       |           | metadata_json|                |
|   +-----------+           +-------------+           +--------------+                |
|        |                                                                            |
|        |    1:N    +----------------+                                               |
|        +---------->| UserSettings   |                                               |
|        |           +----------------+                                               |
|        |    1:N    +------------------+                                              |
|        +---------->| UserSavedPrompt  |                                              |
|                    +------------------+                                              |
|                                                                                     |
|                                                                                     |
|   STANDALONE TABLES                                                                 |
|   =================                                                                 |
|                                                                                     |
|   +----------------+  +----------------+  +-------------------+                     |
|   | ChangeLog      |  | ActivityLog    |  | RefreshSession    |                     |
|   | (audit trail)  |  | (user actions) |  | (scrape history)  |                     |
|   +----------------+  +----------------+  +-------------------+                     |
|                                                                                     |
|   +----------------+  +----------------+  +-------------------+                     |
|   | SystemPrompt   |  | WinLossDeal    |  | DiscoveryProfile  |                     |
|   | (41 prompts,   |  | (deal tracking)|  | (saved criteria)  |                     |
|   |  6 categories) |  +----------------+  +-------------------+                     |
|   +----------------+                                                                |
|                                                                                     |
|   +----------------+  +----------------+  +-------------------+                     |
|   |KnowledgeBase   |  | WebhookConfig  |  | PersistentCache   |                    |
|   |Item            |  | (integrations) |  | (AI result cache)  |                    |
|   +----------------+  +----------------+  +-------------------+                     |
|                                                                                     |
|   +----------------+  +------------------+  +-------------------+                   |
|   | SystemSetting  |  | DashboardConfig  |  | CompetitorSubscr  |                   |
|   +----------------+  +------------------+  +-------------------+                   |
|                                                                                     |
+=====================================================================================+
```

---

## DISCOVERY SCOUT PIPELINE (4-Stage AI System)

```
+=====================================================================================+
|                     DISCOVERY SCOUT - 4-STAGE AI PIPELINE                            |
|                  discovery_engine.py (61 KB) | ~120s total timeout                   |
+=====================================================================================+
|                                                                                     |
|   User Input: Qualification Criteria                                                |
|   (market segment, capabilities, geography, funding, custom prompt)                 |
|        |                                                                            |
|        v                                                                            |
|   +=========================================================================+       |
|   | STAGE 1: SEARCH                                         ~30s timeout    |       |
|   |-------------------------------------------------------------------------|       |
|   |                                                                         |       |
|   |  Provider: Gemini 3-Flash (with Google Search grounding)               |       |
|   |  Cost: ~$0.002 per search                                              |       |
|   |                                                                         |       |
|   |  Input:  Qualification criteria + market context                       |       |
|   |  Action: Web search for matching companies                             |       |
|   |  Output: List of candidate company names + URLs                        |       |
|   |                                                                         |       |
|   +=========================================================================+       |
|        |                                                                            |
|        v  (candidate URLs)                                                          |
|   +=========================================================================+       |
|   | STAGE 2: SCRAPE                            ~10s/site, max 5 concurrent  |       |
|   |-------------------------------------------------------------------------|       |
|   |                                                                         |       |
|   |  Provider: Firecrawl API (paid) or httpx (free fallback)               |       |
|   |  Cost: Free - $0.01 per page                                           |       |
|   |                                                                         |       |
|   |  Input:  Candidate URLs from Stage 1                                   |       |
|   |  Action: Extract website content, company info, products               |       |
|   |  Output: Structured company data (name, desc, products, size)          |       |
|   |                                                                         |       |
|   +=========================================================================+       |
|        |                                                                            |
|        v  (enriched candidate data)                                                 |
|   +=========================================================================+       |
|   | STAGE 3: QUALIFY                                        ~30s timeout    |       |
|   |-------------------------------------------------------------------------|       |
|   |                                                                         |       |
|   |  Provider: Claude Opus 4.5 (via AIRouter primary)                      |       |
|   |  Cost: ~$0.01-$0.05 per candidate                                     |       |
|   |                                                                         |       |
|   |  Input:  Scraped data + qualification criteria                         |       |
|   |  Action: Score each candidate against criteria (0-100)                 |       |
|   |  Output: Qualification scores + match assessments                      |       |
|   |                                                                         |       |
|   |  Scoring Dimensions:                                                   |       |
|   |    - Market segment alignment                                          |       |
|   |    - Product capability overlap                                        |       |
|   |    - Geographic presence                                               |       |
|   |    - Company size/funding match                                        |       |
|   |    - Competitive threat potential                                      |       |
|   |                                                                         |       |
|   +=========================================================================+       |
|        |                                                                            |
|        v  (qualified candidates with scores)                                        |
|   +=========================================================================+       |
|   | STAGE 4: ANALYZE                                        ~30s timeout    |       |
|   |-------------------------------------------------------------------------|       |
|   |                                                                         |       |
|   |  Provider: Claude Opus 4.5                                             |       |
|   |  Cost: ~$0.02-$0.10 per candidate                                     |       |
|   |                                                                         |       |
|   |  Input:  Qualified candidates + existing competitor DB                 |       |
|   |  Action: Deep competitive analysis & threat assessment                 |       |
|   |  Output: Threat level, positioning, strategic insights                 |       |
|   |                                                                         |       |
|   +=========================================================================+       |
|        |                                                                            |
|        v                                                                            |
|   +-----------------------------+    +----------------------------------+           |
|   | Results Grid (Frontend)     |    | Actions Available                |           |
|   |-----------------------------|    |----------------------------------|           |
|   | Score | Name | Assessment   |    | - Send to Battlecards            |           |
|   | 95    | Acme | High Match   |    | - Send to Comparison             |           |
|   | 82    | Beta | Good Match   |    | - Add as Competitor              |           |
|   | 71    | Corp | Partial      |    | - Generate Executive Summary     |           |
|   +-----------------------------+    | - Save Discovery Profile         |           |
|                                      +----------------------------------+           |
|                                                                                     |
+=====================================================================================+
```

---

## NEWS MONITORING PIPELINE

```
+=====================================================================================+
|                          NEWS MONITORING SYSTEM                                      |
|               news_monitor.py (35 KB) | comprehensive_news_scraper.py (21 KB)       |
+=====================================================================================+
|                                                                                     |
|   TRIGGER: APScheduler (periodic) or Manual Refresh                                 |
|        |                                                                            |
|        v                                                                            |
|   +-----------------------------------------------------------------+               |
|   |  PARALLEL FETCH (ThreadPoolExecutor - 10 workers)               |               |
|   |  fetch_news_async() with asyncio.gather()                       |               |
|   |  ~8 seconds for all 74 competitors (vs ~50s sequential)         |               |
|   +-----------------------------------------------------------------+               |
|        |                                                                            |
|        +------+------+------+------+------+------+                                  |
|        |      |      |      |      |      |      |                                  |
|        v      v      v      v      v      v      v                                  |
|                                                                                     |
|  +----------+ +----------+ +----------+ +----------+ +----------+ +----------+      |
|  | Google   | | NewsAPI  | |Bing News | |  GNews   | |MediaStack| |NewsData  |      |
|  | News RSS | | (500/day)| |(1K/mo)   | |          | |          | |   .io    |      |
|  +----------+ +----------+ +----------+ +----------+ +----------+ +----------+      |
|                                                                                     |
|        |  (raw articles)                                                            |
|        v                                                                            |
|   +-----------------------------------------------------------------+               |
|   |  SMART SEARCH QUERY CONSTRUCTION                                |               |
|   |-----------------------------------------------------------------|               |
|   |                                                                 |               |
|   |  Generic names (e.g., "Access", "Unity"):                      |               |
|   |    '"Access" healthcare OR "accessefm.com"'                    |               |
|   |                                                                 |               |
|   |  Specific names (e.g., "Epic Systems"):                        |               |
|   |    '"Epic Systems" healthcare'                                  |               |
|   |                                                                 |               |
|   +-----------------------------------------------------------------+               |
|        |                                                                            |
|        v                                                                            |
|   +-----------------------------------------------------------------+               |
|   |  RELEVANCE FILTER (_filter_irrelevant_articles)                 |               |
|   |-----------------------------------------------------------------|               |
|   |                                                                 |               |
|   |  Tier 1: Domain check (single-word generic names)              |               |
|   |    - Requires company domain in article text                   |               |
|   |                                                                 |               |
|   |  Tier 2: Healthcare keyword check                              |               |
|   |    - Must contain healthcare-related terms                     |               |
|   |    - OR be a major corporate event (funding, acquisition)      |               |
|   |                                                                 |               |
|   |  Result: 920 active / 1,951 archived from 2,871 total          |               |
|   +-----------------------------------------------------------------+               |
|        |                                                                            |
|        v                                                                            |
|   +-----------------------------------------------------------------+               |
|   |  AI CLASSIFICATION (Gemini 3-Flash)                             |               |
|   |-----------------------------------------------------------------|               |
|   |                                                                 |               |
|   |  Sentiment:   positive | negative | neutral                    |               |
|   |  Event Type:  funding | acquisition | partnership | product    |               |
|   |               | legal | executive | expansion | other          |               |
|   |  Dimensions:  Maps to 9 sales & marketing dimensions           |               |
|   |                                                                 |               |
|   +-----------------------------------------------------------------+               |
|        |                                                                            |
|        v                                                                            |
|   +--------------------+                                                            |
|   | NewsArticleCache   |   Stored in database with full metadata                    |
|   | (920 active)       |   WebSocket push to connected clients                      |
|   +--------------------+                                                            |
|                                                                                     |
+=====================================================================================+
```

---

## DESKTOP APPLICATION (Electron + PyInstaller)

```
+=====================================================================================+
|                        DESKTOP APP ARCHITECTURE                                      |
|                    Electron + PyInstaller | Windows .exe                              |
+=====================================================================================+
|                                                                                     |
|   +-------------------------------------------------------------------------+       |
|   |                    ELECTRON MAIN PROCESS (main.js - 27 KB)              |       |
|   |-------------------------------------------------------------------------|       |
|   |                                                                         |       |
|   |  App Startup Sequence:                                                  |       |
|   |                                                                         |       |
|   |  1. Clear Electron cache (stale code prevention)                       |       |
|   |  2. Spawn backend process (certify_backend.exe)                        |       |
|   |  3. Health check loop (GET http://localhost:8000/health)               |       |
|   |  4. Create BrowserWindow -> file:///frontend/index.html                |       |
|   |  5. Check for auto-updates (GitHub releases)                           |       |
|   |  6. Initialize tray icon                                               |       |
|   |                                                                         |       |
|   +-------------------------------------------------------------------------+       |
|        |                        |                          |                        |
|        v                        v                          v                        |
|  +----------------+   +--------------------+   +------------------------+           |
|  | RENDERER       |   | BACKEND BUNDLE     |   | AUTO-UPDATER           |           |
|  | PROCESS        |   | (PyInstaller)      |   | (electron-updater)     |           |
|  |----------------|   |--------------------|   |------------------------|           |
|  |                |   |                    |   |                        |           |
|  | BrowserWindow  |   | certify_backend    |   | Polls GitHub Releases  |           |
|  | loads frontend/|   |   .exe             |   | Downloads new .exe     |           |
|  | index.html     |   |                    |   | Installs on next       |           |
|  |                |   | certify_intel.db   |   |   restart              |           |
|  | Same SPA as    |   | (bundled database) |   |                        |           |
|  | web version    |   |                    |   | Requires 3 files:      |           |
|  |                |   | .env (API keys)    |   |  - Setup.exe           |           |
|  | file:// proto  |   |                    |   |  - .blockmap           |           |
|  | (not http://)  |   | Runs on port 8000  |   |  - latest.yml          |           |
|  +----------------+   +--------------------+   +------------------------+           |
|                                                                                     |
|   INSTALLATION LAYOUT (Windows)                                                     |
|   ==============================                                                    |
|                                                                                     |
|   C:\Users\{user}\AppData\Local\Programs\Certify Intel\                            |
|      +-- Certify Intel.exe          (Electron shell)                               |
|      +-- resources\                                                                 |
|      |     +-- frontend\             (SPA files)                                    |
|      |     +-- backend-bundle\       (Python backend)                               |
|      +-- locales\                    (i18n)                                         |
|                                                                                     |
|   C:\Users\{user}\AppData\Roaming\Certify Intel\                                   |
|      +-- config.json                 (user settings)                                |
|      +-- logs\                       (app logs)                                     |
|                                                                                     |
+=====================================================================================+
```

---

## SECURITY ARCHITECTURE

```
+=====================================================================================+
|                           SECURITY LAYERS                                            |
+=====================================================================================+
|                                                                                     |
|   LAYER 1: AUTHENTICATION                                                           |
|   +-----------------------------------------------------------------+               |
|   |  JWT Token Flow                                                 |               |
|   |                                                                 |               |
|   |  Login (POST /token)                                           |               |
|   |     |                                                          |               |
|   |     v                                                          |               |
|   |  PBKDF2-HMAC-SHA256 password verification                     |               |
|   |     |                                                          |               |
|   |     v                                                          |               |
|   |  JWT token generated (24-hour expiry)                          |               |
|   |     |                                                          |               |
|   |     v                                                          |               |
|   |  Stored in localStorage (frontend)                             |               |
|   |     |                                                          |               |
|   |     v                                                          |               |
|   |  Every API call: Authorization: Bearer {token}                 |               |
|   |     |                                                          |               |
|   |     v                                                          |               |
|   |  Backend: Depends(get_current_user) validates on each request  |               |
|   +-----------------------------------------------------------------+               |
|                                                                                     |
|   LAYER 2: INPUT SANITIZATION (input_sanitizer.py - 17 KB)                          |
|   +-----------------------------------------------------------------+               |
|   |                                                                 |               |
|   |  +-- SQL Injection Detection                                   |               |
|   |  |     UNION SELECT, DROP TABLE, exec(), 1=1, etc.            |               |
|   |  |                                                             |               |
|   |  +-- XSS Prevention                                           |               |
|   |  |     <script>, onerror=, javascript:, HTML entity encoding  |               |
|   |  |     Frontend: escapeHtml() for all dynamic innerHTML       |               |
|   |  |                                                             |               |
|   |  +-- Prompt Injection Filtering                                |               |
|   |  |     "ignore instructions", "act as", "roleplay", etc.     |               |
|   |  |                                                             |               |
|   |  +-- Path Traversal Protection                                 |               |
|   |  |     ../../../, /etc/passwd, C:\Windows\, /proc/            |               |
|   |  |                                                             |               |
|   |  +-- Command Injection Protection                              |               |
|   |        rm -rf, wget|bash, $(cmd), backtick evaluation         |               |
|   +-----------------------------------------------------------------+               |
|                                                                                     |
|   LAYER 3: AI HALLUCINATION PREVENTION                                              |
|   +-----------------------------------------------------------------+               |
|   |                                                                 |               |
|   |  NO_HALLUCINATION_INSTRUCTION prepended to ALL AI prompts:     |               |
|   |                                                                 |               |
|   |  "CRITICAL DATA INTEGRITY RULE: You must ONLY reference        |               |
|   |   data provided in this context. Do NOT fabricate, estimate,   |               |
|   |   or assume any data points. If data is not available, state   |               |
|   |   'No verified data available for this metric.'"               |               |
|   |                                                                 |               |
|   |  + Citation Validator agent checks every AI response           |               |
|   |  + Confidence scores attached to each data point               |               |
|   +-----------------------------------------------------------------+               |
|                                                                                     |
|   LAYER 4: DATA INTEGRITY                                                           |
|   +-----------------------------------------------------------------+               |
|   |  - ChangeLog tracks ALL data modifications (old/new values)    |               |
|   |  - ActivityLog records user actions (audit trail)              |               |
|   |  - DataSource provides provenance for every fact               |               |
|   |  - Confidence scoring (0-100) on all data points               |               |
|   |  - Source verification with clickable URLs                     |               |
|   +-----------------------------------------------------------------+               |
|                                                                                     |
+=====================================================================================+
```

---

## BACKGROUND TASK SYSTEM

```
+=====================================================================================+
|                       BACKGROUND TASK ARCHITECTURE                                   |
+=====================================================================================+
|                                                                                     |
|   +-------------------------------------------+                                    |
|   |  IN-MEMORY TASK REGISTRY (_ai_tasks dict) |                                    |
|   |-------------------------------------------|                                    |
|   |                                           |                                    |
|   |  task_id -> {                             |                                    |
|   |    status: "running" | "completed",       |                                    |
|   |    progress: 0-100,                       |                                    |
|   |    result: {...},                         |                                    |
|   |    created_at: timestamp,                 |                                    |
|   |    completed_at: timestamp                |                                    |
|   |  }                                        |                                    |
|   |                                           |                                    |
|   |  Auto-prune: 1 hour after completion      |                                    |
|   +-------------------------------------------+                                    |
|                                                                                     |
|   TASK TYPES & TIMEOUTS                                                             |
|                                                                                     |
|   +-----------------------+----------+----------------------------------+           |
|   | Task                  | Timeout  | Provider                         |           |
|   |-----------------------|----------|----------------------------------|           |
|   | Discovery Pipeline    | 120s     | Gemini (search) + Claude (qual)  |           |
|   | Batch Verification    | 45s/each | Gemini Pro (grounded search)     |           |
|   | Full Scrape/Refresh   | 300s     | Multiple news APIs               |           |
|   | Battlecard Generation | 45s      | Claude Opus 4.5                  |           |
|   | Dashboard Summary     | 45s      | Claude Opus 4.5                  |           |
|   | News Fetch (bulk)     | 120s     | News APIs + Gemini (classify)    |           |
|   | Executive Summary     | 45s      | Claude Opus 4.5                  |           |
|   +-----------------------+----------+----------------------------------+           |
|                                                                                     |
|   FRONTEND POLLING PATTERN (Tab-Resilient)                                          |
|                                                                                     |
|   +-----------------------------------------------+                                |
|   |  1. Start task -> store task_id in localStorage|                                |
|   |  2. Set global polling flag = true             |                                |
|   |  3. while (polling) {                          |                                |
|   |       GET /api/ai/tasks/{id}                   |                                |
|   |       if (completed) break;                    |                                |
|   |       update progress UI                       |                                |
|   |       await sleep(1000);                       |                                |
|   |     }                                          |                                |
|   |  4. On page navigation:                        |                                |
|   |     - Polling continues (global state)         |                                |
|   |     - DOM updates guarded by getElementById    |                                |
|   |  5. On page return:                            |                                |
|   |     - resume*IfRunning() checks localStorage   |                                |
|   |     - Re-attaches to running poll              |                                |
|   +-----------------------------------------------+                                |
|                                                                                     |
+=====================================================================================+
```

---

## COMPLETE DATA FLOW DIAGRAM

```
+=====================================================================================+
|                          END-TO-END DATA FLOW                                        |
+=====================================================================================+

    USER (Browser / Desktop App)
      |
      |  1. Login: POST /token
      |  2. JWT stored in localStorage
      |  3. All requests include: Authorization: Bearer {jwt}
      |
      v
+------------------+
|   FRONTEND SPA   |    fetchAPI() -> ${API_BASE}/api/...
|   (app_v2.js)    |    WebSocket: /ws/updates, /ws/refresh-progress
+------------------+
      |
      |  HTTP JSON / WebSocket
      |
      v
+------------------+      +------------------+      +------------------+
|   FASTAPI        |      |   AI ROUTER      |      |   AI PROVIDERS   |
|   BACKEND        |----->|   (ai_router.py) |----->|                  |
|   (main.py)      |      |                  |      |  Claude Opus 4.5 |
|                  |      |  Task classify   |      |  GPT-4o          |
|  100+ endpoints  |      |  Model select    |      |  Gemini Flash/Pro|
|  JWT validation  |      |  Cost track      |      |  DeepSeek v3.2   |
|  Input sanitize  |      |  Budget enforce  |      |                  |
+------------------+      +------------------+      +------------------+
      |                                                    |
      |                                                    |
      v                                                    v
+------------------+      +------------------+      +------------------+
|   DATABASE       |      | LANGGRAPH AGENTS |      | EXTERNAL DATA    |
|   (SQLAlchemy)   |<-----|                  |----->|                  |
|                  |      | Orchestrator     |      | Google News RSS  |
|  28+ tables      |      |   +-- Dashboard  |      | NewsAPI          |
|  74 competitors  |      |   +-- Discovery  |      | SEC EDGAR        |
|  789 products    |      |   +-- Battlecard |      | USPTO            |
|  920 news        |      |   +-- News       |      | Firecrawl        |
|  512 sources     |      |   +-- Analytics  |      | Bing News        |
|                  |      |   +-- Validation |      |                  |
|  SQLite (dev)    |      |   +-- Records    |      |                  |
|  PostgreSQL(prod)|      |   +-- Citation   |      |                  |
+------------------+      +------------------+      +------------------+
      |
      |
      v
+------------------+
| PERSISTENT CACHE |   Discovery results, AI summaries,
| (PersistentCache)|   Dashboard data - survives restart
+------------------+


          REAL-TIME UPDATE FLOW
          =====================

  Backend Event (new data, task complete)
       |
       v
  WebSocket broadcast to /ws/updates
       |
       v
  Frontend handler: handleWebSocketMessage()
       |
       +-- competitor_update -> refresh competitor grid
       +-- news_update -> refresh news feed
       +-- refresh_progress -> update progress bar
       +-- task_complete -> show notification toast
```

---

## BUILD & DEPLOYMENT PIPELINE

```
+=====================================================================================+
|                        BUILD & DEPLOYMENT PIPELINE                                   |
+=====================================================================================+

  DEVELOPMENT WORKFLOW
  ====================

  Developer edits code
       |
       v
  +------------------+     +------------------+     +------------------+
  |  LOCAL DEV       |     |  GIT PUSH        |     |  GITHUB ACTIONS  |
  |  python main.py  |---->|  git push origin |---->|  CI/CD Pipeline  |
  |  localhost:8000   |     |  master          |     |                  |
  +------------------+     +------------------+     +------------------+
                                                          |
                                                          v
                                                    +------------------+
                                                    | AUTOMATED TESTS  |
                                                    |  368 tests       |
                                                    |  pytest + flake8 |
                                                    +------------------+
                                                          |
                                                     Pass | Fail
                                                          |
                                              +-----------+-----------+
                                              |                       |
                                              v                       v
                                    +------------------+    +------------------+
                                    | AUTO-CREATE PR   |    | NOTIFY DEVELOPER |
                                    | (feature branch) |    | (fix & re-push)  |
                                    +------------------+    +------------------+
                                              |
                                              v
                                    +------------------+
                                    | AUTO-MERGE       |
                                    | (if auto-pr tag) |
                                    +------------------+


  DESKTOP APP BUILD (11-Step Protocol)
  =====================================

  +--------+    +--------+    +--------+    +--------+
  | Step 1 |    | Step 2 |    | Step 3 |    | Step 4 |
  | Bump   |--->| Sync   |--->| Kill   |--->| Clear  |
  | Version|    | Front  |    | Procs  |    | Cache  |
  | 6 files|    | ->Desk |    | Clean  |    | ALL    |
  +--------+    +--------+    +--------+    +--------+
                                                |
                                                v
  +--------+    +--------+    +--------+    +--------+
  | Step 5 |    | Step 6 |    | Step 7 |    | Step 8 |
  | Verify |<---| Build  |<---| Copy   |<---| Build  |
  | Source |    | PyInst |    | Backend|    | Electrn|
  | Files  |    | .exe   |    | Bundle |    | .exe   |
  +--------+    +--------+    +--------+    +--------+
       |
       v
  +--------+    +--------+    +--------+
  | Step 9 |    | Step 10|    | Step 11|
  | Verify |--->| Report |--->| Git    |
  | Built  |    | Install|    | Tag    |
  | Output |    | Path   |    | Release|
  +--------+    +--------+    +--------+
                                   |
                                   v
                            +------------------+
                            | GITHUB RELEASE   |
                            |                  |
                            | Setup.exe        |
                            | .blockmap        |
                            | latest.yml       |
                            +------------------+
                                   |
                                   v
                            +------------------+
                            | AUTO-UPDATE      |
                            | Desktop clients  |
                            | pull new version |
                            +------------------+
```

---

## TECHNOLOGY STACK SUMMARY

```
+=====================================================================================+
|                           TECHNOLOGY STACK                                            |
+=====================================================================================+
|                                                                                     |
|  BACKEND                           FRONTEND                                         |
|  ================================  ================================                  |
|  Python 3.9+                       HTML5 / CSS3 / ES6+ JavaScript                   |
|  FastAPI + Uvicorn                 Single Page Application (SPA)                    |
|  SQLAlchemy ORM (2.0)             Chart.js (visualizations)                         |
|  SQLite (dev) / PostgreSQL (prod)  Service Worker (offline PWA)                     |
|  Anthropic SDK (Claude)           Glassmorphism dark theme                          |
|  OpenAI SDK (GPT-4o)              Responsive: 1920/1366/768px                       |
|  Google GenAI SDK (Gemini)                                                          |
|  LangGraph (agent orchestration)   DESKTOP APP                                      |
|  APScheduler (background jobs)     ================================                  |
|  ReportLab / WeasyPrint (PDF)     Electron (Chromium shell)                         |
|  python-jose (JWT)                 electron-builder (packaging)                     |
|  PBKDF2-HMAC-SHA256 (passwords)   PyInstaller (Python -> .exe)                     |
|  Langfuse (observability)          electron-updater (auto-update)                   |
|  pgvector (vector embeddings)      Sentry (crash reporting)                         |
|                                                                                     |
|  EXTERNAL SERVICES                 DEV / OPS                                         |
|  ================================  ================================                  |
|  Anthropic API (Claude Opus 4.5)  GitHub (source + releases)                        |
|  OpenAI API (GPT-4o)             GitHub Actions (CI/CD)                             |
|  Google AI API (Gemini 3)         pytest (368 tests, 8 skipped)                     |
|  DeepSeek API (v3.2)             flake8 (linting)                                  |
|  Firecrawl (web scraping)        Docker (production deploy)                         |
|  Google News RSS                  Langfuse (AI tracing)                             |
|  NewsAPI, Bing News, GNews       Let's Encrypt (SSL/TLS)                            |
|  SEC EDGAR, USPTO                                                                    |
|                                                                                     |
+=====================================================================================+
```

---

## KEY METRICS AT A GLANCE

```
+=====================================================================================+
|                              SYSTEM METRICS                                          |
+=====================================================================================+
|                                                                                     |
|  CODEBASE SIZE                         DATA COVERAGE                                |
|  ==================                    ==================                           |
|  main.py:          13,400+ lines       Competitors:    74 active                    |
|  app_v2.js:        795 KB              Products:       789 (100%)                   |
|  styles.css:       289 KB              News Articles:  920 active                   |
|  index.html:       213 KB              Data Sources:   512 (86% verified)           |
|  database.py:      1,547 lines         DB Tables:      28+                          |
|  Total agents:     ~200 KB             System Prompts: 41 (6 categories)            |
|                                                                                     |
|  API SURFACE                           TEST COVERAGE                                |
|  ==================                    ==================                           |
|  REST Endpoints:   100+                Tests Passing:  368                           |
|  WebSocket Ch.:    2                   Tests Skipped:  8                             |
|  Frontend Pages:   11                  Test Files:     15+                           |
|  AI Agents:        8 + orchestrator    CI/CD:          GitHub Actions                |
|  AI Providers:     5 models            Linting:        flake8 (120 char)            |
|                                                                                     |
|  PERFORMANCE                           COST MANAGEMENT                              |
|  ==================                    ==================                           |
|  News fetch:       ~8s (74 competitors) Daily budget:  $50 default                  |
|  Discovery:        ~120s (full pipeline) Cheapest:     Gemini Flash $0.50/1M        |
|  Page load:        <2s (cached)         Expensive:    Claude Opus $75/1M out        |
|  Service worker:   Offline capable      Fallback:     Auto-downgrade on budget      |
|                                                                                     |
+=====================================================================================+
```

---

*Generated February 12, 2026 | Certify Intel v8.1.0*
