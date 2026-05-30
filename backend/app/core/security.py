"""JWT verification + claim extraction (Supabase-issued tokens).

Identity/tenant/org/role come from the VERIFIED JWT's `app_metadata` — never from
`user_metadata` (user-editable). See docs/PERMISSIONS.md + ERROR_HANDLING.md.
"""
from __future__ import annotations

import httpx
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import settings
from app.core.errors import AppError, ErrorCode

# Cache of JWKS public keys by `kid` (Supabase asymmetric signing keys rotate rarely).
_jwks_keys: dict[str, dict] = {}


def _jwks_url() -> str:
    return settings.supabase_jwks_url or (
        f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
    )


def _refresh_jwks() -> None:
    try:
        resp = httpx.get(_jwks_url(), timeout=5)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise AppError(ErrorCode.upstream_error, "Could not fetch signing keys") from exc
    for key in resp.json().get("keys", []):
        if key.get("kid"):
            _jwks_keys[key["kid"]] = key


def _jwk_for(kid: str) -> dict | None:
    if kid not in _jwks_keys:
        _refresh_jwks()  # key may be new/rotated
    return _jwks_keys.get(kid)


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


_ASYMMETRIC = {"ES256", "RS256", "EdDSA", "ES384", "RS384", "RS512"}


def decode_token(token: str) -> CurrentUser:
    """Verify signature + expiry, then extract claims. Raises AppError(401) on failure.

    Supports Supabase **asymmetric** JWTs (ES256/RS256 verified via JWKS) and the
    **legacy HS256** shared secret — chosen by the token's `alg` header.
    """
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise AppError(ErrorCode.unauthorized, "Malformed token") from exc

    alg = header.get("alg", "")
    if alg in _ASYMMETRIC:
        kid = header.get("kid")
        key = _jwk_for(kid) if kid else None
        if key is None:
            raise AppError(ErrorCode.unauthorized, "Unknown signing key")
        verify_key: object = key
        algorithms = [alg]
    else:  # legacy HS256
        if not settings.supabase_jwt_secret:
            raise AppError(ErrorCode.internal_error, "Auth not configured")
        verify_key = settings.supabase_jwt_secret
        algorithms = ["HS256"]

    try:
        payload = jwt.decode(
            token, verify_key, algorithms=algorithms,
            options={"verify_aud": False},  # Supabase aud varies; verify exp/sig.
        )
    except JWTError as exc:
        raise AppError(ErrorCode.unauthorized, "Invalid or expired token") from exc
    return extract_claims(payload)
