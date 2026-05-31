"""Usage / metering service (M5) — current resource counts vs plan limits.

Counting decisions
------------------
policies
    Counts all Policy rows for the tenant whose status is NOT 'cancelled'.
    Rationale: cancelled policies no longer consume active slot capacity in the
    product (they can't trigger alerts, can't be renewed), so excluding them
    gives a fair picture of active policy load.  Draft and pending_approval
    policies ARE counted — they hold a slot until resolved.

users
    Counts all Profile rows for the tenant where is_active=True.
    Inactive (deactivated) users do not consume a seat.

documents
    Counts all PolicyDocument rows for the tenant (no status filter on documents —
    every stored file consumes vault storage regardless of policy state).

alerts_month
    Counts Alert rows for the tenant where scheduled_for falls within the current
    calendar month (UTC date range, inclusive of today).  All statuses are counted
    (scheduled, sent, delivered, failed, etc.) because they were all generated
    against the quota.  Cancelled alerts are excluded — they were explicitly
    withdrawn and should not count against the limit.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.alerts import Alert
from app.db.models.billing import Plan, Subscription
from app.db.models.insurance import Policy, PolicyDocument
from app.db.models.tenancy import Profile
from app.schemas.billing import UsageMetric, UsageResponse
from app.services.entitlements import get_entitlements

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _metric(used: int, limits: dict, key: str) -> UsageMetric:
    """Build a UsageMetric from a raw count and a limits dict entry."""
    limit: int = limits.get(key, -1)
    if limit is None:
        limit = -1
    return UsageMetric(used=used, limit=limit)


def _month_bounds() -> tuple[date, date]:
    """Return (first_day_of_month, last_day_of_month) for the current UTC month."""
    today = datetime.now(UTC).date()
    first = today.replace(day=1)
    # Find last day by going to the first of next month minus one day
    if today.month == 12:
        last = date(today.year + 1, 1, 1).replace(day=1)
    else:
        last = date(today.year, today.month + 1, 1)
    # last is the first day of next month — we use an open-ended < comparison
    return first, last


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_usage(db: AsyncSession, tenant_id: str | uuid.UUID) -> UsageResponse:
    """Return current resource usage vs plan limits for ``tenant_id``.

    Steps:
    1. Load subscription to determine plan_tier + status.
    2. Resolve entitlements (reuses get_entitlements — same logic as all gated calls).
    3. Run 4 aggregate COUNT queries, all tenant-scoped.
    4. Return UsageResponse.
    """
    tid = uuid.UUID(str(tenant_id))

    # ---- 1. Subscription / tier resolution -----------------------------------
    sub: Subscription | None = (
        await db.execute(select(Subscription).where(Subscription.tenant_id == tid))
    ).scalar_one_or_none()

    if sub is None:
        status = "none"
        plan_tier = "free"
    else:
        status = sub.status
        if sub.status == "trialing":
            plan_tier = "trialing"
        elif sub.plan_id is not None:
            plan_row: Plan | None = (
                await db.execute(select(Plan).where(Plan.id == sub.plan_id))
            ).scalar_one_or_none()
            plan_tier = plan_row.tier if plan_row else "free"
        else:
            plan_tier = "free"

    # ---- 2. Entitlements (limits) -------------------------------------------
    ents = await get_entitlements(db, tenant_id)
    limits: dict = ents.get("limits", {})

    # ---- 3. Aggregate counts ------------------------------------------------
    month_start, month_end = _month_bounds()

    # policies: exclude cancelled — they no longer occupy an active slot
    policies_count: int = (
        await db.execute(
            select(func.count(Policy.id)).where(
                Policy.tenant_id == tid,
                Policy.status != "cancelled",
            )
        )
    ).scalar_one()

    # users: active profiles only
    users_count: int = (
        await db.execute(
            select(func.count(Profile.id)).where(
                Profile.tenant_id == tid,
                Profile.is_active.is_(True),
            )
        )
    ).scalar_one()

    # documents: all documents (vault storage regardless of policy state)
    documents_count: int = (
        await db.execute(
            select(func.count(PolicyDocument.id)).where(
                PolicyDocument.tenant_id == tid
            )
        )
    ).scalar_one()

    # alerts_month: all non-cancelled alerts whose scheduled_for is in the current month
    alerts_count: int = (
        await db.execute(
            select(func.count(Alert.id)).where(
                Alert.tenant_id == tid,
                Alert.scheduled_for >= month_start,
                Alert.scheduled_for < month_end,
                Alert.status != "cancelled",
            )
        )
    ).scalar_one()

    # ---- 4. Build response --------------------------------------------------
    return UsageResponse(
        plan_tier=plan_tier,
        status=status,
        usage={
            "policies": _metric(policies_count, limits, "policies"),
            "users": _metric(users_count, limits, "users"),
            "documents": _metric(documents_count, limits, "documents"),
            "alerts_month": _metric(alerts_count, limits, "alerts_month"),
        },
    )
