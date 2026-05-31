"""Policy premium instalment endpoints.

Routes
------
GET    /policies/{policy_id}/installments          list instalments for a policy   → 200
POST   /policies/{policy_id}/installments          create a new instalment         → 201
POST   /installments/{installment_id}/pay          mark an instalment paid         → 200
DELETE /installments/{installment_id}              delete an instalment            → 204

Authorization
-------------
* `policy:read`   — list instalments (Admin / Manager / Owner / Viewer)
* `policy:update` — create / pay / delete instalments (Admin / Manager / Owner)
* Cross-tenant / non-owned objects → 404 (never 403) per ERROR_HANDLING.md.
"""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import require_permission
from app.core.security import CurrentUser
from app.db.session import get_db
from app.schemas.installment import InstallmentCreate, InstallmentRead
from app.services import installment_service

router = APIRouter(tags=["installments"])

# Module-level dep singletons — avoids ruff B008 (do-not-call-in-default-arg).
_read = require_permission("policy:read")
_update = require_permission("policy:update")


@router.get(
    "/policies/{policy_id}/installments",
    response_model=list[InstallmentRead],
    summary="List instalments for a policy",
)
async def list_installments(
    policy_id: uuid.UUID,
    user: CurrentUser = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> list[InstallmentRead]:
    """Return all premium instalments for a policy, ordered by due_date ascending.

    The policy must be accessible to the caller (tenant + org scoped).
    Returns 404 if the policy does not exist or is outside the caller's scope.
    Requires `policy:read` (Admin, Manager, Owner, Viewer).
    """
    return await installment_service.list_for_policy(db, user, policy_id)


@router.post(
    "/policies/{policy_id}/installments",
    response_model=InstallmentRead,
    status_code=201,
    summary="Create an instalment for a policy",
)
async def create_installment(
    policy_id: uuid.UUID,
    payload: InstallmentCreate,
    user: CurrentUser = Depends(_update),
    db: AsyncSession = Depends(get_db),
) -> InstallmentRead:
    """Create a new premium instalment (status=pending) for a policy.

    The policy must be accessible to the caller.
    Returns 404 if the policy does not exist or is outside the caller's scope.
    Requires `policy:update` (Admin, Manager, Owner).
    """
    return await installment_service.create(db, user, policy_id, payload)


@router.post(
    "/installments/{installment_id}/pay",
    response_model=InstallmentRead,
    summary="Mark an instalment as paid",
)
async def pay_installment(
    installment_id: uuid.UUID,
    user: CurrentUser = Depends(_update),
    db: AsyncSession = Depends(get_db),
) -> InstallmentRead:
    """Mark an instalment as paid (status=paid, paid_at=now).

    Returns 404 if the instalment does not exist or belongs to a different tenant.
    Requires `policy:update` (Admin, Manager, Owner).
    """
    return await installment_service.mark_paid(db, user, installment_id)


@router.delete(
    "/installments/{installment_id}",
    status_code=204,
    summary="Delete an instalment",
)
async def delete_installment(
    installment_id: uuid.UUID,
    user: CurrentUser = Depends(_update),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an instalment record.

    Returns 404 if the instalment does not exist or belongs to a different tenant.
    Requires `policy:update` (Admin, Manager, Owner).
    """
    await installment_service.delete(db, user, installment_id)
