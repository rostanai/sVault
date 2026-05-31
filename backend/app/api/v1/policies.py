"""Policy endpoints (M2) — CRUD with role/scoping guards."""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import require_permission
from app.core.security import CurrentUser
from app.db.session import get_db
from app.schemas.policy import PolicyCreate, PolicyRead, PolicyUpdate, RenewPolicyRequest
from app.services import policy_service

router = APIRouter(prefix="/policies", tags=["policies"])

_read = require_permission("policy:read")
_create = require_permission("policy:create")
_update = require_permission("policy:update")
_delete = require_permission("policy:delete")


@router.get("", response_model=list[PolicyRead])
async def list_policies(
    category: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    user: CurrentUser = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> list[PolicyRead]:
    return await policy_service.list_policies(
        db, user, category=category, status=status, limit=limit, offset=offset
    )


@router.post("", response_model=PolicyRead, status_code=201)
async def create_policy(
    payload: PolicyCreate,
    user: CurrentUser = Depends(_create),
    db: AsyncSession = Depends(get_db),
) -> PolicyRead:
    return await policy_service.create_policy(db, user, payload)


@router.get("/{policy_id}", response_model=PolicyRead)
async def get_policy(
    policy_id: uuid.UUID,
    user: CurrentUser = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> PolicyRead:
    return await policy_service.get_policy(db, user, policy_id)


@router.patch("/{policy_id}", response_model=PolicyRead)
async def update_policy(
    policy_id: uuid.UUID,
    payload: PolicyUpdate,
    user: CurrentUser = Depends(_update),
    db: AsyncSession = Depends(get_db),
) -> PolicyRead:
    return await policy_service.update_policy(db, user, policy_id, payload)


@router.delete("/{policy_id}", status_code=204)
async def delete_policy(
    policy_id: uuid.UUID,
    user: CurrentUser = Depends(_delete),
    db: AsyncSession = Depends(get_db),
) -> None:
    await policy_service.delete_policy(db, user, policy_id)


@router.post("/{policy_id}/mark-renewed", response_model=PolicyRead)
async def mark_policy_renewed(
    policy_id: uuid.UUID,
    user: CurrentUser = Depends(_update),
    db: AsyncSession = Depends(get_db),
) -> PolicyRead:
    """Mark a policy as renewed and cancel all its pending/sent alerts.

    Requires policy:update permission. Tenant- and org-scoped (404 if not accessible).
    """
    return await policy_service.mark_renewed(db, user, policy_id)


@router.post("/{policy_id}/renew", response_model=PolicyRead, status_code=201)
async def renew_policy(
    policy_id: uuid.UUID,
    payload: RenewPolicyRequest,
    user: CurrentUser = Depends(_create),
    db: AsyncSession = Depends(get_db),
) -> PolicyRead:
    """Create a renewal policy for the next term and mark the source as renewed.

    Carries over org_id, category, title, provider_id, owner_id, and policy_number
    from the source policy. The caller must supply the new expiry_date; all other
    fields (inception_date, premium_inr, gst_inr, sum_insured_inr, policy_number)
    are optional overrides — omitted values fall back to source policy values.
    inception_date defaults to the source policy's expiry_date (continuous cover).

    The new policy's prev_policy_id links back to the source. The source is atomically
    marked as status=renewed and all its pending/sent alerts are cancelled.

    Requires policy:create permission. Returns the newly created renewal policy (201).
    Tenant- and org-scoped: 404 for cross-tenant or inaccessible source policies.
    """
    return await policy_service.renew(db, user, policy_id, payload)
