"""Outbound webhook service — business logic only; no FastAPI imports.

Design notes
------------
* Secrets use the prefix ``whsec_`` followed by a url-safe random token so they
  are visually distinct from API keys (``svk_``).
* Secrets are stored in plain text in the ``webhooks.secret`` column (they are
  not user passwords — they are symmetric signing keys the tenant must keep
  private; hashing them would prevent signature verification without storing a
  separate copy).
* The ``deliver()`` function is intentionally best-effort: it catches ALL
  exceptions, logs them, and returns without re-raising.  Callers (alert engine,
  approval service) wrap it in an additional try/except so a webhook failure
  can NEVER break the main request path.
* HMAC-SHA256 is computed over the raw JSON body bytes.  Header format:
      X-sVault-Signature: sha256=<hex>
* httpx.AsyncClient is created per call (short-lived) with a 5-second timeout.
  For production scale, move to a background task queue / worker.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import not_found
from app.core.security import CurrentUser
from app.db.models.webhooks import Webhook
from app.schemas.webhook import WebhookCreate

logger = logging.getLogger("svault.webhooks")

# ---------------------------------------------------------------------------
# Secret generation
# ---------------------------------------------------------------------------

def generate_secret() -> str:
    """Return a new signing secret with the ``whsec_`` prefix.

    Format: ``whsec_<43-char-url-safe-random>``
    """
    return f"whsec_{secrets.token_urlsafe(32)}"


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def create(
    db: AsyncSession,
    user: CurrentUser,
    payload: WebhookCreate,
) -> tuple[Webhook, str]:
    """Register a new webhook; return ``(ORM obj, plaintext_secret)``.

    The plaintext secret is returned here and must be forwarded to the caller —
    it is **never** retrievable again via the API.
    """
    from app.core.errors import AppError, ErrorCode  # local to avoid top-level cycle risk

    if not user.tenant_id:
        raise AppError(ErrorCode.forbidden, "No tenant context")

    secret = generate_secret()

    webhook = Webhook(
        tenant_id=uuid.UUID(user.tenant_id),
        url=str(payload.url),
        events=list(payload.events),
        secret=secret,
        is_active=True,
    )
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)
    return webhook, secret


async def list_webhooks(
    db: AsyncSession,
    user: CurrentUser,
) -> list[Webhook]:
    """Return all webhooks for the caller's tenant, newest first."""
    if not user.tenant_id:
        return []

    stmt = (
        select(Webhook)
        .where(Webhook.tenant_id == uuid.UUID(user.tenant_id))
        .order_by(Webhook.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def delete(
    db: AsyncSession,
    user: CurrentUser,
    webhook_id: uuid.UUID,
) -> None:
    """Delete a webhook (tenant-scoped).

    Raises not_found (404) if the webhook doesn't exist or belongs to another tenant.
    """
    if not user.tenant_id:
        raise not_found("Webhook not found")

    stmt = select(Webhook).where(
        Webhook.id == webhook_id,
        Webhook.tenant_id == uuid.UUID(user.tenant_id),
    )
    webhook = (await db.execute(stmt)).scalar_one_or_none()
    if webhook is None:
        raise not_found("Webhook not found")

    await db.delete(webhook)
    await db.commit()


# ---------------------------------------------------------------------------
# Signing helper
# ---------------------------------------------------------------------------

def _sign(secret: str, body: bytes) -> str:
    """Compute ``sha256=<hex>`` HMAC-SHA256 of ``body`` using ``secret``."""
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------

async def deliver(
    db: AsyncSession,
    tenant_id: uuid.UUID | str,
    event: str,
    payload: dict,
) -> None:
    """Dispatch ``event`` to all active webhooks for ``tenant_id`` subscribed to it.

    * Best-effort: all exceptions are caught and logged; never raises.
    * Sends a POST with JSON body ``{event, created_at, data: payload}``.
    * Signs with HMAC-SHA256; header: ``X-sVault-Signature: sha256=<hex>``.
    * Short timeout (5 s) — does not retry on failure.
    """
    try:
        tid = uuid.UUID(str(tenant_id))
        stmt = select(Webhook).where(
            Webhook.tenant_id == tid,
            Webhook.is_active.is_(True),
        )
        webhooks: list[Webhook] = list((await db.execute(stmt)).scalars().all())
    except Exception:  # noqa: BLE001
        logger.exception("webhook_deliver: failed to query webhooks for event=%s", event)
        return

    # Filter to only active webhooks subscribed to this event.
    # The SQL query already filters is_active=True; this is defense-in-depth.
    targets = [w for w in webhooks if w.is_active and event in (w.events or [])]
    if not targets:
        return

    envelope = {
        "event": event,
        "created_at": datetime.now(UTC).isoformat(),
        "data": payload,
    }
    body_bytes = json.dumps(envelope, default=str).encode()

    for webhook in targets:
        try:
            signature = _sign(webhook.secret, body_bytes)
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    webhook.url,
                    content=body_bytes,
                    headers={
                        "Content-Type": "application/json",
                        "X-sVault-Signature": signature,
                        "X-sVault-Event": event,
                    },
                )
            logger.debug(
                "webhook_delivered: event=%s url=%s webhook_id=%s",
                event, webhook.url, webhook.id,
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "webhook_deliver_failed: event=%s url=%s webhook_id=%s",
                event, webhook.url, webhook.id,
                exc_info=True,
            )


# ---------------------------------------------------------------------------
# Test delivery
# ---------------------------------------------------------------------------

async def test_webhook(
    db: AsyncSession,
    user: CurrentUser,
    webhook_id: uuid.UUID,
) -> dict:
    """Send a ``webhook.test`` event to the specified webhook.

    Returns ``{delivered: bool, status_code: int | None}``.
    Raises 404 if the webhook does not exist within the caller's tenant.
    """
    if not user.tenant_id:
        raise not_found("Webhook not found")

    stmt = select(Webhook).where(
        Webhook.id == webhook_id,
        Webhook.tenant_id == uuid.UUID(user.tenant_id),
    )
    webhook = (await db.execute(stmt)).scalar_one_or_none()
    if webhook is None:
        raise not_found("Webhook not found")

    envelope = {
        "event": "webhook.test",
        "created_at": datetime.now(UTC).isoformat(),
        "data": {"message": "This is a test delivery from sVault."},
    }
    body_bytes = json.dumps(envelope, default=str).encode()
    signature = _sign(webhook.secret, body_bytes)

    delivered = False
    status_code: int | None = None

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                webhook.url,
                content=body_bytes,
                headers={
                    "Content-Type": "application/json",
                    "X-sVault-Signature": signature,
                    "X-sVault-Event": "webhook.test",
                },
            )
        status_code = resp.status_code
        delivered = resp.is_success
    except Exception:  # noqa: BLE001
        logger.warning(
            "webhook_test_failed: webhook_id=%s url=%s",
            webhook.id, webhook.url,
            exc_info=True,
        )

    return {"delivered": delivered, "status_code": status_code}
