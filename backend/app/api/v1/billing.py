"""Billing endpoints (M5) — plans, subscriptions, invoices, Razorpay webhook.

Route map:
  GET  /plans                     any authed user — active plan list + prices
  GET  /billing/subscription      any authed user — tenant's subscription + entitlements
  GET  /billing/invoices          any authed user — tenant's invoices (issued_at desc)
  POST /billing/subscribe         billing:manage — start/upgrade Razorpay subscription
  POST /billing/webhook           NO user auth  — Razorpay webhook (sig-verified, idempotent)

Webhook design: the handler reads and verifies the HMAC-SHA256 signature from the
raw request body synchronously inside _check_webhook_signature (a Depends that does
NOT itself depend on get_db).  Only after that dependency succeeds does the handler
open a DB session via get_db — enforcing signature-before-DB-access.
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import get_current_user, require_permission
from app.core.errors import AppError, ErrorCode
from app.core.razorpay import verify_webhook_signature
from app.core.security import CurrentUser
from app.db.session import get_db
from app.schemas.billing import (
    InvoiceRead,
    PlanRead,
    SubscribeRequest,
    SubscribeResponse,
    SubscriptionRead,
    SubscriptionWithEntitlements,
    UsageResponse,
)
from app.services import subscription_service, usage_service
from app.services.entitlements import resolve_entitlements

log = logging.getLogger("svault.billing")

router = APIRouter(tags=["billing"])

# Module-level dependency singletons (ruff B008 — no Depends() in default arg position)
_authed = get_current_user
_billing_manage = require_permission("billing:manage")


# ---------------------------------------------------------------------------
# Webhook signature dependency — no DB access; raises 400 on bad sig
# ---------------------------------------------------------------------------

async def _check_webhook_signature(
    request: Request,
    x_razorpay_signature: str | None = Header(None, alias="X-Razorpay-Signature"),
) -> bytes:
    """Verify the Razorpay HMAC-SHA256 webhook signature.

    Returns the raw request body on success (so callers can parse it).
    Raises AppError(http_status=400) on missing or invalid signature.
    This dependency does NOT inject get_db, so an invalid signature is rejected
    before any DB work is attempted.
    """
    raw_body: bytes = await request.body()

    if not x_razorpay_signature:
        raise AppError(
            ErrorCode.validation_error,
            "Missing webhook signature",
            http_status=400,
        )
    if not verify_webhook_signature(raw_body, x_razorpay_signature):
        raise AppError(
            ErrorCode.validation_error,
            "Webhook signature verification failed",
            http_status=400,
        )
    return raw_body


# Module-level singleton for the sig-check dep (ruff B008)
_sig_check = _check_webhook_signature


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/plans", response_model=list[PlanRead])
async def list_plans(
    user: CurrentUser = Depends(_authed),
    db: AsyncSession = Depends(get_db),
) -> list[PlanRead]:
    """Return all active plans with INR pricing (any authenticated user)."""
    return await subscription_service.list_active_plans(db)


@router.get("/billing/subscription", response_model=SubscriptionWithEntitlements)
async def get_subscription(
    user: CurrentUser = Depends(_authed),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionWithEntitlements:
    """Return the tenant's current subscription and resolved entitlements."""
    if not user.tenant_id:
        raise AppError(ErrorCode.unauthorized, "No tenant context")
    sub = await subscription_service.get_current(db, user.tenant_id)
    ents, locked, effective_status = await resolve_entitlements(db, user.tenant_id)
    return SubscriptionWithEntitlements(
        subscription=SubscriptionRead.model_validate(sub) if sub else None,
        entitlements=ents,
        locked=locked,
        effective_status=effective_status,
    )


@router.get("/billing/usage", response_model=UsageResponse)
async def get_usage(
    user: CurrentUser = Depends(_authed),
    db: AsyncSession = Depends(get_db),
) -> UsageResponse:
    """Return current resource usage vs plan limits for the authenticated tenant.

    Any authenticated user may call this endpoint (read-only, tenant-scoped).
    Returns the 4 metered dimensions — policies, users, documents, alerts_month —
    each with their current count and plan limit (-1 = unlimited).
    """
    if not user.tenant_id:
        raise AppError(ErrorCode.unauthorized, "No tenant context")
    return await usage_service.get_usage(db, user.tenant_id)


@router.get("/billing/invoices", response_model=list[InvoiceRead])
async def list_invoices(
    user: CurrentUser = Depends(_authed),
    db: AsyncSession = Depends(get_db),
) -> list[InvoiceRead]:
    """Return the tenant's invoices ordered by issued_at desc (any authenticated user)."""
    if not user.tenant_id:
        raise AppError(ErrorCode.unauthorized, "No tenant context")
    return await subscription_service.list_invoices(db, user.tenant_id)


@router.post("/billing/subscribe", response_model=SubscribeResponse)
async def subscribe(
    payload: SubscribeRequest,
    user: CurrentUser = Depends(_billing_manage),
    db: AsyncSession = Depends(get_db),
) -> SubscribeResponse:
    """Start a new subscription or upgrade the current one.

    Requires billing:manage permission (admin role or super admin).
    Returns Razorpay subscription id + short_url for the checkout flow.
    """
    if not user.tenant_id:
        raise AppError(ErrorCode.unauthorized, "No tenant context")
    result = await subscription_service.start_or_update_subscription(
        db,
        tenant_id=user.tenant_id,
        plan_id=payload.plan_id,
        notes=payload.notes,
    )
    return SubscribeResponse(**result)


@router.post("/billing/cancel", response_model=SubscriptionRead)
async def cancel_subscription(
    user: CurrentUser = Depends(_billing_manage),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionRead:
    """Cancel the tenant's subscription.

    Requires billing:manage permission.
    If Razorpay is configured and the subscription has a Razorpay subscription id,
    the cancellation is requested at cycle end (best-effort Razorpay API call) and
    cancel_at_period_end is set; the webhook will flip status to 'cancelled'.
    In demo / no-Razorpay mode the subscription is cancelled immediately and
    entitlements fall back to Free defaults.
    """
    if not user.tenant_id:
        raise AppError(ErrorCode.unauthorized, "No tenant context")
    sub = await subscription_service.cancel_subscription(db, user.tenant_id)
    return SubscriptionRead.model_validate(sub)


@router.post("/billing/pause", response_model=SubscriptionRead)
async def pause_subscription(
    user: CurrentUser = Depends(_billing_manage),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionRead:
    """Pause the tenant's subscription.

    Requires billing:manage permission.
    Sets status='paused'; entitlements fall back to Free defaults per PLANS.md.
    Returns 404 if the tenant has no subscription.
    """
    if not user.tenant_id:
        raise AppError(ErrorCode.unauthorized, "No tenant context")
    sub = await subscription_service.pause_subscription(db, user.tenant_id)
    return SubscriptionRead.model_validate(sub)


@router.post("/billing/resume", response_model=SubscriptionRead)
async def resume_subscription(
    user: CurrentUser = Depends(_billing_manage),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionRead:
    """Undo a pending cancel or reactivate a paused / cancelled subscription.

    Requires billing:manage permission.
    Clears cancel_at_period_end; restores status to 'active' when currently
    'cancelled' or 'paused' (demo mode).  plan_id is preserved.
    Returns 404 if the tenant has no subscription.
    """
    if not user.tenant_id:
        raise AppError(ErrorCode.unauthorized, "No tenant context")
    sub = await subscription_service.resume_subscription(db, user.tenant_id)
    return SubscriptionRead.model_validate(sub)


@router.post("/billing/webhook", status_code=200)
async def razorpay_webhook(
    raw_body: bytes = Depends(_sig_check),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Razorpay webhook receiver — no user auth; signature-verified; idempotent.

    _sig_check runs first (no DB dep) and raises 400 on bad signatures.
    get_db is only reached after the signature passes.
    Razorpay expects HTTP 200 even for already-processed (duplicate) events.
    """
    try:
        body_dict = json.loads(raw_body)
    except (json.JSONDecodeError, ValueError) as exc:
        raise AppError(ErrorCode.validation_error, "Invalid webhook payload") from exc

    event_type: str = body_dict.get("event", "")
    log.info("razorpay_webhook_received event=%s", event_type)

    await subscription_service.handle_webhook(db, event_type, body_dict)
    return {"received": True}
