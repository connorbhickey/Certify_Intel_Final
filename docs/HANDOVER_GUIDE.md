# Certify Intel v8.2.0 - Client Handover Guide

## Table of Contents

1. [Project Overview](#project-overview)
2. [Technology Stack](#technology-stack)
3. [Getting Started](#getting-started)
4. [Environment Variables](#environment-variables)
5. [Default Credentials](#default-credentials)
6. [Running the Application](#running-the-application)
7. [AI Provider Configuration](#ai-provider-configuration)
8. [Database Management](#database-management)
9. [Feature Overview](#feature-overview)
10. [Desktop Application](#desktop-application)
11. [Testing](#testing)
12. [Observability & Monitoring](#observability--monitoring)
13. [Backup & Recovery](#backup--recovery)
14. [Troubleshooting](#troubleshooting)
15. [Support & Maintenance](#support--maintenance)

---

## Project Overview

Certify Intel is a production-ready Competitive Intelligence Platform designed to track, analyze, and counter competitors in the healthcare technology space.

**Current State:**
- 74 active competitors tracked (115+ data fields each)
- 789 products catalogued across all competitors
- 920 active news articles with AI sentiment analysis
- 512 data sources (86% verified)
- 7 AI agents for automated intelligence gathering
- 11 frontend pages covering all competitive intelligence workflows

**Version:** v8.2.0 (February 2026)

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend** | FastAPI (Python 3.9+) | REST API with 100+ endpoints |
| **Database** | SQLite (dev) / PostgreSQL (prod) | 24+ tables, SQLAlchemy 2.0 ORM |
| **AI Primary** | Anthropic Claude Opus 4.5 | Complex analysis, strategy, reasoning |
| **AI Fallback** | OpenAI GPT-4o | Secondary provider for reliability |
| **AI Bulk** | Google Gemini 3 Flash | Chat, summarization, classification |
| **AI Quality** | Google Gemini 3 Pro | Grounded search, deep research |
| **AI Optional** | Google Vertex AI | Enterprise GCP integration |
| **AI Optional** | DeepSeek V3.2 | Budget-friendly bulk tasks |
| **Orchestration** | LangGraph | 7-agent StateGraph routing |
| **Vector Store** | PostgreSQL + pgvector | RAG pipeline, semantic search |
| **Frontend** | Vanilla JavaScript SPA | Single-page app, Chart.js |
| **Desktop** | Electron + PyInstaller | Windows installer with auto-update |
| **Scheduling** | APScheduler | Background task automation |
| **Observability** | Langfuse (optional) | AI trace monitoring, cost tracking |

---

## Getting Started

### Prerequisites

- Python 3.9 or higher
- Node.js 18+ (for desktop app builds only)
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/[YOUR-GITHUB-ORG]/Project_Intel_v6.1.1.git
cd Project_Intel_v6.1.1

# Set up Python virtual environment
cd backend
python -m venv venv

# Activate virtual environment
# Windows:
.\venv\Scripts\Activate.ps1
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your API keys (see Environment Variables section)

# Start the server
python main.py
```

The application will be available at **http://localhost:8000**.

---

## Environment Variables

Create a `backend/.env` file with the following variables:

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | JWT signing key (32+ chars) | `your-secret-key-change-in-production` |

### AI Providers

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Claude API key (primary AI) | — |
| `OPENAI_API_KEY` | OpenAI API key (fallback) | — |
| `OPENAI_MODEL` | OpenAI model ID | `gpt-4.1` |
| `GOOGLE_AI_API_KEY` | Google Gemini API key (bulk/cheap) | — |
| `GOOGLE_AI_MODEL` | Default Gemini model | `gemini-3-flash-preview` |
| `DEEPSEEK_API_KEY` | DeepSeek API key (optional) | — |

### AI Routing

| Variable | Description | Default |
|----------|-------------|---------|
| `AI_PROVIDER` | Routing strategy | `hybrid` |
| `AI_BULK_TASKS` | Provider for bulk operations | `gemini` |
| `AI_QUALITY_TASKS` | Provider for complex analysis | `anthropic` |
| `AI_FALLBACK_ENABLED` | Enable provider fallback chain | `true` |
| `AI_DAILY_BUDGET_USD` | Daily AI spend limit | `50.0` |

### Vertex AI (Optional - Enterprise GCP)

| Variable | Description | Default |
|----------|-------------|---------|
| `VERTEX_AI_ENABLED` | Enable Vertex AI provider | `false` |
| `GOOGLE_CLOUD_PROJECT` | GCP project ID | — |
| `GOOGLE_CLOUD_LOCATION` | GCP region | `us-central1` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account JSON | — |

### Database

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Sync database URL | `sqlite:///./certify_intel.db` |
| `DATABASE_URL_ASYNC` | Async database URL (PostgreSQL) | — |
| `DB_POOL_SIZE` | Connection pool size | `10` |
| `DB_MAX_OVERFLOW` | Max overflow connections | `20` |
| `DB_POOL_TIMEOUT` | Pool timeout (seconds) | `30` |
| `DB_ECHO` | Log SQL queries | `false` |

### Observability (Optional)

| Variable | Description | Default |
|----------|-------------|---------|
| `ENABLE_LANGFUSE` | Enable Langfuse tracing | `false` |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public API key | — |
| `LANGFUSE_SECRET_KEY` | Langfuse secret API key | — |
| `LANGFUSE_HOST` | Langfuse server URL | `http://localhost:3000` |

### Optional Features

| Variable | Description | Default |
|----------|-------------|---------|
| `SMTP_HOST` | SMTP server for email alerts | — |
| `SMTP_PORT` | SMTP port | `587` |
| `SMTP_USER` | SMTP username | — |
| `SMTP_PASSWORD` | SMTP password | — |
| `SLACK_WEBHOOK_URL` | Slack notification webhook | — |

---

## Default Credentials

### Admin Account

| Field | Value |
|-------|-------|
| Email | `[YOUR-ADMIN-EMAIL]` |
| Password | `[YOUR-ADMIN-PASSWORD]` |

### Changing the Admin Password

1. Log in with the default credentials
2. Navigate to **Settings** page
3. Use the account management section to update your password

Alternatively, create a new admin user and deactivate the default:

```bash
# Via API
curl -X POST http://localhost:8000/api/users/invite \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"email": "your@email.com", "full_name": "Your Name", "role": "admin"}'
```

### User Roles

| Role | Permissions |
|------|------------|
| `admin` | Full access: manage users, edit competitors, trigger refreshes, configure AI |
| `analyst` | Read/write: edit competitors, run analyses, export data |
| `viewer` | Read-only: view dashboards, reports, and analytics |

---

## Running the Application

### Web Application (Development)

```bash
cd backend
python main.py
```

Open http://localhost:8000 in your browser.

### Web Application (Production)

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Desktop Application (Windows)

1. Download the latest installer from GitHub Releases
2. Run `Certify_Intel_v8.2.0_Setup.exe`
3. The app starts the backend automatically and opens in a native window

### Docker (Production)

```bash
# Start all services
docker-compose -f docker-compose.prod.yml up -d

# With PostgreSQL + pgvector
docker-compose -f docker-compose.postgres.yml up -d
```

---

## AI Provider Configuration

### Model Routing Strategy

The AI router automatically selects the best model for each task type:

| Task Type | Default Model | Cost (per 1M tokens) |
|-----------|--------------|---------------------|
| Chat, Summarization, RAG | Gemini 3 Flash | $0.50 / $3.00 |
| Classification, Bulk Extraction | Gemini 3 Flash | $0.50 / $3.00 |
| Grounded Search, Deep Research | Gemini 3 Pro | $2.00 / $12.00 |
| Analysis, Strategy, Battlecards | Claude Opus 4.5 | $15.00 / $75.00 |
| Complex Reasoning, Discovery | Claude Opus 4.5 | $15.00 / $75.00 |

### Fallback Chain

If the primary provider fails, the system automatically falls back:

```
Claude Opus 4.5 → GPT-4o → Gemini 3 Flash → Error
```

### Budget Control

- Default daily budget: $50 USD
- Budget is tracked per model, per task type
- When 80% of budget is consumed, a warning appears in `/api/ai/status`
- Exceeding budget blocks new AI requests until the next day

### Checking Provider Status

```
GET /api/ai/status          # Provider availability + budget
GET /api/discovery/provider-status  # Detailed provider diagnostics
GET /api/observability/status       # Langfuse tracing status
```

---

## Database Management

### SQLite (Default - Development)

The application uses SQLite by default. The database file is `backend/certify_intel.db`.

- No setup required - auto-created on first run
- Tables are created automatically from ORM models
- Schema migrations run on startup via `init_db()` in `main.py`

### PostgreSQL (Production)

For production deployments with full RAG/vector search capabilities:

```bash
# Start PostgreSQL with pgvector
docker-compose -f docker-compose.postgres.yml up -d

# Update .env
DATABASE_URL=postgresql://certify:certify@localhost:5432/certify_intel
DATABASE_URL_ASYNC=postgresql+asyncpg://certify:certify@localhost:5432/certify_intel
```

### Backups

```bash
# Create backup via API
POST /api/backup/create

# List backups
GET /api/backup/list

# Restore from backup
POST /api/backup/restore/{filename}
```

### Database Schema

24+ tables organized into domains:

- **Core**: Competitor (115+ fields), ChangeLog, DataSource, RefreshSession
- **Products**: CompetitorProduct, ProductPricingTier, ProductFeatureMatrix, CustomerCountEstimate
- **Sales**: Battlecard, TalkingPoint, CompetitorDimensionHistory, DimensionNewsTag, WinLossDeal
- **Users**: User, UserSettings, UserSavedPrompt, SystemPrompt (41 seeded prompts)
- **Intelligence**: KnowledgeBaseItem, KBEntityLink, KBDataExtraction, DiscoveryProfile
- **Collaboration**: Team, TeamMembership, CompetitorAnnotation, AnnotationReply
- **News**: NewsArticleCache, CompetitorSubscription
- **Chat**: ChatSession, ChatMessage
- **System**: SystemSetting, ActivityLog, WebhookConfig, PersistentCache, DashboardConfiguration

---

## Feature Overview

### 1. Dashboard

The main landing page with an AI-generated executive summary, threat statistics, recent changes, and news highlights.

- Real-time threat distribution (High/Medium/Low)
- AI-generated summary of competitive landscape
- Threat level trend chart (90-day rolling)
- Quick access to top competitors

### 2. Competitors

Full CRUD management for all tracked competitors with 115+ data fields per competitor.

- Grid and list views with filtering and sorting
- Quick detail panels with key metrics
- Bulk operations (update, delete, refresh)
- Data correction with audit trail

### 3. Discovery Scout

AI-driven competitor discovery pipeline that finds and qualifies new competitors.

- 4-stage pipeline: Search, Qualify, Analyze, Summarize
- Configurable qualification criteria and profiles
- Real-time progress tracking with background operation
- Send results directly to Battlecards or Comparisons

### 4. Battlecards

Sales-ready one-page battlecards with AI-generated content and data verification.

- AI-generated competitive positioning
- Clickable source links with verification status
- PDF export capability
- Version history

### 5. Comparisons

Side-by-side comparison of 2-4 competitors across all dimensions.

- Feature matrix comparison
- Product and pricing comparison
- Dimension score radar chart
- Export as PDF report

### 6. Sales & Marketing

9-dimension competitive scoring system with talking points and playbook generation.

- 9 competitive dimensions (1-5 scoring)
- Radar chart visualization
- AI-generated talking points per dimension
- Sales playbook generator with deal context

### 7. News Feed

Real-time news monitoring with AI sentiment analysis and healthcare relevance filtering.

- Aggregated from Google News RSS and other sources
- AI classification (sentiment, event type)
- Healthcare relevance filtering (removes noise)
- Competitor-specific news views

### 8. Analytics

Market analysis dashboards with charts and trend visualization.

- Market position quadrant chart
- Threat trend analysis
- Sentiment trends over time
- Growth and activity trends

### 9. Records

Data change tracking with full audit trail.

- All changes logged with old/new values
- Field-level history per competitor
- Rollback capability for erroneous changes
- Bulk export of change history

### 10. Validation

Data quality management with confidence scoring.

- Admiralty Code confidence scoring (A-F reliability, 1-6 credibility)
- AI-powered batch verification using Gemini grounded search
- Source triangulation across multiple data sources
- Low-confidence alert dashboard

### 11. Settings

Application configuration and user preferences.

- User account management
- AI provider status and configuration
- Notification preferences
- Schedule configuration
- Prompt management (41 system prompts, user-customizable)

---

## Desktop Application

### Building the Desktop App

The desktop app bundles the FastAPI backend (via PyInstaller) with an Electron frontend. See the 11-step build protocol in the root `CLAUDE.md` file.

### Auto-Updates

The desktop app supports auto-updates via GitHub Releases. Three files are required for each release:

1. `Certify_Intel_vX.X.X_Setup.exe` - The installer
2. `Certify_Intel_vX.X.X_Setup.exe.blockmap` - Differential update data
3. `latest.yml` - Version manifest for update checking

### Version Files

Version must be consistent across 6 files:

| File | Field |
|------|-------|
| `backend/main.py` | `__version__ = "X.X.X"` |
| `frontend/index.html` | `<span class="app-version">vX.X.X</span>` |
| `desktop-app/frontend/index.html` | `<span class="app-version">vX.X.X</span>` |
| `desktop-app/package.json` | `"version": "X.X.X"` |
| `frontend/service-worker.js` | `const CACHE_VERSION = 'vX.X.X'` |
| `desktop-app/frontend/service-worker.js` | `const CACHE_VERSION = 'vX.X.X'` |

---

## Testing

### Running Tests

```bash
cd backend

# Full CI-safe test suite (no API keys needed)
python -m pytest -x --tb=short --ignore=tests/test_all_endpoints.py --ignore=tests/test_e2e.py

# Specific test files
python -m pytest -xvs tests/test_api_endpoints.py
python -m pytest -xvs tests/test_ai_router.py
python -m pytest -xvs tests/test_hallucination_prevention.py
python -m pytest -xvs tests/test_cost_comparison.py
python -m pytest -xvs tests/test_sales_marketing.py

# Linting
python -m flake8 --max-line-length=120 main.py ai_router.py agents/
```

### Test Coverage

- **368 tests passing, 8 skipped** across 10+ test files
- CI-safe tests require no API keys or running server
- `test_all_endpoints.py` and `test_e2e.py` require a running server

### E2E Tests

End-to-end tests require the server to be running:

```bash
# Terminal 1: Start server
cd backend && python main.py

# Terminal 2: Run E2E tests
cd backend && python -m pytest tests/test_e2e.py -xvs
```

---

## Observability & Monitoring

### Langfuse (Optional)

Langfuse provides AI observability - tracing every LLM call with cost, latency, and token usage.

```bash
# Start Langfuse (self-hosted)
docker-compose -f docker-compose.langfuse.yml up -d

# Access dashboard
open http://localhost:3000

# Create account (first user becomes admin)
# Get API keys from Settings -> API Keys

# Add to backend/.env
ENABLE_LANGFUSE=true
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

When enabled, every AI generation call is traced with:
- Model used and provider
- Token count (input/output)
- Cost (USD)
- Latency (ms)
- Task type and agent type

### Health Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Basic health check |
| `GET /api/health` | Detailed health with DB status |
| `GET /api/ai/status` | AI provider status + budget |
| `GET /api/observability/status` | Langfuse connection status |
| `GET /api/discovery/provider-status` | Detailed AI diagnostics |

---

## Backup & Recovery

### Automated Backups

Configure scheduled backups via the Settings page or API:

```bash
# Create manual backup
POST /api/backup/create

# List available backups
GET /api/backup/list

# Restore from backup
POST /api/backup/restore/{filename}

# Download backup file
GET /api/backup/download/{filename}
```

### Manual Database Backup

```bash
# SQLite
cp backend/certify_intel.db backend/certify_intel_backup_$(date +%Y%m%d).db

# PostgreSQL
pg_dump -h localhost -U certify certify_intel > backup_$(date +%Y%m%d).sql
```

---

## Troubleshooting

### Desktop App Won't Start

**Symptom:** "Failed to start the backend server"

```powershell
# Step 1: Kill all processes
taskkill /F /IM "Certify Intel.exe"
taskkill /F /IM "certify_backend.exe"
netstat -ano | findstr :8000
# If port is in use: taskkill /F /PID <pid_number>

# Step 2: Clean old installations
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\Programs\Certify Intel"
Remove-Item -Recurse -Force "$env:APPDATA\Certify Intel"

# Step 3: Reinstall from desktop-app/dist/Certify_Intel_vX.X.X_Setup.exe
```

### Port 8000 Already in Use

```bash
# Find what's using port 8000
# Windows:
netstat -ano | findstr :8000
taskkill /F /PID <pid>

# Linux/macOS:
lsof -i :8000
kill -9 <pid>
```

### AI Features Not Working

1. Check API keys are set in `backend/.env`
2. Verify provider status: `GET /api/ai/status`
3. Check budget hasn't been exceeded: look at `budget.budget_warning` in status
4. Check logs: `backend/certify_intel.log`

### Database Migration Issues

If a new column is missing after an update:

```python
# The app auto-migrates on startup via init_db()
# If migration fails, check backend logs for ALTER TABLE errors
# Manual fix: restart the server - migrations are idempotent
```

### News Feed Empty

1. Run a news fetch: `POST /api/news-feed/fetch`
2. Check fetch progress: `GET /api/news-feed/fetch-progress/{key}`
3. If articles appear irrelevant, run cleanup: `POST /api/news-feed/cleanup-irrelevant`

### Slow Performance

1. Check if SQLite WAL mode is enabled (automatic on startup)
2. Consider migrating to PostgreSQL for production workloads
3. Monitor AI latency via `GET /api/ai/status` (budget section)
4. Check for connection pool exhaustion in logs

---

## Support & Maintenance

### Log Files

- Application logs are written to stdout/stderr
- Configure logging level via `LOG_LEVEL` environment variable
- In production, redirect to file: `python main.py > certify.log 2>&1`

### Regular Maintenance Tasks

| Task | Frequency | How |
|------|-----------|-----|
| News refresh | Daily (automated) | APScheduler or `POST /api/news-feed/fetch` |
| Data verification | Weekly | `POST /api/verification/run-all` |
| News cleanup | Monthly | `POST /api/news-feed/cleanup-irrelevant` |
| Database backup | Daily | `POST /api/backup/create` or cron job |
| Review AI spend | Weekly | `GET /api/ai/status` budget section |

### Updating the Application

```bash
cd Project_Intel_v6.1.1
git pull origin master
cd backend
pip install -r requirements.txt
python main.py  # Migrations run automatically on startup
```

---

*Document generated for Certify Intel v8.2.0 - February 2026*
