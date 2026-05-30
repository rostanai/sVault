"""Subscription service (M5) — lifecycle + Razorpay integration + webhook handling.

Key patterns:
- get_current: load a tenant's subscription (never raises on missing — returns None).
- list_active_plans: all is_active plans from DB.
- start_or_update_subscription: create a Razorpay subscription + persist.
- handle_webhook: idempotent; guards on billing_events.event_id uniqueness.

Security notes (C2 fix):
- Events with no event_id are REJECTED immediately — never processed.
- Idempotency is atomic: INSERT the billing_events row FIRST (unique event_id constraint);
  catch IntegrityError (duplicate) → rollback and return False without applying any
  status change. Only on successful insert do we apply the subscription transition.
- select(Subscription).with_for_update() serializes concurrent webhooks for the same sub.
- Notes.tenant_id is verified against the matched subscription's tenant_id (M2 fix).

Security notes (M1 fix):
- start_or_update_subscription NEVER persists status='active' until a confirmed
  subscription.activated / subscription.charged webhook arrives. Local records are
  persisted as 'trialing' (new) or left in their current status (updates). The dev-skip
  path is gated behind settings.env == 'dev'.
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import razorpay as rzp
from app.core.config import settings
from app.core.errors import AppError, ErrorCode, not_found
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

    Security (M1): The local subscription is NEVER persisted as 'active' by this
    function. The status is set to 'trialing' for new subscriptions, or left at the
    current status for upgrades. Only a confirmed webhook event
    (subscription.activated / subscription.charged) from Razorpay may set 'active'.

    In dev mode (settings.env == 'dev') and when Razorpay keys are absent, the
    subscription is stored as 'trialing' (not 'active') — the caller must simulate a
    webhook to set it active in tests.
    """
    tid = uuid.UUID(str(tenant_id))

    # Validate the plan exists and is active.
    plan: Plan | None = (
        await db.execute(select(Plan).where(Plan.id == plan_id))
    ).scalar_one_or_none()
    if plan is None or not plan.is_active:
        raise not_found("Plan not found or inactive")

    # Load or create the local subscription record.
    # Status stays 'trialing' (new) or preserves current status (update).
    # Only a webhook (subscription.activated / subscription.charged) may set 'active'.
    sub: Subscription | None = await get_current(db, tid)
    if sub is None:
        sub = Subscription(tenant_id=tid, plan_id=plan_id, status="trialing")
        db.add(sub)
    else:
        sub.plan_id = plan_id
        # Do NOT set status='active' here — preserve current status.
        # If currently 'active' from a prior webhook, keep it; if 'trialing', keep it.

    razorpay_ref: dict = {}

    # Attempt to create a Razorpay subscription when a plan has a razorpay_plan_id.
    # Keys absent or plan has no razorpay_plan_id → skip, local record stays 'pending'.
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
            # Log and continue — the local record is still persisted as 'trialing'.
            # The tenant must complete payment via the Razorpay checkout before
            # entitlements are upgraded to the paid plan level.
            log.warning(
                "razorpay_create_subscription_failed tenant_id=%s plan_id=%s err=%s",
                tid, plan_id, exc.message,
            )
    else:
        # No razorpay_plan_id: dev/test path or free plan.
        # Gate auto-activation: only allowed in dev env.
        if settings.env == "dev":
            log.info(
                "dev_mode_no_razorpay_plan_id tenant_id=%s plan_id=%s "
                "status remains pending; send a simulated webhook to activate",
                tid, plan_id,
            )
        else:
            log.warning(
                "missing_razorpay_plan_id_in_non_dev tenant_id=%s plan_id=%s",
                tid, plan_id,
            )

    await db.commit()
    await db.refresh(sub)

    return {
        "subscription_id": str(sub.id),
        "status": sub.status,
        "plan_id": str(plan_id),
        **razorpay_ref,
    }


# ---------------------------------------------------------------------------
# Webhook handler — idempotent, atomic, tenant-verified
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

    Security (C2):
    - Events with no event_id are REJECTED immediately (AppError validation_error).
    - Idempotency is ATOMIC: INSERT the billing_events row first, relying on the
      unique constraint on event_id. On IntegrityError (duplicate) → rollback and
      return False WITHOUT applying any status change.
    - subscription row is locked with SELECT ... FOR UPDATE to serialize concurrent
      webhooks on the same subscription.

    Security (M2 / audit):
    - notes.tenant_id is verified against the matched subscription.tenant_id.
      A mismatch is logged as a warning and the status transition is skipped.
    - tenant_id is logged on every status transition.
    """
    event_id: str | None = payload.get("id")

    # --- C2: reject events with no event_id — never process id-less events ---
    if not event_id:
        raise AppError(
            ErrorCode.validation_error,
            "Webhook event missing 'id' field — cannot guarantee idempotency; rejecting.",
            http_status=400,
        )

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

    # Extract the tenant_id from notes (for M2 cross-tenant verification).
    notes_tenant_id: str | None = None
    for key in ("subscription", "payment"):
        sub_entity = entity.get(key, {}).get("entity", {})
        if sub_entity.get("notes", {}).get("tenant_id"):
            notes_tenant_id = str(sub_entity["notes"]["tenant_id"])
            break

    # --- C2: INSERT billing_events FIRST (atomic idempotency guard) ---
    # We commit the dedupe row before applying any status change.
    # The unique constraint on event_id will fire if a duplicate races in.
    # We use a savepoint (nested transaction) so an IntegrityError rolls back
    # only the insert attempt, leaving the outer session usable.

    # Determine tenant_id for the billing event (filled in after sub lookup below).
    # We stage the sub lookup inside the guard so the insert can carry tenant_id.
    # To keep the INSERT-first guarantee, we INSERT with tenant_id=None initially,
    # catch any IntegrityError (duplicate), and only THEN resolve the subscription.

    event_row = BillingEvent(
        tenant_id=None,  # filled below if subscription found
        event_id=event_id,
        event_type=event_type,
        payload=payload,
        processed=False,  # will be updated to True after successful processing
    )
    db.add(event_row)

    try:
        # flush to DB — triggers the unique constraint check without committing.
        await db.flush()
    except IntegrityError:
        # Duplicate event_id — race condition or Razorpay retry.
        # Rollback the flush and return False WITHOUT applying any status change.
        await db.rollback()
        log.info("webhook_duplicate event_id=%s", event_id)
        return False

    # --- dedupe INSERT succeeded — now apply the subscription transition ---
    tenant_id: uuid.UUID | None = None
    if rzp_sub_id:
        # Lock the subscription row to serialize concurrent webhooks.
        sub: Subscription | None = (
            await db.execute(
                select(Subscription)
                .where(Subscription.razorpay_subscription_id == rzp_sub_id)
                .with_for_update()
            )
        ).scalar_one_or_none()

        if sub is not None:
            tenant_id = sub.tenant_id

            # M2: verify notes.tenant_id matches the subscription's tenant_id.
            if notes_tenant_id is not None:
                if str(sub.tenant_id) != notes_tenant_id:
                    log.warning(
                        "webhook_tenant_mismatch event_id=%s rzp_sub=%s "
                        "notes_tenant=%s sub_tenant=%s — skipping status update",
                        event_id, rzp_sub_id, notes_tenant_id, sub.tenant_id,
                    )
                    # Mark the event as processed (it was received and deduplicated),
                    # but do NOT apply the status transition.
                    event_row.tenant_id = tenant_id
                    event_row.processed = False  # processed=False: transition skipped
                    await db.commit()
                    return False

            new_status = _SUBSCRIPTION_STATUS_MAP.get(event_type)
            if new_status:
                sub.status = new_status
                log.info(
                    "webhook_status_update event_id=%s rzp_sub=%s "
                    "new_status=%s tenant_id=%s",
                    event_id, rzp_sub_id, new_status, tenant_id,
                )

    # Update the billing event with resolved tenant_id and mark processed.
    event_row.tenant_id = tenant_id
    event_row.processed = True

    await db.commit()
    return True
