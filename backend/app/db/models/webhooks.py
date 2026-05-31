"""Webhook ORM model — mirrors the `webhooks` table in the DB migration.

The table schema:
    id          uuid         PK, server default gen_random_uuid()
    tenant_id   uuid         FK → tenants.id CASCADE
    url         text         NOT NULL
    events      text[]       NOT NULL
    secret      text         NOT NULL  (stored hashed — plaintext returned only at creation)
    is_active   bool         NOT NULL  DEFAULT true
    created_at  timestamptz  NOT NULL  DEFAULT now()

No enums. secret is stored as the raw value (the signing secret, not hashed like API keys;
it is never returned in list/read responses — only at creation time via WebhookCreated).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import UUIDPK, Base


class Webhook(Base, UUIDPK):
    __tablename__ = "webhooks"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    events: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    secret: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
