"""Alert engine schemas (M4)."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Channel = Literal["whatsapp", "email", "sms", "telegram"]


class AlertRuleRead(BaseModel):
    id: uuid.UUID | None
    policy_id: uuid.UUID | None
    lead_days: list[int]
    channels: list[str]
    escalate: bool
    is_active: bool


class AlertRuleUpdate(BaseModel):
    lead_days: list[int] | None = None
    channels: list[Channel] | None = None
    escalate: bool | None = None
    is_active: bool | None = None


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    policy_id: uuid.UUID
    channel: str
    lead_day: int
    scheduled_for: date
    status: str
    acknowledged_at: datetime | None


class SnoozeRequest(BaseModel):
    days: int = Field(..., ge=1, le=90, description="Days to push the alert forward (1–90)")


class SnoozeResponse(BaseModel):
    id: uuid.UUID
    status: str
    scheduled_for: date


class DispatchSummary(BaseModel):
    date: str
    alerts_created: int
    dispatched: int
