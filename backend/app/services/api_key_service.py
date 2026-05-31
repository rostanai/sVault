"""API key service — business logic only; no FastAPI imports.

Key design notes
----------------
* Keys are hashed with SHA-256 (hex) — fast, deterministic, not a password (no
  need for bcrypt/argon2 since keys are already high-entropy random strings).
* Plaintext is returned ONCE from create(); it is never stored.
* All management queries are scoped by tenant_id — cross-tenant lookups return 404.
* authenticate() is used by the public API dependency; it updates last_used_at
  best-effort (no exception on failure) and returns a lightweight principal.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ErrorCode, not_found
from app.core.security import CurrentUser
from app.db.models.api_keys import ApiKey
from app.schemas.api_key import ApiKeyCreate

# ---------------------------------------------------------------------------
# Key generation
# ---------------------------------------------------------------------------

def generate_key() -> tuple[str, str, str]:
    """Return ``(plaintext, prefix, key_hash)``.

    Format: ``svk_<8-char-random-hex>_<32-byte-url-safe-secret>``
    Example: ``svk_a3f9c1d2_dGhpcyBpcyBhIHRlc3Qga2V5IGZvciBzVmF1bHQK``

    * ``prefix``    = ``svk_<8char>``  — safe to store and display.
    * ``key_hash``  = SHA-256 hex of the full plaintext.
    """
    eight_hex = secrets.token_hex(4)          # 4 bytes → 8 hex chars
    secret_part = secrets.token_urlsafe(32)   # 43-char url-safe random
    plaintext = f"svk_{eight_hex}_{secret_part}"
    prefix = f"svk_{eight_hex}"
    key_hash = hashlib.sha256(plaintext.encode()).hexdigest()
    return plaintext, prefix, key_hash


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def create(
    db: AsyncSession,
    user: CurrentUser,
    payload: ApiKeyCreate,
) -> tuple[ApiKey, str]:
    """Insert a new API key row; return ``(ORM obj, plaintext)``.

    The plaintext is returned here and must be forwarded to the caller — it is
    **never** stored or retrievable after this function returns.
    """
    if not user.tenant_id:
        raise AppError(ErrorCode.forbidden, "No tenant context")

    plaintext, prefix, key_hash = generate_key()

    api_key = ApiKey(
        tenant_id=uuid.UUID(user.tenant_id),
        created_by=uuid.UUID(user.user_id),
        name=payload.name,
        key_prefix=prefix,
        key_hash=key_hash,
        scopes=payload.scopes,
        rate_limit_per_min=payload.rate_limit_per_min,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    return api_key, plaintext


async def list_keys(
    db: AsyncSession,
    user: CurrentUser,
) -> list[ApiKey]:
    """Return all (including revoked) API keys for the caller's tenant, newest first."""
    if not user.tenant_id:
        return []

    stmt = (
        select(ApiKey)
        .where(ApiKey.tenant_id == uuid.UUID(user.tenant_id))
        .order_by(ApiKey.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def revoke(
    db: AsyncSession,
    user: CurrentUser,
    key_id: uuid.UUID,
) -> ApiKey:
    """Set revoked_at = now for the given key (tenant-scoped).

    Idempotent: if already revoked the timestamp is updated to now again (simple
    and safe — callers can re-revoke without error).
    Returns the updated ORM object.
    Raises not_found (404) if the key doesn't exist or belongs to another tenant.
    """
    if not user.tenant_id:
        raise not_found("API key not found")

    stmt = select(ApiKey).where(
        ApiKey.id == key_id,
        ApiKey.tenant_id == uuid.UUID(user.tenant_id),
    )
    api_key = (await db.execute(stmt)).scalar_one_or_none()
    if api_key is None:
        raise not_found("API key not found")

    api_key.revoked_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(api_key)
    return api_key


# ---------------------------------------------------------------------------
# Public authentication principal
# ---------------------------------------------------------------------------

@dataclass
class ApiKeyPrincipal:
    """Lightweight principal returned by authenticate() — no JWT, no ORM object."""

    tenant_id: uuid.UUID
    key_id: uuid.UUID
    scopes: list[str]
    rate_limit_per_min: int


async def authenticate(
    db: AsyncSession,
    plaintext: str,
) -> ApiKeyPrincipal | None:
    """Hash the key, look it up, and return a principal or None.

    * Returns ``None`` if the key doesn't exist or is revoked.
    * Updates ``last_used_at`` best-effort (fire-and-forget on the same session;
      a failure here must never block the request — callers should handle None
      as "unauthenticated" and non-None as "authenticated").
    """
    key_hash = hashlib.sha256(plaintext.encode()).hexdigest()

    stmt = select(ApiKey).where(
        ApiKey.key_hash == key_hash,
        ApiKey.revoked_at.is_(None),
    )
    api_key = (await db.execute(stmt)).scalar_one_or_none()
    if api_key is None:
        return None

    # Best-effort last_used_at update — don't block on failure.
    try:
        await db.execute(
            update(ApiKey)
            .where(ApiKey.id == api_key.id)
            .values(last_used_at=datetime.now(UTC))
        )
        await db.commit()
    except Exception:  # noqa: BLE001
        await db.rollback()

    return ApiKeyPrincipal(
        tenant_id=api_key.tenant_id,
        key_id=api_key.id,
        scopes=list(api_key.scopes or []),
        rate_limit_per_min=api_key.rate_limit_per_min,
    )
