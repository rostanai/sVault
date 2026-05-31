"""Onboarding status endpoint — first-run checklist.

GET /onboarding/status

Computes which first-run steps the authenticated user's tenant has completed
by running cheap COUNT queries against live data.  Read-only; any authenticated
user can call it (all roles benefit from the checklist).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import get_current_user
from app.core.security import CurrentUser
from app.db.session import get_db
from app.schemas.onboarding import OnboardingStatus
from app.services import onboarding_service

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get(
    "/status",
    response_model=OnboardingStatus,
    summary="Get first-run onboarding checklist",
)
async def get_onboarding_status(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OnboardingStatus:
    """Return the onboarding checklist for the authenticated user's tenant.

    Each step reflects whether the tenant has at least one of the required
    resources in the database:

    1. **provider** — at least one insurer/provider record.
    2. **policy** — at least one policy.
    3. **document** — at least one policy document.
    4. **alert** — at least one alert rule (or generated alert).
    5. **team** — more than one team member *or* at least one pending invitation.

    **complete** is `true` when every step is done.
    **completed_count** / **total** expose progress as integers for a progress bar.

    Authorization: any authenticated user (no special role required).
    Scope: tenant + accessible org(s) — same scoping rules as policies/documents.
    """
    return await onboarding_service.get_status(db, user)
