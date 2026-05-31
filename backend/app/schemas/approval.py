"""Approval workflow request/response schemas (M6).

Separate Create / Decision / Read shapes — ORM objects never returned directly.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ApprovalActionType = Literal[
    "renewal",
    "new_policy",
    "vendor_finalization",
    "high_value_premium",
    "other",
]
ApprovalStatus = Literal["pending", "approved", "rejected", "cancelled"]


class ApprovalCreate(BaseModel):
    """Payload to submit a new approval request."""

    action_type: ApprovalActionType
    entity_type: str = Field(..., min_length=1, max_length=100)
    entity_id: uuid.UUID
    amount_inr: Decimal | None = Field(None, ge=0)


class ApprovalDecision(BaseModel):
    """Body for approve / reject endpoints."""

    reason: str | None = Field(None, max_length=2000)


class ApprovalRead(BaseModel):
    """Full approval record returned by all endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    org_id: uuid.UUID | None
    action_type: str
    entity_type: str
    entity_id: uuid.UUID
    amount_inr: Decimal | None
    status: str
    requested_by: uuid.UUID | None
    approver_id: uuid.UUID | None
    is_self_approval: bool
    reason: str | None
    decided_at: datetime | None
    created_at: datetime
