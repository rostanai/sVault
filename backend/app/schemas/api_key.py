"""API key request/response schemas.

Separate Create / Read / Created shapes — ORM objects never returned directly.
key_hash is intentionally excluded from all public shapes.
There is no expires_at column in the DB schema.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ApiKeyCreate(BaseModel):
    """Payload to mint a new API key."""

    name: str = Field(..., min_length=1, max_length=200, description="Human-readable label")
    scopes: list[str] = Field(
        default_factory=list,
        description="List of permission scopes granted to this key, e.g. ['policy:read']",
    )
    rate_limit_per_min: int = Field(
        60,
        ge=1,
        le=10_000,
        description="Maximum requests per minute this key may make",
    )


class ApiKeyRead(BaseModel):
    """Safe API key record — key_hash is never exposed."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    prefix: str = Field(
        validation_alias="key_prefix",
        description="Safe display prefix (e.g. svk_abcd1234) — the full key is never stored",
    )
    scopes: list[str]
    rate_limit_per_min: int
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class ApiKeyCreated(ApiKeyRead):
    """Returned only at creation — includes the plaintext key, shown once."""

    plaintext_key: str = Field(
        ...,
        description="Full API key — store it now; it will not be shown again",
    )


class ApiKeyRevokeResponse(BaseModel):
    """Minimal confirmation returned after a revoke."""

    id: uuid.UUID
    revoked_at: datetime
