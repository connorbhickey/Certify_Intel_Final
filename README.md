# Certify Intel

**Competitive Intelligence Platform for Healthcare Technology**

![Version](https://img.shields.io/badge/version-6.3.9-blue)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Web-lightgrey)
![License](https://img.shields.io/badge/license-Proprietary-red)
![Status](https://img.shields.io/badge/status-Production%20Ready-green)

---

## Table of Contents

1. [Overview](#overview)
2. [Who Is This For?](#who-is-this-for)
3. [Key Features](#key-features)
4. [Platform Architecture](#platform-architecture)
5. [Technology Stack](#technology-stack)
6. [Installation](#installation)
7. [Configuration](#configuration)
8. [Usage Guide](#usage-guide)
9. [API Reference](#api-reference)
10. [Data Sources](#data-sources)
11. [Security](#security)
12. [Desktop App Distribution](#desktop-app-distribution)
13. [Development](#development)
14. [Troubleshooting](#troubleshooting)
15. [Contributing](#contributing)

---

## Overview

**Certify Intel** is a production-ready competitive intelligence platform designed to track, analyze, and counter 30+ competitors in the healthcare technology space. It provides a centralized, real-time dashboard that aggregates data from multiple sources to deliver actionable competitive insights.

### What It Does

- **Tracks 30+ competitors** with 30+ data points each (pricing, customers, employee count, funding, etc.)
- **Aggregates data from 15+ sources** including SEC filings, job boards, app stores, and industry databases
- **Generates AI-powered insights** using GPT-4 for executive summaries and strategic analysis
- **Delivers reports** in multiple formats: Excel dashboards, PDF battlecards, and JSON for Power BI
- **Monitors changes** with real-time alerts when competitors update their messaging, pricing, or strategy
- **Auto-updates** across all installed desktop apps when you push new versions

### Key Differentiators

| Feature | Certify Intel | Traditional Methods |
|---------|---------------|---------------------|
| Data freshness | Real-time to daily | Manual quarterly reviews |
| Sources covered | 15+ automated | 2-3 manual |
| Time to insight | Seconds | Days to weeks |
| Consistency | 100% systematic | Varies by analyst |
| Cost | One-time setup | Ongoing analyst hours |

---

## Who Is This For?

### Executive Leadership
- High-level market summaries and threat analysis
- Strategic planning with data-driven insights
- M&A activity monitoring
- Market positioning visualization

### Sales Teams
- Instant access to competitive battlecards
- Feature comparison matrices for sales calls
- Win/loss tracking and analysis
- Real-time competitive objection handling

### Product Management
- Feature gap identification
- Competitor release monitoring
- Product roadmap guidance
- Pricing strategy intelligence

### Strategy & Operations
- Market shift tracking
- Funding event monitoring
- Employee growth analysis
- Industry trend identification

---

## Key Features

### 1. Real-Time Intelligence & Monitoring

**Automated Competitor Tracking**
- Monitors 30+ data points per competitor
- Configurable refresh schedules (daily, weekly, on-demand)
- Change detection with configurable alert thresholds
- Historical trend tracking

**AI Discovery Agent ("Certify Scout")**
- Autonomously crawls the web for emerging threats
- Identifies new market entrants
- Discovers competitor news and announcements
- Uses GPT-4 for intelligent content analysis

**Alert System**
- Email notifications for significant changes
- Slack and Microsoft Teams integration
- SMS alerts via Twilio (optional)
- Configurable alert thresholds per competitor

### 2. Multi-Source Data Collection (15+ Scrapers)

| Category | Sources | Data Collected |
|----------|---------|----------------|
| **Finance & Legal** | SEC Edgar, CrunchBase, PitchBook | Funding rounds, revenue estimates, acquisitions |
| **Employment** | Glassdoor, Indeed, LinkedIn, H1B filings | Employee count, growth rate, hiring trends |
| **Industry** | HIMSS Conference, KLAS Ratings | Industry rankings, conference presence |
| **App Ecosystem** | App Store, Google Play | App ratings, reviews, feature lists |
| **Market Intelligence** | SimilarWeb, G2/Capterra | Web traffic, user reviews, market share |
| **Social & News** | Twitter, LinkedIn, News APIs | Announcements, sentiment, PR activity |

### 3. Advanced Analytics

**AI Executive Summaries**
- GPT-4 generated weekly strategic briefings
- Highlights key competitive movements
- Identifies threats and opportunities
- Provides actionable recommendations

**Market Positioning Map**
- Visual competitor landscape
- Threat level scoring (1-10 scale)
- Market focus categorization
- Company size comparison

**Feature Gap Analysis**
- Side-by-side product comparisons
- Feature matrix generation
- Competitive advantage identification
- Product roadmap recommendations

**Threat Analysis Dashboard**
- Risk scoring and prioritization
- Threat level trends over time
- Competitive pressure indicators
- Early warning system

### 4. Reporting & Export

**Excel Export**
- Data-validated spreadsheets
- Auto-fit columns and formatting
- Multiple worksheets (Overview, Details, Changes)
- Power Query compatible

**PDF Battlecards**
- One-click sales battlecard generation
- Customizable templates
- Competitive positioning summaries
- Objection handling scripts

**JSON Export**
- Power BI integration ready
- API-consumable format
- Webhook delivery option
- Real-time data feeds

**Historical Data**
- Trend analysis over time
- Change log with timestamps
- Data seeding for new competitors
- Audit trail for compliance

### 5. Data Quality & Verification

**Quality Scoring System**
- Freshness scores (days since last update)
- Completeness metrics (% of fields populated)
- Source reliability ratings
- Confidence indicators

**Source Attribution**
- Every data point traced to its source
- Last verified timestamp
- Verification workflow
- Manual override with audit trail

**Stale Data Detection**
- Automatic identification of outdated fields
- Configurable staleness thresholds
- Refresh prioritization
- Quality alerts

### 6. Multi-User System & Security

**User Registration & Authentication**
- Self-registration on login page
- Admin can invite team members
- JWT token-based authentication
- Secure password hashing (SHA256 with salt)

**Role-Based Access Control**
| Role | Capabilities |
|------|--------------|
| **Admin** | Full system access, user management, invite users |
| **Analyst** | Full data access, create/modify intelligence, run scrapers |
| **Viewer** | Read-only access to dashboards and reports |

**Data Isolation**
| Data Type | Scope |
|-----------|-------|
| Competitors | Shared - all users see same data |
| Knowledge Base | Shared - updates visible to everyone |
| AI Prompts | Personal - each user customizes their own |
| Win/Loss Deals | Personal - each user tracks their own |
| Settings | Personal - notification preferences per user |

**Activity Logging & Audit Trail**
- All data changes logged with username and timestamp
- "Refresh Data" button logs who triggered it
- Activity logs shared across all users
- Complete audit trail for compliance

### 7. Automated Scheduling

**Pre-configured Schedules**
| Schedule | Frequency | Scope |
|----------|-----------|-------|
| Weekly Refresh | Sundays 2 AM | Full database (all competitors) |
| Daily Check | 6 AM | High-threat competitors only |
| Database Backup | Daily | Automated backup with retention |
| Email Digest | Daily/Weekly | Summary reports to stakeholders |

**Custom Scheduling**
- Cron-based job scheduling via APScheduler
- Per-competitor refresh schedules
- On-demand scraping via API
- Webhook triggers for external systems

---

## Platform Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CERTIFY INTEL                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐              │
│  │   Desktop    │    │     Web      │    │    Mobile    │              │
│  │   (Electron) │    │  (Browser)   │    │    (PWA)     │              │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘              │
│         │                   │                   │                       │
│         └───────────────────┼───────────────────┘                       │
│                             │                                           │
│                    ┌────────▼────────┐                                  │
│                    │    Frontend     │                                  │
│                    │  (HTML/JS/CSS)  │                                  │
│                    │   Chart.js      │                                  │
│                    └────────┬────────┘                                  │
│                             │                                           │
│                    ┌────────▼────────┐                                  │
│                    │   FastAPI       │                                  │
│                    │   Backend       │                                  │
│                    │  (40+ endpoints)│                                  │
│                    └────────┬────────┘                                  │
│                             │                                           │
│         ┌───────────────────┼───────────────────┐                       │
│         │                   │                   │                       │
│  ┌──────▼──────┐    ┌──────▼──────┐    ┌──────▼──────┐                │
│  │   SQLite    │    │   OpenAI    │    │  Scrapers   │                │
│  │  Database   │    │   GPT-4     │    │ (15+ types) │                │
│  │ (11 tables) │    │ Integration │    │             │                │
│  └─────────────┘    └─────────────┘    └─────────────┘                │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Database Schema (11 Core Tables)

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `competitors` | Main competitor records | 30+ fields per competitor |
| `change_log` | Change tracking and alerts | field, old_value, new_value, timestamp |
| `data_sources` | Source attribution per field | source_url, last_verified, confidence |
| `data_change_history` | Audit log with user attribution | user_id, reason, timestamp |
| `users` | User accounts with roles | username, password_hash, role |
| `system_prompts` | Dynamic AI prompts | prompt_name, content, active |
| `knowledge_base` | Internal docs for RAG | document, embedding, category |
| `system_settings` | Global configuration | key, value, description |
| `win_loss_deals` | Competitive deal outcomes | competitor_id, outcome, value |
| `webhooks` | Outbound webhook config | url, events, secret |
| `scheduled_jobs` | Job scheduling state | job_id, next_run, status |

---

## Technology Stack

### Backend (Python 3.9+)

| Component | Technology | Purpose |
|-----------|------------|---------|
| Framework | FastAPI | High-performance async API |
| Server | Uvicorn | ASGI server |
| Database | SQLite + SQLAlchemy | Lightweight, zero-config storage |
| AI/ML | OpenAI GPT-4, Google Gemini, LangChain | Intelligence and summarization |
| Web Scraping | Playwright, BeautifulSoup | Dynamic and static page scraping |
| PDF Generation | ReportLab | Battlecard and report creation |
| Excel Export | openpyxl | Data-validated spreadsheets |
| Scheduling | APScheduler | Background job management |
| Authentication | JWT (python-jose), passlib | Secure token-based auth |
| HTTP Client | httpx, requests | API and web requests |

### Frontend (Web)

| Component | Technology | Purpose |
|-----------|------------|---------|
| Core | HTML5, Vanilla JS (ES6+), CSS3 | No framework dependencies |
| Visualization | Chart.js | Interactive charts and maps |
| Design | CSS Variables, Glassmorphism | Dark-mode premium aesthetic |
| PWA | Service Workers | Offline support and caching |
| Responsive | Mobile-first CSS | Works on all screen sizes |

### Desktop Application

| Component | Technology | Purpose |
|-----------|------------|---------|
| Framework | Electron 28.1.0 | Cross-platform desktop wrapper |
| Build | electron-builder | Windows/macOS installers |
| Auto-Update | electron-updater | Push updates to all users |
| Backend Bundle | PyInstaller | Python bundled as executable |

---

## Installation

> **Quick Start**: See [QUICK_INSTALL.md](QUICK_INSTALL.md) for detailed step-by-step instructions with screenshots.

### Option 1: Automated Setup (Recommended)

Download the ZIP from GitHub and use the included setup scripts.

#### Step 1: Download

1. Go to: https://github.com/[YOUR-GITHUB-ORG]/Project_Intel_v5.0.1
2. Click the green **"<> Code"** button
3. Click **"Download ZIP"**
4. Extract to your Desktop

#### Step 2: Rename the Folder (IMPORTANT!)

> **Why?** GitHub creates long folder names that can cause installation failures on Windows.

Rename the extracted folder:
- **From**: `Project_Intel_v5.0.1-master` (or similar)
- **To**: `certify_intel`

#### Step 3: Run Setup Script

**Windows:**
1. Open the `certify_intel` folder
2. Double-click **`setup.bat`**
3. Follow the prompts

**Mac/Linux:**
```bash
cd ~/Desktop/certify_intel
chmod +x setup.sh
./setup.sh
```

#### Step 4: Access the Application

- Open Chrome: **http://localhost:8000**
- Login: `admin@certifyhealth.com` / `certifyintel2024`

---

### Option 2: Manual Setup

```bash
# Navigate to project
cd certify_intel/backend

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Mac/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create config file
cp .env.example .env

# Start server
python main.py
```

Then open: http://localhost:8000

---

### Option 3: Git Clone (For Developers)

```bash
# Clone the repository
git clone https://github.com/[YOUR-GITHUB-ORG]/Project_Intel_v5.0.1.git
cd Project_Intel_v5.0.1

# Backend setup
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
python main.py  # Starts on http://localhost:8000
```

---

### Option 4: Desktop App (Beta)

> **Note**: Desktop app has a known issue with backend startup. Use web version for now.

Download from [GitHub Releases](https://github.com/[YOUR-GITHUB-ORG]/Project_Intel_v5.0.1/releases):

| Platform | File | Requirements |
|----------|------|--------------|
| Windows | `Certify_Intel_Setup.exe` | Windows 10/11 (64-bit) |
| macOS (Intel) | `Certify_Intel_x64.dmg` | macOS 11+ |
| macOS (Apple Silicon) | `Certify_Intel_arm64.dmg` | macOS 11+ (M1/M2/M3) |

---

### Troubleshooting Installation

| Issue | Solution |
|-------|----------|
| `pip install` fails with path error | Move folder to shorter path (e.g., `C:\certify_intel`) |
| `python` not found | Install Python 3.9+ and add to PATH |
| Port 8000 in use | Use `uvicorn main:app --port 8001` |
| Login doesn't work | See [QUICK_INSTALL.md](QUICK_INSTALL.md#login-doesnt-work) |

For detailed troubleshooting, see [QUICK_INSTALL.md](QUICK_INSTALL.md#troubleshooting).

---

## Configuration

### Environment Variables (backend/.env)

```bash
# Required
SECRET_KEY=your-secret-key         # JWT signing key (generate random string)

# AI Providers (at least one required)
OPENAI_API_KEY=sk-...              # OpenAI API key for GPT-4 features
GOOGLE_AI_API_KEY=AIza...          # Google Gemini API key (get at aistudio.google.com)

# AI Provider Mode (v5.0.6)
AI_PROVIDER=hybrid                 # Options: "openai", "gemini", or "hybrid" (recommended)
AI_BULK_TASKS=gemini               # Provider for bulk operations (cheaper with Gemini)
AI_QUALITY_TASKS=openai            # Provider for quality-critical tasks
AI_FALLBACK_ENABLED=true           # Auto-switch on failure

# Database
DATABASE_URL=sqlite:///./certify_intel.db  # SQLite (default) or PostgreSQL

# Email Notifications (optional)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
ALERT_EMAIL=team@company.com

# Slack Integration (optional)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

# Microsoft Teams (optional)
TEAMS_WEBHOOK_URL=https://outlook.office.com/webhook/...

# SMS via Twilio (optional)
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1234567890

# Debug Mode
DEBUG=False
```

### System Settings (via API or Database)

| Setting | Default | Description |
|---------|---------|-------------|
| `refresh_interval` | 7 | Days between full refreshes |
| `stale_threshold` | 30 | Days before data is marked stale |
| `alert_email_enabled` | true | Send email alerts |
| `threat_threshold` | 7 | Threat level to trigger alerts |

---

## Usage Guide

### Dashboard Overview

The main dashboard displays:
- **Competitor Grid**: All tracked competitors with key metrics
- **Threat Summary**: High-threat competitors highlighted
- **Recent Changes**: Latest detected changes across all competitors
- **Quick Actions**: Export, refresh, and analysis buttons

### Adding a New Competitor

1. Click "Add Competitor" button
2. Fill in basic information (name, website, category)
3. System automatically discovers data from configured sources
4. Review and verify discovered data
5. Set threat level and monitoring priority

### Running Data Refresh

**Manual Refresh:**
- Single competitor: Click refresh icon on competitor card
- All competitors: Dashboard → Actions → Refresh All

**Scheduled Refresh:**
- Automatic weekly refresh: Sundays 2 AM
- High-threat daily check: 6 AM

### Generating Reports

**Excel Dashboard:**
```
GET /api/export/excel
→ Downloads comprehensive Excel workbook
```

**PDF Battlecard:**
```
POST /api/reports/battlecard/{competitor_id}
→ Generates sales battlecard PDF
```

**JSON for Power BI:**
```
GET /api/export/json
→ Power Query compatible JSON
```

### Using AI Features

**Executive Summary:**
```
GET /api/analytics/executive-summary
→ AI-generated strategic briefing
```

**Conversational Analytics:**
```
POST /api/analytics/chat
Body: { "question": "What are Epic's main weaknesses?" }
→ AI-powered competitive analysis
```

### Hybrid AI Features (v5.0.6)

Certify Intel supports both OpenAI and Google Gemini for ~90% cost savings on bulk operations.

**Model Options:**
| Model | Best For | Cost (per 1M tokens) |
|-------|----------|---------------------|
| gemini-2.5-flash-lite | Bulk extraction, classification | $0.019 input / $0.075 output |
| gemini-2.5-flash | Data extraction, summaries | $0.075 input / $0.30 output |
| gemini-2.5-pro | Complex analysis | $1.25 input / $10.00 output |
| gpt-4o-mini | Chat, conversations | $0.15 input / $0.60 output |
| gpt-4o | Quality-critical tasks | $2.50 input / $10.00 output |

**Multimodal Analysis (v5.0.6):**
```
POST /api/ai/analyze-screenshot
→ Analyze competitor website screenshots

POST /api/ai/analyze-pdf
→ Extract intelligence from competitor PDFs

POST /api/ai/analyze-video
→ Analyze competitor demo videos and webinars
```

**Real-Time Intelligence (v5.0.6):**
```
POST /api/ai/search-grounded
→ Get current information using Google Search

POST /api/ai/research-competitor
→ Comprehensive real-time competitor research
```

**Bulk Processing (v5.0.6):**
```
POST /api/ai/process-news-batch
→ Process 100+ news articles efficiently

POST /api/ai/analyze-news-trends
→ Identify trends across news articles
```

---

## API Reference

### Authentication

All API endpoints require JWT authentication:

```bash
# Login to get token
POST /api/auth/login
Body: { "username": "admin", "password": "..." }
Response: { "access_token": "eyJ...", "token_type": "bearer" }

# Use token in requests
Authorization: Bearer eyJ...
```

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/competitors` | List all competitors |
| GET | `/api/competitors/{id}` | Get single competitor |
| POST | `/api/competitors` | Create competitor |
| PUT | `/api/competitors/{id}` | Update competitor |
| DELETE | `/api/competitors/{id}` | Delete competitor |
| POST | `/api/competitors/{id}/correct` | Manual correction with audit |

### Analytics Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/analytics/summary` | Dashboard summary stats |
| GET | `/api/analytics/executive-summary` | AI-generated briefing |
| POST | `/api/analytics/chat` | Conversational AI analysis |
| GET | `/api/analytics/threats` | Threat analysis report |
| GET | `/api/analytics/market-share` | Market positioning data |

### Data Quality Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/data-quality/scores` | Quality metrics per competitor |
| GET | `/api/data-quality/stale` | List stale data fields |
| POST | `/api/data-quality/verify/{id}` | Mark data as verified |

### Export Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/export/excel` | Download Excel dashboard |
| GET | `/api/export/json` | JSON for Power Query |
| POST | `/api/reports/battlecard/{id}` | Generate PDF battlecard |

### Scraping Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/scrape/all` | Full refresh all sources |
| POST | `/api/scrape/{id}` | Scrape single competitor |
| POST | `/api/discovery/run` | Run AI discovery agent |

---

## Data Sources

### Automated Sources (15+)

| Source | Data Type | Frequency |
|--------|-----------|-----------|
| SEC Edgar | Financial filings, 10-K, 8-K | Daily |
| CrunchBase | Funding, acquisitions, investors | Weekly |
| PitchBook | Private company valuations | Weekly |
| USPTO | Patents, IP filings | Weekly |
| Glassdoor | Employee reviews, ratings | Weekly |
| Indeed | Job postings, hiring trends | Daily |
| LinkedIn | Employee count, growth | Weekly |
| H1B Database | Visa filings, salary data | Monthly |
| HIMSS | Conference presence, awards | Event-based |
| KLAS | Industry ratings, rankings | Quarterly |
| App Store | iOS app data, ratings | Daily |
| Google Play | Android app data, ratings | Daily |
| SimilarWeb | Web traffic, engagement | Weekly |
| G2/Capterra | User reviews, ratings | Weekly |
| News APIs | Press releases, articles | Real-time |

### Manual Data Entry

- Win/loss deal tracking
- Field intelligence from sales team
- Pricing information from RFPs
- Feature updates from demos

---

## Security

### Data Protection

- **Local Storage**: All data stored locally in SQLite (no cloud dependency)
- **Encryption**: Sensitive fields encrypted at rest
- **Access Control**: Role-based permissions (Admin/Analyst/Viewer)
- **Audit Trail**: Complete change history with user attribution

### Authentication Security

- **JWT Tokens**: Short-lived access tokens (24 hours)
- **Password Hashing**: SHA256 with random salt
- **Rate Limiting**: API rate limiting to prevent abuse
- **CORS**: Configurable cross-origin resource sharing

### Network Security

- **HTTPS**: Recommended for production deployment
- **API Keys**: Secure storage of third-party API keys
- **Webhook Secrets**: HMAC verification for webhooks

---

## Desktop App Distribution

### For Repository Owners

1. **Trigger a release** by creating a version tag:
   ```bash
   git tag -a v2.0.1 -m "Release 2.0.1"
   git push origin v2.0.1
   ```

2. **GitHub Actions** automatically builds Windows and macOS installers

3. **Download from Releases**: https://github.com/[YOUR-GITHUB-ORG]/Project_Intel_v5.0.1/releases

### For Team Members

1. Visit the [Releases page](https://github.com/[YOUR-GITHUB-ORG]/Project_Intel_v5.0.1/releases)
2. Download the installer for your platform
3. Install and run (bypass SmartScreen/Gatekeeper on first launch)
4. App will auto-update when new versions are released

### Auto-Update System

- Apps check for updates on startup and every 4 hours
- Users see "Update Available" dialog with download option
- Updates install automatically on app restart
- Critical updates can force immediate installation

---

## Development

### Project Structure

```
Project_Intel_v5.0.1/
├── backend/                    # Python FastAPI backend (~8,651 lines)
│   ├── main.py                # Application entry point (3,164 lines)
│   ├── database.py            # SQLAlchemy models (11 tables)
│   ├── analytics.py           # Data analysis engine (807 lines)
│   ├── extended_features.py   # Auth, caching, advanced features
│   ├── discovery_agent.py     # AI web scraping logic
│   ├── scheduler.py           # APScheduler automation
│   ├── alerts.py              # Notifications (Email/Slack/Teams)
│   ├── reports.py             # PDF/Excel generation
│   ├── extractor.py           # GPT-4 data extraction
│   ├── scraper.py             # Base Playwright scraper class
│   ├── *_scraper.py           # 15+ specialized scrapers
│   ├── certify_intel.db       # SQLite database
│   ├── requirements.txt       # Python dependencies (40+)
│   └── .env.example           # Configuration template
│
├── frontend/                   # Web UI SPA
│   ├── index.html             # Main application
│   ├── login.html             # Authentication UI
│   ├── app_v2.js              # Core logic (4,084 lines)
│   ├── styles.css             # Design system (46KB)
│   ├── mobile-responsive.css  # Mobile optimization
│   ├── enhanced_analytics.js  # Advanced charting
│   ├── visualizations.js      # Chart.js integration
│   ├── service-worker.js      # PWA offline support
│   └── manifest.json          # PWA configuration
│
├── desktop-app/                # Electron wrapper
│   ├── electron/
│   │   ├── main.js            # Electron main process
│   │   ├── preload.js         # Security bridge
│   │   ├── splash.html        # Loading screen
│   │   └── setup-wizard.html  # First-run setup
│   ├── package.json           # Build configuration
│   ├── resources/icons/       # App icons
│   └── README.md              # Desktop-specific docs
│
├── .github/
│   └── workflows/
│       └── build-release.yml  # CI/CD for installers
│
├── docs/                       # Documentation
│   ├── DESKTOP_APP_BUILD_PLAN.md
│   └── [other documentation]
│
└── client_docs/                # Client materials
    └── Certify Health Material/
```

### Code Statistics

- **Backend**: ~8,651 lines of Python across 60+ modules
- **Frontend**: ~4,084 lines of JavaScript
- **Database**: 471KB SQLite, 11 core tables
- **Scrapers**: 15+ specialized data collectors
- **API Endpoints**: 40+
- **Dependencies**: 40+ Python packages

### Building Locally

```bash
# Backend build (PyInstaller)
cd backend
pip install pyinstaller
pyinstaller certify_backend.spec --clean --noconfirm

# Desktop app build
cd desktop-app
npm install
npm run build:win   # Windows
npm run build:mac   # macOS
npm run build:all   # Both
```

### Running Tests

```bash
cd backend
python run_tests.py  # Runs 9 automated endpoint tests
```

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Backend won't start | Check `.env` has `OPENAI_API_KEY` and `SECRET_KEY` |
| Port 8000 in use | Change port in `main.py` or kill existing process |
| Scrapers failing | Check internet, verify OpenAI API key is valid |
| AI features not working | Verify OpenAI API key and billing status |
| Desktop app won't launch | Ensure backend is running on port 8000 |
| Update not detected | Check version in `package.json` is higher than installed |

### Logs Location

- **Backend**: Console output / `backend/logs/`
- **Desktop (Windows)**: `%APPDATA%\certify-intel\logs\`
- **Desktop (macOS)**: `~/Library/Logs/certify-intel/`

### Getting Help

- Check documentation in `/docs` folder
- Review CLAUDE.md for development context
- Open an issue on GitHub

---

## Contributing

### CI/CD Pipeline

We use GitHub Actions for continuous integration and deployment with auto-PR and auto-merge capabilities.

#### Local Testing (Before Push)

```bash
# Run local tests before pushing
.\scripts\pre-push-tests.ps1

# Or install git hooks for automatic testing
.\scripts\setup-git-hooks.ps1
```

#### Workflow Options

**Option 1: Feature Branch (Recommended for larger changes)**
```bash
git checkout -b feature/my-feature
# Make changes...
.\scripts\pre-push-tests.ps1
git add -A && git commit -m "[Feature] My new feature"
git push origin feature/my-feature
# CI/CD automatically:
#   1. Runs tests on GitHub
#   2. Creates PR with 'auto-pr' label
#   3. Merges PR when all checks pass
```

**Option 2: Direct to Master (Quick fixes)**
```bash
git checkout master
# Make changes...
.\scripts\pre-push-tests.ps1
git add -A && git commit -m "[Fix] Quick bug fix"
git push origin master
```

#### What CI/CD Checks

- **Linting**: flake8, black, isort
- **Testing**: pytest with coverage
- **Security**: Basic security checks
- **Build**: Windows/macOS installers (on release tags)

### Development Workflow

1. Create feature branch from `master`
2. Make changes following existing code patterns
3. Run local tests: `.\scripts\pre-push-tests.ps1`
4. Commit with clear, descriptive messages
5. Push - CI/CD handles PR creation and merge

### Code Style

- Python: Follow PEP 8, use type hints
- JavaScript: ES6+, no framework dependencies
- CSS: BEM naming, CSS variables for theming
- Commits: Conventional commits format `[Category] Description`

### Adding New Scrapers

1. Create `backend/[source]_scraper.py`
2. Inherit from `Scraper` base class
3. Implement scraping logic with Playwright
4. Add GPT-4 extraction for unstructured data
5. Register in `main.py` scraper routing
6. Add to scheduler if needed
7. Document data fields collected

---

## License

Proprietary - Certify Health Internal Use Only

---

## Credits

- **Lead Developer**: [Your Team]
- **Organization**: Certify Health
- **Repository**: [GitHub - Project_Intel_v5.0.1](https://github.com/[YOUR-GITHUB-ORG]/Project_Intel_v5.0.1)

---

*Last Updated: January 31, 2026*
*Version: 6.3.9*
