"""Policy service — CRUD with tenant/org scoping + object-level ownership.

Defense in depth: this enforces scope in the service layer AND RLS enforces it in
the DB. For cross-tenant / non-accessible / non-owned access we raise not_found
(never reveal existence) per docs/ERROR_HANDLING.md.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import not_found
from app.core.security import CurrentUser
from app.db.models import Policy
from app.schemas.policy import PolicyCreate, PolicyUpdate
from app.services.org_service import is_group_wide


def _accessible_org_filter(user: CurrentUser):
    """Owner/Viewer -> own org only; Admin/Manager -> whole group (handled by RLS too)."""
    if user.is_super_admin or is_group_wide(user.role):
        return None  # all orgs in tenant
    return uuid.UUID(user.org_id) if user.org_id else None


async def list_policies(
    db: AsyncSession,
    user: CurrentUser,
    *,
    category: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Policy]:
    stmt = select(Policy).where(Policy.tenant_id == uuid.UUID(user.tenant_id))
    org = _accessible_org_filter(user)
    if org is not None:
        stmt = stmt.where(Policy.org_id == org)
    if category:
        stmt = stmt.where(Policy.category == category)
    if status:
        stmt = stmt.where(Policy.status == status)
    stmt = stmt.order_by(Policy.expiry_date.asc().nullslast()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_policy(db: AsyncSession, user: CurrentUser, policy_id: uuid.UUID) -> Policy:
    stmt = select(Policy).where(
        Policy.id == policy_id, Policy.tenant_id == uuid.UUID(user.tenant_id)
    )
    org = _accessible_org_filter(user)
    if org is not None:
        stmt = stmt.where(Policy.org_id == org)
    policy = (await db.execute(stmt)).scalar_one_or_none()
    if policy is None:
        raise not_found("Policy not found")
    return policy


async def create_policy(db: AsyncSession, user: CurrentUser, payload: PolicyCreate) -> Policy:
    policy = Policy(
        tenant_id=uuid.UUID(user.tenant_id),
        org_id=payload.org_id,
        category=payload.category,
        title=payload.title,
        policy_number=payload.policy_number,
        provider_id=payload.provider_id,
        owner_id=payload.owner_id or uuid.UUID(user.user_id),
        sum_insured_inr=payload.sum_insured_inr,
        premium_inr=payload.premium_inr,
        gst_inr=payload.gst_inr,
        inception_date=payload.inception_date,
        expiry_date=payload.expiry_date,
        renewal_date=payload.renewal_date,
        custom_fields=payload.custom_fields,
        created_by=uuid.UUID(user.user_id),
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return policy


async def update_policy(
    db: AsyncSession, user: CurrentUser, policy_id: uuid.UUID, payload: PolicyUpdate
) -> Policy:
    policy = await get_policy(db, user, policy_id)  # scope-checked
    # Owners may only edit their own policies (object-level check).
    if user.role == "owner" and policy.owner_id != uuid.UUID(user.user_id):
        raise not_found("Policy not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(policy, field, value)
    await db.commit()
    await db.refresh(policy)
    return policy


async def delete_policy(db: AsyncSession, user: CurrentUser, policy_id: uuid.UUID) -> None:
    policy = await get_policy(db, user, policy_id)
    await db.delete(policy)
    await db.commit()
