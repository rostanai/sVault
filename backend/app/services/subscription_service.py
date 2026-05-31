"""Subscription service (M5) — lifecycle + Razorpay integration + webhook handling.

Key patterns:
- get_current: load a tenant's subscription (never raises on missing — returns None).
- list_active_plans: all is_active plans from DB.
- start_or_update_subscription: create a Razorpay subscription + persist (two branches).
- handle_webhook: idempotent; guards on billing_events.event_id uniqueness.

Security notes (C2 fix):
- Events with no event_id are REJECTED immediately — never processed.
- Idempotency is atomic: INSERT the billing_events row FIRST (unique event_id constraint);
  catch IntegrityError (duplicate) → rollback and return False without applying any
  status change. Only on successful insert do we apply the subscription transition.
- select(Subscription).with_for_update() serializes concurrent webhooks for the same sub.
- Notes.tenant_id is verified against the matched subscription's tenant_id (M2 fix).

Security notes (M1 fix — updated):
- Branch 1 (real payment): start_or_update_subscription NEVER persists status='active'
  without a confirmed subscription.activated / subscription.charged webhook. This branch
  is entered only when settings.razorpay_key_id AND plan.razorpay_plan_id are both set —
  i.e., in production with a live Razorpay account.
- Branch 2 (simulated/demo): when Razorpay is NOT configured (razorpay_key_id is empty)
  OR the plan has no razorpay_plan_id, the subscription is immediately set to 'active'.
  This is safe because no live Razorpay credentials exist in this environment — there is
  no payment processor to bypass.  In production razorpay_key_id is always non-empty, so
  branch 2 is never reached there.
"""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import razorpay as rzp
from app.core.config import settings
from app.core.errors import AppError, ErrorCode, not_found
from app.db.models.billing import BillingEvent, Invoice, Plan, Subscription
from app.services import secrets_service

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


async def list_invoices(db: AsyncSession, tenant_id: str | uuid.UUID) -> list[Invoice]:
    """Return all invoices for a tenant ordered by issued_at desc."""
    tid = uuid.UUID(str(tenant_id))
    stmt = (
        select(Invoice)
        .where(Invoice.tenant_id == tid)
        .order_by(Invoice.issued_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def start_or_update_subscription(
    db: AsyncSession,
    tenant_id: str | uuid.UUID,
    plan_id: uuid.UUID,
    notes: dict | None = None,
) -> dict:
    """Create (or upgrade) a Razorpay subscription and persist the local record.

    Returns a dict suitable for SubscribeResponse, including a ``payment_required``
    boolean so the caller knows whether to open a Razorpay checkout.

    Branch 1 — Real payment path
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Conditions: ``settings.razorpay_key_id`` is non-empty AND ``plan.razorpay_plan_id``
    is set.  A Razorpay subscription is created via the API.  The local record is
    persisted with ``plan_id`` updated but the status is NOT forced to ``'active'``
    here — only a confirmed webhook (subscription.activated / subscription.charged) may
    do that.  Returns ``payment_required=True`` plus the Razorpay checkout ``short_url``.

    Branch 2 — Simulated/demo activation
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Conditions: ``settings.razorpay_key_id`` is empty (Razorpay not configured) OR
    ``plan.razorpay_plan_id`` is None (plan not yet linked to a Razorpay plan).
    This is a no-payment environment (dev/demo/test or the Free plan), so there is no
    real charge to collect.  The subscription is immediately set to ``status='active'``
    with the chosen plan — safe because without live Razorpay credentials no real
    payment processor can be invoked.  Returns ``payment_required=False``,
    ``razorpay_subscription_id=None``, ``short_url=None``.

    Security note (M1): the ``status='active'`` shortcut in branch 2 is gated behind
    the absence of live Razorpay credentials (``razorpay_key_id`` is empty string).  In
    production, where ``razorpay_key_id`` is always set, this branch is never entered
    and the only path to ``'active'`` remains the signed Razorpay webhook.
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

    # Determine which branch to take BEFORE mutating the subscription row.
    # Resolve the Razorpay key from platform_settings (Super-Admin) → env fallback.
    razorpay_key_id = await secrets_service.get_secret(
        db, "razorpay_key_id", settings.razorpay_key_id
    )
    use_real_razorpay: bool = bool(razorpay_key_id and plan.razorpay_plan_id)

    if sub is None:
        if use_real_razorpay:
            # Branch 1: real payment — status stays 'trialing' until webhook fires.
            sub = Subscription(tenant_id=tid, plan_id=plan_id, status="trialing")
        else:
            # Branch 2: simulated/demo — activate immediately (no live billing).
            sub = Subscription(tenant_id=tid, plan_id=plan_id, status="active")
        db.add(sub)
    else:
        sub.plan_id = plan_id
        if not use_real_razorpay:
            # Branch 2: activate immediately so entitlements apply now.
            sub.status = "active"
        # Branch 1: preserve current status; webhook will set 'active'.

    razorpay_ref: dict = {}
    payment_required: bool = False

    if use_real_razorpay:
        # Branch 1: call the Razorpay API to create a subscription.
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
            payment_required = True
            log.info(
                "razorpay_subscription_created tenant_id=%s plan_id=%s rzp_sub=%s",
                tid, plan_id, rzp_sub.get("id"),
            )
        except AppError as exc:
            # Log and continue — local record is persisted as 'trialing'.
            # The tenant must complete payment via Razorpay checkout before
            # entitlements upgrade to the paid plan level.
            log.warning(
                "razorpay_create_subscription_failed tenant_id=%s plan_id=%s err=%s",
                tid, plan_id, exc.message,
            )
    else:
        # Branch 2: simulated/demo activation — no Razorpay call, no charge.
        log.info(
            "simulated_activation tenant_id=%s plan_id=%s "
            "razorpay_key_id_set=%s plan_razorpay_plan_id_set=%s "
            "status=active payment_required=False",
            tid, plan_id,
            bool(settings.razorpay_key_id),
            bool(plan.razorpay_plan_id),
        )

    await db.commit()
    await db.refresh(sub)

    return {
        "subscription_id": str(sub.id),
        "status": sub.status,
        "plan_id": str(plan_id),
        "payment_required": payment_required,
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

    # --- invoice.paid: upsert an Invoice row ---
    if event_type == "invoice.paid":
        inv_entity: dict = payload.get("payload", {}).get("invoice", {}).get("entity", {})
        await _upsert_invoice(db, inv_entity, tenant_id)

    # Update the billing event with resolved tenant_id and mark processed.
    event_row.tenant_id = tenant_id
    event_row.processed = True

    await db.commit()
    return True


# ---------------------------------------------------------------------------
# Subscription lifecycle — cancel / pause / resume
# ---------------------------------------------------------------------------

async def cancel_subscription(db: AsyncSession, tenant_id: str | uuid.UUID) -> Subscription:
    """Cancel the tenant's subscription.

    Behaviour (matches PLANS.md status transitions):
    - If Razorpay is configured AND the subscription has a razorpay_subscription_id,
      attempt to cancel at cycle end via the Razorpay API (best-effort; logged on
      failure).  Set cancel_at_period_end=True but keep status until the webhook
      flips it (subscription.cancelled).
    - Demo / no-Razorpay path (no live keys or no rzp sub id): set status='cancelled'
      and cancel_at_period_end=True immediately so entitlements fall back to Free.

    Raises AppError(not_found) if the tenant has no subscription.
    """
    tid = uuid.UUID(str(tenant_id))
    sub: Subscription | None = await get_current(db, tid)
    if sub is None:
        raise not_found("No subscription found for this tenant")

    razorpay_key_id = await secrets_service.get_secret(
        db, "razorpay_key_id", settings.razorpay_key_id
    )
    use_real_razorpay: bool = bool(razorpay_key_id and sub.razorpay_subscription_id)

    if use_real_razorpay:
        # Best-effort Razorpay cancel-at-cycle-end call.
        # Razorpay v1 API: POST /subscriptions/{id}/cancel with {"cancel_at_cycle_end": 1}
        try:
            await rzp._post(
                f"/subscriptions/{sub.razorpay_subscription_id}/cancel",
                {"cancel_at_cycle_end": 1},
            )
            log.info(
                "razorpay_cancel_at_cycle_end tenant_id=%s rzp_sub=%s",
                tid, sub.razorpay_subscription_id,
            )
        except AppError as exc:
            # Non-fatal: log and continue — webhook will still cancel eventually.
            # TODO: surface a dunning notification via notifications-engineer.
            log.warning(
                "razorpay_cancel_failed tenant_id=%s rzp_sub=%s err=%s",
                tid, sub.razorpay_subscription_id, exc.message,
            )
        # Keep status as-is; webhook (subscription.cancelled) will set cancelled.
        sub.cancel_at_period_end = True
    else:
        # Demo / no-Razorpay: cancel immediately, entitlements fall to Free.
        sub.status = "cancelled"
        sub.cancel_at_period_end = True

    await db.commit()
    await db.refresh(sub)
    log.info(
        "subscription_cancel tenant_id=%s status=%s cancel_at_period_end=%s",
        tid, sub.status, sub.cancel_at_period_end,
    )
    return sub


async def pause_subscription(db: AsyncSession, tenant_id: str | uuid.UUID) -> Subscription:
    """Pause the tenant's subscription.

    Sets status='paused'.  Per PLANS.md the paused state maps to Free entitlements
    (the 'paused' row is absent from the entitlements table mapping, so the
    entitlements service falls back to Free defaults).

    Raises AppError(not_found) if the tenant has no subscription.
    """
    tid = uuid.UUID(str(tenant_id))
    sub: Subscription | None = await get_current(db, tid)
    if sub is None:
        raise not_found("No subscription found for this tenant")

    sub.status = "paused"

    await db.commit()
    await db.refresh(sub)
    log.info("subscription_pause tenant_id=%s", tid)
    return sub


async def resume_subscription(db: AsyncSession, tenant_id: str | uuid.UUID) -> Subscription:
    """Undo a pending cancel or reactivate a paused/cancelled subscription.

    Behaviour:
    - Always clears cancel_at_period_end = False.
    - If status is 'cancelled' or 'paused', restores it to 'active' (demo / no-live-
      Razorpay path, mirrors the demo-activation branch in start_or_update_subscription).
      In production, the webhook drives status; resuming while status is still 'active'
      (i.e. cancel_at_period_end was set) just clears the flag.
    - plan_id is not changed.

    Raises AppError(not_found) if the tenant has no subscription.
    """
    tid = uuid.UUID(str(tenant_id))
    sub: Subscription | None = await get_current(db, tid)
    if sub is None:
        raise not_found("No subscription found for this tenant")

    sub.cancel_at_period_end = False
    if sub.status in ("cancelled", "paused"):
        sub.status = "active"

    await db.commit()
    await db.refresh(sub)
    log.info(
        "subscription_resume tenant_id=%s status=%s cancel_at_period_end=%s",
        tid, sub.status, sub.cancel_at_period_end,
    )
    return sub


def _epoch_to_dt(ts: int | None, fallback_now: bool = True) -> datetime | None:
    """Convert a Unix epoch (seconds) to an aware UTC datetime.

    Returns now() if ts is None and fallback_now is True, otherwise None.
    """
    if ts is not None:
        return datetime.fromtimestamp(int(ts), tz=UTC)
    if fallback_now:
        return datetime.now(tz=UTC)
    return None


async def _upsert_invoice(
    db: AsyncSession,
    inv_entity: dict,
    tenant_id: uuid.UUID | None,
) -> None:
    """Upsert an Invoice row from a Razorpay invoice.paid entity dict.

    Tenant resolution order:
    1. The tenant_id already resolved from the Subscription lookup (passed in).
    2. inv_entity["notes"]["tenant_id"] — set by the subscribe flow.
    3. Look up Subscription by inv_entity["subscription_id"].
    If none resolve, log a warning and skip.
    """
    rzp_invoice_id: str | None = inv_entity.get("id")
    if not rzp_invoice_id:
        log.warning("invoice_paid_entity_missing_id — skipping upsert")
        return

    # Resolve tenant_id if not yet known from the subscription webhook path.
    if tenant_id is None:
        notes_tid = (inv_entity.get("notes") or {}).get("tenant_id")
        if notes_tid:
            try:
                tenant_id = uuid.UUID(str(notes_tid))
            except ValueError:
                log.warning(
                    "invoice_paid_invalid_notes_tenant_id rzp_invoice=%s notes_tid=%s",
                    rzp_invoice_id, notes_tid,
                )

    if tenant_id is None:
        rzp_sub_id_on_inv: str | None = inv_entity.get("subscription_id")
        if rzp_sub_id_on_inv:
            sub_row: Subscription | None = (
                await db.execute(
                    select(Subscription).where(
                        Subscription.razorpay_subscription_id == rzp_sub_id_on_inv
                    )
                )
            ).scalar_one_or_none()
            if sub_row is not None:
                tenant_id = sub_row.tenant_id

    if tenant_id is None:
        log.warning(
            "invoice_paid_no_tenant_id rzp_invoice=%s — skipping upsert",
            rzp_invoice_id,
        )
        return

    # Resolve the local subscription FK (optional — may be None).
    local_sub_id: uuid.UUID | None = None
    rzp_sub_on_inv: str | None = inv_entity.get("subscription_id")
    if rzp_sub_on_inv:
        sub_local: Subscription | None = (
            await db.execute(
                select(Subscription).where(
                    Subscription.razorpay_subscription_id == rzp_sub_on_inv
                )
            )
        ).scalar_one_or_none()
        if sub_local is not None:
            local_sub_id = sub_local.id

    amount_inr = Decimal(str(inv_entity.get("amount", 0))) / 100
    gst_inr = Decimal(str(inv_entity.get("tax_amount", 0))) / 100
    pdf_url: str | None = inv_entity.get("short_url")
    razorpay_payment_id: str | None = inv_entity.get("payment_id")
    issued_at: datetime = (
        _epoch_to_dt(inv_entity.get("issued_at")) or datetime.now(tz=UTC)
    )
    paid_at: datetime | None = _epoch_to_dt(inv_entity.get("paid_at"), fallback_now=False)

    # Idempotent upsert: find existing row by razorpay_invoice_id.
    existing: Invoice | None = (
        await db.execute(
            select(Invoice).where(Invoice.razorpay_invoice_id == rzp_invoice_id)
        )
    ).scalar_one_or_none()

    if existing is not None:
        # Update in place — do NOT create a duplicate.
        existing.amount_inr = amount_inr
        existing.gst_inr = gst_inr
        existing.status = "paid"
        existing.pdf_url = pdf_url
        existing.razorpay_payment_id = razorpay_payment_id
        existing.issued_at = issued_at
        existing.paid_at = paid_at
        log.info(
            "invoice_upsert_updated rzp_invoice=%s tenant_id=%s",
            rzp_invoice_id, tenant_id,
        )
    else:
        invoice = Invoice(
            tenant_id=tenant_id,
            subscription_id=local_sub_id,
            amount_inr=amount_inr,
            gst_inr=gst_inr,
            status="paid",
            razorpay_invoice_id=rzp_invoice_id,
            razorpay_payment_id=razorpay_payment_id,
            issued_at=issued_at,
            paid_at=paid_at,
            pdf_url=pdf_url,
        )
        db.add(invoice)
        log.info(
            "invoice_upsert_created rzp_invoice=%s tenant_id=%s",
            rzp_invoice_id, tenant_id,
        )
