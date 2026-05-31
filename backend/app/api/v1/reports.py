"""Renewal report endpoints — JSON list of policies expiring soon.

Thin router: auth + permission, delegate to data_io_service.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import require_permission
from app.core.security import CurrentUser
from app.db.session import get_db
from app.schemas.reports import RenewalReportRow
from app.services import data_io_service

router = APIRouter(prefix="/reports", tags=["reports"])

_read = require_permission("policy:read")


@router.get(
    "/renewals",
    response_model=list[RenewalReportRow],
    summary="Upcoming renewals report (JSON)",
)
async def renewals_report(
    window_days: int = Query(90, ge=1, le=365, description="Days ahead to include"),
    user: CurrentUser = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> list[RenewalReportRow]:
    """Return policies expiring within `window_days` days, ordered by expiry asc.

    Each row includes policy_id, title, category, provider_name, expiry_date,
    days_left, premium_inr, sum_insured_inr, and status.

    Requires policy:read permission.  Results are tenant/org-scoped.
    """
    return await data_io_service.fetch_renewal_report(db, user, window_days=window_days)
