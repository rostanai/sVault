"""User / team-management endpoints (admin-only, tenant-scoped)."""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import require_permission
from app.core.security import CurrentUser
from app.db.session import get_db
from app.schemas.m1 import InvitationRead, ProfileRead, RoleUpdate
from app.services import user_service

router = APIRouter(tags=["users"])

# Module-level dependency singletons (keeps the call out of arg defaults; ruff B008).
_require_user_manage = require_permission("user:manage")


@router.get("/users", response_model=list[ProfileRead])
async def list_users(
    user: CurrentUser = Depends(_require_user_manage),
    db: AsyncSession = Depends(get_db),
) -> list[ProfileRead]:
    return await user_service.list_users(db, user)


@router.patch("/users/{user_id}", response_model=ProfileRead)
async def update_user(
    user_id: uuid.UUID,
    payload: RoleUpdate,
    user: CurrentUser = Depends(_require_user_manage),
    db: AsyncSession = Depends(get_db),
) -> ProfileRead:
    return await user_service.update_user(db, user, user_id, payload)


@router.get("/invitations", response_model=list[InvitationRead])
async def list_pending_invitations(
    user: CurrentUser = Depends(_require_user_manage),
    db: AsyncSession = Depends(get_db),
) -> list[InvitationRead]:
    return await user_service.list_pending_invitations(db, user)
