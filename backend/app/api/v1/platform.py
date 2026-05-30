"""Platform endpoints (M5, Super Admin only) — plans, settings, tenant management.

ALL routes guarded by require_super_admin (returns 404 for non-super-admin to avoid
leaking platform route existence — see docs/ERROR_HANDLING.md + DECISIONS D18).

Route map:
  GET    /platform/plans              list all plans (including inactive)
  POST   /platform/plans              create a plan
  PATCH  /platform/plans/{id}         update a plan
  GET    /platform/settings/{key}     get a setting (value masked for secrets)
  PUT    /platform/settings/{key}     upsert a setting (encrypted on write)
  GET    /platform/tenants            list tenants
  POST   /platform/tenants/{id}/suspend
  POST   /platform/tenants/{id}/activate
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import require_super_admin
from app.core.security import CurrentUser
from app.db.session import get_db
from app.schemas.billing import (
    PlanCreate,
    PlanRead,
    PlanUpdate,
    SettingRead,
    SettingWrite,
    TenantRead,
)
from app.services import platform_service

router = APIRouter(prefix="/platform", tags=["platform"])

# Module-level singleton (ruff B008)
_super = require_super_admin


@router.get("/plans", response_model=list[PlanRead])
async def list_plans(
    _: CurrentUser = Depends(_super),
    db: AsyncSession = Depends(get_db),
) -> list[PlanRead]:
    return await platform_service.list_plans(db)


@router.post("/plans", response_model=PlanRead, status_code=201)
async def create_plan(
    payload: PlanCreate,
    _: CurrentUser = Depends(_super),
    db: AsyncSession = Depends(get_db),
) -> PlanRead:
    return await platform_service.create_plan(db, payload)


@router.patch("/plans/{plan_id}", response_model=PlanRead)
async def update_plan(
    plan_id: uuid.UUID,
    payload: PlanUpdate,
    _: CurrentUser = Depends(_super),
    db: AsyncSession = Depends(get_db),
) -> PlanRead:
    return await platform_service.update_plan(db, plan_id, payload)


@router.get("/settings/{key}", response_model=SettingRead)
async def get_setting(
    key: str,
    _: CurrentUser = Depends(_super),
    db: AsyncSession = Depends(get_db),
) -> SettingRead:
    result = await platform_service.get_setting(db, key)
    return SettingRead(**result)


@router.put("/settings/{key}", response_model=SettingRead)
async def set_setting(
    key: str,
    payload: SettingWrite,
    user: CurrentUser = Depends(_super),
    db: AsyncSession = Depends(get_db),
) -> SettingRead:
    result = await platform_service.set_setting(
        db,
        key=key,
        value=payload.value,
        is_secret=payload.is_secret,
        updated_by=uuid.UUID(user.user_id) if user.user_id else None,
    )
    return SettingRead(**result)


@router.get("/tenants", response_model=list[TenantRead])
async def list_tenants(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    _: CurrentUser = Depends(_super),
    db: AsyncSession = Depends(get_db),
) -> list[TenantRead]:
    return await platform_service.list_tenants(db, limit=limit, offset=offset)


@router.post("/tenants/{tenant_id}/suspend", response_model=TenantRead)
async def suspend_tenant(
    tenant_id: uuid.UUID,
    _: CurrentUser = Depends(_super),
    db: AsyncSession = Depends(get_db),
) -> TenantRead:
    return await platform_service.suspend_tenant(db, tenant_id)


@router.post("/tenants/{tenant_id}/activate", response_model=TenantRead)
async def activate_tenant(
    tenant_id: uuid.UUID,
    _: CurrentUser = Depends(_super),
    db: AsyncSession = Depends(get_db),
) -> TenantRead:
    return await platform_service.activate_tenant(db, tenant_id)
