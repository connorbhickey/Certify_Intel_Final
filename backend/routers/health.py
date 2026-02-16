"""
Certify Intel - Health & Version Router

Endpoints:
- GET /api/version - Application version info
- GET /health - Kubernetes/Docker liveness probe
- GET /readiness - Kubernetes/Docker readiness probe (checks all dependencies)
- GET /api/health - Legacy health endpoint
"""

import os
import logging
from datetime import datetime
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from constants import __version__

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get("/api/version")
async def get_version():
    """Return application version information."""
    return {"version": __version__, "name": "Certify Intel"}


@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Kubernetes/Docker liveness probe."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "version": __version__}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unhealthy"})


@router.get("/readiness")
async def readiness_check(db: Session = Depends(get_db)):
    """Kubernetes/Docker readiness probe - checks all dependencies."""
    checks = {}

    # Database check
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False

    # AI Router check
    try:
        from ai_router import get_ai_router
        ai_router = get_ai_router()
        checks["ai_router"] = ai_router is not None
    except Exception:
        checks["ai_router"] = False

    # Langfuse check
    try:
        langfuse_enabled = os.getenv("LANGFUSE_ENABLED", "false").lower() == "true"
        checks["langfuse"] = langfuse_enabled
    except Exception:
        checks["langfuse"] = False

    # Ollama check (if enabled)
    ollama_enabled = os.getenv("OLLAMA_ENABLED", "false").lower() == "true"
    if ollama_enabled:
        checks["ollama"] = True

    # LiteLLM check (if enabled)
    litellm_enabled = os.getenv("LITELLM_ENABLED", "false").lower() == "true"
    if litellm_enabled:
        checks["litellm"] = True

    # Critical checks that must pass (database, ai_router)
    critical_ok = checks.get("database", False) and checks.get("ai_router", False)
    all_ok = all(checks.values())

    # Return 200 for ready/degraded, 503 only if critical services are down
    status_code = 200 if critical_ok else 503
    if all_ok:
        status_text = "ready"
    elif critical_ok:
        status_text = "degraded"
    else:
        status_text = "unhealthy"

    return JSONResponse(
        status_code=status_code,
        content={
            "status": status_text,
            "version": __version__,
            "checks": checks,
        }
    )


@router.get("/metrics")
async def metrics_endpoint():
    """Prometheus metrics endpoint.

    Returns Prometheus text format when prometheus_client is installed
    and METRICS_ENABLED=true, otherwise returns a JSON summary.
    """
    from metrics import (
        PROMETHEUS_AVAILABLE, METRICS_ENABLED,
        generate_latest, CONTENT_TYPE_LATEST, get_metrics_summary,
    )
    from starlette.responses import Response

    if PROMETHEUS_AVAILABLE and METRICS_ENABLED:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return get_metrics_summary()


@router.get("/api/health")
def api_health():
    """Legacy health endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat(), "version": __version__}
