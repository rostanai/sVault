"""In-app notification feed endpoint (bell icon).

GET /notifications

Returns a merged feed of:
- Unacknowledged renewal alerts for the caller's accessible policies.
- Pending approvals in the caller's tenant + org scope.

Items are capped at 20 (newest first).  unread_count reflects the real
total (capped display at 99) so the bell badge is accurate.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import get_current_user
from app.core.security import CurrentUser
from app.db.session import get_db
from app.schemas.notification import NotificationFeed
from app.services import notification_feed_service

router = APIRouter(tags=["notifications"])


@router.get(
    "/notifications",
    response_model=NotificationFeed,
    summary="Get in-app notification feed (bell)",
)
async def get_notifications(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationFeed:
    """Return the notification feed for the authenticated user.

    Items (newest first, capped at 20):
    - **type=alert**: unacknowledged renewal alerts — title includes the policy name,
      subtitle includes lead-day and channel.
    - **type=approval**: pending approval requests — title includes the action type,
      subtitle is the entity type.

    **unread_count**: real total of unacked alerts + pending approvals in scope,
    capped at 99 for badge display.

    Authorization: any authenticated user (no special role required).
    Scope: tenant + accessible org(s) — same scoping rules as alerts and approvals.
    """
    return await notification_feed_service.get_feed(db, user)
