"""Organization endpoints (parent/subsidiary tree)."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import get_current_user, require_permission
from app.core.security import CurrentUser
from app.db.session import get_db
from app.schemas.m1 import OrgCreate, OrgRead
from app.services import org_service

router = APIRouter(prefix="/orgs", tags=["organizations"])

# Module-level dependency singletons (keeps the call out of arg defaults).
_require_org_manage = require_permission("org:manage")


@router.get("", response_model=list[OrgRead])
async def list_orgs(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[OrgRead]:
    return await org_service.list_orgs(db, user)


@router.post("", response_model=OrgRead, status_code=201)
async def create_org(
    payload: OrgCreate,
    user: CurrentUser = Depends(_require_org_manage),
    db: AsyncSession = Depends(get_db),
) -> OrgRead:
    return await org_service.create_org(db, user, payload)
