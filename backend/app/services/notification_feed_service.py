"""In-app notification feed service (bell icon).

Merges unacknowledged alerts + pending approvals visible to the caller,
resolves policy titles in a single batched lookup, and returns a capped
feed (newest 20 items) with a real unread_count (capped at 99).

Also exposes ``get_history`` for the paginated history page — returns ALL
recent alerts (any status) + ALL recent approvals (any status), newest first,
with limit/offset pagination.

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
from app.schemas.notification import NotificationFeed, NotificationHistory, NotificationItem
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


# ---------------------------------------------------------------------------
# Shared item-builder helpers
# ---------------------------------------------------------------------------

def _alert_item(alert: Alert, policy_titles: dict[uuid.UUID, str]) -> NotificationItem:
    """Build a NotificationItem from an Alert ORM row."""
    policy_title = policy_titles.get(alert.policy_id, "Unknown policy")
    return NotificationItem(
        id=str(alert.id),
        type="alert",
        title=f"Renewal reminder — {policy_title}",
        subtitle=f"{alert.lead_day}d before expiry · {alert.channel}",
        href="/app/alerts",
        created_at=alert.created_at,
    )


def _approval_item(approval: Approval) -> NotificationItem:
    """Build a NotificationItem from an Approval ORM row."""
    action_label = _ACTION_LABELS.get(approval.action_type, approval.action_type)
    return NotificationItem(
        id=str(approval.id),
        type="approval",
        title=f"Approval pending — {action_label}",
        subtitle=approval.entity_type,
        href="/app/approvals",
        created_at=approval.created_at,
    )


async def _resolve_policy_titles(
    db: AsyncSession, alerts: list[Alert]
) -> dict[uuid.UUID, str]:
    """Resolve policy titles for the given alerts in one batched lookup."""
    policy_ids = {a.policy_id for a in alerts}
    if not policy_ids:
        return {}
    policies = list(
        (
            await db.execute(
                select(Policy.id, Policy.title).where(Policy.id.in_(list(policy_ids)))
            )
        ).all()
    )
    return {row.id: row.title for row in policies}


# ---------------------------------------------------------------------------
# Bell feed (unacked alerts + pending approvals, capped at 20)
# ---------------------------------------------------------------------------

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
    policy_titles = await _resolve_policy_titles(db, alerts)

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
        items.append(_alert_item(alert, policy_titles))

    for approval in approvals:
        items.append(_approval_item(approval))

    # Sort merged list newest-first and truncate.
    items.sort(key=lambda i: i.created_at, reverse=True)
    items = items[:_FEED_CAP]

    return NotificationFeed(unread_count=unread_count, items=items)


# ---------------------------------------------------------------------------
# History feed (all alerts any status + all approvals any status, paginated)
# ---------------------------------------------------------------------------

_HISTORY_DEFAULT_LIMIT = 50
_HISTORY_MAX_LIMIT = 200


async def get_history(
    db: AsyncSession,
    user: CurrentUser,
    limit: int = _HISTORY_DEFAULT_LIMIT,
    offset: int = 0,
) -> NotificationHistory:
    """Return a paginated history feed for *user*.

    Broader than the bell feed — includes ALL alerts (sent, acknowledged,
    cancelled, etc.) and ALL approvals (pending, approved, rejected, cancelled),
    newest first.  Scoped to the caller's tenant + accessible org(s).
    """
    if not user.tenant_id:
        return NotificationHistory(items=[], limit=limit, offset=offset, total=0)

    # Clamp limit to a safe maximum to prevent runaway queries.
    limit = max(1, min(limit, _HISTORY_MAX_LIMIT))

    tid = uuid.UUID(user.tenant_id)
    org = _accessible_org(user)

    # ------------------------------------------------------------------
    # 1. ALL alerts in scope (any status), ordered newest-first.
    # ------------------------------------------------------------------
    alert_stmt = select(Alert).where(Alert.tenant_id == tid)
    if org is not None:
        alert_stmt = alert_stmt.where(Alert.org_id == org)
    alert_stmt = alert_stmt.order_by(Alert.created_at.desc())
    all_alerts = list((await db.execute(alert_stmt)).scalars().all())

    # ------------------------------------------------------------------
    # 2. ALL approvals in scope (any status), ordered newest-first.
    # ------------------------------------------------------------------
    approval_stmt = select(Approval).where(Approval.tenant_id == tid)
    if org is not None:
        approval_stmt = approval_stmt.where(Approval.org_id == org)
    approval_stmt = approval_stmt.order_by(Approval.created_at.desc())
    all_approvals = list((await db.execute(approval_stmt)).scalars().all())

    # ------------------------------------------------------------------
    # 3. Resolve policy titles for all alerts in ONE batched lookup.
    # ------------------------------------------------------------------
    policy_titles = await _resolve_policy_titles(db, all_alerts)

    # ------------------------------------------------------------------
    # 4. Merge and sort newest-first, then paginate.
    # ------------------------------------------------------------------
    items: list[NotificationItem] = []

    for alert in all_alerts:
        items.append(_alert_item(alert, policy_titles))

    for approval in all_approvals:
        items.append(_approval_item(approval))

    items.sort(key=lambda i: i.created_at, reverse=True)

    total = len(items)
    page = items[offset: offset + limit]

    return NotificationHistory(items=page, limit=limit, offset=offset, total=total)
