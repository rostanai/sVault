"""Dashboard endpoints (M3)."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import require_permission
from app.core.security import CurrentUser
from app.db.session import get_db
from app.schemas.dashboard import DashboardResponse, GroupDashboardResponse
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


@router.get("/dashboard/group", response_model=GroupDashboardResponse)
async def get_group_dashboard(
    user: CurrentUser = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> GroupDashboardResponse:
    """Consolidated group dashboard — roll-up across all subsidiaries the caller can see.

    Returns group-wide ``totals`` (same shape as ``GET /dashboard``) and a
    ``by_org`` breakdown with one entry per subsidiary/org that has at least
    one policy in scope.  Access is gated by the caller's accessible orgs:

    - Admin / Manager → all orgs in the tenant (full group roll-up).
    - Owner / Viewer  → their own org only (``by_org`` has a single entry).

    Monetary fields (``sum_insured_inr``, ``premium_inr``) are returned as
    fixed-point decimal strings to avoid JSON floating-point drift.
    ``expiring_30`` counts policies expiring within the next 30 calendar days
    that are in an alertable status (``active`` or ``expiring``).
    Results are ordered by ``premium_inr`` descending then ``org_name``
    ascending.
    """
    return await dashboard_service.get_group_dashboard(db, user)
