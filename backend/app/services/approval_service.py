"""Approval-workflow service — business logic only; no FastAPI imports.

Defense-in-depth notes
----------------------
* All queries are scoped by tenant_id + accessible org(s) so cross-tenant
  lookups silently return 404 (never reveal existence — see ERROR_HANDLING.md).
* Self-approval requires the dedicated `approve:self` permission; the caller
  must verify that permission BEFORE calling decide() — but the service also
  re-checks so the rule is enforced even if called directly.
* Already-decided approvals raise 409 Conflict.
* The DB `audit_row` trigger on the approvals table handles audit logging
  automatically; no extra writes needed here.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import has_permission
from app.core.errors import AppError, ErrorCode, not_found
from app.core.security import CurrentUser
from app.db.models.approvals import Approval
from app.schemas.approval import ApprovalCreate
from app.services.org_service import is_group_wide

_DECIDED = {"approved", "rejected", "cancelled"}


def _accessible_org_filter(user: CurrentUser) -> uuid.UUID | None:
    """Mirrors the same helper in policy_service — consistent scoping."""
    if user.is_super_admin or is_group_wide(user.role):
        return None  # all orgs in tenant
    return uuid.UUID(user.org_id) if user.org_id else None


async def submit(
    db: AsyncSession,
    user: CurrentUser,
    payload: ApprovalCreate,
) -> Approval:
    """Create a new pending approval request for the calling user's tenant/org."""
    if not user.tenant_id:
        raise AppError(ErrorCode.forbidden, "No tenant context")

    approval = Approval(
        tenant_id=uuid.UUID(user.tenant_id),
        org_id=uuid.UUID(user.org_id) if user.org_id else None,
        action_type=payload.action_type,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        amount_inr=payload.amount_inr,
        status="pending",
        requested_by=uuid.UUID(user.user_id),
        is_self_approval=False,  # set on decision, not on submission
    )
    db.add(approval)
    await db.commit()
    await db.refresh(approval)
    return approval


async def list_approvals(
    db: AsyncSession,
    user: CurrentUser,
    *,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Approval]:
    """Return approvals visible to the caller, tenant+org scoped, newest first."""
    if not user.tenant_id:
        return []

    stmt = select(Approval).where(Approval.tenant_id == uuid.UUID(user.tenant_id))

    org = _accessible_org_filter(user)
    if org is not None:
        stmt = stmt.where(Approval.org_id == org)

    if status:
        stmt = stmt.where(Approval.status == status)

    stmt = stmt.order_by(Approval.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _load_approval(
    db: AsyncSession,
    user: CurrentUser,
    approval_id: uuid.UUID,
) -> Approval:
    """Load and scope-check an approval; 404 for anything not in the caller's tenant/orgs."""
    if not user.tenant_id:
        raise not_found("Approval not found")

    stmt = select(Approval).where(
        Approval.id == approval_id,
        Approval.tenant_id == uuid.UUID(user.tenant_id),
    )
    org = _accessible_org_filter(user)
    if org is not None:
        stmt = stmt.where(Approval.org_id == org)

    approval = (await db.execute(stmt)).scalar_one_or_none()
    if approval is None:
        raise not_found("Approval not found")
    return approval


async def decide(
    db: AsyncSession,
    user: CurrentUser,
    approval_id: uuid.UUID,
    *,
    approve: bool,
    reason: str | None,
) -> Approval:
    """Approve or reject an approval request.

    Rules
    -----
    * The approval must exist within the caller's accessible tenant+org scope.
    * Already-decided approvals raise 409 Conflict.
    * If requested_by == current user (self-approval), the caller must have
      the `approve:self` permission or the request is rejected with 403.
    """
    approval = await _load_approval(db, user, approval_id)

    if approval.status in _DECIDED:
        raise AppError(
            ErrorCode.conflict,
            f"Approval is already {approval.status} and cannot be changed",
        )

    # Determine self-approval before mutating.
    is_self = (
        approval.requested_by is not None
        and str(approval.requested_by) == user.user_id
    )

    if is_self and not has_permission(user, "approve:self"):
        raise AppError(
            ErrorCode.forbidden,
            "Self-approval is not permitted for your role",
        )

    approval.status = "approved" if approve else "rejected"
    approval.approver_id = uuid.UUID(user.user_id)
    approval.is_self_approval = is_self
    approval.reason = reason
    approval.decided_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(approval)
    return approval
