"""Provider contact-log + provider-update request/response schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

ContactKind = Literal["call", "email", "meeting", "note"]


class ProviderContactCreate(BaseModel):
    """Payload to log a new provider interaction."""

    kind: ContactKind
    subject: Annotated[str | None, Field(default=None, max_length=500)]
    note: str | None = None
    contacted_at: datetime | None = None  # defaults to now() server-side when omitted


class ProviderContactRead(BaseModel):
    """Response schema for a provider contact log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider_id: uuid.UUID
    kind: str
    subject: str | None
    note: str | None
    contacted_at: datetime
    created_by: uuid.UUID | None
    created_at: datetime


class ProviderUpdate(BaseModel):
    """PATCH payload for updating a provider's mutable fields (all optional)."""

    name: Annotated[str | None, Field(default=None, min_length=1, max_length=255)]
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    notes: str | None = None
