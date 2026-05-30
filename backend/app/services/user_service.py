"""User/team-management service — list profiles, change roles, list pending invites.

Strictly tenant-scoped: a profile in another tenant is treated as not_found (never
revealing existence) per docs/ERROR_HANDLING.md. RLS enforces the same in the DB.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ErrorCode, not_found
from app.core.security import CurrentUser
from app.db.models import Invitation, Profile
from app.schemas.m1 import RoleUpdate

ADMIN_ROLE = "admin"


def would_remove_last_admin(
    *, target_is_admin: bool, admin_count: int, new_role: str, new_is_active: bool
) -> bool:
    """Pure guard logic (unit-testable): is this change demoting/deactivating the
    last remaining active admin of the tenant?
    """
    if not target_is_admin or admin_count > 1:
        return False
    # Target is the only admin. Block if it stops being an active admin.
    return new_role != ADMIN_ROLE or not new_is_active


async def count_admins(db: AsyncSession, tenant_id: uuid.UUID) -> int:
    """Number of active admins in the tenant."""
    stmt = select(func.count()).select_from(Profile).where(
        Profile.tenant_id == tenant_id,
        Profile.role == ADMIN_ROLE,
        Profile.is_active.is_(True),
    )
    return int((await db.execute(stmt)).scalar_one())


async def list_users(db: AsyncSession, user: CurrentUser) -> list[Profile]:
    if not user.tenant_id:
        return []
    stmt = (
        select(Profile)
        .where(Profile.tenant_id == uuid.UUID(user.tenant_id))
        .order_by(Profile.created_at.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_user(
    db: AsyncSession, user: CurrentUser, user_id: uuid.UUID, payload: RoleUpdate
) -> Profile:
    if not user.tenant_id:
        raise AppError(ErrorCode.forbidden, "No tenant context")
    tenant_id = uuid.UUID(user.tenant_id)
    stmt = select(Profile).where(
        Profile.id == user_id, Profile.tenant_id == tenant_id
    )
    profile = (await db.execute(stmt)).scalar_one_or_none()
    if profile is None:
        raise not_found("User not found")

    new_is_active = (
        payload.is_active if payload.is_active is not None else profile.is_active
    )
    target_is_admin = profile.role == ADMIN_ROLE and profile.is_active
    if target_is_admin:
        admins = await count_admins(db, tenant_id)
        if would_remove_last_admin(
            target_is_admin=True,
            admin_count=admins,
            new_role=payload.role,
            new_is_active=new_is_active,
        ):
            raise AppError(
                ErrorCode.conflict,
                "Cannot demote or deactivate the last remaining admin of the tenant",
            )

    profile.role = payload.role
    if payload.is_active is not None:
        profile.is_active = payload.is_active
    await db.commit()
    await db.refresh(profile)
    return profile


async def list_pending_invitations(
    db: AsyncSession, user: CurrentUser
) -> list[Invitation]:
    if not user.tenant_id:
        return []
    stmt = (
        select(Invitation)
        .where(
            Invitation.tenant_id == uuid.UUID(user.tenant_id),
            Invitation.accepted_at.is_(None),
            Invitation.expires_at >= datetime.now(UTC),
        )
        .order_by(Invitation.created_at.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
