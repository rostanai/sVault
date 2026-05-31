"""Platform service (M5, Super Admin only) — plans CRUD, settings, tenant management.

All operations in this service are called exclusively from platform endpoints that
require `require_super_admin` — the service layer itself does NOT re-check identity.
Secrets:
  - Written via encrypt() before persisting; never stored as plaintext.
  - Read with mask() — callers never receive the plaintext secret.

Audit logging (H1 + H2 — DPDP):
  - Every Super Admin mutation writes a platform_audit_log row.
  - actor = the super-admin user id (threaded in from the endpoint via CurrentUser).
  - action = one of the audit_action enum values ('create', 'update', 'delete').
  - target = the object id / setting key — NEVER a secret value.
  - detail = small jsonb with context (field names that changed, not their values).
"""
from __future__ import annotations

import logging
import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import secrets_store
from app.core.errors import not_found
from app.db.models.billing import Plan, PlatformAuditLog, PlatformSetting, Subscription
from app.db.models.tenancy import Tenant
from app.schemas.billing import PlanCreate, PlanUpdate, PlatformAnalytics, TenantCounts, TierCount

log = logging.getLogger("svault.platform")


# ---------------------------------------------------------------------------
# Internal audit helper
# ---------------------------------------------------------------------------

async def _audit(
    db: AsyncSession,
    actor: uuid.UUID | None,
    action: str,
    target: str | None,
    detail: dict | None = None,
) -> None:
    """Insert a platform_audit_log row. Never raises — audit failures are logged
    server-side but must NOT block the primary operation."""
    try:
        row = PlatformAuditLog(
            actor=actor,
            action=action,
            target=target,
            detail=detail or {},
        )
        db.add(row)
        # Flushed in the same transaction as the primary operation; committed together.
    except Exception:  # pragma: no cover
        log.exception(
            "platform_audit_write_failed actor=%s action=%s target=%s",
            actor, action, target,
        )


# ---------------------------------------------------------------------------
# Plan management
# ---------------------------------------------------------------------------

async def list_plans(db: AsyncSession) -> list[Plan]:
    stmt = select(Plan).order_by(Plan.price_inr.asc())
    return list((await db.execute(stmt)).scalars().all())


async def create_plan(
    db: AsyncSession,
    payload: PlanCreate,
    actor: uuid.UUID | None = None,
) -> Plan:
    plan = Plan(**payload.model_dump())
    db.add(plan)
    await db.flush()  # get plan.id before audit
    await _audit(
        db, actor, "create",
        target=str(plan.id),
        detail={"tier": plan.tier, "name": plan.name, "price_inr": str(plan.price_inr)},
    )
    await db.commit()
    await db.refresh(plan)
    return plan


async def get_plan(db: AsyncSession, plan_id: uuid.UUID) -> Plan:
    plan: Plan | None = (
        await db.execute(select(Plan).where(Plan.id == plan_id))
    ).scalar_one_or_none()
    if plan is None:
        raise not_found("Plan not found")
    return plan


async def update_plan(
    db: AsyncSession,
    plan_id: uuid.UUID,
    payload: PlanUpdate,
    actor: uuid.UUID | None = None,
) -> Plan:
    plan = await get_plan(db, plan_id)
    changed_fields = list(payload.model_dump(exclude_unset=True).keys())
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)
    await _audit(
        db, actor, "update",
        target=str(plan_id),
        detail={"fields_changed": changed_fields},
    )
    await db.commit()
    await db.refresh(plan)
    return plan


# ---------------------------------------------------------------------------
# Platform settings (encrypted secrets)
# ---------------------------------------------------------------------------

async def get_setting(
    db: AsyncSession,
    key: str,
    actor: uuid.UUID | None = None,
) -> dict:
    """Return a masked view of the setting — never returns plaintext.

    Reads of secret settings are audit-logged (H2 — DPDP secret-access logging).
    """
    row: PlatformSetting | None = (
        await db.execute(select(PlatformSetting).where(PlatformSetting.key == key))
    ).scalar_one_or_none()
    if row is None:
        raise not_found(f"Setting '{key}' not found")

    # Audit secret reads (H2).
    if row.is_secret:
        await _audit(
            db, actor, "export",
            target=key,
            detail={"action": "secret_read"},
        )
        await db.commit()

    return {
        "key": row.key,
        "value": secrets_store.mask(row.value_encrypted) if row.is_secret else row.value_encrypted,
        "is_secret": row.is_secret,
        "updated_at": row.updated_at,
    }


async def set_setting(
    db: AsyncSession,
    key: str,
    value: str,
    is_secret: bool = True,
    updated_by: uuid.UUID | None = None,
) -> dict:
    """Upsert a platform setting. If is_secret, encrypt value before storing.

    Every write is audit-logged (H2 — DPDP). The secret value is NEVER placed in
    the audit detail — only the key and whether it was a create vs update.
    """
    stored_value = secrets_store.encrypt(value) if is_secret else value

    row: PlatformSetting | None = (
        await db.execute(select(PlatformSetting).where(PlatformSetting.key == key))
    ).scalar_one_or_none()

    is_new = row is None
    if is_new:
        row = PlatformSetting(
            key=key,
            value_encrypted=stored_value,
            is_secret=is_secret,
            updated_by=updated_by,
        )
        db.add(row)
    else:
        row.value_encrypted = stored_value
        row.is_secret = is_secret
        row.updated_by = updated_by

    await _audit(
        db, updated_by,
        action="create" if is_new else "update",
        target=key,
        detail={"is_secret": is_secret, "operation": "create" if is_new else "rotate"},
    )
    await db.commit()
    await db.refresh(row)
    return {
        "key": row.key,
        "value": secrets_store.mask(row.value_encrypted) if row.is_secret else row.value_encrypted,
        "is_secret": row.is_secret,
        "updated_at": row.updated_at,
    }


# ---------------------------------------------------------------------------
# Tenant management
# ---------------------------------------------------------------------------

async def list_tenants(
    db: AsyncSession, limit: int = 50, offset: int = 0
) -> list[Tenant]:
    stmt = (
        select(Tenant)
        .order_by(Tenant.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list((await db.execute(stmt)).scalars().all())


async def _get_tenant(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant:
    t: Tenant | None = (
        await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    ).scalar_one_or_none()
    if t is None:
        raise not_found("Tenant not found")
    return t


async def suspend_tenant(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    actor: uuid.UUID | None = None,
) -> Tenant:
    t = await _get_tenant(db, tenant_id)
    t.status = "suspended"
    await _audit(
        db, actor, "update",
        target=str(tenant_id),
        detail={"action": "suspend", "new_status": "suspended"},
    )
    await db.commit()
    await db.refresh(t)
    return t


async def activate_tenant(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    actor: uuid.UUID | None = None,
) -> Tenant:
    t = await _get_tenant(db, tenant_id)
    t.status = "active"
    await _audit(
        db, actor, "update",
        target=str(tenant_id),
        detail={"action": "activate", "new_status": "active"},
    )
    await db.commit()
    await db.refresh(t)
    return t


# ---------------------------------------------------------------------------
# Platform analytics
# ---------------------------------------------------------------------------

async def get_analytics(db: AsyncSession) -> PlatformAnalytics:
    """Return platform-wide metrics: tenant counts, subscription status breakdown,
    active subscriptions by plan tier, and monthly recurring revenue.

    Uses aggregate SQL (func.count / func.sum + group_by) — no Python loops over rows.
    """
    # --- tenant counts (total / active / suspended) ---
    tenant_counts_stmt = select(
        func.count().label("total"),
        func.count(Tenant.id).filter(Tenant.status == "active").label("active"),
        func.count(Tenant.id).filter(Tenant.status == "suspended").label("suspended"),
    )
    row = (await db.execute(tenant_counts_stmt)).one()
    tenants = TenantCounts(total=row.total, active=row.active, suspended=row.suspended)

    # --- subscription status breakdown ---
    sub_status_stmt = (
        select(Subscription.status, func.count().label("cnt"))
        .group_by(Subscription.status)
    )
    sub_rows = (await db.execute(sub_status_stmt)).all()
    subscriptions: dict[str, int] = {r.status: r.cnt for r in sub_rows}

    # --- active subscriptions grouped by plan tier ---
    tier_stmt = (
        select(Plan.tier, func.count().label("cnt"))
        .join(Plan, Subscription.plan_id == Plan.id)
        .where(Subscription.status == "active")
        .group_by(Plan.tier)
        .order_by(Plan.tier)
    )
    tier_rows = (await db.execute(tier_stmt)).all()
    by_tier = [TierCount(tier=r.tier, count=r.cnt) for r in tier_rows]

    # --- MRR: sum of plan.price_inr over active subscriptions ---
    mrr_stmt = (
        select(func.coalesce(func.sum(Plan.price_inr), 0).label("mrr"))
        .join(Plan, Subscription.plan_id == Plan.id)
        .where(Subscription.status == "active")
    )
    mrr_row = (await db.execute(mrr_stmt)).one()
    mrr_inr = str(mrr_row.mrr or Decimal(0))

    return PlatformAnalytics(
        tenants=tenants,
        subscriptions=subscriptions,
        by_tier=by_tier,
        mrr_inr=mrr_inr,
    )
