"""Webhook request/response schemas.

Separate Create / Read / Created shapes — ORM objects are never returned directly.
The signing `secret` is intentionally excluded from WebhookRead; it appears only
once in WebhookCreated (at creation time) and is never retrievable again.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WebhookCreate(BaseModel):
    """Payload to register a new outbound webhook."""

    url: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description=(
            "Destination URL that receives POST requests for subscribed events. "
            "Must be a reachable HTTPS (or HTTP for local dev) endpoint."
        ),
    )
    events: list[str] = Field(
        ...,
        min_length=1,
        description=(
            "Event types to subscribe to, e.g. "
            "['renewal.due', 'approval.pending', 'policy.created', 'payment.failed']"
        ),
    )


class WebhookRead(BaseModel):
    """Safe webhook record — secret is never exposed after creation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    url: str
    events: list[str]
    is_active: bool
    created_at: datetime


class WebhookCreated(WebhookRead):
    """Returned ONLY at creation — includes the signing secret shown once.

    Store this value securely: it is **never** returned again.
    Compute the expected signature as::

        hmac.new(secret.encode(), body_bytes, 'sha256').hexdigest()

    and compare to the ``X-sVault-Signature: sha256=<hex>`` header.
    """

    secret: str = Field(
        ...,
        description=(
            "HMAC-SHA256 signing secret — store it now; it will not be shown again. "
            "Verify payloads by computing sha256=HMAC(secret, raw_body) and comparing "
            "to the X-sVault-Signature header."
        ),
    )


class WebhookTestResult(BaseModel):
    """Result of a test-delivery attempt."""

    delivered: bool = Field(
        ..., description="True if the webhook endpoint responded with a 2xx status."
    )
    status_code: int | None = Field(
        None, description="HTTP status code returned by the endpoint, or None on connection error."
    )
