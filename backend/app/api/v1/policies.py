"""Policy endpoints (M2) — CRUD with role/scoping guards."""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import require_permission
from app.core.security import CurrentUser
from app.db.session import get_db
from app.schemas.policy import PolicyCreate, PolicyRead, PolicyUpdate
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
