"""Subscription service (M5) — lifecycle + Razorpay integration + webhook handling.

Key patterns:
- get_current: load a tenant's subscription (never raises on missing — returns None).
- list_active_plans: all is_active plans from DB.
- start_or_update_subscription: create a Razorpay subscription + persist.
- handle_webhook: idempotent; guards on billing_events.event_id uniqueness.
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import razorpay as rzp
from app.core.errors import AppError, not_found
from app.db.models.billing import BillingEvent, Plan, Subscription

log = logging.getLogger("svault.subscription")


async def get_current(db: AsyncSession, tenant_id: str | uuid.UUID) -> Subscription | None:
    """Return the tenant's subscription row or None."""
    tid = uuid.UUID(str(tenant_id))
    stmt = select(Subscription).where(Subscription.tenant_id == tid)
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_active_plans(db: AsyncSession) -> list[Plan]:
    """All active plans ordered by price."""
    stmt = select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.price_inr.asc())
    return list((await db.execute(stmt)).scalars().all())


async def start_or_update_subscription(
    db: AsyncSession,
    tenant_id: str | uuid.UUID,
    plan_id: uuid.UUID,
    notes: dict | None = None,
) -> dict:
    """Create (or upgrade) a Razorpay subscription and persist the local record.

    Returns a dict with the Razorpay subscription id and short_url for checkout.
    If Razorpay keys are not configured the function still persists the local
    subscription in 'active' status (useful for test/dev without real keys).
    """
    tid = uuid.UUID(str(tenant_id))

    # Validate the plan exists and is active.
    plan: Plan | None = (
        await db.execute(select(Plan).where(Plan.id == plan_id))
    ).scalar_one_or_none()
    if plan is None or not plan.is_active:
        raise not_found("Plan not found or inactive")

    # Load or create the local subscription record.
    sub: Subscription | None = await get_current(db, tid)
    if sub is None:
        sub = Subscription(tenant_id=tid, plan_id=plan_id, status="active")
        db.add(sub)
    else:
        sub.plan_id = plan_id
        sub.status = "active"

    razorpay_ref: dict = {}

    # Attempt to create a Razorpay subscription (silently skip if keys absent).
    if plan.razorpay_plan_id:
        try:
            rzp_sub = await rzp.create_subscription(
                plan_id=plan.razorpay_plan_id,
                notes=notes or {"tenant_id": str(tid)},
            )
            sub.razorpay_subscription_id = rzp_sub.get("id")
            razorpay_ref = {
                "razorpay_subscription_id": rzp_sub.get("id"),
                "short_url": rzp_sub.get("short_url"),
            }
        except AppError as exc:
            # Log and continue — the local record is still persisted so the
            # subscription page can show the state; Razorpay can be retried.
            log.warning("razorpay_create_subscription_failed: %s", exc.message)

    await db.commit()
    await db.refresh(sub)

    return {
        "subscription_id": str(sub.id),
        "status": sub.status,
        "plan_id": str(plan_id),
        **razorpay_ref,
    }


# ---------------------------------------------------------------------------
# Webhook handler — idempotent
# ---------------------------------------------------------------------------

_SUBSCRIPTION_STATUS_MAP: dict[str, str] = {
    "subscription.authenticated": "active",
    "subscription.activated": "active",
    "subscription.charged": "active",
    "subscription.pending": "past_due",
    "subscription.halted": "past_due",
    "subscription.cancelled": "cancelled",
    "subscription.completed": "expired",
    "payment.failed": "past_due",
}


async def handle_webhook(db: AsyncSession, event_type: str, payload: dict) -> bool:
    """Process a Razorpay webhook payload idempotently.

    Returns True if the event was processed, False if it was a duplicate.
    Idempotency is enforced via billing_events.event_id (unique constraint in DB).
    """
    event_id: str | None = payload.get("id")

    # --- idempotency check ---
    if event_id:
        exists = (
            await db.execute(
                select(BillingEvent).where(BillingEvent.event_id == event_id)
            )
        ).scalar_one_or_none()
        if exists is not None:
            log.info("webhook_duplicate event_id=%s", event_id)
            return False  # already processed

    # --- extract Razorpay subscription id from the payload ---
    rzp_sub_id: str | None = None
    entity = payload.get("payload", {})
    # Razorpay wraps event data under payload.subscription.entity or payload.payment.entity
    for key in ("subscription", "payment"):
        sub_entity = entity.get(key, {}).get("entity", {})
        if sub_entity.get("id", "").startswith("sub_"):
            rzp_sub_id = sub_entity.get("id")
            break
        # payment.failed carries subscription_id on the payment entity
        if sub_entity.get("subscription_id", "").startswith("sub_"):
            rzp_sub_id = sub_entity.get("subscription_id")
            break

    # --- update local subscription if we can match it ---
    tenant_id: uuid.UUID | None = None
    if rzp_sub_id:
        sub: Subscription | None = (
            await db.execute(
                select(Subscription).where(
                    Subscription.razorpay_subscription_id == rzp_sub_id
                )
            )
        ).scalar_one_or_none()

        if sub is not None:
            tenant_id = sub.tenant_id
            new_status = _SUBSCRIPTION_STATUS_MAP.get(event_type)
            if new_status:
                sub.status = new_status
                log.info(
                    "webhook_status_update rzp_sub=%s new_status=%s",
                    rzp_sub_id, new_status,
                )

    # --- persist the billing event (idempotency guard) ---
    event = BillingEvent(
        tenant_id=tenant_id,
        event_id=event_id,
        event_type=event_type,
        payload=payload,
        processed=True,
    )
    db.add(event)

    try:
        await db.commit()
    except IntegrityError:
        # Race condition: another process beat us; treat as duplicate.
        await db.rollback()
        log.info("webhook_race_duplicate event_id=%s", event_id)
        return False

    return True
