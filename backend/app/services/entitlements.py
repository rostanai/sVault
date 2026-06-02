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
from datetime import UTC, datetime

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

# Hard-lock entitlements — applied once a 14-day trial lapses without converting
# to a paid plan, or when a subscription is cancelled/expired. EVERY feature is
# off and every limit is 0, so the only thing a tenant can do is upgrade. The
# frontend renders a full upgrade wall on top of this; this server-side lock is
# the real enforcement (UI gating is convenience only).
_LOCKED_ENTITLEMENTS: dict = {
    "features": dict.fromkeys(_PRO_ENTITLEMENTS["features"], False),
    "limits": {"policies": 0, "users": 0, "alerts_month": 0, "documents": 0},
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

def trial_expired(sub: Subscription) -> bool:
    """True when a trialing subscription is past its trial_ends_at instant."""
    ends = sub.trial_ends_at
    return isinstance(ends, datetime) and datetime.now(UTC) >= ends


async def resolve_entitlements(
    db: AsyncSession, tenant_id: str | uuid.UUID
) -> tuple[dict, bool, str]:
    """Resolve (entitlements, locked, effective_status) for a tenant.

    - ``locked`` is True when the tenant has NO access and must upgrade to
      continue: a lapsed 14-day trial (real-time check against trial_ends_at,
      even before the daily cron flips the row) or a cancelled/expired sub.
    - ``effective_status`` is what the UI should display ("expired" for a
      lapsed trial whose DB row still says "trialing").

    Entitlement dict shape: {"features": {...}, "limits": {...}}.
    """
    tid = uuid.UUID(str(tenant_id))
    sub: Subscription | None = (
        await db.execute(select(Subscription).where(Subscription.tenant_id == tid))
    ).scalar_one_or_none()

    if sub is None:
        return _FREE_ENTITLEMENTS, False, "none"

    # Trialing tenants get full access DURING the trial (FEATURES §16). Once the
    # 14-day window lapses without converting to a paid plan, hard-lock them.
    if sub.status == "trialing":
        if trial_expired(sub):
            return _LOCKED_ENTITLEMENTS, True, "expired"
        # If the trial is attached to a specific plan (e.g. Enterprise), honor
        # THAT plan's entitlements (SSO etc.); else generic Pro trial defaults.
        if sub.plan_id is not None:
            plan = (
                await db.execute(select(Plan).where(Plan.id == sub.plan_id))
            ).scalar_one_or_none()
            if plan and plan.entitlements:
                return plan.entitlements, False, sub.status
        return _PRO_ENTITLEMENTS, False, sub.status

    # Expired (trial lapsed — set by the daily cron, or a finished paid sub) →
    # hard lock: only the upgrade page is usable.
    if sub.status == "expired":
        return _LOCKED_ENTITLEMENTS, True, sub.status

    # Cancelled → downgrade to free tier (they keep basic email-alert access).
    if sub.status == "cancelled":
        return _FREE_ENTITLEMENTS, False, sub.status

    # Active / paused / past_due with a plan → read plan.entitlements
    if sub.plan_id is not None:
        plan = (
            await db.execute(select(Plan).where(Plan.id == sub.plan_id))
        ).scalar_one_or_none()
        if plan and plan.entitlements:
            return plan.entitlements, False, sub.status

    # Fallback: subscription exists but no plan linked yet → free defaults
    return _FREE_ENTITLEMENTS, False, sub.status


async def get_entitlements(db: AsyncSession, tenant_id: str | uuid.UUID) -> dict:
    """Return just the entitlements dict for a tenant (see resolve_entitlements)."""
    ents, _locked, _status = await resolve_entitlements(db, tenant_id)
    return ents


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
