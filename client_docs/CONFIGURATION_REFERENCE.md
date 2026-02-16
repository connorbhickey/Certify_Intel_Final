# Configuration Reference

All configuration is via environment variables in `backend/.env`.

Copy `backend/.env.example` to `backend/.env` and edit.

---

## Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | JWT signing key. Generate with `python -c "import secrets; print(secrets.token_hex(32))"` | `a1b2c3d4e5...` |
| `ADMIN_EMAIL` | Initial admin account email (created on first startup) | `admin@company.com` |
| `ADMIN_PASSWORD` | Initial admin account password | `StrongPass123!` |

At least one AI provider key is required for AI features to work.

---

## AI Provider Keys

| Variable | Provider | Purpose | Cost |
|----------|----------|---------|------|
| `ANTHROPIC_API_KEY` | Claude (Anthropic) | Primary - complex analysis, quality tasks | Pay-as-you-go |
| `OPENAI_API_KEY` | GPT-4o (OpenAI) | Fallback provider | Pay-as-you-go |
| `OPENAI_MODEL` | Model override | Default: `gpt-4.1` | - |
| `GOOGLE_AI_API_KEY` | Gemini (Google) | Speed/bulk tasks, grounded search | Free tier available |
| `GOOGLE_AI_MODEL` | Model override | Default: `gemini-3-flash-preview` | - |
| `DEEPSEEK_API_KEY` | DeepSeek | Optional - very cheap bulk tasks | Pay-as-you-go |

### AI Routing

| Variable | Description | Default |
|----------|-------------|---------|
| `AI_PROVIDER` | Routing mode: `hybrid`, `anthropic`, `openai`, `gemini` | `hybrid` |
| `AI_BULK_TASKS` | Provider for bulk/cheap tasks | `gemini` |
| `AI_QUALITY_TASKS` | Provider for quality-critical tasks | `anthropic` |
| `AI_FALLBACK_ENABLED` | Auto-fallback to next provider on failure | `true` |

---

## Optional: Local AI (Free)

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_ENABLED` | Enable Ollama local LLM | `false` |
| `OLLAMA_URL` | Ollama server URL | `http://localhost:11434` |
| `OLLAMA_DEFAULT_MODEL` | Default model | `llama3.1:8b` |
| `USE_LOCAL_EMBEDDINGS` | Use sentence-transformers instead of OpenAI embeddings | `false` |

---

## Optional: AI Gateway

| Variable | Description | Default |
|----------|-------------|---------|
| `LITELLM_ENABLED` | Enable LiteLLM proxy (100+ providers) | `false` |
| `LITELLM_PROXY_URL` | LiteLLM proxy URL | `http://localhost:4000` |

---

## Optional: AI Evaluation

| Variable | Description | Default |
|----------|-------------|---------|
| `OPIK_ENABLED` | Enable Opik hallucination detection | `false` |

---

## Optional: Vertex AI

| Variable | Description | Default |
|----------|-------------|---------|
| `VERTEX_AI_ENABLED` | Enable Google Cloud Vertex AI | `false` |
| `VERTEX_AI_PROJECT` | GCP project ID | - |
| `VERTEX_AI_LOCATION` | GCP region | `us-central1` |

---

## Database

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | SQLite (no config needed) |

SQLite is used when `DATABASE_URL` is not set. The database file is automatically created at `backend/certify_intel.db`.

---

## Caching

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_ENABLED` | Enable Redis caching | `false` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |

When Redis is disabled, an in-memory cache (TTL-based, max 1000 entries) is used automatically.

---

## Observability

| Variable | Description | Default |
|----------|-------------|---------|
| `LANGFUSE_ENABLED` | Enable Langfuse AI tracing | `false` |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key | - |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key | - |
| `LANGFUSE_HOST` | Langfuse server URL | `http://localhost:3100` |
| `METRICS_ENABLED` | Enable Prometheus /metrics endpoint | `false` |
| `JSON_LOGGING` | Structured JSON log output | `false` |

---

## Security

| Variable | Description | Default |
|----------|-------------|---------|
| `SECURITY_HEADERS_ENABLED` | Enable CSP, HSTS, X-Frame-Options | `true` |
| `RATE_LIMIT_ENABLED` | Enable per-endpoint rate limiting | `true` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT access token lifetime | `15` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | JWT refresh token lifetime | `7` |

---

## News Feed APIs

| Variable | Description | Free Tier |
|----------|-------------|-----------|
| `GNEWS_API_KEY` | gnews.io | 100 requests/day |
| `MEDIASTACK_API_KEY` | mediastack.com | 500/month |
| `NEWSDATA_API_KEY` | newsdata.io | 200/day |

---

## Design Principle

All optional features default to **OFF** with zero overhead. The app runs perfectly with just:
- `SECRET_KEY`
- `ADMIN_EMAIL` + `ADMIN_PASSWORD`
- One AI provider API key

Everything else can be enabled incrementally as needed.
