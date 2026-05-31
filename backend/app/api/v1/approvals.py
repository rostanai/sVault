"""Approval-workflow endpoints (M6).

Routes
------
POST   /approvals                  submit a new approval request   → 201
GET    /approvals?status=&limit=&offset=   list (tenant/org-scoped)   → 200
POST   /approvals/{id}/approve     approve a pending request         → 200
POST   /approvals/{id}/reject      reject  a pending request         → 200

Authorization
-------------
* `approval:submit`  — Admin / Manager / Owner
* `approval:approve` — Admin / Manager
* Any authenticated tenant user can list approvals within their scope.
* Self-approval additionally requires `approve:self` (enforced in the service).
* Cross-tenant / not-found → 404 (not 403) per ERROR_HANDLING.md.
"""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import get_current_user, require_permission
from app.core.security import CurrentUser
from app.db.session import get_db
from app.schemas.approval import ApprovalCreate, ApprovalDecision, ApprovalRead
from app.services import approval_service

router = APIRouter(prefix="/approvals", tags=["approvals"])

# Module-level dep singletons avoid ruff B008 (do-not-call-in-default-arg).
_submit = require_permission("approval:submit")
_approve = require_permission("approval:approve")


@router.post("", response_model=ApprovalRead, status_code=201)
async def submit_approval(
    payload: ApprovalCreate,
    user: CurrentUser = Depends(_submit),
    db: AsyncSession = Depends(get_db),
) -> ApprovalRead:
    """Submit a new approval request.

    Creates a `pending` approval record scoped to the caller's tenant and org.
    The caller must have the `approval:submit` permission (Admin, Manager, Owner).
    """
    return await approval_service.submit(db, user, payload)


@router.get("", response_model=list[ApprovalRead])
async def list_approvals(
    status: str | None = Query(
        None, description="Filter by status: pending | approved | rejected | cancelled"
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ApprovalRead]:
    """List approval requests visible to the caller.

    Results are scoped by tenant_id and, for Owner/Viewer roles, by org_id.
    Admin and Manager roles see approvals across all orgs in the tenant group.
    Ordered by `created_at` descending (newest first).
    Supports cursor-compatible limit/offset pagination.
    """
    return await approval_service.list_approvals(
        db, user, status=status, limit=limit, offset=offset
    )


@router.post("/{approval_id}/approve", response_model=ApprovalRead)
async def approve_approval(
    approval_id: uuid.UUID,
    body: ApprovalDecision,
    user: CurrentUser = Depends(_approve),
    db: AsyncSession = Depends(get_db),
) -> ApprovalRead:
    """Approve a pending approval request.

    Requires `approval:approve` permission (Admin / Manager).
    Self-approval (requester == approver) additionally requires `approve:self`.
    Returns 409 if the approval is already decided.
    Returns 404 if the approval is not found within the caller's tenant/org scope.
    """
    return await approval_service.decide(
        db, user, approval_id, approve=True, reason=body.reason
    )


@router.post("/{approval_id}/reject", response_model=ApprovalRead)
async def reject_approval(
    approval_id: uuid.UUID,
    body: ApprovalDecision,
    user: CurrentUser = Depends(_approve),
    db: AsyncSession = Depends(get_db),
) -> ApprovalRead:
    """Reject a pending approval request.

    Requires `approval:approve` permission (Admin / Manager).
    Returns 409 if the approval is already decided.
    Returns 404 if the approval is not found within the caller's tenant/org scope.
    """
    return await approval_service.decide(
        db, user, approval_id, approve=False, reason=body.reason
    )
