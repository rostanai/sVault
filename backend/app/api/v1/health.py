"""Health & readiness endpoints (liveness + DB readiness)."""
from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Liveness — process is up."""
    return {"status": "ok", "service": settings.app_name, "env": settings.env}


@router.get("/ready")
async def ready() -> dict:
    """Readiness — dependencies reachable. DB check wired in M1 once the pool exists."""
    checks = {"app": "ok"}
    # TODO(M1): ping Supabase via the transaction pooler and set checks["db"].
    return {"status": "ready", "checks": checks}
