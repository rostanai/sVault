"""Team invitations — invite by email, accept via token (auto-join tenant/org)."""
from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ErrorCode
from app.core.security import CurrentUser
from app.core.supabase_admin import set_app_metadata
from app.db.models import Invitation, Profile
from app.schemas.m1 import InvitationCreate

INVITE_DAYS = 7


async def create_invitation(
    db: AsyncSession, user: CurrentUser, payload: InvitationCreate
) -> Invitation:
    if not user.tenant_id:
        raise AppError(ErrorCode.forbidden, "No tenant context")
    inv = Invitation(
        tenant_id=uuid.UUID(user.tenant_id),
        org_id=payload.org_id or (uuid.UUID(user.org_id) if user.org_id else None),
        email=payload.email,
        role=payload.role,
        token=secrets.token_urlsafe(32),
        invited_by=uuid.UUID(user.user_id),
        expires_at=datetime.now(UTC) + timedelta(days=INVITE_DAYS),
    )
    db.add(inv)
    await db.commit()
    await db.refresh(inv)
    return inv


async def accept_invitation(
    db: AsyncSession, user: CurrentUser, token: str
) -> Invitation:
    result = await db.execute(select(Invitation).where(Invitation.token == token))
    inv = result.scalar_one_or_none()
    if (
        inv is None
        or inv.accepted_at is not None
        or inv.expires_at < datetime.now(UTC)
    ):
        raise AppError(ErrorCode.not_found, "Invalid or expired invitation")

    uid = uuid.UUID(user.user_id)
    profile = await db.get(Profile, uid)
    if profile is None:
        profile = Profile(id=uid, email=user.email)
        db.add(profile)
    profile.tenant_id = inv.tenant_id
    profile.org_id = inv.org_id
    profile.role = inv.role
    inv.accepted_at = datetime.now(UTC)
    await db.commit()

    await set_app_metadata(
        user.user_id,
        {
            "tenant_id": str(inv.tenant_id),
            "org_id": str(inv.org_id) if inv.org_id else None,
            "role": inv.role,
            "is_platform_admin": False,
        },
    )
    return inv
