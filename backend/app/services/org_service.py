"""Organization (parent/subsidiary) service. RLS enforces the same scoping in the DB."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ErrorCode
from app.core.security import CurrentUser
from app.db.models import Organization
from app.schemas.m1 import OrgCreate

# Admin/Manager see the whole group (roll-up across subsidiaries); others see own org.
GROUP_WIDE_ROLES = {"admin", "manager"}


def is_group_wide(role: str) -> bool:
    return role in GROUP_WIDE_ROLES


async def list_orgs(db: AsyncSession, user: CurrentUser) -> list[Organization]:
    if not user.tenant_id:
        return []
    stmt = select(Organization).where(
        Organization.tenant_id == uuid.UUID(user.tenant_id)
    )
    if not (user.is_super_admin or is_group_wide(user.role)):
        if not user.org_id:
            return []
        stmt = stmt.where(Organization.id == uuid.UUID(user.org_id))
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_org(
    db: AsyncSession, user: CurrentUser, payload: OrgCreate
) -> Organization:
    if not user.tenant_id:
        raise AppError(ErrorCode.forbidden, "No tenant context")
    parent = payload.parent_org_id or (
        uuid.UUID(user.org_id) if user.org_id else None
    )
    org = Organization(
        tenant_id=uuid.UUID(user.tenant_id),
        parent_org_id=parent,
        name=payload.name,
        org_type=payload.org_type,
        gstin=payload.gstin,
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org
