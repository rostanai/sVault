"""API key management endpoints (M7 — Developer API).

Routes
------
GET    /api-keys            list all keys for the caller's tenant   → 200
POST   /api-keys            create a new key (plaintext shown once) → 201
DELETE /api-keys/{key_id}   revoke a key                            → 200

Authorization
-------------
* All three routes require `apikey:manage` (Admin-only per PERMISSIONS.md).
* Keys are scoped to the caller's tenant; cross-tenant lookups return 404.
"""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import require_permission
from app.core.security import CurrentUser
from app.db.session import get_db
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyRead, ApiKeyRevokeResponse
from app.services import api_key_service

router = APIRouter(prefix="/api-keys", tags=["api-keys"])

_manage = require_permission("apikey:manage")


@router.get("", response_model=list[ApiKeyRead])
async def list_api_keys(
    user: CurrentUser = Depends(_manage),
    db: AsyncSession = Depends(get_db),
) -> list[ApiKeyRead]:
    """List all API keys for the caller's tenant.

    Returns all keys (active and revoked), newest first.
    The ``key_hash`` is never exposed; only the safe ``prefix`` is shown.
    Requires the ``apikey:manage`` permission (Admin only).
    """
    keys = await api_key_service.list_keys(db, user)
    return [ApiKeyRead.model_validate(k) for k in keys]


@router.post("", response_model=ApiKeyCreated, status_code=201)
async def create_api_key(
    payload: ApiKeyCreate,
    user: CurrentUser = Depends(_manage),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyCreated:
    """Create a new API key.

    The ``plaintext_key`` field in the response is shown **once** — store it
    securely.  Subsequent reads via ``GET /api-keys`` show only the prefix.
    Requires the ``apikey:manage`` permission (Admin only).
    """
    api_key, plaintext = await api_key_service.create(db, user, payload)
    read = ApiKeyRead.model_validate(api_key)
    return ApiKeyCreated(**read.model_dump(), plaintext_key=plaintext)


@router.delete("/{key_id}", response_model=ApiKeyRevokeResponse)
async def revoke_api_key(
    key_id: uuid.UUID,
    user: CurrentUser = Depends(_manage),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyRevokeResponse:
    """Revoke an API key immediately.

    All requests using this key will return 401 after revocation.
    Returns 404 if the key does not exist within the caller's tenant.
    Idempotent: revoking an already-revoked key updates ``revoked_at`` to now.
    Requires the ``apikey:manage`` permission (Admin only).
    """
    api_key = await api_key_service.revoke(db, user, key_id)
    return ApiKeyRevokeResponse(id=api_key.id, revoked_at=api_key.revoked_at)
