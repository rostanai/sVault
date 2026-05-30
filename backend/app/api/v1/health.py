"""Health & readiness endpoints (liveness + DB readiness)."""
from fastapi import APIRouter

from app.core.config import settings
from app.db.session import db_configured, ping_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Liveness — process is up."""
    return {"status": "ok", "service": settings.app_name, "env": settings.env}


@router.get("/ready")
async def ready() -> dict:
    """Readiness — pings the database via the transaction pooler."""
    checks = {"app": "ok"}
    if not db_configured():
        checks["db"] = "not_configured"
        return {"status": "ready", "checks": checks}
    try:
        await ping_db()
        checks["db"] = "ok"
    except Exception:
        checks["db"] = "error"
    return {"status": "ready" if checks["db"] == "ok" else "degraded", "checks": checks}
