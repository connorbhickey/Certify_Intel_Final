# Enterprise Production Build
FROM python:3.11-slim as builder

WORKDIR /app
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Final Stage
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Playwright/Chrome if needed
# For now, we use a lighter setup. If Playwright is critical, we'd use the mcr.microsoft.com/playwright/python image
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY . .

# Create directory for exports and database
RUN mkdir -p /app/exports && mkdir -p /app/data

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

EXPOSE 8000

# Healthcheck using /health liveness probe (v8.3.1)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Launch with Enterprise Configuration (2 workers for production)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
