"""JWT verification + claim extraction (Supabase-issued tokens).

Identity/tenant/org/role come from the VERIFIED JWT's `app_metadata` — never from
`user_metadata` (user-editable). See docs/PERMISSIONS.md + ERROR_HANDLING.md.
"""
from __future__ import annotations

from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import settings
from app.core.errors import AppError, ErrorCode


class CurrentUser(BaseModel):
    user_id: str
    tenant_id: str | None = None
    org_id: str | None = None
    role: str = ""
    is_super_admin: bool = False
    email: str | None = None


def extract_claims(payload: dict) -> CurrentUser:
    """Pure mapping from a decoded JWT payload to CurrentUser. Unit-testable."""
    app_md = payload.get("app_metadata") or {}
    return CurrentUser(
        user_id=payload.get("sub", ""),
        tenant_id=app_md.get("tenant_id"),
        org_id=app_md.get("org_id"),
        role=app_md.get("role", "") or "",
        is_super_admin=bool(app_md.get("is_platform_admin", False)),
        email=payload.get("email"),
    )


def decode_token(token: str) -> CurrentUser:
    """Verify signature + expiry, then extract claims. Raises AppError(401) on failure."""
    if not settings.supabase_jwt_secret:
        raise AppError(ErrorCode.internal_error, "Auth not configured")
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=list(settings.jwt_algorithms),
            audience="authenticated",
            options={"verify_aud": False},  # Supabase aud varies; verify exp/sig.
        )
    except JWTError as exc:
        raise AppError(ErrorCode.unauthorized, "Invalid or expired token") from exc
    return extract_claims(payload)
