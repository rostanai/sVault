"""Invitation endpoints (invite teammates; accept to join)."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import get_current_user, require_permission
from app.core.security import CurrentUser
from app.db.session import get_db
from app.schemas.m1 import AcceptInvite, InvitationCreate, InvitationRead
from app.services import invitation_service

router = APIRouter(prefix="/invitations", tags=["invitations"])

_require_user_manage = require_permission("user:manage")


@router.post("", response_model=InvitationRead, status_code=201)
async def create_invitation(
    payload: InvitationCreate,
    user: CurrentUser = Depends(_require_user_manage),
    db: AsyncSession = Depends(get_db),
) -> InvitationRead:
    return await invitation_service.create_invitation(db, user, payload)


@router.post("/accept", status_code=200)
async def accept_invitation(
    payload: AcceptInvite,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    inv = await invitation_service.accept_invitation(db, user, payload.token)
    return {"joined_tenant": str(inv.tenant_id), "role": inv.role,
            "note": "Refresh your session to load the new claims."}
