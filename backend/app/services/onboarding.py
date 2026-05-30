"""Signup/onboarding — turn an authenticated Supabase user into a tenant admin.

Flow: user authenticates via Supabase Auth (frontend) -> calls /auth/onboard ->
we create the corporate group (tenant) + parent org + admin profile + 14-day trial,
then set their JWT claims (app_metadata). The client refreshes its session afterward.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ErrorCode
from app.core.security import CurrentUser
from app.core.supabase_admin import set_app_metadata
from app.db.models import Organization, Profile, Subscription, Tenant
from app.schemas.m1 import OnboardRequest

TRIAL_DAYS = 14


def trial_end(start: datetime) -> datetime:
    return start + timedelta(days=TRIAL_DAYS)


async def onboard_user(
    db: AsyncSession, user: CurrentUser, payload: OnboardRequest
) -> tuple[Tenant, Organization, datetime]:
    if user.tenant_id:
        raise AppError(ErrorCode.conflict, "User already belongs to a tenant")

    now = datetime.now(UTC)
    tenant = Tenant(name=payload.company_name)
    db.add(tenant)
    await db.flush()  # assigns tenant.id

    org = Organization(tenant_id=tenant.id, name=payload.company_name, org_type="parent")
    db.add(org)
    await db.flush()  # assigns org.id

    # Profile may already exist (created by the handle_new_user trigger) -> update it.
    uid = uuid.UUID(user.user_id)
    profile = await db.get(Profile, uid)
    if profile is None:
        profile = Profile(id=uid)
        db.add(profile)
    profile.tenant_id = tenant.id
    profile.org_id = org.id
    profile.role = "admin"
    profile.email = user.email
    if payload.full_name:
        profile.full_name = payload.full_name

    ends = trial_end(now)
    db.add(Subscription(tenant_id=tenant.id, status="trialing", trial_ends_at=ends))

    await db.commit()

    # Set verified JWT claims so subsequent requests are tenant/org-scoped.
    await set_app_metadata(
        user.user_id,
        {
            "tenant_id": str(tenant.id),
            "org_id": str(org.id),
            "role": "admin",
            "is_platform_admin": False,
        },
    )
    return tenant, org, ends
