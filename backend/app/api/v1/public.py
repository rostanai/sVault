"""Public Developer API — authenticated by API key, not JWT.

Authentication
--------------
Every endpoint in this router requires a valid, non-revoked API key passed as
either:
  * ``Authorization: Bearer svk_<prefix>_<secret>``
  * ``X-API-Key: svk_<prefix>_<secret>``

The ``require_api_key`` dependency authenticates the key via SHA-256 lookup and
returns an ``ApiKeyPrincipal`` (tenant_id, key_id, scopes, rate_limit_per_min).

Rate limiting
-------------
Rate limiting is **designed but not fully enforced in this release**.  The
``rate_limit_per_min`` value from the key is checked against an in-memory
per-key counter (``_rate_counter``) that is reset every 60 seconds using a
background expiry map.  This is intentionally simple (single-process, no Redis)
— a TODO comment marks where a distributed counter (Redis INCR + EXPIRE) should
replace it before multi-process/multi-worker deployment.  The current
implementation is correct for single-process dev/staging; in production behind
multiple uvicorn workers, swap ``_rate_counter`` for a Redis-backed limiter.

Routes
------
GET /public/v1/policies   list policies for the authenticated tenant   → 200
"""
from __future__ import annotations

import time
import uuid
from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.security import APIKeyHeader, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ErrorCode
from app.db.models.insurance import Policy
from app.db.session import get_db
from app.schemas.policy import PolicyRead
from app.services import api_key_service
from app.services.api_key_service import ApiKeyPrincipal

router = APIRouter(prefix="/public/v1", tags=["public-api"])

# ---- security schemes (OpenAPI) ----
_bearer_scheme = HTTPBearer(auto_error=False)
_header_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)

# ---- simple in-process rate limiter ----
# Structure: {key_id: (window_start_ts, request_count)}
# TODO: replace with Redis INCR+EXPIRE for multi-worker deployments.
_rate_counter: dict[uuid.UUID, tuple[float, int]] = defaultdict(lambda: (0.0, 0))


def _check_rate_limit(principal: ApiKeyPrincipal) -> None:
    """Raise 429 if the key has exceeded its rate_limit_per_min in the current window."""
    now = time.monotonic()
    window_start, count = _rate_counter[principal.key_id]

    if now - window_start >= 60.0:
        # New window
        _rate_counter[principal.key_id] = (now, 1)
        return

    count += 1
    _rate_counter[principal.key_id] = (window_start, count)

    if count > principal.rate_limit_per_min:
        raise AppError(
            ErrorCode.rate_limited,
            f"Rate limit exceeded: {principal.rate_limit_per_min} requests/min for this key",
        )


# ---- header extraction (pure, no DB) ----

def _extract_key_plaintext(request: Request) -> str:
    """Extract the API key plaintext from headers; raise 401 immediately if absent.

    Accepts ``Authorization: Bearer <key>`` or ``X-API-Key: <key>``.
    This dependency is pure (no DB) so the 401 fires before the DB session is opened.
    """
    x_api_key = request.headers.get("X-API-Key")
    if x_api_key:
        return x_api_key

    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        candidate = auth.removeprefix("Bearer ").strip()
        if candidate:
            return candidate

    raise AppError(ErrorCode.unauthorized, "API key required")


# ---- auth dependency (DB-backed lookup) ----

async def require_api_key(
    plaintext: Annotated[str, Depends(_extract_key_plaintext)],
    db: AsyncSession = Depends(get_db),
) -> ApiKeyPrincipal:
    """Authenticate a request using an API key.

    Header extraction (and immediate 401) happens in ``_extract_key_plaintext``
    before the DB session is opened — so missing-key 401s work without a DB.
    Returns an ``ApiKeyPrincipal`` with tenant_id, scopes, and rate limit.
    Raises 401 if the key is invalid or revoked.
    """
    principal = await api_key_service.authenticate(db, plaintext)
    if principal is None:
        raise AppError(ErrorCode.unauthorized, "Invalid or revoked API key")

    _check_rate_limit(principal)
    return principal


# ---- public endpoints ----

@router.get("/policies", response_model=list[PolicyRead])
async def public_list_policies(
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
    principal: ApiKeyPrincipal = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> list[PolicyRead]:
    """List policies for the authenticated tenant.

    Results are strictly scoped to the tenant that owns the API key.
    No cross-tenant data is ever returned.
    Supports limit/offset pagination.

    Requires a valid, non-revoked API key with no specific scope restriction
    (any active key for the tenant may call this endpoint — scope-based filtering
    for fine-grained access can be layered on by checking
    ``principal.scopes`` before returning results).
    """
    stmt = (
        select(Policy)
        .where(Policy.tenant_id == principal.tenant_id)
        .order_by(Policy.expiry_date.asc().nullslast())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    policies = list(result.scalars().all())
    return [PolicyRead.model_validate(p) for p in policies]
