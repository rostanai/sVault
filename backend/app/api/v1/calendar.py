"""iCalendar (.ics) renewal-feed endpoint.

GET /calendar.ics — returns a text/calendar document with one all-day VEVENT
per policy expiry date (and a second event per renewal date when set).  The
feed can be imported directly into Google Calendar, Outlook, Apple Calendar etc.

Auth: Bearer JWT required, policy:read permission.
Scope: tenant + org-scoped (same as list_policies via _accessible_org_filter).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import require_permission
from app.core.security import CurrentUser
from app.db.session import get_db
from app.services import calendar_service, policy_service

router = APIRouter(tags=["calendar"])

_read = require_permission("policy:read")


@router.get(
    "/calendar.ics",
    summary="Download iCalendar renewal feed",
    response_class=Response,
    responses={
        200: {
            "description": "iCalendar (.ics) file with policy expiry / renewal events",
            "content": {"text/calendar": {}},
        },
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permission"},
    },
)
async def get_calendar_feed(
    user: CurrentUser = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Return an RFC 5545 iCalendar feed of policy renewal dates.

    Each policy with an expiry_date contributes:
    - One all-day event on the expiry date ("Renewal due: …").
    - One all-day event on the renewal date ("Renewal date: …") when set.

    The feed is tenant/org-scoped: admins/managers see the full group; owners/viewers
    see their own org only (same rules as the policy list endpoint).

    Requires **policy:read** permission.
    """
    # Fetch all accessible policies (up to 1000; renewals feed is a complete snapshot).
    policies = await policy_service.list_policies(db, user, limit=1000)

    ics_content = calendar_service.build_ics(policies)

    return Response(
        content=ics_content,
        media_type="text/calendar",
        headers={
            "Content-Disposition": 'attachment; filename="svault-renewals.ics"',
            "Cache-Control": "no-store",
        },
    )
