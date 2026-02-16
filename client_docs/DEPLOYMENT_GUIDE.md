# Deployment Guide

---

## Deployment Options

| Option | Best For | Complexity |
|--------|----------|------------|
| **Local/Development** | Single user, testing | Simple |
| **Docker Production** | Team use, cloud hosting | Medium |
| **Desktop App** | Offline use, client demos | Medium |

---

## Option 1: Local Development Server

```bash
cd backend
python main.py
```

- Runs on `http://localhost:8000`
- Uses SQLite (zero config)
- Good for 1-3 concurrent users

---

## Option 2: Docker Production Stack

### Prerequisites
- Docker and Docker Compose installed
- Domain name (for SSL) or IP address

### Quick Start

```bash
# Start production stack (nginx + backend + optional services)
docker compose -f docker-compose.prod.yml up -d

# Check status
docker compose -f docker-compose.prod.yml ps
```

### Docker Compose Files

| File | Services | Purpose |
|------|----------|---------|
| `docker-compose.yml` | Backend only | Basic development |
| `docker-compose.prod.yml` | nginx + backend + Redis | Production with reverse proxy |
| `docker-compose.postgres.yml` | PostgreSQL | Database upgrade from SQLite |
| `docker-compose.langfuse.yml` | Langfuse (6 services) | AI observability |
| `docker-compose.monitoring.yml` | Prometheus + Grafana | Metrics dashboards |
| `docker-compose.ai.yml` | LiteLLM + Ollama | Local/gateway AI |

### Production Architecture

```
Internet -> nginx (port 80/443)
               |
               +-> Backend API (port 8000)
               +-> Static frontend files
               |
            Optional:
               +-> Redis (caching)
               +-> PostgreSQL (production DB)
               +-> Langfuse (AI monitoring)
               +-> Prometheus + Grafana (metrics)
```

### nginx Configuration

The `nginx/` directory contains:
- `nginx.conf` - Reverse proxy config (API proxy + static file serving)
- `ssl/` - SSL certificate setup scripts

Key features:
- Serves frontend static files directly (faster than Python)
- Proxies `/api/*`, `/token`, `/health`, `/readiness` to backend
- Gzip compression enabled
- WebSocket support for real-time features

### SSL Setup

```bash
# Using Let's Encrypt (recommended for production)
cd nginx/ssl
./setup-ssl.sh yourdomain.com
```

---

## Option 3: PostgreSQL (Production Database)

SQLite works well for small teams but PostgreSQL is recommended for:
- Multiple concurrent users
- Better write performance
- Vector search (pgvector extension)
- Proper ACID transactions

### Setup

```bash
# Start PostgreSQL
docker compose -f docker-compose.postgres.yml up -d

# Configure backend
# In backend/.env:
DATABASE_URL=postgresql+asyncpg://certify:certify@localhost:5432/certify_intel

# Migrate data from SQLite
python scripts/migrate_sqlite_to_postgres.py
```

See `docs/POSTGRESQL_MIGRATION_GUIDE.md` for detailed instructions.

---

## Option 4: Desktop App (Windows)

### Build Prerequisites
- Node.js 18+
- Python with PyInstaller
- Windows (for .exe builds)

### Build Steps (Summary)

1. Sync frontend -> desktop-app/frontend/
2. Build backend with PyInstaller: `pyinstaller certify_backend.spec --clean`
3. Copy backend bundle to desktop-app/backend-bundle/
4. Build Electron installer: `npm run build:win`
5. Installer at: `desktop-app/dist/Certify_Intel_v*_Setup.exe`

See `CLAUDE.md` "Desktop App Build Protocol" for the full 11-step process.

---

## Monitoring Stack

### Prometheus + Grafana

```bash
# Start monitoring
docker compose -f docker-compose.monitoring.yml up -d

# Enable metrics in backend
# In backend/.env:
METRICS_ENABLED=true
```

- **Prometheus**: http://localhost:9090 (metrics collection)
- **Grafana**: http://localhost:3000 (dashboards, default login admin/admin)

Available metrics:
- `http_requests_total` - Request count by endpoint, method, status
- `http_request_duration_seconds` - Request latency histogram
- `ai_requests_total` - AI provider call count
- `ai_request_duration_seconds` - AI call latency

### Langfuse (AI Observability)

```bash
# Start Langfuse (6 services: web, worker, clickhouse, redis, minio, postgres)
docker compose -f docker-compose.langfuse.yml up -d

# Enable in backend
# In backend/.env:
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_HOST=http://localhost:3100
```

- **Langfuse UI**: http://localhost:3100
- Traces every AI call with input/output, latency, cost
- Dashboard for AI usage analytics

---

## Environment Variables for Production

```env
# REQUIRED
SECRET_KEY=<strong-random-key>
ADMIN_EMAIL=admin@yourcompany.com
ADMIN_PASSWORD=<strong-password>

# AI (at least one)
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
GOOGLE_AI_API_KEY=...

# Production recommendations
SECURITY_HEADERS_ENABLED=true
RATE_LIMIT_ENABLED=true
JSON_LOGGING=true                # Structured logs for log aggregation
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# Optional but recommended for production
REDIS_ENABLED=true
REDIS_URL=redis://localhost:6379/0
METRICS_ENABLED=true
```

---

## Backup Strategy

### SQLite Backup
```bash
# Manual backup
cp backend/certify_intel.db backend/certify_intel.db.backup

# Automated backup script (30-day retention)
bash scripts/backup-db.sh
```

### PostgreSQL Backup
```bash
docker exec certify-postgres pg_dump -U certify certify_intel > backup.sql
```

---

## Health Checks

The app exposes two unauthenticated health endpoints:

```bash
# Quick liveness check (DB ping + version)
curl http://localhost:8000/health

# Full dependency check (DB, AI providers, Langfuse, etc.)
curl http://localhost:8000/readiness
```

Use these for load balancer health checks and monitoring alerts.
