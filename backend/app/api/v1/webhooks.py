"""Outbound webhook management endpoints (M7 — Developer Integration).

Routes
------
GET    /webhooks              list webhooks for the caller's tenant   → 200
POST   /webhooks              register a new webhook (secret shown once) → 201
DELETE /webhooks/{webhook_id} remove a webhook                        → 204
POST   /webhooks/{webhook_id}/test  send a test event                 → 200

Authorization
-------------
* All routes require ``apikey:manage`` (Admin-only per PERMISSIONS.md).
  Webhook management is colocated with API key management as both are
  developer-integration controls only an Admin should configure.
* All queries are scoped to the caller's tenant; cross-tenant IDs return 404.

Events supported
----------------
* ``renewal.due``       — fired by the alert engine per policy/lead-day
* ``approval.pending``  — fired when an approval is submitted
* ``policy.created``    — (reserved; fired by policy service in a later wave)
* ``payment.failed``    — (reserved; fired by billing service)
* ``webhook.test``      — synthetic event sent by POST /webhooks/{id}/test
"""
import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import require_permission
from app.core.security import CurrentUser
from app.db.session import get_db
from app.schemas.webhook import WebhookCreate, WebhookCreated, WebhookRead, WebhookTestResult
from app.services import webhook_service

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_manage = require_permission("apikey:manage")


@router.get("", response_model=list[WebhookRead])
async def list_webhooks(
    user: CurrentUser = Depends(_manage),
    db: AsyncSession = Depends(get_db),
) -> list[WebhookRead]:
    """List all registered webhooks for the caller's tenant.

    Returns metadata only — the signing secret is **never** included in
    list responses. Requires the ``apikey:manage`` permission (Admin only).
    """
    hooks = await webhook_service.list_webhooks(db, user)
    return [WebhookRead.model_validate(h) for h in hooks]


@router.post("", response_model=WebhookCreated, status_code=201)
async def create_webhook(
    payload: WebhookCreate,
    user: CurrentUser = Depends(_manage),
    db: AsyncSession = Depends(get_db),
) -> WebhookCreated:
    """Register a new outbound webhook.

    The ``secret`` field in the response is shown **once** — store it securely.
    Use it to verify incoming payloads by computing:

        sha256=HMAC-SHA256(secret, raw_request_body)

    and comparing to the ``X-sVault-Signature`` header.

    Supported events: ``renewal.due``, ``approval.pending``, ``policy.created``,
    ``payment.failed``, ``webhook.test``.

    Requires the ``apikey:manage`` permission (Admin only).
    """
    webhook, secret = await webhook_service.create(db, user, payload)
    read = WebhookRead.model_validate(webhook)
    return WebhookCreated(**read.model_dump(), secret=secret)


@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(
    webhook_id: uuid.UUID,
    user: CurrentUser = Depends(_manage),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete a webhook registration.

    Returns 204 on success, 404 if the webhook does not exist within the
    caller's tenant.  Requires the ``apikey:manage`` permission (Admin only).
    """
    await webhook_service.delete(db, user, webhook_id)
    return Response(status_code=204)


@router.post("/{webhook_id}/test", response_model=WebhookTestResult)
async def test_webhook(
    webhook_id: uuid.UUID,
    user: CurrentUser = Depends(_manage),
    db: AsyncSession = Depends(get_db),
) -> WebhookTestResult:
    """Send a synthetic ``webhook.test`` event to the specified webhook.

    Returns ``{delivered: true, status_code: 200}`` on success.
    ``delivered`` is ``false`` if the endpoint returned a non-2xx or was
    unreachable; ``status_code`` is ``null`` on connection error.
    Returns 404 if the webhook does not exist within the caller's tenant.

    Requires the ``apikey:manage`` permission (Admin only).
    """
    result = await webhook_service.test_webhook(db, user, webhook_id)
    return WebhookTestResult(**result)
