"""In-app notification feed endpoints (bell icon + history page).

GET /notifications         — bell feed (unacked alerts + pending approvals, capped 20)
GET /notifications/history — paginated full history (all statuses, limit/offset)

Both endpoints share the same router so no router.py change is needed.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import get_current_user
from app.core.security import CurrentUser
from app.db.session import get_db
from app.schemas.notification import NotificationFeed, NotificationItem
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


@router.get(
    "/notifications/history",
    response_model=list[NotificationItem],
    summary="Get paginated notification history",
)
async def get_notification_history(
    limit: int = Query(default=50, ge=1, le=200, description="Max items to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[NotificationItem]:
    """Return a paginated history of ALL notifications for the authenticated user.

    Unlike the bell feed, history includes:
    - **All alerts** regardless of status (scheduled, sent, acknowledged, cancelled …)
    - **All approvals** regardless of status (pending, approved, rejected, cancelled)

    Items are sorted newest-first.  Use `limit` and `offset` for pagination.
    The `total` field in the response reflects the full count before pagination.

    Authorization: any authenticated user (no special role required).
    Scope: tenant + accessible org(s) — same scoping rules as alerts and approvals.
    """
    result = await notification_feed_service.get_history(db, user, limit=limit, offset=offset)
    return result.items
