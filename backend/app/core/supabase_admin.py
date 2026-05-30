"""Supabase Auth Admin client — sets JWT claims (app_metadata) via the service role.

Tenant/org/role live in app_metadata so they're verified in the JWT (not user-editable).
After this, the client must refresh its session to pick up the new claims.
"""
from __future__ import annotations

import httpx

from app.core.config import settings
from app.core.errors import AppError, ErrorCode


async def set_app_metadata(user_id: str, app_metadata: dict) -> None:
    if not (settings.supabase_url and settings.supabase_service_role_key):
        raise AppError(ErrorCode.internal_error, "Supabase admin not configured")
    url = f"{settings.supabase_url}/auth/v1/admin/users/{user_id}"
    headers = {
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "apikey": settings.supabase_service_role_key,
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.put(url, headers=headers, json={"app_metadata": app_metadata})
    except httpx.HTTPError as exc:
        raise AppError(ErrorCode.upstream_error, "Auth service unreachable") from exc
    if resp.status_code >= 400:
        raise AppError(ErrorCode.upstream_error, "Failed to set user claims")
