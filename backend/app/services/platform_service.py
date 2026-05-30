"""Platform service (M5, Super Admin only) — plans CRUD, settings, tenant management.

All operations in this service are called exclusively from platform endpoints that
require `require_super_admin` — the service layer itself does NOT re-check identity.
Secrets:
  - Written via encrypt() before persisting; never stored as plaintext.
  - Read with mask() — callers never receive the plaintext secret.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import secrets_store
from app.core.errors import not_found
from app.db.models.billing import Plan, PlatformSetting
from app.db.models.tenancy import Tenant
from app.schemas.billing import PlanCreate, PlanUpdate

# ---------------------------------------------------------------------------
# Plan management
# ---------------------------------------------------------------------------

async def list_plans(db: AsyncSession) -> list[Plan]:
    stmt = select(Plan).order_by(Plan.price_inr.asc())
    return list((await db.execute(stmt)).scalars().all())


async def create_plan(db: AsyncSession, payload: PlanCreate) -> Plan:
    plan = Plan(**payload.model_dump())
    db.add(plan)
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
    db: AsyncSession, plan_id: uuid.UUID, payload: PlanUpdate
) -> Plan:
    plan = await get_plan(db, plan_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)
    await db.commit()
    await db.refresh(plan)
    return plan


# ---------------------------------------------------------------------------
# Platform settings (encrypted secrets)
# ---------------------------------------------------------------------------

async def get_setting(db: AsyncSession, key: str) -> dict:
    """Return a masked view of the setting — never returns plaintext."""
    row: PlatformSetting | None = (
        await db.execute(select(PlatformSetting).where(PlatformSetting.key == key))
    ).scalar_one_or_none()
    if row is None:
        raise not_found(f"Setting '{key}' not found")
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
    """Upsert a platform setting. If is_secret, encrypt value before storing."""
    stored_value = secrets_store.encrypt(value) if is_secret else value

    row: PlatformSetting | None = (
        await db.execute(select(PlatformSetting).where(PlatformSetting.key == key))
    ).scalar_one_or_none()

    if row is None:
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


async def suspend_tenant(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant:
    t = await _get_tenant(db, tenant_id)
    t.status = "suspended"
    await db.commit()
    await db.refresh(t)
    return t


async def activate_tenant(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant:
    t = await _get_tenant(db, tenant_id)
    t.status = "active"
    await db.commit()
    await db.refresh(t)
    return t
