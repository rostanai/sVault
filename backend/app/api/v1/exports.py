"""Export endpoints — policies as CSV/XLSX and renewal reports as CSV/XLSX.

Thin routers: auth + permission check, call service, return streaming file.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import require_permission
from app.core.security import CurrentUser
from app.db.session import get_db
from app.services import data_io_service

router = APIRouter(tags=["exports"])

_read = require_permission("policy:read")


# ---------------------------------------------------------------------------
# Policy export
# ---------------------------------------------------------------------------


@router.get(
    "/policies/export",
    summary="Export policies as CSV or XLSX",
    responses={
        200: {
            "description": "File download",
            "content": {
                "text/csv": {},
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {},
            },
        }
    },
)
async def export_policies(
    format: str = Query("csv", pattern="^(csv|xlsx)$", description="csv or xlsx"),  # noqa: A002
    user: CurrentUser = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Download all accessible policies as a flat CSV or XLSX file.

    Columns: title, category, policy_number, provider, sum_insured_inr,
    premium_inr, gst_inr, inception_date, expiry_date, renewal_date, status.

    Requires policy:read permission.  Results are scoped to the caller's
    accessible orgs (admin/manager = whole tenant group; owner/viewer = own org).
    """
    policies, provider_map = await data_io_service._fetch_policies_for_export(db, user)

    if format == "xlsx":
        buf = data_io_service.write_policies_xlsx(policies, provider_map)
        return Response(
            content=buf.read(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=\"policies.xlsx\""},
        )

    buf = data_io_service.write_policies_csv(policies, provider_map)

    def _iter():
        yield buf.read()

    return StreamingResponse(
        _iter(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=\"policies.csv\""},
    )


# ---------------------------------------------------------------------------
# Renewal report export
# ---------------------------------------------------------------------------


@router.get(
    "/reports/renewals/export",
    summary="Export renewal report as CSV or XLSX",
    responses={
        200: {
            "description": "File download",
            "content": {
                "text/csv": {},
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {},
            },
        }
    },
)
async def export_renewals(
    format: str = Query("csv", pattern="^(csv|xlsx)$", description="csv or xlsx"),  # noqa: A002
    window_days: int = Query(90, ge=1, le=365, description="Days ahead to look for renewals"),
    user: CurrentUser = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Download the renewal report (policies expiring within window_days) as CSV or XLSX.

    Requires policy:read permission.  Results are tenant/org-scoped.
    """
    rows = await data_io_service.fetch_renewal_report(db, user, window_days=window_days)

    if format == "xlsx":
        buf = data_io_service.write_renewals_xlsx(rows)
        return Response(
            content=buf.read(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=\"renewals.xlsx\""},
        )

    buf = data_io_service.write_renewals_csv(rows)

    def _iter():
        yield buf.read()

    return StreamingResponse(
        _iter(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=\"renewals.csv\""},
    )
