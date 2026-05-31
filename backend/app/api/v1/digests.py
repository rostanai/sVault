"""Weekly renewal email digest endpoints.

Endpoints
---------
POST /digests/dispatch
    Cron-only (guarded by X-Cron-Secret).  Scans all active tenants and sends
    the weekly digest to each tenant's admin/owner recipients.  Intended to be
    called weekly via pg_cron or Vercel Cron.

POST /digests/send-me
    Authenticated user.  Sends the digest for the caller's tenant to the
    caller's own email address (on-demand / test).

Route includes must be added to app/api/v1/router.py:
    from app.api.v1 import digests
    api_router.include_router(digests.router)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.alerts import verify_cron
from app.core.authz import get_current_user
from app.core.errors import AppError, ErrorCode
from app.core.security import CurrentUser
from app.db.session import get_db
from app.schemas.digest import DigestDispatchResponse, DigestSendMeResponse
from app.services import digest_service

router = APIRouter(prefix="/digests", tags=["digests"])


@router.post(
    "/dispatch",
    response_model=DigestDispatchResponse,
    dependencies=[Depends(verify_cron)],
)
async def dispatch_digests(
    db: AsyncSession = Depends(get_db),
) -> DigestDispatchResponse:
    """Cron-triggered (NOT user-facing): send the weekly digest to all active tenants.

    The X-Cron-Secret header is required; without it the endpoint returns 404.
    Schedule weekly via pg_cron or a Vercel Cron job targeting this path.
    """
    summary = await digest_service.dispatch_all(db)
    return DigestDispatchResponse(**summary)


@router.post("/send-me", response_model=DigestSendMeResponse)
async def send_me_digest(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DigestSendMeResponse:
    """Send the caller's tenant digest to their own email (on-demand / test).

    Email resolution order:
    1. JWT claim (user.email — set by Supabase from auth.users.email).
    2. Profile row looked up from the DB as a fallback (covers edge cases where
       the JWT was issued before the email was set in app_metadata).
    """
    # Resolve recipient email.
    recipient_email: str | None = user.email

    if not recipient_email:
        # Fallback: look up the profile row.
        import uuid as _uuid

        from app.db.models.tenancy import Profile

        profile = await db.get(Profile, _uuid.UUID(user.user_id))
        if profile is not None:
            recipient_email = profile.email

    if not recipient_email:
        raise AppError(ErrorCode.validation_error, "No email address on file for your account.")

    if not user.tenant_id:
        raise AppError(ErrorCode.validation_error, "Your account is not associated with a tenant.")

    result = await digest_service.send_for_tenant(db, user.tenant_id, recipient_email)
    return DigestSendMeResponse(**result)
