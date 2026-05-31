"""Schemas for the weekly renewal email digest endpoints."""
from __future__ import annotations

from pydantic import BaseModel


class DigestSendMeResponse(BaseModel):
    sent: bool
    recipient: str
    policies: int


class DigestDispatchResponse(BaseModel):
    tenants: int
    emails_sent: int
