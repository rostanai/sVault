"""Policy service — CRUD with tenant/org scoping + object-level ownership.

Defense in depth: this enforces scope in the service layer AND RLS enforces it in
the DB. For cross-tenant / non-accessible / non-owned access we raise not_found
(never reveal existence) per docs/ERROR_HANDLING.md.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import not_found
from app.core.security import CurrentUser
from app.db.models import Alert, Policy
from app.schemas.policy import PolicyCreate, PolicyUpdate, RenewPolicyRequest
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


async def _apply_mark_renewed(
    db: AsyncSession, user: CurrentUser, policy: Policy
) -> None:
    """Mutate *policy* to 'renewed' and bulk-cancel its pending alerts.

    Does NOT commit — callers are responsible for the commit so this can be
    composed inside a larger transaction (e.g. renew()).
    """
    policy.status = "renewed"
    await db.execute(
        update(Alert)
        .where(
            Alert.policy_id == policy.id,
            Alert.tenant_id == uuid.UUID(user.tenant_id),
            Alert.status.in_(["scheduled", "sent"]),
        )
        .values(status="cancelled")
    )


async def mark_renewed(
    db: AsyncSession, user: CurrentUser, policy_id: uuid.UUID
) -> Policy:
    """Set policy status to 'renewed' and cancel all pending alerts for that policy.

    'Pending' alerts are those with status in ('scheduled', 'sent') — i.e., not yet
    acknowledged, not already cancelled/failed.  This uses a bulk UPDATE so that the
    notification_log history is preserved unchanged (only the alert row status changes).

    Scoping: tenant + org filtering via get_policy (raises not_found for out-of-scope).
    """
    policy = await get_policy(db, user, policy_id)  # scope-checked; raises if not accessible
    await _apply_mark_renewed(db, user, policy)
    await db.commit()
    await db.refresh(policy)
    return policy


async def renew(
    db: AsyncSession,
    user: CurrentUser,
    policy_id: uuid.UUID,
    payload: RenewPolicyRequest,
) -> Policy:
    """Create a renewal policy for the next term and mark the source as renewed.

    Steps:
    1. Load and scope-check the source policy (404 if not accessible).
    2. Build a new Policy row carrying over org_id, category, title, provider_id,
       owner_id, and policy_number from the source; override any fields the caller
       supplies in the payload.  inception_date defaults to the source's expiry_date
       (continuous cover) when not provided.  status = "active".  prev_policy_id
       points to the source.
    3. Persist the new policy (flush to get its id).
    4. Mark the SOURCE as renewed (status=renewed + cancel pending alerts) within
       the same session — commit once.
    5. Return the NEW policy.
    """
    source = await get_policy(db, user, policy_id)

    _policy_number = (
        payload.policy_number
        if payload.policy_number is not None
        else source.policy_number
    )
    _sum_insured = (
        payload.sum_insured_inr
        if payload.sum_insured_inr is not None
        else source.sum_insured_inr
    )
    _inception = (
        payload.inception_date
        if payload.inception_date is not None
        else source.expiry_date  # continuous cover default
    )

    new_policy = Policy(
        tenant_id=uuid.UUID(user.tenant_id),
        org_id=source.org_id,
        category=source.category,
        title=source.title,
        policy_number=_policy_number,
        provider_id=source.provider_id,
        owner_id=source.owner_id,
        sum_insured_inr=_sum_insured,
        premium_inr=payload.premium_inr
        if payload.premium_inr is not None
        else source.premium_inr,
        gst_inr=payload.gst_inr if payload.gst_inr is not None else source.gst_inr,
        inception_date=_inception,
        expiry_date=payload.expiry_date,
        renewal_date=payload.renewal_date,
        status="active",
        prev_policy_id=source.id,
        custom_fields=source.custom_fields or {},
        created_by=uuid.UUID(user.user_id),
    )
    db.add(new_policy)
    await db.flush()  # assign new_policy.id without committing

    # Mark the source renewed + cancel its pending alerts within the same transaction.
    await _apply_mark_renewed(db, user, source)

    await db.commit()
    await db.refresh(new_policy)
    return new_policy
