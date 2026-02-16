# Certify Intel Backend

Backend API for the Certify Intel competitive intelligence Excel dashboard.

## Features

- **REST API** for competitor data management
- **Web Scraping** with Playwright
- **AI Extraction** with OpenAI GPT
- **Excel Export** with auto-fit columns and white backgrounds
- **JSON Export** for Power Query
- **Automated Scheduling** for weekly updates
- **Email Alerts** for competitor changes

## Quick Start

### 1. Install Dependencies

```powershell
cd backend
pip install -r requirements.txt
python -m playwright install chromium
```

### 2. Configure Environment

```powershell
copy .env.example .env
# Edit .env with your OpenAI API key and email settings
```

### 3. Seed Database

```powershell
python seed_db.py
```

### 4. Start Server

```powershell
python -m uvicorn main:app --reload --port 8000
```

Server runs at: `http://localhost:8000`

## API Endpoints

### Competitors

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/competitors` | List all competitors |
| GET | `/api/competitors/{id}` | Get single competitor |
| POST | `/api/competitors` | Create competitor |
| PUT | `/api/competitors/{id}` | Update competitor |
| DELETE | `/api/competitors/{id}` | Soft delete competitor |

### Export

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/export/excel` | Download Excel file |
| GET | `/api/export/json` | Get JSON for Power Query |

### Dashboard

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dashboard/stats` | Get summary statistics |
| GET | `/api/changes` | Get change log |

### Scraping

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/scrape/{id}` | Scrape single competitor |
| POST | `/api/scrape/all` | Scrape all competitors |

### Alerts

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/alerts/send-digest` | Send daily digest email |
| POST | `/api/alerts/send-summary` | Send weekly summary email |

## File Structure

```
backend/
├── main.py           # FastAPI application
├── scraper.py        # Playwright web scraper
├── extractor.py      # GPT data extraction
├── scheduler.py      # Automated job scheduling
├── alerts.py         # Email alert system
├── seed_db.py        # Database seeding
├── requirements.txt  # Python dependencies
├── .env.example      # Environment template
└── exports/          # Generated Excel files
```

## Configuration

### Required

- **OPENAI_API_KEY**: For GPT data extraction

### Optional (for email alerts)

- **SMTP_HOST**: SMTP server (default: smtp.gmail.com)
- **SMTP_PORT**: SMTP port (default: 587)
- **SMTP_USER**: Email username
- **SMTP_PASSWORD**: Email password (use App Password for Gmail)
- **ALERT_TO_EMAILS**: Comma-separated recipient list

## Scheduling

The scheduler runs:

- **Weekly refresh**: Sundays at 2 AM (all competitors)
- **Daily check**: 6 AM (high-threat competitors only)

To start the scheduler:

```powershell
python scheduler.py
```

## Power Query Integration

See `docs/Power_Query_Connection_Guide.md` for Excel connection instructions.
