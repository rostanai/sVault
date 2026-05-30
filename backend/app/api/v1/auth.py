"""Auth/onboarding endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import get_current_user
from app.core.security import CurrentUser
from app.db.session import get_db
from app.schemas.m1 import MeResponse, OnboardRequest, OnboardResponse
from app.services import onboarding

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/onboard", response_model=OnboardResponse, status_code=201)
async def onboard(
    payload: OnboardRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OnboardResponse:
    """Create the corporate group + parent org + admin profile + 14-day trial."""
    tenant, org, ends = await onboarding.onboard_user(db, user, payload)
    return OnboardResponse(tenant_id=tenant.id, org_id=org.id, trial_ends_at=ends)


@router.get("/me", response_model=MeResponse)
async def me(user: CurrentUser = Depends(get_current_user)) -> MeResponse:
    return MeResponse(**user.model_dump())
