"""Dashboard endpoint (M3)."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import require_permission
from app.core.security import CurrentUser
from app.db.session import get_db
from app.schemas.dashboard import DashboardResponse
from app.services import dashboard_service

router = APIRouter(tags=["dashboard"])

_read = require_permission("policy:read")


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    user: CurrentUser = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> DashboardResponse:
    """Portfolio overview: totals, status counts, expiry buckets, category breakdown, upcoming."""
    return await dashboard_service.get_dashboard(db, user)
