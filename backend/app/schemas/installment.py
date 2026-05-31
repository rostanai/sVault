"""Installment request/response schemas — Pydantic v2.

Separate Create / Read shapes; ORM objects are never returned directly.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class InstallmentCreate(BaseModel):
    """Payload to create a new installment for a policy."""

    amount_inr: Decimal = Field(..., gt=0, description="Premium instalment amount in INR")
    due_date: date = Field(..., description="Date by which the instalment must be paid")
    note: str | None = Field(None, max_length=2000, description="Optional free-text note")


class InstallmentRead(BaseModel):
    """Full instalment record returned by all endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    policy_id: uuid.UUID
    amount_inr: Decimal
    due_date: date
    status: str
    paid_at: datetime | None
    note: str | None
    created_at: datetime
