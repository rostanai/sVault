"""Billing endpoints (M5) — plans, subscriptions, Razorpay webhook.

Route map:
  GET  /plans                     any authed user — active plan list + prices
  GET  /billing/subscription      any authed user — tenant's subscription + entitlements
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
    PlanRead,
    SubscribeRequest,
    SubscribeResponse,
    SubscriptionRead,
    SubscriptionWithEntitlements,
)
from app.services import subscription_service
from app.services.entitlements import get_entitlements

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
            ErrorCode.unauthorized,
            "Missing webhook signature",
            http_status=400,
        )
    if not verify_webhook_signature(raw_body, x_razorpay_signature):
        raise AppError(
            ErrorCode.unauthorized,
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
    ents = await get_entitlements(db, user.tenant_id)
    return SubscriptionWithEntitlements(
        subscription=SubscriptionRead.model_validate(sub) if sub else None,
        entitlements=ents,
    )


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
