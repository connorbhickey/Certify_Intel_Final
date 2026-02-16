# Getting Started with Certify Intel

Welcome to **Certify Intel** - your Competitive Intelligence Platform for healthcare technology.

This guide will have you up and running in under 10 minutes.

---

## Prerequisites

| Requirement | Version | Check |
|-------------|---------|-------|
| **Python** | 3.9 or higher | `python --version` |
| **pip** | Latest | `pip --version` |
| **Node.js** (desktop only) | 18+ | `node --version` |

> **Note:** Node.js is only needed if you want to build the desktop app. The web version needs only Python.

---

## Quick Setup (5 Steps)

### Step 1: Clone or Extract

```bash
# If using Git
git clone <repo-url>
cd Certify_Intel

# Or extract the ZIP
unzip Certify_Intel_v9.0.0.zip
cd Certify_Intel_v9.0.0
```

### Step 2: Create Python Virtual Environment

```bash
cd backend
python -m venv venv

# Activate it:
# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment

```bash
# Copy the example config
copy .env.example .env        # Windows
cp .env.example .env          # macOS/Linux
```

Now edit `backend/.env` and set these **required** values:

```env
# Generate a random secret key
SECRET_KEY=<run: python -c "import secrets; print(secrets.token_hex(32))">

# Your admin login credentials
ADMIN_EMAIL=admin@yourcompany.com
ADMIN_PASSWORD=YourStrongPasswordHere

# At least one AI provider API key
ANTHROPIC_API_KEY=sk-ant-...    # or
OPENAI_API_KEY=sk-...           # or
GOOGLE_AI_API_KEY=...
```

> **Tip:** You can add more AI providers later in the Settings page. At minimum, set one API key to enable AI features.

### Step 5: Start the Server

```bash
python main.py
```

Open your browser to: **http://localhost:8000**

---

## First Login

1. Go to http://localhost:8000
2. Log in with the `ADMIN_EMAIL` and `ADMIN_PASSWORD` you set in `.env`
3. The admin account is automatically created on first startup

---

## What's Included

### Pre-loaded Data
| Data | Count | Description |
|------|-------|-------------|
| **Competitors** | 74 | Healthcare technology companies with full profiles |
| **Products** | 789 | Product details across all competitors |
| **News Articles** | 920+ | Recent healthcare industry news |
| **Data Sources** | 512 | Verified source links for competitor data |

### 11 Application Pages

| Page | What It Does |
|------|-------------|
| **Dashboard** | AI-powered competitive summary, threat stats, PDF export |
| **Competitors** | Browse, search, and manage competitor profiles |
| **Discovery Scout** | AI-driven discovery of new competitors |
| **Battlecards** | Generate sales-ready one-page competitor summaries |
| **Comparisons** | Side-by-side comparison of 2-4 competitors |
| **Sales & Marketing** | 9-dimension scoring, radar charts, talking points |
| **News Feed** | Real-time competitor news with sentiment analysis |
| **Analytics** | Market map, win/loss tracking, deal history |
| **Records** | Data records management |
| **Validation** | Data validation and verification workflows |
| **Settings** | API keys, user preferences, MFA, audit logs |

### AI Features

The platform uses AI for:
- Competitive analysis and threat assessment
- Battlecard generation
- News sentiment analysis
- Competitor discovery
- Data verification against live web sources
- Natural language chat on every page

**AI Provider Priority:** Claude (quality) > GPT-4o (fallback) > Gemini (speed/bulk)

---

## Adding AI Provider Keys

You can configure AI providers in two ways:

**Option A: Edit `.env` file** (recommended for initial setup)
- Add your API keys to `backend/.env`
- Restart the server

**Option B: Settings page** (for runtime changes)
- Navigate to Settings > AI Providers
- Enter API keys in the provider status panel

### Getting API Keys

| Provider | Sign Up | Free Tier |
|----------|---------|-----------|
| Anthropic Claude | [console.anthropic.com](https://console.anthropic.com/) | Pay-as-you-go |
| OpenAI | [platform.openai.com](https://platform.openai.com/) | $5 free credit |
| Google Gemini | [aistudio.google.com](https://aistudio.google.com/) | Generous free tier |

---

## Optional: Desktop App (Windows)

Build a standalone Windows application:

```bash
cd desktop-app
npm install
npm run build:win
```

The installer will be at: `desktop-app/dist/Certify_Intel_v9.0.0_Setup.exe`

> **Note:** The desktop app bundles the backend as an executable. You'll need to build the backend with PyInstaller first and copy the output to `desktop-app/backend-bundle/`. See the full build protocol in `CLAUDE.md` for details.

---

## Optional: PostgreSQL (Production)

The default SQLite database works great for single-user or small team use. For production with multiple concurrent users:

1. Start PostgreSQL with Docker:
   ```bash
   docker compose -f docker-compose.postgres.yml up -d
   ```

2. Update `backend/.env`:
   ```env
   DATABASE_URL=postgresql+asyncpg://certify:certify@localhost:5432/certify_intel
   ```

3. Run the migration script:
   ```bash
   python scripts/migrate_sqlite_to_postgres.py
   ```

See `docs/POSTGRESQL_MIGRATION_GUIDE.md` for full details.

---

## Optional: Monitoring Stack

For production observability:

```bash
# Langfuse (AI trace monitoring)
docker compose -f docker-compose.langfuse.yml up -d

# Prometheus + Grafana (metrics dashboards)
docker compose -f docker-compose.monitoring.yml up -d
```

Then enable in `.env`:
```env
LANGFUSE_ENABLED=true
METRICS_ENABLED=true
```

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+K` | Open command palette (search everything) |
| `Ctrl+1` through `Ctrl+9` | Quick-navigate to pages |
| `Escape` | Close modals and menus |

---

## Troubleshooting

### Server won't start
- Check that `SECRET_KEY` is set in `.env`
- Check that Python 3.9+ is active: `python --version`
- Check that dependencies are installed: `pip install -r requirements.txt`

### Can't log in
- Verify `ADMIN_EMAIL` and `ADMIN_PASSWORD` are set in `.env`
- The admin account is created on first startup only. If you changed credentials after first run, you'll need to delete the old user from the database or reset it

### AI features not working
- At least one AI provider API key must be set
- Check the Settings > AI Providers panel for connection status
- Verify your API key has available credits

### Port 8000 already in use
```bash
# Windows
netstat -ano | findstr :8000
taskkill /F /PID <pid>

# macOS/Linux
lsof -i :8000
kill -9 <pid>
```

---

## Documentation

| Document | Contents |
|----------|----------|
| `CLAUDE.md` | Full technical reference (architecture, API endpoints, configuration) |
| `docs/API_REFERENCE.md` | Complete API documentation with examples |
| `docs/HANDOVER_GUIDE.md` | Detailed system handover documentation |
| `docs/ARCHITECTURE.md` | System architecture diagrams |
| `docs/POSTGRESQL_MIGRATION_GUIDE.md` | PostgreSQL setup guide |
| `docs/ENTERPRISE_DATA_PROVIDERS.md` | Enterprise data provider integration |

---

## Support

For technical questions or issues, please contact the development team or file an issue in the project repository.
