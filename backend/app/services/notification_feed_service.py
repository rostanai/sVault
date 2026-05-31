"""In-app notification feed service (bell icon).

Merges unacknowledged alerts + pending approvals visible to the caller,
resolves policy titles in a single batched lookup, and returns a capped
feed (newest 20 items) with a real unread_count (capped at 99).

No FastAPI imports — pure business logic.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.db.models.alerts import Alert
from app.db.models.approvals import Approval
from app.db.models.insurance import Policy
from app.schemas.notification import NotificationFeed, NotificationItem
from app.services.org_service import is_group_wide

_FEED_CAP = 20
_COUNT_CAP = 99

# Human-readable labels for approval action types.
_ACTION_LABELS: dict[str, str] = {
    "renewal": "Policy renewal",
    "new_policy": "New policy",
    "vendor_finalization": "Vendor finalisation",
    "high_value_premium": "High-value premium",
    "other": "Action",
}


def _accessible_org(user: CurrentUser) -> uuid.UUID | None:
    if user.is_super_admin or is_group_wide(user.role):
        return None
    return uuid.UUID(user.org_id) if user.org_id else None


async def get_feed(db: AsyncSession, user: CurrentUser) -> NotificationFeed:
    """Build the notification feed for *user*."""
    if not user.tenant_id:
        return NotificationFeed(unread_count=0, items=[])

    tid = uuid.UUID(user.tenant_id)
    org = _accessible_org(user)

    # ------------------------------------------------------------------
    # 1. Unacknowledged (non-terminal) alerts in scope.
    # ------------------------------------------------------------------
    alert_stmt = select(Alert).where(
        Alert.tenant_id == tid,
        Alert.status.in_(["scheduled", "sent"]),
    )
    if org is not None:
        alert_stmt = alert_stmt.where(Alert.org_id == org)
    alert_stmt = alert_stmt.order_by(Alert.created_at.desc())
    alerts = list((await db.execute(alert_stmt)).scalars().all())

    # ------------------------------------------------------------------
    # 2. Pending approvals in scope.
    # ------------------------------------------------------------------
    approval_stmt = select(Approval).where(
        Approval.tenant_id == tid,
        Approval.status == "pending",
    )
    if org is not None:
        approval_stmt = approval_stmt.where(Approval.org_id == org)
    approval_stmt = approval_stmt.order_by(Approval.created_at.desc())
    approvals = list((await db.execute(approval_stmt)).scalars().all())

    # ------------------------------------------------------------------
    # 3. Resolve policy titles for alerts in ONE batched lookup.
    # ------------------------------------------------------------------
    policy_ids = {a.policy_id for a in alerts}
    policy_titles: dict[uuid.UUID, str] = {}
    if policy_ids:
        policies = list(
            (
                await db.execute(
                    select(Policy.id, Policy.title).where(Policy.id.in_(list(policy_ids)))
                )
            ).all()
        )
        policy_titles = {row.id: row.title for row in policies}

    # ------------------------------------------------------------------
    # 4. Compute real unread_count (capped at 99) before truncation.
    # ------------------------------------------------------------------
    total_unread = len(alerts) + len(approvals)
    unread_count = min(total_unread, _COUNT_CAP)

    # ------------------------------------------------------------------
    # 5. Merge, sort newest-first, cap to _FEED_CAP items.
    # ------------------------------------------------------------------
    items: list[NotificationItem] = []

    for alert in alerts:
        policy_title = policy_titles.get(alert.policy_id, "Unknown policy")
        items.append(
            NotificationItem(
                id=str(alert.id),
                type="alert",
                title=f"Renewal reminder — {policy_title}",
                subtitle=f"{alert.lead_day}d before expiry · {alert.channel}",
                href="/app/alerts",
                created_at=alert.created_at,
            )
        )

    for approval in approvals:
        action_label = _ACTION_LABELS.get(approval.action_type, approval.action_type)
        items.append(
            NotificationItem(
                id=str(approval.id),
                type="approval",
                title=f"Approval pending — {action_label}",
                subtitle=approval.entity_type,
                href="/app/approvals",
                created_at=approval.created_at,
            )
        )

    # Sort merged list newest-first and truncate.
    items.sort(key=lambda i: i.created_at, reverse=True)
    items = items[:_FEED_CAP]

    return NotificationFeed(unread_count=unread_count, items=items)
