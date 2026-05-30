"""Subscription (trial starts at signup). Minimal mirror of 0003_billing.sql;
full billing fields (Razorpay, invoices) are fleshed out in M5.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import UUIDPK, Base, Timestamps

subscription_status_enum = ENUM(
    "trialing", "active", "past_due", "paused", "cancelled", "expired",
    name="subscription_status", create_type=False,
)


class Subscription(Base, UUIDPK, Timestamps):
    __tablename__ = "subscriptions"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id")
    )
    status: Mapped[str] = mapped_column(subscription_status_enum, default="trialing")
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
