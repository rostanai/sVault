"""Server-side entitlement layer (M5) — plan feature flags + quantitative limits.

Every gated action asks:
    given the tenant's plan + limits + usage + subscription state → allowed / limited / denied?

Two entitlement types:
  1. Feature flags — on/off per plan   e.g. {"features": {"rag": true, "sms": false}}
  2. Quantitative limits — int caps    e.g. {"limits": {"policies": 100, "users": 3}}

Enforcement is server-side only. UI gating is convenience only.
See docs/FEATURES.md §17 and docs/DECISIONS.md D10.

Free-tier defaults (used when no subscription/plan row exists):
  features: email alerts only; no RAG, no SMS, no API, no SSO.
  limits:   10 policies, 1 user, 200 alerts/month.
"""
from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import get_current_user
from app.core.errors import AppError, ErrorCode
from app.core.security import CurrentUser
from app.db.models.billing import Plan, Subscription
from app.db.session import get_db

# ---------------------------------------------------------------------------
# Default / free-tier entitlements (fallback when tenant has no subscription)
# ---------------------------------------------------------------------------

_FREE_ENTITLEMENTS: dict = {
    "features": {
        "email_alerts": True,
        "whatsapp_alerts": False,
        "sms_alerts": False,
        "telegram_alerts": False,
        "rag": False,
        "analytics": False,
        "sso": False,
        "mfa": False,
        "api": False,
        "audit_log": False,
        "document_vault": True,
    },
    "limits": {
        "policies": 10,
        "users": 1,
        "alerts_month": 200,
        "documents": 20,
    },
}

# Trial and Pro share the same rich defaults (see FEATURES §16 draft map)
_PRO_ENTITLEMENTS: dict = {
    "features": {
        "email_alerts": True,
        "whatsapp_alerts": True,
        "sms_alerts": True,
        "telegram_alerts": True,
        "rag": True,
        "analytics": True,
        "sso": False,
        "mfa": True,
        "api": True,
        "audit_log": True,
        "document_vault": True,
    },
    "limits": {
        "policies": -1,   # -1 = unlimited
        "users": 15,
        "alerts_month": -1,
        "documents": -1,
    },
}


# ---------------------------------------------------------------------------
# Pure helper functions — no DB, fully unit-testable
# ---------------------------------------------------------------------------

def feature_allowed(entitlements: dict, feature: str) -> bool:
    """Return True if the feature flag is enabled in the entitlements dict."""
    return bool(entitlements.get("features", {}).get(feature, False))


def within_limit(entitlements: dict, key: str, count: int) -> bool:
    """Return True if `count` is within the plan limit for `key`.

    A limit value of -1 means unlimited.
    If the key is not present in the limits dict, defaults to unlimited (True).
    """
    limit = entitlements.get("limits", {}).get(key)
    if limit is None or limit == -1:
        return True
    return count < limit


# ---------------------------------------------------------------------------
# DB-backed helpers
# ---------------------------------------------------------------------------

async def get_entitlements(db: AsyncSession, tenant_id: str | uuid.UUID) -> dict:
    """Return the entitlements dict for a tenant.

    Resolves:
      - Active/trialing subscription with a linked plan → plan.entitlements
        (if non-empty) or _PRO_ENTITLEMENTS for trialing.
      - No subscription → _FREE_ENTITLEMENTS.

    Entitlement dict shape: {"features": {...}, "limits": {...}}.
    """
    tid = uuid.UUID(str(tenant_id))
    stmt = (
        select(Subscription)
        .where(Subscription.tenant_id == tid)
    )
    sub: Subscription | None = (await db.execute(stmt)).scalar_one_or_none()

    if sub is None:
        return _FREE_ENTITLEMENTS

    # Trialing tenants get full access during the trial (FEATURES §16). If the
    # trial is attached to a specific plan (e.g. Enterprise), honor THAT plan's
    # entitlements — an Enterprise trial must include Enterprise-only features
    # such as SSO. Fall back to the generic Pro-level trial defaults otherwise.
    if sub.status == "trialing":
        if sub.plan_id is not None:
            plan = (
                await db.execute(select(Plan).where(Plan.id == sub.plan_id))
            ).scalar_one_or_none()
            if plan and plan.entitlements:
                return plan.entitlements
        return _PRO_ENTITLEMENTS

    # Cancelled / expired / past_due → fall back to free
    if sub.status in ("cancelled", "expired"):
        return _FREE_ENTITLEMENTS

    # Active / paused / past_due with a plan → read plan.entitlements
    if sub.plan_id is not None:
        plan: Plan | None = (
            await db.execute(select(Plan).where(Plan.id == sub.plan_id))
        ).scalar_one_or_none()
        if plan and plan.entitlements:
            return plan.entitlements

    # Fallback: no plan linked yet but subscription exists → free defaults
    return _FREE_ENTITLEMENTS


async def has_feature(db: AsyncSession, tenant_id: str | uuid.UUID, feature: str) -> bool:
    """Return True if the tenant's current plan grants `feature`."""
    ents = await get_entitlements(db, tenant_id)
    return feature_allowed(ents, feature)


async def check_limit(
    db: AsyncSession, tenant_id: str | uuid.UUID, key: str, current_count: int
) -> bool:
    """Return True if `current_count` is within the tenant's limit for `key`."""
    ents = await get_entitlements(db, tenant_id)
    return within_limit(ents, key, current_count)


# ---------------------------------------------------------------------------
# FastAPI dependency factories
# ---------------------------------------------------------------------------

def require_entitlement(feature: str) -> Callable[..., CurrentUser]:
    """Dependency factory: 403 (entitlement_required) if the tenant lacks `feature`.

    Usage (module-level singleton to satisfy ruff B008):
        _need_rag = require_entitlement("rag")

        @router.get("/ask")
        async def ask(user: CurrentUser = Depends(_need_rag), db = Depends(get_db)):
            ...
    """

    async def _dep(
        user: CurrentUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> CurrentUser:
        if user.is_super_admin:
            return user
        if not user.tenant_id:
            raise AppError(ErrorCode.entitlement_required, f"Feature not available: {feature}")
        allowed = await has_feature(db, user.tenant_id, feature)
        if not allowed:
            raise AppError(
                ErrorCode.entitlement_required,
                f"Your plan does not include the '{feature}' feature. "
                "Upgrade your subscription to unlock it.",
            )
        return user

    return _dep
